# -*- coding: UTF-8 -*-
"""科技新报 — 列表 article h1.entry-title a，正文 div.indent"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/141.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
LIST_URL = "https://technews.tw/"


class TechnewsScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("technews", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 科技新报...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "lxml")
            for item in soup.select("article h1.entry-title a")[:5]:
                if getattr(self, "_timed_out", False):
                    break
                link = (item.get("href") or "").strip()
                title = (item.get_text() or "").strip()
                if not link or not title or self.is_link_exists(link):
                    if link and self.is_link_exists(link):
                        break
                    continue
                desc = ""
                try:
                    r2 = _get(link, headers=HEADERS, timeout=10)
                    if r2.status_code == 200:
                        r2.encoding = "utf-8"
                        s2 = BeautifulSoup(r2.text, "lxml")
                        indent = s2.select_one("div.indent")
                        if indent:
                            for el in indent.select("script,style,div"):
                                el.decompose()
                            desc = str(indent).strip()
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
                    "language": "zh-TW",
                    "source_name": "科技新报",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"科技新报 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
