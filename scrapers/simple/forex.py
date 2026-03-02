# -*- coding: UTF-8 -*-
"""Forex.com 爬虫 — requests + BeautifulSoup"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8",
}
BASE_URL = "https://www.forex.com"
LIST_URL = "https://www.forex.com/en-us/news-and-analysis/"


class ForexScraper(BaseSimpleScraper):
    """Forex.com 爬虫"""

    def __init__(self, bq_client):
        super().__init__("forex", bq_client)

    def _get_detail(self, link: str) -> str:
        self.util.info(f"link: {link}")
        try:
            resp = _get(link, headers=HEADERS, timeout=15)
            resp.encoding = "utf-8"
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            node = soup.select_one(".field-content")
            if not node:
                return ""
            for el in node.select("div"):
                el.decompose()
            return str(node).strip().replace("\n", "").replace("\r", "")
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Forex.com...")
            new_articles = []

            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            resp.encoding = "utf-8"
            if resp.status_code != 200:
                self.util.error("列表请求失败")
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            nodes = soup.select(".news-list__article-title a")[:4]

            for node in nodes:
                if getattr(self, "_timed_out", False):
                    break
                href = (node.get("href") or "").strip()
                link = BASE_URL + href if href.startswith("/") else href
                title = node.get_text().strip().replace("\n", "")
                if not link or not title or self.is_link_exists(link):
                    continue
                description = self._get_detail(link)
                if description:
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": "forex",
                        "pub_date": self.util.current_time_string(),
                        "kind": 1,
                        "language": "en",
                        "source_name": "Forex",
                    })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Forex.com")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"Forex.com 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
