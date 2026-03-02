# -*- coding: UTF-8 -*-
"""TradingView — news-mediator API 列表，正文 article div[class*='body-']；不传 cookie"""
import sys
import os
import time

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "accept": "*/*",
    "Referer": "https://www.tradingview.com/",
}
API_URL = "https://news-mediator.tradingview.com/news-flow/v1/news?filter=lang%3Aen&streaming=true&time={}"


class TradingviewScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("tradingview", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 TradingView...")
            new_articles = []
            url = API_URL.format(int(time.time()))
            resp = _get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            items = (resp.json() or {}).get("items") or []
            for post in items[:5]:
                if getattr(self, "_timed_out", False):
                    break
                story_path = post.get("storyPath") or ""
                link = ("https://www.tradingview.com" + story_path).strip() if story_path else ""
                title = (post.get("title") or "").strip()
                if not link or not title or self.is_link_exists(link):
                    if link and self.is_link_exists(link):
                        break
                    continue
                sourceName = post.get("source") or ""
                if sourceName:
                    sourceName = sourceName.strip()
                else:
                    sourceName = "tradingview"

                desc = ""
                try:
                    r2 = _get(link, headers=HEADERS, timeout=10)
                    if r2.status_code == 200:
                        s2 = BeautifulSoup(r2.text, "lxml")
                        body = s2.select_one("article div[class*='body-']")
                        if body:
                            for el in body.select("a[href*='/symbols/']"):
                                el.decompose()
                            desc = str(body).strip()
                except Exception:
                    pass
                if not desc:
                    desc = title
                pub = post.get("published")
                pub_date = self.util.convert_utc_to_local(pub) if pub else self.util.current_time_string()
                new_articles.append({
                    "title": title,
                    "description": desc or title,
                    "link": link,
                    "author": "",
                    "pub_date": pub_date,
                    "kind": 1,
                    "language": "en",
                    "source_name": sourceName,
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"TradingView 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
