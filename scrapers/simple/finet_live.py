# -*- coding: UTF-8 -*-
"""Finet 财华社 — API 实时快讯"""
import sys
import os
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "accept": "application/json, text/javascript, */*; q=0.01",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.finet.hk/latest/latestnews",
    "x-requested-with": "XMLHttpRequest",
}
API_URL = "https://www.finet.hk/latest/geteslatest/1/{}"
LINK_TMPL = "https://www.finet.hk/newscenter/news_content/{}"


class FinetLiveScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("finet_live", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Finet Live...")
            new_articles = []
            url = API_URL.format(int(time.time()))
            resp = _get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200 or not resp.text:
                return self.get_stats()
            data = resp.json()
            posts = data.get("data") or []
            for post in posts:
                if getattr(self, "_timed_out", False):
                    break
                nid = post.get("id")
                link = LINK_TMPL.format(nid) if nid else ""
                if not link or self.is_link_exists(link):
                    continue
                title = (post.get("name_sc") or "").strip()
                desc = (post.get("description_sc") or "").replace("【财华社讯】", "").strip()
                if not title or not desc:
                    continue
                pub_date = post.get("create_time") or self.util.current_time_string()
                new_articles.append({
                    "title": title,
                    "description": desc,
                    "link": link,
                    "author": "",
                    "pub_date": pub_date,
                    "kind": 2,
                    "language": "zh-CN",
                    "source_name": "Finet",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles[:10])
        except Exception as e:
            self.util.error(f"Finet Live 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
