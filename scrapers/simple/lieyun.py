# -*- coding: UTF-8 -*-
"""猎云 — 列表页 .news1-item，摘要从 .news1-content"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36", "accept": "text/html,application/xhtml+xml,*/*;q=0.8"}
LIST_URL = "https://lieyunpro.com/news"


class LieyunScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("lieyun", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 猎云...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            for node in soup.select(".news1-item"):
                if getattr(self, "_timed_out", False):
                    break
                img = node.select_one("img")
                if not img or "qrcode?url=" not in (img.get("src") or ""):
                    continue
                link = (img.get("src") or "").split("qrcode?url=")[-1]
                if self.is_link_exists(link):
                    break
                t = node.select_one(".news1-title")
                c = node.select_one(".news1-content")
                title = (t.get_text() if t else "").strip()
                desc = (c.get_text() if c else "").strip()
                if not title or not desc:
                    continue
                new_articles.append({"title": title, "description": desc, "link": link, "author": "", "pub_date": self.util.current_time_string(), "kind": 1, "language": "zh-CN", "source_name": "猎云网"})
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"猎云 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
