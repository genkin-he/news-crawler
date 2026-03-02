# -*- coding: UTF-8 -*-
"""明报 — 列表 .contentwrapper，仅经济/地产；原脚本用 curl_cffi，此处用 requests"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/144.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "zh-CN,zh;q=0.9",
}
LIST_URL = "https://news.mingpao.com/ins/即時新聞/main"
BASE_URL = "https://news.mingpao.com"


class MingpaoScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("mingpao", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 明报...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            for node in soup.select(".contentwrapper"):
                if getattr(self, "_timed_out", False):
                    break
                title_el = node.select_one(".title")
                item_el = node.select_one("figure a")
                if not title_el or not item_el or not item_el.get("href"):
                    continue
                kind = title_el.get_text(strip=True)
                if kind not in ("地 產", "經 濟"):
                    continue
                href = item_el["href"].strip()
                link = href if href.startswith("http") else (BASE_URL.rstrip("/") + "/" + href.lstrip("/"))
                if self.is_link_exists(link):
                    break
                title = (item_el.get("title") or item_el.get_text(strip=True) or "").strip()
                if not title:
                    continue
                new_articles.append({
                    "title": title,
                    "description": title,
                    "link": link,
                    "author": "",
                    "pub_date": self.util.current_time_string(),
                    "kind": 1,
                    "language": "zh-HK",
                    "source_name": "明报",
                })
                if len(new_articles) >= 5:
                    break
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"明报 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
