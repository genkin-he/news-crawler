# -*- coding: UTF-8 -*-
"""时代周报 — 列表 .t4_block，正文 .main_article"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/127.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
LIST_URL = "https://www.time-weekly.com/"


class TimeweeklyScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("timeweekly", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 时代周报...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            for post in soup.select(".t4_block")[:5]:
                if getattr(self, "_timed_out", False):
                    break
                text_el = post.select_one(".t4_block_text")
                href = post.get("href")
                if not text_el or not href:
                    continue
                link = href.strip()
                title = (text_el.get_text() or "").strip()
                if not link or not title or self.is_link_exists(link):
                    if link and self.is_link_exists(link):
                        break
                    continue
                desc = ""
                try:
                    r2 = _get(link, headers=HEADERS, timeout=10)
                    if r2.status_code == 200:
                        s2 = BeautifulSoup(r2.text, "lxml")
                        main = s2.select_one(".main_article")
                        if main:
                            for el in main.select("script,style"):
                                el.decompose()
                            desc = str(main).strip()
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
                    "language": "zh-CN",
                    "source_name": "时代周报",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"时代周报 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
