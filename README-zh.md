# 新闻爬虫 Cloud Functions + BigQuery

新闻爬虫 Google Cloud Functions + BigQuery 的**学习项目**。

> **声明**：本项目仅供**学习与交流**使用。若任何内容或使用侵犯您的权益，请联系作者**立即删除**。

## 项目特点

- **无服务器架构**: 使用 Cloud Functions 按需执行爬虫
- **数据持久化**: BigQuery 按日期分区存储，支持 SQL 查询
- **高效去重**: 基于 BigQuery 分区查询的去重机制
- **并发爬取**: 多个新闻源并发执行，提高效率
- **定时触发**: Cloud Scheduler 每 10 分钟自动触发

## 技术栈

- **运行时**: Python 3.11
- **计算**: Google Cloud Functions (Gen 2)
- **数据库**: Google BigQuery（按日期分区）
- **调度**: Google Cloud Scheduler
- **依赖**: BeautifulSoup4, requests, google-cloud-bigquery

## 项目结构

```
news-google/
├── main.py                      # 双入口：crawl_news（简单）+ crawl_news_browser（无头浏览器）
├── Makefile                     # 本地运行与部署（make run / deploy / deploy-browser）
├── requirements.txt            # 简单爬虫依赖
├── requirements-browser.txt    # 无头浏览器爬虫依赖（playwright 等）
├── config.yaml                 # 配置文件（GCP、并发等）
├── scrapers/
│   ├── base_scraper.py
│   ├── simple/                 # 简单爬虫（requests/BeautifulSoup，无浏览器）→ Cloud Functions
│   └── browser/                # 无头浏览器爬虫（Playwright）→ 仅 Cloud Run
│       └── __init__.py         # SCRAPER_REGISTRY_BROWSER
├── utils/
└── deploy/
    ├── deploy.sh               # 部署 crawl-news（简单）→ Cloud Functions
    ├── deploy_cloudrun_browser.sh  # 无头浏览器爬虫 → Cloud Run（含 Scheduler 定时触发）
    ├── setup_scheduler.sh       # 定时触发 crawl-news
    └── create_bigquery_table.sql
└── Dockerfile.firefox          # Cloud Run 无头浏览器镜像（仅 Firefox，体积小）
```

**两个入口（依赖隔离）**

| 名称 | 入口 | 依赖 | 部署方式 |
|------|------|------|----------|
| 简单爬虫 | `crawl_news` | requirements.txt | Cloud Functions（`deploy.sh`） |
| 无头浏览器爬虫 | `crawl_news_browser` | requirements-browser.txt + **浏览器二进制** | **Cloud Run**（`deploy_cloudrun_browser.sh`） |

**重要**：无头浏览器爬虫依赖 Playwright 的**浏览器二进制**，需用 **Cloud Run + Dockerfile.firefox**（仅含 Firefox，体积小）部署。

## 快速开始

### 1. 前置准备

1. **安装 Google Cloud SDK**
   ```bash
   # macOS
   brew install --cask google-cloud-sdk

   # 登录
   gcloud auth login
   gcloud auth application-default login
   ```

2. **设置环境变量**
   ```bash
   export GCP_PROJECT_ID="your-project-id"
   export GCP_REGION="us-central1"
   ```

3. **修改配置文件**
   编辑 `config.yaml`，替换 `your-project-id` 为您的 GCP 项目 ID

### 2. 创建 GCP 资源

1. **创建 BigQuery 数据集和表**
   ```bash
   bq query --use_legacy_sql=false < deploy/create_bigquery_table.sql
   ```

### 3. 部署

**使用 Makefile（推荐）**
```bash
export GCP_PROJECT_ID="your-project-id"
make deploy              # 部署简单爬虫到 Cloud Functions
make deploy-browser      # 部署无头浏览器爬虫到 Cloud Run + Scheduler
make deploy-all         # 依次执行上述两者
```

**或直接执行脚本**
```bash
cd /path/to/news-google
sh deploy/deploy.sh                    # 简单爬虫 → Cloud Functions
sh deploy/deploy_cloudrun_browser.sh  # 无头浏览器 → Cloud Run（含每 30 分钟定时触发）
```

**配置定时任务（可选）**
- 简单爬虫每 10 分钟：`./deploy/setup_scheduler.sh`
- 无头浏览器爬虫：`deploy_cloudrun_browser.sh` 部署完成后会自动配置每 30 分钟触发

### 4. 测试

**手动触发测试**
```bash
# 触发爬取（sources: 逗号分隔或 "all"）
curl -X POST -H "Content-Type: application/json" \
  -d '{"sources": "all"}' \
  https://REGION-PROJECT.cloudfunctions.net/crawl-news
```

**本地测试**

需在项目根目录执行，并已配置 GCP 认证（`gcloud auth application-default login`）。默认使用 **uv**，也可用 `make run PYTHON=python`。

**简单爬虫**
```bash
make run
# 或
uv run python main.py
# 或
pip install -r requirements.txt && python main.py
```

**无头浏览器爬虫**
```bash
make install-browser   # 首次：安装 requirements-browser.txt + playwright install firefox
make run-browser       # 运行（sources=all, test=True，不写 BigQuery）
# 或
uv run python main.py browser
```

