# -*- coding: UTF-8 -*-
"""BigQuery 客户端，封装 BigQuery 读写操作"""
import hashlib
import os
import json
import traceback
from datetime import datetime
from typing import List, Dict, Optional, TYPE_CHECKING
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
import yaml

if TYPE_CHECKING:
    from utils.spider_util import SpiderUtil


class BigQueryClient:
    """BigQuery 客户端类"""

    def __init__(self, config_path='config.yaml', log_util: Optional["SpiderUtil"] = None):
        """
        初始化 BigQuery 客户端

        Args:
            config_path: 配置文件路径
            log_util: 可选，用于 info/error 日志；未传则使用 print
        """
        self._log = log_util
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        self.bq_config = config['bigquery']
        self.project_id = self.bq_config['project_id']
        self.dataset_id = self.bq_config['dataset']
        self.table_id = self.bq_config['table']
        self.location = self.bq_config.get('location', 'US')

        # 初始化 BigQuery 客户端
        self.client = bigquery.Client(project=self.project_id, location=self.location)
        self.table_ref = f"{self.project_id}.{self.dataset_id}.{self.table_id}"
        self._link_cache = None  # Optional[Dict[str, set]]: source -> set of url，由调用方在启动时注入

        # 确保数据集和表存在
        self._ensure_dataset_exists()
        self._ensure_table_exists()

    def _log_info(self, message: str) -> None:
        if self._log:
            self._log.info(message)
        else:
            print(message)

    def _log_error(self, message: str) -> None:
        if self._log:
            self._log.error(message)
        else:
            print(message)

    def _ensure_dataset_exists(self):
        """确保数据集存在"""
        dataset_id = f"{self.project_id}.{self.dataset_id}"
        try:
            self.client.get_dataset(dataset_id)
            self._log_info(f"数据集 {dataset_id} 已存在")
        except NotFound:
            dataset = bigquery.Dataset(dataset_id)
            dataset.location = self.location
            dataset = self.client.create_dataset(dataset, timeout=30)
            self._log_info(f"已创建数据集 {dataset.dataset_id}")

    def _ensure_table_exists(self):
        """确保表存在，如果不存在则创建"""
        try:
            self.client.get_table(self.table_ref)
            self._log_info(f"表 {self.table_ref} 已存在")
        except NotFound:
            self._log_info(f"表 {self.table_ref} 不存在，正在创建...")
            schema = [
                bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("title", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("description", "STRING"),
                bigquery.SchemaField("link", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("author", "STRING"),
                bigquery.SchemaField("pub_date", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("source", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("source_name", "STRING"),
                bigquery.SchemaField("kind", "INTEGER"),
                bigquery.SchemaField("language", "STRING"),
                bigquery.SchemaField("crawled_at", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("metadata", "JSON"),
            ]

            table = bigquery.Table(self.table_ref, schema=schema)

            # 配置分区
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="pub_date",
                expiration_ms=365 * 24 * 60 * 60 * 1000  # 365天过期
            )

            # 配置聚簇
            table.clustering_fields = ["source", "language"]

            table = self.client.create_table(table)
            self._log_info(f"已创建表 {table.project}.{table.dataset_id}.{table.table_id}")

    def set_link_cache(self, cache: Dict[str, set]) -> None:
        """
        设置按新闻源的链接内存缓存。设置后 link_exists 仅查内存，不再打 BigQuery。
        调用方应在启动时按源拉取最新 N 条 URL 注入此 cache。
        """
        self._link_cache = cache

    def get_latest_urls(self, source: str, limit: int = 20) -> List[str]:
        """
        按新闻源查出最新写入的 limit 条 link（ORDER BY crawled_at DESC），用于初始化内存缓存。
        """
        query = f"""
            SELECT link
            FROM `{self.table_ref}`
            WHERE source = @source
              AND DATE(pub_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
            ORDER BY crawled_at DESC
            LIMIT @limit
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("source", "STRING", source),
                bigquery.ScalarQueryParameter("limit", "INT64", limit),
            ]
        )
        try:
            query_job = self.client.query(query, job_config=job_config)
            return [row.link for row in query_job.result()]
        except Exception as e:
            self._log_error(f"获取最新链接时出错 [{source}]: {e}")
            return []

    def get_latest_urls_bulk(self, sources: List[str], limit_per_source: int = 20) -> Dict[str, List[str]]:
        """
        一次 SQL 按多个新闻源拉取各自最新 limit_per_source 条 link，用于初始化内存缓存。
        返回 { source: [link, ...], ... }。
        """
        if not sources:
            return {}
        query = f"""
            WITH ranked AS (
                SELECT source, link,
                       ROW_NUMBER() OVER (PARTITION BY source ORDER BY crawled_at DESC) AS rn
                FROM `{self.table_ref}`
                WHERE source IN UNNEST(@sources)
                  AND DATE(pub_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
            )
            SELECT source, link
            FROM ranked
            WHERE rn <= @limit
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("sources", "STRING", sources),
                bigquery.ScalarQueryParameter("limit", "INT64", limit_per_source),
            ]
        )
        try:
            query_job = self.client.query(query, job_config=job_config)
            out: Dict[str, List[str]] = {s: [] for s in sources}
            for row in query_job.result():
                out.setdefault(row.source, []).append(row.link)
            return out
        except Exception as e:
            self._log_error(f"批量获取最新链接时出错: {e}")
            return {s: [] for s in sources}

    def link_exists(self, link: str, source: Optional[str] = None) -> bool:
        """
        检查链接是否已存在。若已通过 set_link_cache 注入缓存，则仅查内存；否则查 BigQuery。
        """
        if self._link_cache is not None and source is not None:
            return link in self._link_cache.get(source, set())

        # 未使用缓存时的回退：查 BigQuery
        query_parameters = [
            bigquery.ScalarQueryParameter("link", "STRING", link),
        ]
        query = f"""
            SELECT COUNT(*) as count
            FROM `{self.table_ref}`
            WHERE link = @link
        """
        if source:
            query += " AND source = @source"
            query_parameters.append(
                bigquery.ScalarQueryParameter("source", "STRING", source)
            )
        query += " AND DATE(pub_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)"
        query += " LIMIT 1"
        job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
        try:
            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())
            return results[0].count > 0 if results else False
        except Exception as e:
            self._log_error(f"检查链接存在性时出错: {e}")
            return False

    def insert_article(self, article: Dict) -> bool:
        """
        插入单篇文章到 BigQuery

        Args:
            article: 文章字典，包含 title, description, link, author, pub_date, source, kind, language

        Returns:
            bool: 是否插入成功
        """
        return self.insert_articles([article])

    def insert_articles(self, articles: List[Dict]) -> bool:
        """
        批量插入文章到 BigQuery

        Args:
            articles: 文章列表

        Returns:
            bool: 是否全部插入成功
        """
        if not articles:
            return True

        # 为每篇文章生成 ID 和爬取时间
        rows_to_insert = []
        for article in articles:
            # 生成文章 ID (MD5(link))
            article_id = hashlib.md5(article['link'].encode()).hexdigest()

            # 处理发布时间
            pub_date = article.get('pub_date')
            if isinstance(pub_date, str):
                # 尝试解析时间字符串
                try:
                    pub_date = datetime.strptime(pub_date, "%Y-%m-%d %H:%M:%S")
                except:
                    pub_date = datetime.now()
            elif not isinstance(pub_date, datetime):
                pub_date = datetime.now()

            source = article.get('source', '')
            row = {
                "id": article_id,
                "title": article.get('title', ''),
                "description": article.get('description', ''),
                "link": article['link'],
                "author": article.get('author', ''),
                "pub_date": pub_date.isoformat(),
                "source": source,
                "source_name": article.get('source_name') or source,
                "kind": article.get('kind', 1),
                "language": article.get('language', 'en'),
                "crawled_at": datetime.now().isoformat(),
                "metadata": json.dumps(article.get('metadata', {}))  # JSON 字段需要序列化为字符串
            }
            rows_to_insert.append(row)

        # 批量插入
        try:
            errors = self.client.insert_rows_json(self.table_ref, rows_to_insert)
            if errors:
                self._log_error(f"插入 BigQuery 时出错 ({len(errors)} 个错误):")
                for i, error in enumerate(errors):
                    self._log_error(f"  错误 {i+1}: {error}")
                if rows_to_insert:
                    self._log_error(f"  第一条数据示例: {rows_to_insert[0]}")
                return False
            else:
                self._log_info(f"成功插入 {len(rows_to_insert)} 条记录到 BigQuery")
                if self._link_cache is not None and rows_to_insert:
                    source = rows_to_insert[0].get("source")
                    if source and source in self._link_cache:
                        for row in rows_to_insert:
                            self._link_cache[source].add(row["link"])
                return True
        except Exception as e:
            self._log_error(f"批量插入失败 (异常): {e}")
            self._log_error(f"  错误类型: {type(e).__name__}")
            if rows_to_insert:
                self._log_error(f"  尝试插入的数据示例: {rows_to_insert[0]}")
            self._log_error(traceback.format_exc())
            return False

    def get_recent_links(self, source: str, days: int = 7) -> List[str]:
        """
        获取指定新闻源最近N天的所有链接（用于初始化 Redis 缓存）

        Args:
            source: 新闻源
            days: 天数

        Returns:
            List[str]: 链接列表
        """
        query = f"""
            SELECT DISTINCT link
            FROM `{self.table_ref}`
            WHERE source = @source
              AND DATE(pub_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("source", "STRING", source),
                bigquery.ScalarQueryParameter("days", "INTEGER", days),
            ]
        )

        try:
            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())
            return [row.link for row in results]
        except Exception as e:
            self._log_error(f"获取最近链接时出错: {e}")
            return []

    def get_stats(self, source: Optional[str] = None, days: int = 1) -> Dict:
        """
        获取统计信息

        Args:
            source: 新闻源（可选）
            days: 统计最近N天

        Returns:
            Dict: 统计信息
        """
        query = f"""
            SELECT
                source,
                COUNT(*) as total_articles,
                COUNT(DISTINCT DATE(pub_date)) as days_with_data
            FROM `{self.table_ref}`
            WHERE DATE(pub_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
        """

        if source:
            query += " AND source = @source"

        query += " GROUP BY source ORDER BY total_articles DESC"

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("days", "INTEGER", days),
            ]
        )

        if source:
            job_config.query_parameters.append(
                bigquery.ScalarQueryParameter("source", "STRING", source)
            )

        try:
            query_job = self.client.query(query, job_config=job_config)
            results = list(query_job.result())

            stats = {}
            for row in results:
                stats[row.source] = {
                    'total_articles': row.total_articles,
                    'days_with_data': row.days_with_data
                }

            return stats
        except Exception as e:
            self._log_error(f"获取统计信息时出错: {e}")
            return {}
