# -*- coding: UTF-8 -*-
"""Money Morning — requests + BeautifulSoup"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/141.0.0.0 Safari/537.36", "accept": "text/html,application/xhtml+xml,*/*;q=0.8", "referer": "https://moneymorning.com/"}
LIST_URL = "https://moneymorning.com/all-posts/"


class MoneymorningScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("moneymorning", bq_client)

    def _get_detail(self, link: str) -> str:
        self.util.info(f"link: {link}")
        try:
            r = _get(link, headers=HEADERS, timeout=12)
            r.encoding = "utf-8"
            if r.status_code != 200 or "Access Restricted" in r.text:
                return ""
            soup = BeautifulSoup(r.text, "lxml")
            node = soup.select_one(".single-content")
            if not node:
                return ""
            for el in node.select("script, style"):
                el.decompose()
            return str(node).strip().replace("\n", "").replace("\r", "")
        except Exception as e:
            self.util.error(f"detail {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Money Morning...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            resp.encoding = "utf-8"
            if resp.status_code != 200 or "Access Restricted" in resp.text:
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            for node in soup.select("h4.entry-title a")[:4]:
                if getattr(self, "_timed_out", False):
                    break
                link = (node.get("href") or "").strip()
                title = node.get_text().strip().replace("\n", "")
                if not link or not title or self.is_link_exists(link):
                    continue
                desc = self._get_detail(link)
                if desc:
                    new_articles.append({"title": title, "description": desc, "link": link, "author": "", "pub_date": self.util.current_time_string(), "kind": 1, "language": "en", "source_name": "Money Morning"})
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"Money Morning 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
