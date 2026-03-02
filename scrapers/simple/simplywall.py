# -*- coding: UTF-8 -*-
"""Simply Wall St — 列表 div[data-cy-id="list-article"] article，正文 div[data-cy-id="article-content"]"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
LIST_URL = "https://simplywall.st/news"


class SimplywallScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("simplywall", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Simply Wall St...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            for node in soup.select('div[data-cy-id="list-article"] > article'):
                if getattr(self, "_timed_out", False):
                    break
                link_el = node.select_one("div:first-child > a")
                title_el = node.select_one("div:nth-of-type(2) h2")
                if not link_el or not link_el.get("href") or not title_el:
                    continue
                link = (link_el["href"] or "").strip()
                title = (title_el.get_text() or "").strip()
                if not link or not title or self.is_link_exists(link):
                    if link and self.is_link_exists(link):
                        break
                    continue
                desc = ""
                try:
                    r2 = _get(link, headers=HEADERS, timeout=10)
                    if r2.status_code == 200:
                        s2 = BeautifulSoup(r2.text, "lxml")
                        art = s2.select_one('div[data-cy-id="article-content"]')
                        if art:
                            for el in art.select("figure, div"):
                                el.decompose()
                            last_p = art.find_all("p")
                            if last_p:
                                last_p[-1].decompose()
                            desc = str(art).strip()
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
                    "source_name": "Simplywall",
                })
                if len(new_articles) >= 5:
                    break
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"Simply Wall St 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
