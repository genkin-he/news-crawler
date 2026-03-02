# -*- coding: UTF-8 -*-
"""橙新闻 — API pageList 返回 data.records，txt 即摘要"""
import sys
import os
import re

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36",
    "accept": "application/json",
}
API_URL = "https://apps.orangenews.hk/app/bus/tag/news/common/pageList?handlerName=contentTagPageListHandler&page=1&limit=12&params=%7B%22tagId%22%3A%22126%22%2C%22requestType%22%3A%22IOS%22%7D"


class OrangenewsScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("orangenews", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 橙新闻...")
            new_articles = []
            resp = _get(API_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            data = resp.json()
            records = (data.get("data") or {}).get("records") or []
            for a in records[:5]:
                if getattr(self, "_timed_out", False):
                    break
                link = (a.get("detailsUrl") or "").strip()
                title = (a.get("title") or "").strip()
                if not link or not title or self.is_link_exists(link):
                    continue
                description = (a.get("txt") or "").strip()
                if description:
                    description = re.sub(r".*?【橙訊】", "", description, flags=re.DOTALL).strip()
                if not description:
                    description = title
                new_articles.append({
                    "title": title,
                    "description": description,
                    "link": link,
                    "author": "",
                    "pub_date": self.util.current_time_string(),
                    "kind": 1,
                    "language": "zh-HK",
                    "source_name": "橙新聞",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"橙新闻 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
