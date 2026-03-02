# -*- coding: UTF-8 -*-
"""金十数据文章 — API 列表 + 详情 .setWebViewConentHeight"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/127.0.0.0 Safari/537.36", "accept": "application/json"}
API_URL = "https://reference-api.jin10.com/reference?page_size=10&nav_bar_id=28"


class Jin10ArticlesScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("jin10_articles", bq_client)

    def _get_detail(self, link: str) -> str:
        self.util.info(f"link: {link}")
        try:
            r = _get(link, headers=HEADERS, timeout=12)
            if r.status_code != 200:
                return ""
            soup = BeautifulSoup(r.text, "lxml")
            node = soup.select_one(".setWebViewConentHeight > div")
            if not node:
                return ""
            for el in node.select("ad"):
                el.decompose()
            return str(node).strip()
        except Exception as e:
            self.util.error(f"detail {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 金十文章...")
            new_articles = []
            resp = _get(API_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            posts = (resp.json().get("data") or {}).get("list") or []
            for post in posts:
                if getattr(self, "_timed_out", False):
                    break
                if post.get("vip") != 0 or post.get("type") != "news" or post.get("original_article") != 1:
                    continue
                link = f"https://xnews.jin10.com/details/{post['id']}"
                if self.is_link_exists(link):
                    break
                title = (post.get("title") or "").strip()
                if not title:
                    continue
                desc = self._get_detail(link)
                if desc:
                    new_articles.append({"title": title, "description": desc, "link": link, "author": "", "pub_date": post.get("display_datetime") or self.util.current_time_string(), "kind": 1, "language": "zh-CN", "source_name": "金十数据资讯"})
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"金十文章 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
