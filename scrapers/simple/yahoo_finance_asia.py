# -*- coding: UTF-8 -*-
"""Yahoo 财经香港 — 列表页 .js-stream-content h3>a，正文 .caas-body"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/135.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
LIST_URL = "https://hk.news.yahoo.com/business/"
BASE = "https://hk.news.yahoo.com"


class YahooFinanceAsiaScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("yahoo_finance_asia", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Yahoo 财经香港...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            for node in soup.select(".js-stream-content")[:5]:
                if getattr(self, "_timed_out", False):
                    break
                a = node.select_one("h3 > a")
                if not a or not a.get("href"):
                    continue
                href = (a["href"] or "").strip()
                if not href or "https://" in href:
                    continue
                link = BASE + href
                title = (a.get_text() or "").strip()
                if not title or self.is_link_exists(link):
                    if self.is_link_exists(link):
                        break
                    continue
                desc = ""
                try:
                    r2 = _get(link, headers=HEADERS, timeout=10)
                    if r2.status_code == 200:
                        s2 = BeautifulSoup(r2.text, "lxml")
                        body = s2.select_one(".caas-body") or s2.select_one(".atoms")
                        if body:
                            for el in body.select('div[data-testid="inarticle-ad"]'):
                                el.decompose()
                            vc = body.select_one('div[data-testid="view-comments"]')
                            if vc:
                                vc.decompose()
                            desc = str(body).strip()
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
                    "source_name": "雅虎亚洲",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"Yahoo 财经香港 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
