# -*- coding: UTF-8 -*-
"""星岛头条 — 列表 .news-detail .title + a，正文 div.content-body"""
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
LIST_URL = "https://www.stheadline.com/finance/財經"
BASE_URL = "https://www.stheadline.com"


class StheadlineScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("stheadline", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 星岛头条...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            for node in soup.select("div.news-detail")[:6]:
                if getattr(self, "_timed_out", False):
                    break
                title_el = node.select_one(".title")
                a = node.select_one("a")
                if not a or not a.get("href") or not title_el:
                    continue
                link = BASE_URL + a["href"].strip()
                title = (title_el.get_text() or "").strip()
                if not title or self.is_link_exists(link):
                    if self.is_link_exists(link):
                        break
                    continue
                desc = ""
                try:
                    r2 = _get(link, headers=HEADERS, timeout=10)
                    if r2.status_code == 200:
                        s2 = BeautifulSoup(r2.text, "lxml")
                        content = s2.select_one("div.content-body ")
                        if content:
                            for el in content.select("ad, .img-block, .img_caption, img"):
                                el.decompose()
                            desc = str(content).strip()
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
                    "language": "zh-HK",
                    "source_name": "星岛网",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"星岛头条 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
