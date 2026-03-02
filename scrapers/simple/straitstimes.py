# -*- coding: UTF-8 -*-
"""Strait Times 爬虫 — requests + BeautifulSoup，可部署到 Cloud Functions"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
}
BASE_URL = "https://www.straitstimes.com"
LIST_URLS = [
    "https://www.straitstimes.com/business/economy?ref=top-navbar",
    "https://www.straitstimes.com/business/companies-markets?ref=top-navbar",
]


class StraitstimesScraper(BaseSimpleScraper):
    """Strait Times 商业新闻爬虫"""

    def __init__(self, bq_client):
        super().__init__("straitstimes", bq_client)
        self._current_links = []

    def _get_detail(self, link: str) -> str:
        if link in self._current_links:
            return ""
        self.util.info(f"link: {link}")
        self._current_links.append(link)
        try:
            resp = _get(link, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            node = soup.select_one(".storyline-wrapper")
            if not node:
                return ""
            for el in node.select("style, script, div"):
                el.decompose()
            return str(node).strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Strait Times...")
            self._current_links = []
            new_articles = []

            for list_url in LIST_URLS:
                if getattr(self, "_timed_out", False):
                    break
                try:
                    resp = _get(list_url, headers=HEADERS, timeout=15)
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "lxml")
                    items = soup.select(".container a.select-none.items-start")[:4]
                    for a in items:
                        if getattr(self, "_timed_out", False):
                            break
                        href = a.get("href")
                        if not href:
                            continue
                        link = BASE_URL + href.strip()
                        title_el = a.select_one("h4")
                        title = (title_el.get_text() or "").strip() if title_el else ""
                        if not title:
                            continue
                        if self.is_link_exists(link):
                            self.util.info(f"exists link: {link}")
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
                                "source_name": "Straitstimes",
                            })
                except Exception as e:
                    self.util.error(f"列表请求失败 {list_url}: {e}")

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Strait Times")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"Strait Times 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
