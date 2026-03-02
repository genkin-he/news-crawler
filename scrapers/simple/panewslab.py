# -*- coding: UTF-8 -*-
"""PANews — API flashnews 列表，desc 即摘要"""
import sys
import os

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/127.0.0.0 Safari/537.36",
    "accept": "*/*",
    "Referer": "https://www.panewslab.com/",
}
API_URL = "https://www.panewslab.com/webapi/flashnews?LId=1&LastTime=0&Rn=10"
BASE_URL = "https://www.panewslab.com"


class PanewslabScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("panewslab", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 PANews...")
            new_articles = []
            resp = _get(API_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            body = resp.json()
            flash = (body.get("data") or {}).get("flashNews") or []
            posts = (flash[0].get("list") or []) if flash else []
            for post in posts[:5]:
                if getattr(self, "_timed_out", False):
                    break
                aid = post.get("id")
                link = f"{BASE_URL}/zh/sqarticledetails/{aid}.html" if aid else ""
                title = (post.get("title") or "").strip()
                desc = (post.get("desc") or "").strip()
                if not link or not title or self.is_link_exists(link):
                    continue
                pub = post.get("publishTime")
                pub_date = self.util.convert_utc_to_local(pub) if pub else self.util.current_time_string()
                new_articles.append({
                    "title": title,
                    "description": desc or title,
                    "link": link,
                    "author": "",
                    "pub_date": pub_date,
                    "kind": 2,
                    "language": "zh-CN",
                    "source_name": "PANews",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"PANews 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
