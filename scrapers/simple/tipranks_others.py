# -*- coding: UTF-8 -*-
"""TipRanks Others — API article 等栏目列表，仅标题作摘要"""
import sys
import os

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/142.0.0.0 Safari/537.36",
    "accept": "application/json",
}
API_URL = "https://www.tipranks.com/api/news/posts?per_page=10&category=article"


class TipranksOthersScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("tipranks_others", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 TipRanks Others...")
            new_articles = []
            resp = _get(API_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            posts = (resp.json() or {}).get("data") or []
            for post in posts[:5]:
                if getattr(self, "_timed_out", False):
                    break
                link = (post.get("link") or "").strip()
                title = (post.get("title") or "").strip()
                if not link or not title or self.is_link_exists(link):
                    if link and self.is_link_exists(link):
                        break
                    continue
                pub = post.get("date")
                pub_date = self.util.parse_time(pub, "%Y-%m-%dT%H:%M:%S.%fZ") if pub else self.util.current_time_string()
                author = (post.get("author") or {}).get("name") or ""
                new_articles.append({
                    "title": title,
                    "description": title,
                    "link": link,
                    "author": author,
                    "pub_date": pub_date,
                    "kind": 1,
                    "language": "en",
                    "source_name": "tipranks",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"TipRanks Others 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
