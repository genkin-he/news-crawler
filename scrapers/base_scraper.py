# -*- coding: UTF-8 -*-
"""爬虫基类，提供通用的去重、保存等功能"""
from typing import List, Dict, Optional
import sys
import os

# 添加 utils 目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.spider_util import SpiderUtil
from utils.bigquery_client import BigQueryClient


class BaseScraper:
    """爬虫基类"""

    def __init__(self, source_name: str, bq_client: BigQueryClient):
        """
        初始化爬虫

        Args:
            source_name: 新闻源名称（如 bloomberg, coinlive）
            bq_client: BigQuery 客户端实例
        """
        self.source = source_name
        self.bq = bq_client
        self.util = SpiderUtil(name=source_name)

        # 统计信息
        self.stats = {
            'new_articles': 0,
            'skipped': 0,
            'errors': 0
        }

    def is_link_exists(self, link: str) -> bool:
        """
        检查链接是否已存在（查 BigQuery）

        Args:
            link: 文章链接

        Returns:
            bool: 链接是否存在
        """
        return self.bq.link_exists(link, self.source)

    def save_article(self, article: Dict) -> bool:
        """
        保存文章到 BigQuery

        Args:
            article: 文章字典

        Returns:
            bool: 是否保存成功
        """
        article['source'] = self.source
        success = self.bq.insert_article(article)
        if success:
            self.stats['new_articles'] += 1
        else:
            self.stats['errors'] += 1
        return success

    def save_articles(self, articles: List[Dict]) -> bool:
        """
        批量保存文章到 BigQuery

        Args:
            articles: 文章列表

        Returns:
            bool: 是否全部保存成功
        """
        if not articles:
            return True

        for article in articles:
            article['source'] = self.source

        success = self.bq.insert_articles(articles)
        if success:
            self.stats['new_articles'] += len(articles)
        else:
            self.stats['errors'] += len(articles)
        return success

    def run(self) -> Dict:
        """
        执行爬虫（子类需要实现）

        Returns:
            Dict: 执行结果统计
        """
        raise NotImplementedError("子类必须实现 run() 方法")

    def get_stats(self) -> Dict:
        """
        获取统计信息

        Returns:
            Dict: 统计信息
        """
        return self.stats.copy()
