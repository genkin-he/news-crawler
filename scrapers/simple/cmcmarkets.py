# -*- coding: UTF-8 -*-
"""CMC Markets — 列表页 + 详情正文"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en,zh-CN,zh;q=0.9",
}
BASE_URL = "https://www.cmcmarkets.com"
LIST_URL = "https://www.cmcmarkets.com/en-gb/news-and-analysis"


class CmcmarketsScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("cmcmarkets", bq_client)

    def _get_detail(self, link: str) -> str:
        try:
            resp = _get(link, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                return ""
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "lxml")
            body = soup.select_one(".article-content")
            if not body:
                return ""
            for el in body.select("script,style,.news-article-widget,.block"):
                el.decompose()
            return str(body).strip()
        except Exception as e:
            self.util.error(f"get_detail {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 CMC Markets...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "lxml")
            items = soup.select(".article-feature")
            for item in items[:3]:
                if getattr(self, "_timed_out", False):
                    break
                href = (item.get("href") or "").strip()
                link = BASE_URL + href if href.startswith("/") else href
                title_el = item.select_one(".feature-headline")
                title = (title_el.get_text() or "").strip() if title_el else ""
                if not title or self.is_link_exists(link):
                    continue
                description = self._get_detail(link)
                if description:
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": "",
                        "pub_date": self.util.current_time_string(),
                        "kind": 1,
                        "language": "en",
                        "source_name": "CMC Markets",
                    })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"CMC Markets 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
