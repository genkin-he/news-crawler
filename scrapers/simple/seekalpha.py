# -*- coding: UTF-8 -*-
"""Seeking Alpha — API v3/news 列表，attributes.content 即正文 HTML；不传 cookie"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36",
    "accept": "application/json",
    "Referer": "https://seekingalpha.com/market-news",
}
API_URL = "https://seekingalpha.com/api/v3/news?filter[category]=market-news%3A%3Aall&filter[since]=0&filter[until]=0&isMounting=true&page[size]=6&page[number]=1"
BASE_URL = "https://seekingalpha.com"


class SeekalphaScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("seekalpha", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Seeking Alpha...")
            new_articles = []
            resp = _get(API_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            data = resp.json()
            posts = (data.get("data") or [])[:5]
            for post in posts:
                if getattr(self, "_timed_out", False):
                    break
                attrs = post.get("attributes") or {}
                links = post.get("links") or {}
                link = (BASE_URL + links.get("self", "")).strip() if links.get("self") else ""
                title = (attrs.get("title") or "").strip()
                if not link or not title or self.is_link_exists(link):
                    if link and self.is_link_exists(link):
                        break
                    continue
                content = attrs.get("content") or ""
                if content:
                    soup = BeautifulSoup(content, "lxml")
                    for el in soup.select("#more-links"):
                        el.decompose()
                    content = str(soup).strip()
                if not content:
                    content = title
                new_articles.append({
                    "title": title,
                    "description": content,
                    "link": link,
                    "author": "",
                    "pub_date": self.util.current_time_string(),
                    "kind": 1,
                    "language": "en",
                    "source_name": "seekingalpha",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"Seeking Alpha 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
