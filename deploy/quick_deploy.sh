#!/bin/bash
# 一键部署脚本 - 完整部署流程

set -e

echo "========================================"
echo "新闻爬虫 Cloud Functions 一键部署"
echo "========================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查必要的环境变量
if [ -z "$GCP_PROJECT_ID" ]; then
    echo -e "${RED}错误: 请设置环境变量 GCP_PROJECT_ID${NC}"
    echo "示例: export GCP_PROJECT_ID=\"your-project-id\""
    exit 1
fi

PROJECT_ID="$GCP_PROJECT_ID"
REGION="${GCP_REGION:-us-central1}"

echo -e "${GREEN}配置信息:${NC}"
echo "  项目ID: $PROJECT_ID"
echo "  区域: $REGION"
echo ""

# 设置项目
echo -e "${YELLOW}[1/5] 设置 GCP 项目...${NC}"
gcloud config set project "$PROJECT_ID"

# 启用必要的 API
echo -e "${YELLOW}[2/5] 启用必要的 API...${NC}"
gcloud services enable \
  cloudfunctions.googleapis.com \
  cloudscheduler.googleapis.com \
  bigquery.googleapis.com \
  cloudbuild.googleapis.com \
  cloudresourcemanager.googleapis.com

echo -e "${GREEN}✓ API 已启用${NC}"

# 创建 BigQuery 表
echo -e "${YELLOW}[3/5] 创建 BigQuery 数据集和表...${NC}"
if bq show news_project &> /dev/null; then
    echo "数据集 news_project 已存在，跳过创建"
else
    bq mk --dataset --location=US "$PROJECT_ID:news_project"
    echo -e "${GREEN}✓ 数据集已创建${NC}"
fi

if bq show news_project.news_articles &> /dev/null; then
    echo "表 news_articles 已存在，跳过创建"
else
    bq query --use_legacy_sql=false < deploy/create_bigquery_table.sql
    echo -e "${GREEN}✓ BigQuery 表已创建${NC}"
fi

# 更新配置文件
echo -e "${YELLOW}[4/5] 更新配置文件...${NC}"
sed -i.bak "s/your-project-id/$PROJECT_ID/g" config.yaml && rm -f config.yaml.bak
echo -e "${GREEN}✓ 配置文件已更新${NC}"

# 部署 Cloud Functions
echo -e "${YELLOW}[5/5] 部署 Cloud Functions...${NC}"
./deploy/deploy.sh

echo ""
echo -e "${GREEN}========================================"
echo "部署完成！"
echo "========================================${NC}"
echo ""

# 获取函数 URL
FUNCTION_URL=$(gcloud functions describe crawl-news \
  --region="$REGION" \
  --gen2 \
  --format="value(serviceConfig.uri)")

echo -e "${GREEN}函数 URL:${NC} $FUNCTION_URL"
echo ""
echo -e "${YELLOW}下一步操作:${NC}"
echo ""
echo "1. 测试函数:"
echo -e "   ${GREEN}curl -X POST -H \"Content-Type: application/json\" \\${NC}"
echo -e "   ${GREEN}  -d '{\"sources\": \"techcrunch\"}' \\${NC}"
echo -e "   ${GREEN}  $FUNCTION_URL${NC}"
echo ""
echo "2. 配置定时任务:"
echo -e "   ${GREEN}./deploy/setup_scheduler.sh${NC}"
echo ""
echo "3. 查看日志:"
echo -e "   ${GREEN}gcloud logging read \"resource.type=cloud_function\" --limit=20${NC}"
echo ""
echo -e "${GREEN}💰 预计成本: $4-7/月${NC}"
echo ""
