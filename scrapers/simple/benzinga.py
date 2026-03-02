# -*- coding: UTF-8 -*-
"""Benzinga — API 列表，可选详情页正文"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "accept": "application/json",
    "accept-language": "en;q=0.8",
}
API_URL = "https://www.benzinga.com/api/news?limit=10"


class BenzingaScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("benzinga", bq_client)

    def _get_detail(self, link: str) -> str:
        try:
            resp = _get(link, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            body = soup.select_one("#article-body > div:first-child")
            if not body:
                return ""
            for el in body.select("style,figure,script,.copyright,.sr-only,.adthrive-content,.call-to-action-container,.lazyload-wrapper"):
                el.decompose()
            for el in body.select(".core-block"):
                if el.text and any(k in el.text for k in ("See Also:", "SEE ALSO:", "Read Next:", "READ MORE:", "Read More:")):
                    el.decompose()
                elif "<em>Disclaimer</em>" in str(el):
                    el.decompose()
            return str(body).strip()
        except Exception as e:
            self.util.error(f"get_detail {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Benzinga...")
            new_articles = []
            resp = _get(API_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            posts = resp.json()
            for post in posts[:5]:
                if getattr(self, "_timed_out", False):
                    break
                link = post.get("url") or ""
                if not link or self.is_link_exists(link):
                    continue
                title = (post.get("title") or "").strip()
                description = (post.get("teaserText") or "").strip()
                detail = self._get_detail(link)
                if detail and "Read the full article here" not in detail:
                    description = detail
                if not title or not description:
                    continue
                pub_date = self.util.parse_time(post.get("created", ""), "%Y-%m-%dT%H:%M:%SZ") if post.get("created") else self.util.current_time_string()
                new_articles.append({
                    "title": title,
                    "description": f"<div>{description.replace(chr(10), '<br>')}</div>",
                    "link": link,
                    "author": "",
                    "pub_date": pub_date,
                    "kind": 1,
                    "language": "en",
                    "source_name": "Benzinga",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"Benzinga 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
