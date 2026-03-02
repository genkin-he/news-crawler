# -*- coding: UTF-8 -*-
"""品玩 态 — API state/list 返回 HTML，.title > a，正文 .article-style"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "accept": "*/*",
    "Referer": "https://www.pingwest.com/",
}
API_URL = "https://www.pingwest.com/api/state/list"


class PingwestStatusScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("pingwest_status", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 品玩态...")
            new_articles = []
            resp = _get(API_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            data = resp.json()
            html = (data.get("data") or {}).get("list") or ""
            if not html:
                return self.get_stats()
            soup = BeautifulSoup(html, "lxml")
            for a in soup.select(".title > a")[:5]:
                if getattr(self, "_timed_out", False):
                    break
                href = a.get("href")
                if not href:
                    continue
                link = "https:" + href.strip()
                title = (a.get_text() or "").strip()
                if not title or self.is_link_exists(link):
                    if self.is_link_exists(link):
                        break
                    continue
                desc = ""
                try:
                    r2 = _get(link, headers=HEADERS, timeout=10)
                    if r2.status_code == 200:
                        s2 = BeautifulSoup(r2.text, "lxml")
                        art = s2.find(class_="article-style")
                        if art:
                            for el in art.select(".ad"):
                                el.decompose()
                            desc = str(art).strip()
                except Exception:
                    pass
                if not desc:
                    desc = title
                new_articles.append({
                    "title": title,
                    "description": desc or title,
                    "link": link,
                    "author": "",
                    "pub_date": self.util.current_time_string(),
                    "kind": 1,
                    "language": "zh-CN",
                    "source_name": "品玩",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"品玩态 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
