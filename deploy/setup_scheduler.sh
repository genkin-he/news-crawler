#!/bin/bash
# Cloud Scheduler 配置脚本

set -e

echo "========================================="
echo "配置 Cloud Scheduler 定时任务"
echo "========================================="

# 配置变量
PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="${GCP_REGION:-us-central1}"
JOB_NAME="news-crawler-job"
FUNCTION_NAME="crawl-news"
SCHEDULE="*/10 * * * *"  # 每10分钟执行一次
TIMEZONE="Asia/Shanghai"

echo ""
echo "配置信息:"
echo "  项目ID: $PROJECT_ID"
echo "  区域: $REGION"
echo "  任务名: $JOB_NAME"
echo "  执行频率: $SCHEDULE (每10分钟)"
echo "  时区: $TIMEZONE"
echo ""

# 设置项目
gcloud config set project "$PROJECT_ID"

# 获取 Cloud Function URL
echo "获取 Cloud Function URL..."
FUNCTION_URL=$(gcloud functions describe "$FUNCTION_NAME" \
  --region="$REGION" \
  --gen2 \
  --format="value(serviceConfig.uri)")

if [ -z "$FUNCTION_URL" ]; then
    echo "错误: 无法获取 Cloud Function URL，请先部署 Cloud Functions"
    exit 1
fi

echo "Cloud Function URL: $FUNCTION_URL"

# 删除已存在的任务（如果有）
if gcloud scheduler jobs describe "$JOB_NAME" --location="$REGION" &> /dev/null; then
    echo "删除已存在的任务..."
    gcloud scheduler jobs delete "$JOB_NAME" --location="$REGION" --quiet
fi

# 创建新任务
echo "创建 Cloud Scheduler 任务..."
gcloud scheduler jobs create http "$JOB_NAME" \
  --location="$REGION" \
  --schedule="$SCHEDULE" \
  --uri="$FUNCTION_URL" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body='{"sources": "all"}' \
  --time-zone="$TIMEZONE" \
  --attempt-deadline=360s

echo ""
echo "========================================="
echo "Cloud Scheduler 配置完成！"
echo "========================================="
echo ""
echo "查看任务:"
echo "  gcloud scheduler jobs describe $JOB_NAME --location=$REGION"
echo ""
echo "手动触发任务:"
echo "  gcloud scheduler jobs run $JOB_NAME --location=$REGION"
echo ""
echo "查看执行日志:"
echo "  gcloud logging read \"resource.type=cloud_function AND resource.labels.function_name=$FUNCTION_NAME\" --limit=50 --format=json"
echo ""
