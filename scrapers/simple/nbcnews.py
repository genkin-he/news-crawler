# -*- coding: UTF-8 -*-
"""NBC News — __NEXT_DATA__ 列表，正文从 ld+json articleBody"""
import sys
import os
import json

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/140.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
LIST_URL = "https://www.nbcnews.com/tech-media"


class NbcnewsScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("nbcnews", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 NBC News...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            try:
                raw = resp.text.split('<script id="__NEXT_DATA__" type="application/json">')[1].split("</script>")[0]
                data = json.loads(raw)
            except (IndexError, json.JSONDecodeError):
                return self.get_stats()
            layouts = (data.get("props") or {}).get("initialState", {}).get("front", {}).get("curation", {}).get("layouts") or []
            posts = []
            if layouts:
                packages = layouts[0].get("packages") or []
                for p in packages[1:3]:
                    posts.extend((p or {}).get("items") or [])
            for post in posts[:5]:
                if getattr(self, "_timed_out", False):
                    break
                cv = (post or {}).get("computedValues") or {}
                title = (cv.get("headline") or "").strip()
                link = (cv.get("url") or "").strip()
                if not link or not title or self.is_link_exists(link):
                    if link and self.is_link_exists(link):
                        break
                    continue
                desc = ""
                try:
                    r2 = _get(link, headers=HEADERS, timeout=10)
                    if r2.status_code == 200 and "application/ld+json" in r2.text:
                        part = r2.text.split('<script type="application/ld+json" data-next-head="">')[1].split("</script>")[0]
                        ld = json.loads(part)
                        desc = (ld.get("articleBody") or "").strip()
                except Exception:
                    pass
                if not desc:
                    desc = title
                new_articles.append({
                    "title": title,
                    "description": "<div>" + desc + "</div>" if desc else title,
                    "link": link,
                    "author": "",
                    "pub_date": self.util.current_time_string(),
                    "kind": 1,
                    "language": "en",
                    "source_name": "nbcnews",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"NBC News 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
