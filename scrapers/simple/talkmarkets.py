# -*- coding: UTF-8 -*-
"""Talk Markets — 列表 h5.card-title a，正文 #blog-content"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/133.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
LIST_URL = "https://talkmarkets.com"


class TalkmarketsScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("talkmarkets", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Talk Markets...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "lxml")
            for node in soup.select("h5.card-title a")[:5]:
                if getattr(self, "_timed_out", False):
                    break
                link = (node.get("href") or "").strip()
                title = (node.get_text() or "").replace("\n", "").strip()
                if not link or not title or self.is_link_exists(link):
                    if link and self.is_link_exists(link):
                        break
                    continue
                desc = ""
                try:
                    r2 = _get(link, headers=HEADERS, timeout=10)
                    if r2.status_code == 200 and "Access Restricted" not in (r2.text or ""):
                        r2.encoding = "utf-8"
                        s2 = BeautifulSoup(r2.text, "lxml")
                        blog = s2.select_one("#blog-content")
                        if blog:
                            for el in blog.select("div"):
                                el.decompose()
                            desc = str(blog).replace("\n", "").replace("\r", "")
                except Exception:
                    pass
                if not desc:
                    desc = title
                new_articles.append({
                    "title": title,
                    "description": desc or title,
                    "link": link,
                    "author": "",
                    "pub_date": self.util.current_time_string(),
                    "kind": 1,
                    "language": "en",
                    "source_name": "Talkmarkets",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"Talk Markets 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
