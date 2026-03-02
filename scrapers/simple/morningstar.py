# -*- coding: UTF-8 -*-
"""Morningstar — requests + BeautifulSoup"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/127.0.0.0 Safari/537.36", "accept": "text/html,application/xhtml+xml,*/*;q=0.8"}
BASE_URL = "https://www.morningstar.com"
LIST_URL = "https://www.morningstar.com/news"


class MorningstarScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("morningstar", bq_client)

    def _get_detail(self, link: str) -> str:
        self.util.info(f"link: {link}")
        try:
            r = _get(link, headers=HEADERS, timeout=12)
            if r.status_code != 200:
                return ""
            soup = BeautifulSoup(r.text, "lxml")
            nodes = soup.select(".mdc-article-body")
            if not nodes:
                return ""
            node = nodes[0]
            for el in node.select(".article-ad"):
                el.decompose()
            return str(node).strip()
        except Exception as e:
            self.util.error(f"detail {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Morningstar...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            for node in soup.select(".mdc-feed__mdc > a")[:3]:
                if getattr(self, "_timed_out", False):
                    break
                href = (node.get("href") or "").strip()
                link = BASE_URL + href if href.startswith("/") else href
                if self.is_link_exists(link):
                    break
                h2 = node.select_one("header > h2")
                title = (h2.get_text() if h2 else "").strip()
                if not title:
                    continue
                desc = self._get_detail(link)
                if desc:
                    new_articles.append({"title": title, "description": desc, "link": link, "author": "", "pub_date": self.util.current_time_string(), "kind": 1, "language": "en", "source_name": "morningstar"})
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"Morningstar 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
