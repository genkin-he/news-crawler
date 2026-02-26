-- 创建 BigQuery 表的 SQL 脚本
-- 使用方法: bq query --use_legacy_sql=false < create_bigquery_table.sql

-- 1. 创建数据集（如果不存在）
CREATE SCHEMA IF NOT EXISTS `news_project`
OPTIONS(
  location="US",
  description="新闻爬虫数据集"
);

-- 2. 创建分区表
CREATE OR REPLACE TABLE `news_project.news_articles` (
  id STRING NOT NULL OPTIONS(description="文章唯一ID (MD5(link))"),
  title STRING NOT NULL OPTIONS(description="文章标题"),
  description STRING OPTIONS(description="文章内容或摘要"),
  link STRING NOT NULL OPTIONS(description="原文链接"),
  author STRING OPTIONS(description="作者"),
  pub_date TIMESTAMP NOT NULL OPTIONS(description="发布时间"),
  source STRING NOT NULL OPTIONS(description="新闻源"),
  kind INT64 OPTIONS(description="类型: 1=文章, 2=快讯"),
  language STRING OPTIONS(description="语言: en/zh/etc"),
  crawled_at TIMESTAMP NOT NULL OPTIONS(description="爬取时间"),
  metadata JSON OPTIONS(description="扩展字段")
)
PARTITION BY DATE(pub_date)
CLUSTER BY source, language
OPTIONS(
  description="新闻文章表，按发布日期分区，按来源和语言聚簇",
  partition_expiration_days=7,    -- 分区保留7天
  require_partition_filter=true   -- 查询时必须使用分区过滤
);

-- 完成提示
SELECT 'BigQuery 表创建完成!' as status;
