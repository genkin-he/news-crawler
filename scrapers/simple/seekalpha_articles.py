# -*- coding: UTF-8 -*-
"""Seeking Alpha Articles — API v3/articles 列表，详情 API 取 content；不传 cookie"""
import sys
import os

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36",
    "accept": "application/json",
    "Referer": "https://seekingalpha.com/latest-articles",
}
LIST_URL = "https://seekingalpha.com/api/v3/articles?filter[category]=latest-articles&filter[since]=0&filter[until]=0&include=author%2CprimaryTickers%2CsecondaryTickers&isMounting=true&page[size]=20&page[number]=1"
BASE_URL = "https://seekingalpha.com"


class SeekalphaArticlesScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("seekalpha_articles", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Seeking Alpha Articles...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            data = resp.json()
            posts = (data.get("data") or [])[:3]
            for post in posts:
                if getattr(self, "_timed_out", False):
                    break
                aid = post.get("id")
                attrs = post.get("attributes") or {}
                links = post.get("links") or {}
                link = (BASE_URL + links.get("self", "")).strip() if links.get("self") else ""
                title = (attrs.get("title") or "").strip()
                if not link or not title or self.is_link_exists(link):
                    if link and self.is_link_exists(link):
                        break
                    continue
                desc = ""
                if aid:
                    try:
                        r2 = _get(
                            f"https://seekingalpha.com/api/v3/articles/{aid}?include=author",
                            headers=HEADERS,
                            timeout=10,
                        )
                        if r2.status_code == 200:
                            d2 = r2.json()
                            desc = ((d2.get("data") or {}).get("attributes") or {}).get("content") or ""
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
                    "source_name": "seekingalpha",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"Seeking Alpha Articles 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
