# -*- coding: UTF-8 -*-
"""TVB 新闻 — API category 列表，desc 即摘要"""
import sys
import os

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/127.0.0.0 Safari/537.36",
    "accept": "application/json, text/plain, */*",
    "Referer": "https://news.tvb.com/",
}
API_URL = "https://inews-api.tvb.com/news/entry/category?id=finance&mpmLimit=0&lang=sc&page=1&limit=10&country=HK"


class TvbScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("tvb", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 TVB 新闻...")
            new_articles = []
            resp = _get(API_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            body = resp.json()
            posts = body.get("content") or []
            for post in posts[:5]:
                if getattr(self, "_timed_out", False):
                    break
                aid = post.get("id")
                link = f"https://news.tvb.com/sc/finance/{aid}" if aid else ""
                title = (post.get("title") or "").strip()
                desc = (post.get("desc") or "").strip()
                if not link or not title or self.is_link_exists(link):
                    continue
                if not desc:
                    desc = title
                new_articles.append({
                    "title": title,
                    "description": desc,
                    "link": link,
                    "author": "",
                    "pub_date": self.util.current_time_string(),
                    "kind": 1,
                    "language": "zh-CN",
                    "source_name": "香港无线新闻",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"TVB 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
