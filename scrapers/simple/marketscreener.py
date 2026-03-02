# -*- coding: UTF-8 -*-
"""Marketscreener — 列表页 #newsScreener tbody tr，摘要用标题"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/139.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
LIST_URL = "https://hk.marketscreener.com/news/"
BASE_URL = "https://hk.marketscreener.com"


class MarketscreenerScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("marketscreener", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Marketscreener...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            items = soup.select("#newsScreener > tbody > tr")
            for node in items[:10]:
                if getattr(self, "_timed_out", False):
                    break
                a = node.select_one("td.w-100 div.gnowrap a.txt-overflow-2")
                if not a or not a.get("href"):
                    continue
                link = BASE_URL + a["href"].strip()
                if self.is_link_exists(link):
                    break
                title = (a.get_text() or "").strip()
                if not title:
                    continue
                new_articles.append({
                    "title": title,
                    "description": title,
                    "link": link,
                    "author": "",
                    "pub_date": self.util.current_time_string(),
                    "kind": 1,
                    "language": "en",
                    "source_name": "marketscreener",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"Marketscreener 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
