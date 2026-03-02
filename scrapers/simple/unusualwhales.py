# -*- coding: UTF-8 -*-
"""Unusual Whales — API free_news 列表，summary/headline 即摘要；跳过 Bloomberg"""
import sys
import os

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/142.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
API_URL = "https://api.unusualwhales.com/market_news/api/free_news?page=0"


class UnusualwhalesScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("unusualwhales", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Unusual Whales...")
            new_articles = []
            resp = _get(API_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            news_list = (resp.json() or {}).get("news") or []
            for item in news_list[:10]:
                if getattr(self, "_timed_out", False):
                    break
                if (item.get("source") or "") == "Bloomberg":
                    continue
                aid = item.get("id")
                link = f"https://www.markets.news/headlines/{aid}" if aid else ""
                headline = (item.get("headline") or "").strip()
                summary = (item.get("summary") or "").strip()
                if not link or self.is_link_exists(link):
                    continue
                if not summary:
                    summary = headline
                    headline = ""
                title = headline or summary
                pub = item.get("timestamp")
                pub_date = self.util.parse_time(pub, "%Y-%m-%dT%H:%M:%SZ") if pub else self.util.current_time_string()
                new_articles.append({
                    "title": title,
                    "description": summary,
                    "link": link,
                    "author": "",
                    "pub_date": pub_date,
                    "kind": 1,
                    "language": "en",
                    "source_name": "Unusual Whales",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"Unusual Whales 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
