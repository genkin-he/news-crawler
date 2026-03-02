# -*- coding: UTF-8 -*-
"""SBR — 列表 .with-border-bottom .item__title a，正文 .nf__description"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
LIST_URL = "https://sbr.com.sg/news"


class SbrScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("sbr", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 SBR...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            items = soup.select(".with-border-bottom > .item__title")
            for node in items[:5]:
                if getattr(self, "_timed_out", False):
                    break
                a_list = node.select("a")
                if not a_list:
                    continue
                a = a_list[0]
                link = (a.get("href") or "").strip()
                title = (a.get_text() or "").strip()
                if not link or not title or self.is_link_exists(link):
                    if link and self.is_link_exists(link):
                        break
                    continue
                desc = ""
                try:
                    r2 = _get(link, headers=HEADERS, timeout=10)
                    if r2.status_code == 200:
                        s2 = BeautifulSoup(r2.text, "lxml")
                        desc_nodes = s2.select(".nf__description")
                        if desc_nodes:
                            n = desc_nodes[0]
                            for el in n.select(".block-newsletter"):
                                el.decompose()
                            desc = str(n).strip()
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
                    "source_name": "sbr",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"SBR 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
