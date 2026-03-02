# -*- coding: UTF-8 -*-
"""TipRanks — BFF payload 列表，正文从详情页 __STATE__ 解析；仅列表+标题作摘要"""
import sys
import os

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/142.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
API_URL = "https://tr-cdn.tipranks.com/bff/prod/header/payload.json"
BASE_URL = "https://tipranks.com"


class TipranksScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("tipranks", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 TipRanks...")
            new_articles = []
            resp = _get(API_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            posts = (resp.json() or {}).get("posts") or []
            for post in posts[:5]:
                if getattr(self, "_timed_out", False):
                    break
                link = (BASE_URL + (post.get("link") or "")).strip()
                title = (post.get("title") or "").strip()
                if not link or not title or self.is_link_exists(link):
                    if link and self.is_link_exists(link):
                        break
                    continue
                pub = post.get("date")
                pub_date = self.util.parse_time(pub, "%Y-%m-%dT%H:%M:%S.%fZ") if pub else self.util.current_time_string()
                author = ""
                if post.get("author") and post["author"].get("name"):
                    author = post["author"]["name"]
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
            self.util.error(f"TipRanks 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
