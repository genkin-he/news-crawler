# -*- coding: UTF-8 -*-
"""Channel News Asia 爬虫 — Algolia API，可部署到 Cloud Functions"""
import sys
import os
import json

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "accept": "application/json",
    "content-type": "application/x-www-form-urlencoded",
    "Origin": "https://www.channelnewsasia.com",
    "Referer": "https://www.channelnewsasia.com/",
}
ALGOLIA_URL = "https://kkwfbq38xf-2.algolianet.com/1/indexes/*/queries"
ALGOLIA_HEADERS = {
    **HEADERS,
    "x-algolia-agent": "Algolia for JavaScript (3.35.1); Browser (lite)",
    "x-algolia-application-id": "KKWFBQ38XF",
    "x-algolia-api-key": "e5eb600a29d13097eef3f8da05bf93c1",
}
ALGOLIA_PAYLOAD = {
    "requests": [
        {
            "indexName": "cnarevamp-ezrqv5hx",
            "params": "query=&maxValuesPerFacet=40&page=0&hitsPerPage=15&facets=%5B%22categories%22%2C%22type%22%5D&facetFilters=%5B%5B%22categories%3ABusiness%22%5D%2C%5B%22type%3Aarticle%22%5D%5D"
        }
    ]
}


class ChannelnewsasiaScraper(BaseSimpleScraper):
    """Channel News Asia Business 爬虫（Algolia API）"""

    def __init__(self, bq_client):
        super().__init__("channelnewsasia", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Channel News Asia...")
            new_articles = []

            resp = _post(
                ALGOLIA_URL,
                headers=ALGOLIA_HEADERS,
                json=ALGOLIA_PAYLOAD,
                timeout=15,
            )
            if resp.status_code != 200:
                self.util.error(f"Algolia API 请求失败: {resp.status_code}")
                return self.get_stats()

            data = resp.json()
            results = data.get("results") or []
            if not results:
                self.util.info("无列表数据")
                return self.get_stats()
            hits = results[0].get("hits") or []

            for hit in hits[:10]:
                if getattr(self, "_timed_out", False):
                    break
                title = (hit.get("title") or "").strip()
                link = hit.get("link_absolute") or hit.get("url") or hit.get("link") or ""
                if not link or not title:
                    continue
                if self.is_link_exists(link):
                    self.util.info(f"exists link: {link}")
                    continue
                para = hit.get("paragraph_text")
                if isinstance(para, list):
                    description = "".join(para)
                else:
                    description = para or ""
                if not description.strip():
                    continue
                pub_date = self.util.current_time_string()
                for key in ("published_at", "created_at", "date"):
                    if hit.get(key):
                        try:
                            pub_date = self.util.parse_time(hit[key], "%Y-%m-%dT%H:%M:%SZ")
                        except Exception:
                            pass
                        break
                new_articles.append({
                    "title": title,
                    "description": description.strip(),
                    "link": link,
                    "author": "",
                    "pub_date": pub_date,
                    "kind": 1,
                    "language": "en",
                    "source_name": "CNA",
                })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Channel News Asia")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"Channel News Asia 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
