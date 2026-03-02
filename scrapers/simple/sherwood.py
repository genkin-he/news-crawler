# -*- coding: UTF-8 -*-
"""Sherwood News — 列表页内嵌摘要 + 正文"""
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
    "accept-language": "en;q=0.9",
}
BASE_URL = "https://sherwood.news"
LIST_URL = "https://sherwood.news/markets/"


class SherwoodScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("sherwood", bq_client)

    def _get_detail_from_node(self, node) -> str:
        try:
            a = node.select("a")
            if a:
                a[0].decompose()
            for el in node.select("div"):
                el.decompose()
            return str(node).strip()
        except Exception:
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Sherwood...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "lxml")
            nodes_one = soup.select("div.css-ivtglt")
            nodes_two = soup.select("div.css-12fbs19")
            nodes = nodes_one + nodes_two
            for node in nodes:
                if getattr(self, "_timed_out", False):
                    break
                a_list = node.select("a")
                if not a_list:
                    continue
                href = (a_list[0].get("href") or "").strip()
                link = BASE_URL + href if href.startswith("/") else href
                if not link.startswith("http"):
                    continue
                title = (a_list[0].get_text() or "").strip()
                if not title or self.is_link_exists(link):
                    continue
                description = self._get_detail_from_node(node)
                if description:
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": "",
                        "pub_date": self.util.current_time_string(),
                        "kind": 1,
                        "language": "en",
                        "source_name": "Sherwoodnews",
                    })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles[:20])
        except Exception as e:
            self.util.error(f"Sherwood 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
