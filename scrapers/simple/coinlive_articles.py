# -*- coding: UTF-8 -*-
"""CoinLive Articles — API 列表 + 详情页正文"""
import sys
import os
import json

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "accept": "application/json, text/plain, */*",
    "Referer": "https://www.coinlive.com/",
}
LIST_API = "https://api.coinlive.com/api/v1/news/list"


class CoinliveArticlesScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("coinlive_articles", bq_client)

    def _get_detail(self, link: str) -> str:
        try:
            resp = _get(link, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            detail = soup.select_one("[class^=detail_html]")
            if not detail:
                return ""
            share = detail.select_one("[class^=share__]")
            if not share:
                return ""
            for el in share.select("[class^=share_container], [class^=ad_wrap]"):
                el.decompose()
            return str(share).strip()
        except Exception as e:
            self.util.error(f"get_detail {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 CoinLive Articles...")
            new_articles = []
            body = {"symbols": [], "page": 1, "size": 10, "show_position": 2, "sort": "published_at"}
            resp = _post(LIST_API, headers=HEADERS, data=json.dumps(body), timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            data = resp.json()
            posts = (data.get("data") or {}).get("list") or []
            for post in posts[:5]:
                if getattr(self, "_timed_out", False):
                    break
                tid = post.get("tid")
                link = f"https://www.coinlive.com/news/{tid}" if tid else ""
                if not link or self.is_link_exists(link):
                    continue
                title = (post.get("title") or "").strip()
                if not title:
                    continue
                try:
                    pub_ts = post.get("published_at")
                    pub_date = self.util.convert_utc_to_local(pub_ts) if pub_ts else self.util.current_time_string()
                except (TypeError, ValueError):
                    pub_date = self.util.current_time_string()
                description = self._get_detail(link)
                if description:
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": "",
                        "pub_date": pub_date,
                        "kind": 1,
                        "language": "en",
                        "source_name": "CoinLive",
                    })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"CoinLive Articles 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
