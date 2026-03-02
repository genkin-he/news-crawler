# -*- coding: UTF-8 -*-
"""新浪美股 — API roll/get 列表，正文 .article"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
}
API_URL = "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2518&k=&num=10&page=1"


class SinaUsStockScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("sina_us_stock", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 新浪美股...")
            new_articles = []
            resp = _get(API_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            data = resp.json()
            posts = (data.get("result") or {}).get("data") or []
            for post in posts[:5]:
                if getattr(self, "_timed_out", False):
                    break
                link = (post.get("url") or "").strip()
                title = (post.get("title") or "").strip()
                author = (post.get("author") or "").strip()
                if not link or not title or self.is_link_exists(link):
                    if link and self.is_link_exists(link):
                        break
                    continue
                desc = ""
                try:
                    r2 = _get(link, headers=HEADERS, timeout=10)
                    if r2.status_code == 200:
                        s2 = BeautifulSoup(r2.text, "lxml")
                        for el in s2.select(".appendQr_wrap, .article-editor, style, script"):
                            el.decompose()
                        art = s2.select(".article")
                        if art:
                            desc = str(art[0]).strip()
                except Exception:
                    pass
                if not desc:
                    desc = title
                new_articles.append({
                    "title": title,
                    "description": desc or title,
                    "link": link,
                    "author": author,
                    "pub_date": self.util.current_time_string(),
                    "kind": 1,
                    "language": "zh-CN",
                    "source_name": "新浪财经",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"新浪美股 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
