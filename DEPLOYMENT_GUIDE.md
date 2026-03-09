# 🚀 新闻爬虫部署指南

本指南覆盖**简单爬虫**（Cloud Functions）与**无头浏览器爬虫**（Cloud Run）的部署与验证。

## 📋 前置准备

### 1. 检查环境
```bash
gcloud --version
gcloud auth list

# 如未登录
gcloud auth login
gcloud auth application-default login
```

### 2. 设置环境变量
```bash
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"
```

⚠️ 将 `your-project-id` 替换为实际项目 ID。

---

## 🎯 部署步骤

### 方法 1：使用 Makefile（推荐）

在**项目根目录**执行：

```bash
# 仅部署简单爬虫（Cloud Functions）
make deploy

# 仅部署无头浏览器爬虫（Cloud Run + Scheduler）
make deploy-browser

# 两者都部署
make deploy-all
```

需已设置 `GCP_PROJECT_ID`。

---

### 方法 2：一键部署简单爬虫

若存在 `deploy/quick_deploy.sh`，可一键完成：启用 API、创建 BigQuery、更新 config、部署 Cloud Functions。

```bash
cd /path/to/news-google
./deploy/quick_deploy.sh
```

**预计时间**：5-10 分钟

---

### 方法 3：分步部署（手动控制）

#### 步骤 1：启用 API
```bash
gcloud config set project $GCP_PROJECT_ID

gcloud services enable \
  cloudfunctions.googleapis.com \
  cloudscheduler.googleapis.com \
  bigquery.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com
```

#### 步骤 2：创建 BigQuery 表
```bash
bq mk --dataset --location=US "$GCP_PROJECT_ID:news_project"
bq query --use_legacy_sql=false < deploy/create_bigquery_table.sql
```

**验证**：
```bash
bq show news_project.news_articles
```

> 表为按 `pub_date` 分区，查询时必须带 `DATE(pub_date)` 条件。

#### 步骤 3：更新配置文件
```bash
sed -i.bak "s/your-project-id/$GCP_PROJECT_ID/g" config.yaml
rm -f config.yaml.bak
```

#### 步骤 4：部署简单爬虫（Cloud Functions）
```bash
sh deploy/deploy.sh
```

#### 步骤 5（可选）：部署无头浏览器爬虫（Cloud Run）
```bash
sh deploy/deploy_cloudrun_browser.sh
```
会构建并部署到 Cloud Run，并配置 Cloud Scheduler 每 30 分钟触发。使用 `Dockerfile.firefox`（仅 Firefox）。

---

## ✅ 测试验证

### 1. 获取函数 URL
```bash
FUNCTION_URL=$(gcloud functions describe crawl-news \
  --region=$GCP_REGION \
  --gen2 \
  --format="value(serviceConfig.uri)")

echo "函数 URL: $FUNCTION_URL"
```

### 2. 测试简单爬虫（Cloud Functions）
```bash
# sources: 逗号分隔的 source 名，或 "all" 表示全部
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"sources": "all"}' \
  $FUNCTION_URL
```

**期望**：返回 JSON，含 `success`、`total_new_articles`、`results`（各 source 的统计）、`errors`。

### 3. 测试指定 source
```bash
# 仅跑某几个 source（具体名称见 main.py 中 SCRAPER_REGISTRY）
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"sources": "source1,source2"}' \
  $FUNCTION_URL
```

### 4. 验证数据写入 BigQuery
```bash
# 查询今天爬取的文章（必须带 pub_date 分区条件）
bq query --use_legacy_sql=false \
  "SELECT source, COUNT(*) as count
   FROM \`$GCP_PROJECT_ID.news_project.news_articles\`
   WHERE DATE(pub_date) >= CURRENT_DATE()
   GROUP BY source"
```

**期望**：按 `source` 分组的条数，说明数据已写入。

### 5. 查看函数日志
```bash
gcloud logging read \
  "resource.type=cloud_function AND resource.labels.function_name=crawl-news" \
  --limit=20 \
  --format=json
```

