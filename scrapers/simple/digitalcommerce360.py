# -*- coding: UTF-8 -*-
"""Digital Commerce 360 爬虫 — Algolia API，列表即摘要"""
import sys
import os
from datetime import datetime

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "accept": "*/*",
    "content-type": "application/x-www-form-urlencoded",
    "Referer": "https://www.digitalcommerce360.com/type/news/",
}
ALGOLIA_URL = "https://rsx8q1fola-dsn.algolia.net/1/indexes/*/queries?x-algolia-agent=Algolia%20for%20JavaScript%20(4.18.0)%3B%20Browser%20(lite)&x-algolia-api-key=62bbeeff0c155050d813eec2f8bb0b36&x-algolia-application-id=RSX8Q1FOLA"
PAYLOAD = {
    "requests": [
        {
            "indexName": "wp_searchable_posts_genre",
            "params": "facetingAfterDistinct=true&facets=%5B%22genre%22%2C%22taxonomies.vertical%22%5D&filters=taxonomies.genre%3A'News'&highlightPostTag=__%2Fais-highlight__&highlightPreTag=__ais-highlight__&maxValuesPerFacet=50&page=0&query=&tagFilters=",
        }
    ]
}


class Digitalcommerce360Scraper(BaseSimpleScraper):
    """Digital Commerce 360 爬虫 — 仅列表摘要"""

    def __init__(self, bq_client):
        super().__init__("digitalcommerce360", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Digital Commerce 360...")
            new_articles = []

            resp = _post(ALGOLIA_URL, headers=HEADERS, json=PAYLOAD, timeout=15)
            if resp.status_code != 200:
                self.util.error("API 请求失败")
                return self.get_stats()
            results = resp.json().get("results") or []
            hits = results[0].get("hits") or [] if results else []

            for post in hits[:4]:
                if getattr(self, "_timed_out", False):
                    break
                link = (post.get("permalink") or "").strip()
                if not link or self.is_link_exists(link):
                    if link and self.is_link_exists(link):
                        self.util.info(f"exists link: {link}")
                        break
                    continue
                title = (post.get("post_title") or "").strip()
                description = (post.get("subhead") or "").strip()
                if not title or not description:
                    continue
                ts = post.get("post_date")
                try:
                    pub_date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else self.util.current_time_string()
                except (TypeError, ValueError):
                    pub_date = self.util.current_time_string()

                new_articles.append({
                    "title": title,
                    "description": description,
                    "link": link,
                    "author": "",
                    "pub_date": pub_date,
                    "kind": 1,
                    "language": "en",
                    "source_name": "digitalcommerce360",
                })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Digital Commerce 360")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"Digital Commerce 360 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
