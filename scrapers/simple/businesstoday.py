# -*- coding: UTF-8 -*-
"""Business Today Malaysia 爬虫 — requests + BeautifulSoup"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
}
BASE_URL = "https://www.businesstoday.com.my"
LIST_URL = "https://www.businesstoday.com.my/category/marketing/"


class BusinesstodayScraper(BaseSimpleScraper):
    """Business Today Malaysia 爬虫"""

    def __init__(self, bq_client):
        super().__init__("businesstoday", bq_client)

    def _get_detail(self, link: str) -> str:
        self.util.info(f"link: {link}")
        try:
            resp = _get(link, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            node = soup.select_one("#tdi_40 div[data-td-block-uid=tdi_61] .tdb-block-inner")
            if not node:
                node = soup.select_one(".td-post-content, .tdb-block-inner, article .entry-content")
            if not node:
                return ""
            for el in node.select("div.td-a-rec, script, style, .sharedaddy, .jp-relatedposts"):
                el.decompose()
            return str(node).strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Business Today...")
            new_articles = []

            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                self.util.error("列表请求失败")
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            items = soup.select("h3.entry-title a")[:3]

            for a in items:
                if getattr(self, "_timed_out", False):
                    break
                link = (a.get("href") or "").strip()
                title = a.get_text().strip()
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
                        "source_name": "Business Today",
                    })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Business Today")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"Business Today 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
