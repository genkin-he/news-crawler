# -*- coding: UTF-8 -*-
"""Reporteros del Sur — 列表 lisboatv.pt article h2>a，正文 .entry-content"""
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
    "accept-language": "en",
}
LIST_URL = "https://lisboatv.pt"


class ReporterosdelsurScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("reporterosdelsur", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Reporteros del Sur...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            for post in soup.select("article")[:5]:
                if getattr(self, "_timed_out", False):
                    break
                a = post.select_one("h2 > a")
                if not a or not a.get("href"):
                    continue
                link = (a["href"] or "").strip()
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
                        entry = s2.select_one(".entry-content")
                        if entry:
                            for el in entry.select("div[itemprop='video']"):
                                el.decompose()
                            desc = str(entry).strip()
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
                    "source_name": "ReportErosdelsur",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"Reporteros del Sur 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
