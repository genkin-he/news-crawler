#!/bin/bash
# 无头浏览器爬虫：部署到 Cloud Run + 配置 Cloud Scheduler 定时触发

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="crawl-news-browser"
JOB_NAME="news-crawler-browser-job"
SCHEDULE="*/30 * * * *"   # 每30分钟
TIMEZONE="Asia/Shanghai"

echo "========================================="
echo "部署无头浏览器爬虫到 Cloud Run"
echo "========================================="
echo "  项目ID: $PROJECT_ID"
echo "  区域: $REGION"
echo "  服务名: $SERVICE_NAME"
echo "  镜像: Dockerfile.firefox（仅 Firefox，体积更小）"
echo ""

if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    echo "错误: 未登录 Google Cloud，请先运行 'gcloud auth login'"
    exit 1
fi

gcloud config set project "$PROJECT_ID"

# 1. 构建并部署（使用仅含 Firefox 的轻量镜像 Dockerfile.firefox）
BUILD_DIR=$(mktemp -d)
trap "rm -rf $BUILD_DIR" EXIT
cp -r "$ROOT"/* "$BUILD_DIR/"
cp "$ROOT/Dockerfile.firefox" "$BUILD_DIR/Dockerfile"

echo "[1/2] 构建并部署 Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
  --source="$BUILD_DIR" \
  --region="$REGION" \
  --allow-unauthenticated \
  --memory=2Gi \
  --timeout=360s \
  --max-instances=1 \
  --set-env-vars="BQ_DATASET=news_project"

SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --format="value(status.url)")
if [ -z "$SERVICE_URL" ]; then
    echo "错误: 无法获取服务 URL"
    exit 1
fi
echo "  服务 URL: $SERVICE_URL"

# 2. 配置 Cloud Scheduler 定时触发
echo ""
echo "[2/2] 配置 Cloud Scheduler（$SCHEDULE，$TIMEZONE）..."
if gcloud scheduler jobs describe "$JOB_NAME" --location="$REGION" &> /dev/null; then
    gcloud scheduler jobs delete "$JOB_NAME" --location="$REGION" --quiet
fi
gcloud scheduler jobs create http "$JOB_NAME" \
  --location="$REGION" \
  --schedule="$SCHEDULE" \
  --uri="$SERVICE_URL" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body='{"sources": "all"}' \
  --time-zone="$TIMEZONE" \
  --attempt-deadline=600s

echo ""
echo "========================================="
echo "部署与定时任务配置完成"
echo "========================================="
echo ""
echo "测试: curl -X POST -H 'Content-Type: application/json' -d '{\"sources\": \"stcn\", \"test\": true}' $SERVICE_URL"
echo ""
echo "手动触发定时任务: gcloud scheduler jobs run $JOB_NAME --location=$REGION"
echo ""
