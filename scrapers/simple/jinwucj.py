# -*- coding: UTF-8 -*-
"""金吾财经 IPO — POST API 列表，content 即正文"""
import sys
import os

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36", "Content-Type": "application/json"}
API_URL = "https://ipo.jinwucj.com/api/info/getInfoList"
BASE_URL = "https://ipo.jinwucj.com"


class JinwucjScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("jinwucj", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 金吾财经...")
            new_articles = []
            resp = _post(API_URL, headers=HEADERS, json={"pageNum": 1, "pageSize": 10}, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            posts = (resp.json().get("body") or {}).get("list") or []
            for post in posts[:4]:
                if getattr(self, "_timed_out", False):
                    break
                id_ = post.get("id")
                link = f"{BASE_URL}/info/infoDetails/{id_}"
                if self.is_link_exists(link):
                    break
                title = (post.get("title") or "").strip()
                desc = (post.get("content") or "").strip()
                if not title or not desc:
                    continue
                new_articles.append({"title": title, "description": desc, "link": link, "author": "", "pub_date": post.get("updatedTime") or self.util.current_time_string(), "kind": 1, "language": "zh-CN", "source_name": "金吾资讯"})
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"金吾财经 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
