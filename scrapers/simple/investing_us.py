# -*- coding: UTF-8 -*-
"""Investing.com US — API 列表，body 即摘要"""
import sys
import os

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/127.0.0.0 Safari/537.36", "accept": "application/json","Domain-Id": "www",}
BASE_URL = "https://www.investing.com"
API_URL = "https://api.investing.com/api/news/homepage/21/5?is-ad-free-user=false&is-pro-user=false&max-pro-news-updated-hours=12"


class InvestingUsScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("investing_us", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Investing US...")
            new_articles = []
            resp = _get(API_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            posts = resp.json().get("items") or []
            for post in posts[:10]:
                if getattr(self, "_timed_out", False):
                    break
                link = BASE_URL + (post.get("href") or "")
                if not link or self.is_link_exists(link):
                    if link and self.is_link_exists(link):
                        break
                    continue
                title = (post.get("headline") or "").strip()
                body = (post.get("body") or "").strip()
                if not title or not body:
                    continue
                pub = post.get("updated_date")
                pub_date = self.util.parse_time(pub, "%Y-%m-%dT%H:%M:%SZ") if pub else self.util.current_time_string()
                desc = f"<div>{body.replace(chr(10), '<br>')}</div>"
                new_articles.append({"title": title, "description": desc, "link": link, "author": "", "pub_date": pub_date, "kind": 1, "language": "en", "source_name": "Investing"})
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"Investing US 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