- `make run`：简单爬虫，会请求 BigQuery（非 test 时写入）。
- `make run-browser`：无头浏览器爬虫；本地默认 `test=True` 不写 BigQuery。

### 5. 查看数据

**查询 BigQuery 数据**（表为分区表，查询需带 `pub_date` 条件）
```sql
-- 最近爬取的文章（替换为你的 project.dataset）
SELECT title, link, source, pub_date, crawled_at
FROM `你的项目ID.news_project.news_articles`
WHERE DATE(pub_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
ORDER BY crawled_at DESC
LIMIT 20;

-- 各来源统计
SELECT source, COUNT(*) AS cnt
FROM `你的项目ID.news_project.news_articles`
WHERE DATE(pub_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
GROUP BY source
ORDER BY cnt DESC;

-- 按 source 筛选（替换为实际 source 值）
SELECT title, link, pub_date
FROM `你的项目ID.news_project.news_articles`
WHERE source = 'your_source'
  AND DATE(pub_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)
ORDER BY pub_date DESC
LIMIT 20;
```

**查看 Cloud Functions 日志**
```bash
gcloud logging read \
  "resource.type=cloud_function AND resource.labels.function_name=crawl-news" \
  --limit=50 --format=json
```

## 开发指南

### 添加新爬虫

- **简单爬虫**（requests/BeautifulSoup）：在 `scrapers/simple/` 下新建模块，继承 `BaseScraper`，在 `main.py` 的 `SCRAPER_REGISTRY` 中注册。
- **无头浏览器爬虫**（Playwright）：在 `scrapers/browser/` 下新建模块，继承 `BaseBrowserScraper` 并实现 `_run_impl()`，在 `scrapers/browser/__init__.py` 的 `SCRAPER_REGISTRY_BROWSER` 中注册。

**简单爬虫示例**（`scrapers/simple/example.py`）:
```python
from scrapers.base_scraper import BaseScraper

class ExampleScraper(BaseScraper):
    def __init__(self, bq_client):
        super().__init__('example', bq_client)

    def run(self):
        new_articles = []
        # ... 爬取数据，用 self.is_link_exists(link) 去重 ...
        if new_articles:
            self.save_articles(new_articles)
        return self.get_stats()
```

在 `main.py` 中注册：
```python
from scrapers.simple.example import ExampleScraper
SCRAPER_REGISTRY = { ..., 'example': ExampleScraper }
```

### 迁移现有爬虫

参考 `/Users/genkin/coding/gocode/news/news/scripts/` 中的现有爬虫代码：

1. 复制核心爬取逻辑（`run()` 和 `get_detail()` 函数）
2. 替换 `util.history_posts()` 为 `self.is_link_exists()`
3. 替换 `util.write_json_to_file()` 为 `self.save_articles()`
4. 保持 headers 和 URL 不变

## 成本估算 💰

- **Cloud Functions**: ~$3-5/月（每 10 分钟触发，512MB 内存）
- **BigQuery**: ~$1-2/月（存储 + 查询）
- **总计**: 约 **$4-7/月** ✨

### 去重说明

- 启动时按源拉取最新 20 条 URL 入内存，存在性检查走内存，减少 BigQuery 查询
- 表按 `pub_date` 分区，需带分区条件的查询
- 简单爬虫与无头浏览器爬虫分别部署（Cloud Functions / Cloud Run），互不干扰

### 进一步优化建议

1. 减少触发频率：15 分钟或 30 分钟一次（降低 Cloud Functions 成本）
2. 使用 Cloud Run 替代 Cloud Functions（按请求计费，可能更便宜）
3. 调整 BigQuery 分区过期时间（默认 365 天，可缩短至 90 天）

## 监控与告警

**查看统计信息**
```bash
# 当日各源爬取条数（表按 pub_date 分区，查询需带分区条件）
bq query --use_legacy_sql=false \
  "SELECT source, COUNT(*) as count
   FROM \`YOUR_PROJECT_ID.news_project.news_articles\`
   WHERE DATE(pub_date) >= CURRENT_DATE()
   GROUP BY source"
```

**设置告警**（可选）
- Cloud Monitoring: 监控函数执行时间和错误率
- BigQuery: 监控每日新增数据量
- Slack/Email: 接收异常告警

## 故障排查

### 去重性能问题
- BigQuery 查询已按日期分区优化，仅查询最近 7 天数据
- 对于每 10 分钟触发一次的场景，当前性能已足够

### BigQuery 写入失败
- 检查表是否存在：`bq show news_project.news_articles`
- 检查服务账号权限
- 查看 Cloud Functions 日志

### 爬虫超时
- 增加 Cloud Functions 超时时间：`--timeout=540s`
- 减少并发爬虫数量：修改 `config.yaml` 中的 `max_workers`

## 参考资料

- [Google Cloud Functions 文档](https://cloud.google.com/functions/docs)
- [BigQuery 文档](https://cloud.google.com/bigquery/docs)
- [Cloud Scheduler 文档](https://cloud.google.com/scheduler/docs)
- [原始项目](https://github.com/genkin-he/news)

## License

MIT License。本项目为学习用途；若认为存在侵权，请联系作者立即删除。

## 作者

