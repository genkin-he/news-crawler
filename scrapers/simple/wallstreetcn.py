# -*- coding: UTF-8 -*-
"""华尔街见闻 — API information-flow 列表，详情 API 取 content"""
import sys
import os

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "accept": "*/*",
    "Referer": "https://wallstreetcn.com/",
}
LIST_URL = "https://api-one-wscn.awtmt.com/apiv1/content/information-flow?channel=global&accept=article&cursor=&limit=20&action=upglide"
ARTICLE_API = "https://api-one-wscn.awtmt.com/apiv1/content/articles/{}?extract=0&accept_theme=theme%2Cpremium-theme"
CHART_API = "https://api-one-wscn.awtmt.com/apiv1/content/charts/{}"


class WallstreetcnScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("wallstreetcn", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 华尔街见闻...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            items = ((resp.json() or {}).get("data") or {}).get("items") or []
            for entry in items[:5]:
                if getattr(self, "_timed_out", False):
                    break
                kind = entry.get("resource_type")
                resource = entry.get("resource") or {}
                aid = resource.get("id")
                title = (resource.get("title") or "").strip()
                link = (resource.get("uri") or "").strip()
                if not link or not title or self.is_link_exists(link):
                    if link and self.is_link_exists(link):
                        break
                    continue
                desc = ""
                if kind == "article" and aid:
                    try:
                        r2 = _get(ARTICLE_API.format(aid), headers=HEADERS, timeout=10)
                        if r2.status_code == 200:
                            data = (r2.json() or {}).get("data") or {}
                            if not data.get("is_need_pay") and (data.get("videos") or []) == [] and "content" in data:
                                desc = (data.get("content") or "").strip()
                    except Exception:
                        pass
                elif kind == "live" and aid:
                    try:
                        r2 = _get(CHART_API.format(aid), headers=HEADERS, timeout=10)
                        if r2.status_code == 200:
                            data = (r2.json() or {}).get("data") or {}
                            if "content" in data:
                                desc = (data.get("content") or "").strip()
                    except Exception:
                        pass
                if not desc:
                    desc = title
                new_articles.append({
                    "title": title,
                    "description": desc or title,
                    "link": link,
                    "author": (resource.get("author") or {}).get("display_name") or "",
                    "pub_date": self.util.current_time_string(),
                    "kind": 1,
                    "language": "zh-CN",
                    "source_name": "华尔街见闻资讯",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"华尔街见闻 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