### 6. 测试无头浏览器爬虫（若已部署 Cloud Run）
```bash
# 从 deploy_cloudrun_browser.sh 输出或控制台获取服务 URL
# sources: "all" 或逗号分隔；test: true 不写 BigQuery
curl -X POST -H "Content-Type: application/json" \
  -d '{"sources": "all", "test": true}' \
  https://crawl-news-browser-xxxxx-uc.a.run.app
```

---

## 🔔 配置定时任务

部署成功后，配置 Cloud Scheduler 每 10 分钟自动触发：

```bash
./deploy/setup_scheduler.sh
```

**验证定时任务**：
```bash
# 查看任务详情
gcloud scheduler jobs describe news-crawler-job \
  --location=$GCP_REGION

# 手动触发测试
gcloud scheduler jobs run news-crawler-job \
  --location=$GCP_REGION
```

---

## 📊 监控与管理

### 查看爬取统计
```bash
# 各新闻源统计（需带 pub_date 分区条件）
bq query --use_legacy_sql=false \
  "SELECT source, COUNT(*) as cnt
   FROM \`$GCP_PROJECT_ID.news_project.news_articles\`
   WHERE DATE(pub_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
   GROUP BY source ORDER BY cnt DESC"

# 最近爬取的文章
bq query --use_legacy_sql=false \
  "SELECT title, source, pub_date, link
   FROM \`$GCP_PROJECT_ID.news_project.news_articles\`
   WHERE DATE(pub_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
   ORDER BY crawled_at DESC
   LIMIT 10"
```

### 查看函数执行情况
```bash
# 查看最近的执行
gcloud functions describe crawl-news \
  --region=$GCP_REGION \
  --gen2

# 查看指标
gcloud monitoring time-series list \
  --filter='metric.type="cloudfunctions.googleapis.com/function/execution_count"'
```

---

## 🛠️ 常见问题

### 问题 1：部署失败 - API 未启用
```bash
# 错误信息：API [xxx] not enabled
# 解决方案：手动启用 API
gcloud services enable cloudfunctions.googleapis.com
```

### 问题 2：BigQuery 表已存在
```bash
# 错误信息：Already Exists: Table
# 解决方案：删除重建（会丢失数据）
bq rm -f -t news_project.news_articles
bq query --use_legacy_sql=false < deploy/create_bigquery_table.sql
```

### 问题 3：函数调用失败
```bash
# 查看详细日志
gcloud logging read \
  "resource.type=cloud_function" \
  --limit=50 \
  --format=json | jq '.[] | select(.severity=="ERROR")'
```

### 问题 4：权限不足
```bash
# 确保服务账号有 BigQuery 权限
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:$GCP_PROJECT_ID@appspot.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"
```

---

## 🔄 更新与维护

### 更新爬虫代码
```bash
# 简单爬虫
make deploy
# 或 sh deploy/deploy.sh

# 无头浏览器爬虫
make deploy-browser
# 或 sh deploy/deploy_cloudrun_browser.sh
```

### 添加新爬虫
- **简单爬虫**：在 `scrapers/simple/` 新建模块，继承 `BaseScraper`，在 `main.py` 的 `SCRAPER_REGISTRY` 中注册，然后 `make deploy`。
- **无头浏览器爬虫**：在 `scrapers/browser/` 新建模块，继承 `BaseBrowserScraper` 并实现 `_run_impl()`，在 `scrapers/browser/__init__.py` 的 `SCRAPER_REGISTRY_BROWSER` 中注册，然后 `make deploy-browser`。

### 暂停/恢复定时任务
```bash
# 暂停
gcloud scheduler jobs pause news-crawler-job --location=$GCP_REGION

# 恢复
gcloud scheduler jobs resume news-crawler-job --location=$GCP_REGION
```

