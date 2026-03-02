# -*- coding: UTF-8 -*-
"""Drive Tesla Canada — 列表 + 详情正文"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "zh-CN,zh;q=0.9",
}
BASE_URL = "https://driveteslacanada.ca/"


class DriveteslacanadaScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("driveteslacanada", bq_client)

    def _get_detail(self, link: str) -> str:
        try:
            resp = _get(link, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            body = soup.select_one(".entry-content")
            if not body:
                return ""
            for el in body.select("style,script,.code-block,.twitter-tweet"):
                el.decompose()
            return str(body).strip()
        except Exception as e:
            self.util.error(f"get_detail {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Drive Tesla Canada...")
            new_articles = []
            resp = _get(BASE_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            items = soup.select(".entry-content article")
            for item in items[:6]:
                if getattr(self, "_timed_out", False):
                    break
                title_el = item.select_one(".entry-title > a")
                if not title_el:
                    continue
                link = (title_el.get("href") or "").strip()
                title = (title_el.get_text() or "").strip()
                thumb = item.select_one(".entry-thumb img")
                image = (thumb.get("src") or "").strip() if thumb else ""
                if not link or not title or self.is_link_exists(link):
                    continue
                description = self._get_detail(link)
                if description:
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": "",
                        "pub_date": self.util.current_time_string(),
                        "kind": 1,
                        "language": "en",
                        "source_name": "Drive Tesla Canada",
                    })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"Drive Tesla Canada 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
