#!/bin/bash
# Cloud Functions 部署脚本

set -e

echo "========================================="
echo "部署新闻爬虫到 Google Cloud Functions"
echo "========================================="

# 配置变量（请根据您的实际情况修改）
PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="${GCP_REGION:-us-central1}"
FUNCTION_NAME="crawl-news"

echo ""
echo "配置信息:"
echo "  项目ID: $PROJECT_ID"
echo "  区域: $REGION"
echo "  函数名: $FUNCTION_NAME"
echo ""

# CI（如 GitHub Actions）会设置 GOOGLE_APPLICATION_CREDENTIALS，需在本进程内激活 gcloud
if [ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ] && [ -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    gcloud auth activate-service-account --key-file="$GOOGLE_APPLICATION_CREDENTIALS"
fi

# 检查是否已登录 gcloud（不用 --filter=status:ACTIVE，服务账号下可能不返回）
ACCOUNT=$(gcloud auth list --format="value(account)" 2>/dev/null | head -n1)
if [ -z "$ACCOUNT" ]; then
    echo "错误: 未登录 Google Cloud，请先运行 'gcloud auth login'"
    exit 1
fi

# 设置项目
echo "设置项目..."
gcloud config set project "$PROJECT_ID"

# 检查配置文件
if [ ! -f "config.yaml" ]; then
    echo "错误: 找不到 config.yaml 文件"
    exit 1
fi

# 更新 config.yaml 中的项目ID
echo "更新配置文件中的项目ID..."
sed -i.bak "s/your-project-id/$PROJECT_ID/g" config.yaml && rm config.yaml.bak

echo "开始部署 Cloud Functions..."

# 部署函数
gcloud functions deploy "$FUNCTION_NAME" \
  --gen2 \
  --runtime=python311 \
  --region="$REGION" \
  --source=. \
  --entry-point=crawl_news \
  --trigger-http \
  --allow-unauthenticated \
  --memory=512MB \
  --timeout=540s \
  --max-instances=1 \
  --min-instances=0 \
  --set-env-vars="BQ_DATASET=news_project" \
  --service-account="${PROJECT_ID}@appspot.gserviceaccount.com"

echo ""
echo "========================================="
echo "部署完成！"
echo "========================================="

# 获取函数 URL
FUNCTION_URL=$(gcloud functions describe "$FUNCTION_NAME" \
  --region="$REGION" \
  --gen2 \
  --format="value(serviceConfig.uri)")

echo ""
echo "函数 URL: $FUNCTION_URL"
echo ""
echo "测试命令:"
echo "  curl -X POST -H \"Content-Type: application/json\" \\"
echo "    -d '{\"sources\": \"techcrunch\"}' \\"
echo "    $FUNCTION_URL"
echo ""
