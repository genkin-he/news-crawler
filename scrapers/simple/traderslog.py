# -*- coding: UTF-8 -*-
"""Traders Log 爬虫 — requests + RSS/BeautifulSoup"""
import sys
import os
import time

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "zh-CN,zh;q=0.9",
    "referer": "https://www.traderslog.com/feed",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
}
FEED_URLS = [
    "https://www.traderslog.com/feed",
    "https://www.traderslog.com/category/analysis/feed",
]


class TraderslogScraper(BaseSimpleScraper):
    """Traders Log 爬虫"""

    def __init__(self, bq_client):
        super().__init__("traderslog", bq_client)

    def _get_detail(self, link: str) -> str:
        self.util.info(f"link: {link}")
        time.sleep(1)
        try:
            resp = _get(link, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            node = soup.select_one(".entry-content")
            if not node:
                return ""
            for el in node.select("form, script, style, iframe, noscript"):
                el.decompose()
            return str(node).strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Traders Log...")
            new_articles = []
            for feed_url in FEED_URLS:
                if getattr(self, "_timed_out", False):
                    break
                try:
                    resp = _get(feed_url, headers=HEADERS, timeout=12)
                    if resp.status_code != 200:
                        continue
                    soup = BeautifulSoup(resp.text, "xml")
                    for item in soup.select("item")[:4]:
                        if getattr(self, "_timed_out", False):
                            break
                        title_el = item.select_one("title")
                        link_el = item.select_one("link")
                        if not title_el or not link_el:
                            continue
                        title = title_el.get_text().strip()
                        link = link_el.get_text().strip()
                        if not title or not link or self.is_link_exists(link):
                            continue
                        description = self._get_detail(link)
                        if title and link and description:
                            new_articles.append({
                                "title": title,
                                "description": description,
                                "link": link,
                                "author": "",
                                "pub_date": self.util.current_time_string(),
                                "kind": 1,
                                "language": "en",
                                "source_name": "traderslog",
                            })
                except Exception as e:
                    self.util.error(f"Feed {feed_url}: {e}")

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles[:20])
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Traders Log")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"Traders Log 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
