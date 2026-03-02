# -*- coding: UTF-8 -*-
"""Business Times News (opinion/companies-markets) 爬虫 — requests + BeautifulSoup"""
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
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
}
BASE_URL = "https://www.businesstimes.com.sg"
LIST_URLS = [
    "https://www.businesstimes.com.sg/opinion-features?ref=listing-menubar",
    "https://www.businesstimes.com.sg/breaking-news?filter=companies-markets&ref=listing-menubar",
]


class BusinesstimesNewsScraper(BaseSimpleScraper):
    """Business Times News 多栏目爬虫"""

    def __init__(self, bq_client):
        super().__init__("businesstimes_news", bq_client)

    def _get_detail(self, link: str) -> str:
        self.util.info(f"link: {link}")
        try:
            resp = _get(link, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            node = soup.select_one("div.mx-auto.my-4.font-lucida.text-xl")
            if not node:
                return ""
            for el in node.select("style, script"):
                el.decompose()
            for el in node.select('div[data-testid="article-read-more"],div[data-testid="article-purchase-link-component"],div[data-testid="article-purchase-link-version-2-component"]'):
                el.decompose()
            return str(node).strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Business Times News...")
            new_articles = []

            for page_url in LIST_URLS:
                if getattr(self, "_timed_out", False):
                    break
                try:
                    resp = _get(page_url, headers=HEADERS, timeout=15)
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "lxml")
                    for a in soup.select("h3 a")[:3]:
                        if getattr(self, "_timed_out", False):
                            break
                        href = a.get("href") or ""
                        link = href if href.startswith("http") else BASE_URL + href.strip()
                        title = a.get_text().strip()
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
                                "kind": 1,
                                "language": "en",
                                "source_name": "Businesstimes News",
                            })
                except Exception as e:
                    self.util.error(f"列表请求失败 {page_url}: {e}")

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Business Times News")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"Business Times News 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
