# -*- coding: UTF-8 -*-
"""See It Market — 列表 .td-main-content .item-details h3 a，正文 .td-post-content"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
LIST_URL = "https://www.seeitmarket.com/category/investing/"


class SeeitmarketScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("seeitmarket", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 See It Market...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            for a in soup.select(".td-main-content .item-details h3 a")[:5]:
                if getattr(self, "_timed_out", False):
                    break
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
                        node = s2.select_one(".td-post-content")
                        if node:
                            for el in node.select("div, figure"):
                                el.decompose()
                            raw = str(node).strip()
                            if "<p><strong>Twitter" in raw:
                                raw = raw.split("<p><strong>Twitter")[0]
                            if "<p><em>This report is authored by" in raw:
                                raw = raw.split("<p><em>This report is authored by")[0]
                            desc = raw + "</div>" if raw.endswith("</div>") else raw
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
                    "source_name": "seeitmarket",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"See It Market 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
