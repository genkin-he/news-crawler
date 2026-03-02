# -*- coding: UTF-8 -*-
"""Yahoo Finance US — 列表 .content > .titles-link，正文 .article .body"""
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
LIST_URL = "https://finance.yahoo.com/topic/latest-news/"


class YahooFinanceUsScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("yahoo_finance_us", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Yahoo Finance US...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            for a in soup.select(".content > .titles-link")[:5]:
                if getattr(self, "_timed_out", False):
                    break
                href = a.get("href") or ""
                if "https://finance.yahoo.com/news/" not in href:
                    continue
                link = href.strip()
                title_el = a.select_one("h2") or a.select_one("h3")
                title = (title_el.get_text() or "").strip() if title_el else ""
                if not link or not title or self.is_link_exists(link):
                    if link and self.is_link_exists(link):
                        break
                    continue
                desc = ""
                pub_date = self.util.current_time_string()
                try:
                    r2 = _get(link, headers=HEADERS, timeout=10)
                    if r2.status_code == 200:
                        s2 = BeautifulSoup(r2.text, "lxml")
                        body = s2.select_one(".article .body")
                        if body:
                            for el in body.select('div[data-testid="inarticle-ad"]'):
                                el.decompose()
                            vc = body.select_one('div[data-testid="view-comments"]')
                            if vc:
                                vc.decompose()
                            desc = str(body).strip()
                        time_el = s2.select_one(".byline-attr-time-style > time")
                        if time_el and time_el.get("datetime"):
                            pub_date = (time_el["datetime"] or "").replace("Z", "+00:00")
                except Exception:
                    pass
                if not desc:
                    desc = title
                new_articles.append({
                    "title": title,
                    "description": desc or title,
                    "link": link,
                    "author": "",
                    "pub_date": pub_date,
                    "kind": 1,
                    "language": "en",
                    "source_name": "雅虎英文",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"Yahoo Finance US 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