### 删除所有资源
```bash
# 简单爬虫
gcloud functions delete crawl-news --region=$GCP_REGION --gen2
gcloud scheduler jobs delete news-crawler-job --location=$GCP_REGION 2>/dev/null || true

# 无头浏览器爬虫（若已部署）
gcloud run services delete crawl-news-browser --region=$GCP_REGION
gcloud scheduler jobs delete news-crawler-browser-job --location=$GCP_REGION 2>/dev/null || true

# BigQuery 数据集（包含所有表）
bq rm -r -f $GCP_PROJECT_ID:news_project
```

---

## 🔄 GitHub 持续集成部署

推送到 `main` 分支时自动部署两个服务，无需本地执行 `make deploy` / `make deploy-browser`。

### 方式一：GitHub Actions（推荐，可分开手动部署）

1. **在仓库中已添加** `.github/workflows/deploy.yml`，**仅支持手动触发**，不会随 push 自动部署。

2. **配置 GitHub Secrets**（Settings → Secrets and variables → Actions）：
   - `GCP_PROJECT_ID`：GCP 项目 ID（如 `news-project-487409`）
   - `GCP_SA_KEY`：服务账号密钥 JSON 的**完整内容**
     - 在 GCP 控制台：IAM → 服务账号 → 创建密钥（JSON），复制文件内容粘贴到 Secret

3. **权限**：该服务账号需具备：
   - Cloud Functions 管理员（或至少部署权限）
   - Cloud Run 管理员
   - Cloud Build 编辑者（若用 --source 构建）
   - 或项目角色 `roles/owner`（仅建议测试用）

4. **手动部署**：在 GitHub 仓库 **Actions** 页选择“Deploy to GCP” → 点击 **“Run workflow”**，在 **“部署目标”** 下拉框中选择：
   - **simple**：仅部署 crawl-news（Cloud Functions）
   - **browser**：仅部署 crawl-news-browser（Cloud Run）
   - **all**：两个服务都部署

5. **（可选）仅允许指定人完成部署**：workflow 的部署 job 使用了 `environment: deploy`。
   - **必须先**在仓库 **Settings** → **Environments** 中点击 **New environment**，名称填 **deploy** 并保存（否则 workflow 会因找不到环境而报错）。
   - 若希望**只有指定人（如项目所有者）能完成部署**：在 **deploy** 环境的 **Deployment protection rules** 中勾选 **Required reviewers**，添加允许审批的账号。之后每次有人点“Run workflow”，部署 job 会处于“Waiting for approval”，只有被设为 Required reviewers 的成员在 Actions 页批准后才会真正执行。
   - 若不需要审批：创建 **deploy** 环境后不勾选 Required reviewers 即可，有写权限的人触发后会直接部署。

### 方式二：控制台「连接仓库」（仅 Cloud Run 服务）

若**只**希望 **crawl-news-browser** 自动部署，可用 GCP 控制台：

1. 在 Cloud Run 中选中服务 `crawl-news-browser`
2. 点击 **「连接仓库」**，选择 GitHub 仓库与分支
3. 构建配置选择「Dockerfile」，路径填 `Dockerfile.firefox`
4. 保存后，每次推送到该分支会自动构建并部署该服务

注意：**crawl-news**（Cloud Functions）不能通过「连接仓库」配置，需继续用本地 `make deploy` 或上述 GitHub Actions 部署。

---

## 💰 成本监控

### 查看当前月费用
```bash
gcloud billing accounts list

# 在 GCP Console 查看详细账单
# https://console.cloud.google.com/billing
```

### 预计成本
- Cloud Functions（简单爬虫）: $3-5/月
- Cloud Run（无头浏览器，按请求）: 视调用频率而定
- BigQuery: $0.5-2/月
- **总计**: 约 **$4-10/月**（视是否启用浏览器爬虫及调度频率）

---

## 📚 下一步

部署完成后，您可以：

1. ✅ 迁移更多新闻源（参考现有代码）
2. ✅ 添加监控告警
3. ✅ 集成 BI 工具分析数据
4. ✅ 导出数据到其他系统

---

## 🆘 获取帮助

- 查看 README.md
- GitHub Issues（如果有）

**祝部署顺利！** 🎉
