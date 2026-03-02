# -*- coding: UTF-8 -*-
"""Investing Live — API 列表 + S3 JSON 详情"""
import sys
import os
import re
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/141.0.0.0 Safari/537.36", "Origin": "https://investinglive.com", "Referer": "https://investinglive.com/"}
BASE_URL = "https://investinglive.com"
LIST_API = "https://api.investinglive.com/api/articles/get-all-news?take=12&page=0"


class InvestingliveScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("investinglive", bq_client)

    def _get_detail(self, article_id: int) -> str:
        self.util.info(f"detail id: {article_id}")
        try:
            url = f"https://fmpedia-forexlive-prod.s3.amazonaws.com/investing-articles/{article_id}.json?date={int(time.time() * 1000)}"
            h = {**HEADERS, "Page": f"/news/{article_id}/"}
            r = _get(url, headers=h, timeout=12)
            if r.status_code != 200:
                return ""
            data = r.json()
            body = (data.get("Body") or "")
            body = re.sub(r"<figure[^>]*>.*?</figure>", "", body, flags=re.DOTALL)
            return body.strip()
        except Exception as e:
            self.util.error(f"detail {article_id}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Investing Live...")
            new_articles = []
            resp = _get(LIST_API, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            posts = resp.json().get("Articles") or []
            n = 0
            for post in posts:
                if getattr(self, "_timed_out", False) or n >= 5:
                    break
                cat = (post.get("Category") or {}).get("Slug") or ""
                slug = post.get("Slug") or ""
                link = f"{BASE_URL}/{cat}/{slug}"
                if self.is_link_exists(link):
                    continue
                title = (post.get("Title") or "").strip()
                if not title:
                    continue
                desc = self._get_detail(post.get("Id"))
                if not desc:
                    continue
                pub = post.get("PublishedOn")
                pub_date = self.util.parse_time(pub, "%Y-%m-%dT%H:%M:%S.%fZ") if pub else self.util.current_time_string()
                new_articles.append({"title": title, "description": desc, "link": link, "author": "", "pub_date": pub_date, "kind": 1, "language": "en", "source_name": "Investinglive"})
                n += 1
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"Investing Live 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
