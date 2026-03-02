# -*- coding: UTF-8 -*-
"""Bastille Post 爬虫 — requests + BeautifulSoup，可部署到 Cloud Functions"""
import sys
import os
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "accept-language": "zh-HK,zh;q=0.9,en;q=0.8",
}
BASE_URL = "https://www.bastillepost.com"
LIST_URLS = [
    "https://www.bastillepost.com/hongkong/category/5-%e9%8c%a2%e8%b2%a1%e4%ba%8b",
    "https://www.bastillepost.com/hongkong/category/138491-%e5%9c%b0%e7%94%a2",
]


class BastillepostScraper(BaseSimpleScraper):
    """Bastille Post 香港财经/地产爬虫"""

    def __init__(self, bq_client):
        super().__init__("bastillepost", bq_client)

    def _get_detail(self, link: str) -> str:
        self.util.info(f"link: {link}")
        try:
            resp = _get(quote(link, safe="/:"), headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            node = soup.find(class_="article-body")
            if not node:
                return ""
            for el in node.select(".ad-container"):
                el.decompose()
            return str(node).strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Bastille Post...")
            new_articles = []

            for list_url in LIST_URLS:
                if getattr(self, "_timed_out", False):
                    break
                try:
                    resp = _get(quote(list_url, safe="/:"), headers=HEADERS, timeout=15)
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "lxml")
                    items = soup.select(".bppost-list > .bppost-item")[:4]
                    for node in items:
                        if getattr(self, "_timed_out", False):
                            break
                        href = node.get("href")
                        if not href:
                            a = node.select_one("a[href]")
                            href = a.get("href") if a else None
                        title_el = node.select_one(".bppost-title")
                        if not href or not title_el:
                            continue
                        link = BASE_URL + href.strip() if href.startswith("/") else href.strip()
                        title = title_el.get_text().strip()
                        if not title or self.is_link_exists(link):
                            continue
                        description = self._get_detail(link)
                        if description:
                            new_articles.append({
                                "title": title,
                                "description": description,
                                "link": link,
                                "author": "",
                                "pub_date": self.util.current_time_string(),
                                "kind": 2,
                                "language": "zh-HK",
                                "source_name": "巴士的报",
                            })
                except Exception as e:
                    self.util.error(f"列表请求失败 {list_url}: {e}")

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Bastille Post")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"Bastille Post 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
