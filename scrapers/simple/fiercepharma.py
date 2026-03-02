# -*- coding: UTF-8 -*-
"""Fierce Pharma 爬虫 — requests + BeautifulSoup，支持 curl_cffi"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
}
BASE_URL = "https://www.fiercepharma.com"
LIST_URL = "https://www.fiercepharma.com/marketing"


class FiercepharmaScraper(BaseSimpleScraper):
    """Fierce Pharma 爬虫"""

    def __init__(self, bq_client):
        super().__init__("fiercepharma", bq_client)

    def _get_detail(self, link: str) -> str:
        self.util.info(f"link: {link}")
        try:
            resp = _get(link, headers=HEADERS, timeout=18)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            node = soup.find(id="article-body-row")
            if not node:
                return ""
            for el in node.select(".ad"):
                el.decompose()
            return str(node).strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Fierce Pharma...")
            new_articles = []

            try:
                resp = _get(LIST_URL, headers=HEADERS, timeout=22)
            except Exception as e:
                self.util.error(f"Fierce Pharma 列表请求失败: {e}")
                self.stats["errors"] += 1
                return self.get_stats()
            if resp.status_code != 200:
                self.util.error(f"Fierce Pharma 列表请求失败: HTTP {resp.status_code}")
                self.stats["errors"] += 1
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            top = soup.select(".content-wrapper .title a")
            list_items = soup.select("article .element-title a")
            items = (top + list_items)[:7]

            count = 0
            for title_el in items:
                if getattr(self, "_timed_out", False) or count >= 3:
                    break
                href = (title_el.get("href") or "").strip()
                link = BASE_URL + href if href.startswith("/") else href
                title = title_el.get_text().strip()
                if not link or not title or self.is_link_exists(link):
                    continue
                description = self._get_detail(link)
                if description:
                    count += 1
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": "",
                        "pub_date": self.util.current_time_string(),
                        "kind": 1,
                        "language": "en",
                        "source_name": "Fiercepharma",
                    })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Fierce Pharma")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"Fierce Pharma 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
