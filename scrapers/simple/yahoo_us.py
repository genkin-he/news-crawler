# -*- coding: UTF-8 -*-
"""Yahoo US News — StreamGrid API + caas/content 详情，markup 即正文"""
import sys
import os
import re

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
}
STREAM_URL = "https://news.yahoo.com/fp_ms/_rcv/remote?ctrl=StreamGrid&lang=en-US&m_id=react-wafer-stream&m_mode=json&region=US&rid=4c18971j77t3g&partner=none&site=news"
DETAIL_URL = "https://news.yahoo.com/caas/content/article/?uuid={}&appid=news_web&device=desktop&lang=en-US&region=US&site=news&partner=none"


class YahooUsScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("yahoo_us", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Yahoo US News...")
            new_articles = []
            resp = _get(STREAM_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            data = resp.json()
            html = (data.get("html") or "")
            uuids = list(set(re.findall(r'data-uuid="([^"]+)"', html)))[:10]
            if not uuids:
                return self.get_stats()
            detail_resp = _get(DETAIL_URL.format(",".join(uuids)), headers=HEADERS, timeout=15)
            if detail_resp.status_code != 200:
                return self.get_stats()
            posts = (detail_resp.json() or {}).get("items") or []
            for post in posts[:5]:
                if getattr(self, "_timed_out", False):
                    break
                pd = (post.get("data") or {}).get("partnerData") or {}
                link = (pd.get("url") or "").strip()
                title = (pd.get("title") or "").strip()
                if not link or not title or self.is_link_exists(link):
                    if link and self.is_link_exists(link):
                        break
                    continue
                markup = (post.get("markup") or "").strip()
                if not markup:
                    markup = title
                pub = pd.get("publishDate")
                pub_date = self.util.parse_time(pub, "%a, %d %b %Y %H:%M:%S %Z") if pub else self.util.current_time_string()
                author = (pd.get("publisher") or "").strip()
                new_articles.append({
                    "title": title,
                    "description": markup,
                    "link": link,
                    "author": author,
                    "pub_date": pub_date,
                    "kind": 1,
                    "language": "en",
                    "source_name": "雅虎英文",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"Yahoo US News 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
