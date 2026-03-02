# -*- coding: UTF-8 -*-
"""BusinessWire — 列表页 + 详情页正文"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "zh-CN,zh;q=0.9",
    "referer": "https://www.businesswire.com/newsroom?language=en&industry=1000178%7C1778661",
}
BASE_URL = "https://www.businesswire.com"
LIST_URL = "https://www.businesswire.com/newsroom?language=en&industry=1000178%7C1778661"


class BusinesswireScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("businesswire", bq_client)

    def _get_detail(self, link: str) -> str:
        try:
            resp = _get(link, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return ""
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "lxml")
            content = soup.select("#bw-release-story")
            if not content:
                return ""
            soup = content[0]
            for el in soup.select("style"):
                el.decompose()
            return str(soup).replace("\n", "").replace("\r", "")
        except Exception as e:
            self.util.error(f"get_detail {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 BusinessWire...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                return self.get_stats()
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "lxml")
            nodes = soup.select("div.overflow-hidden a.font-figtree")
            for node in nodes[:5]:
                if getattr(self, "_timed_out", False):
                    break
                href = (node.get("href") or "").strip()
                link = href if href.startswith("http") else BASE_URL + href
                title = (node.get_text() or "").strip()
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
                        "source_name": "BusinessWire",
                    })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"BusinessWire 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
