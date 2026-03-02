# -*- coding: UTF-8 -*-
"""Market Pulse 爬虫 — requests + BeautifulSoup"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "zh-CN,zh;q=0.9",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
}
LIST_URLS = [
    "https://www.marketpulse.com/news/ai/",
    "https://www.marketpulse.com/markets/crypto/",
    "https://www.marketpulse.com/markets/stocks/",
    "https://www.marketpulse.com/markets/daily-market-wraps/",
]


class MarketpulseScraper(BaseSimpleScraper):
    """Market Pulse 爬虫"""

    def __init__(self, bq_client):
        super().__init__("marketpulse", bq_client)

    def _get_detail(self, link: str) -> str:
        try:
            resp = _get(link, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            node = soup.select_one(".post-body")
            if not node:
                return ""
            for el in node.select("link, script, style, .anchor-offset, .block-post_content_disclaimer"):
                el.decompose()
            return str(node).strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Market Pulse...")
            all_items = []
            for url in LIST_URLS:
                if getattr(self, "_timed_out", False):
                    break
                resp = _get(url, headers=HEADERS, timeout=12)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "lxml")
                for node in soup.select("a.item-title")[:3]:
                    link = (node.get("href") or "").strip()
                    title = node.get_text().strip()
                    if link and title:
                        all_items.append({"link": link, "title": title})

            new_articles = []
            for item in all_items:
                if getattr(self, "_timed_out", False):
                    break
                link = item["link"].strip()
                title = item["title"].strip()
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
                        "source_name": "Market Pulse",
                    })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles[:10])
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Market Pulse")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"Market Pulse 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
