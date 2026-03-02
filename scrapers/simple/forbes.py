# -*- coding: UTF-8 -*-
"""Forbes 爬虫 — requests + BeautifulSoup"""
import sys
import os
import time

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "zh-CN,zh;q=0.9",
    "referer": "https://www.forbes.com/money/",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
}
LIST_URL = "https://www.forbes.com/money/?sh=68a28149c19a"


class ForbesScraper(BaseSimpleScraper):
    """Forbes 爬虫"""

    def __init__(self, bq_client):
        super().__init__("forbes", bq_client)

    def _get_detail(self, link: str) -> str:
        self.util.info(f"link: {link}")
        time.sleep(1)
        try:
            resp = _get(link, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            node = soup.select_one(".current-page .article-body")
            if not node:
                return ""
            for el in node.select("figure, div"):
                el.decompose()
            return str(node).strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Forbes...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                self.util.error("列表请求失败")
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            all_items = []
            for item in soup.select("a.zEzPL6aA"):
                link = (item.get("href") or "").strip()
                title = item.get_text().strip()
                if link and title:
                    all_items.append({"link": link, "title": title})
            for item in soup.select("h3.HNChVRGc a"):
                link = (item.get("href") or "").strip()
                title = item.get_text().strip()
                if link and title:
                    all_items.append({"link": link, "title": title})

            data_index = 0
            for item in all_items:
                if getattr(self, "_timed_out", False) or data_index > 4:
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
                        "source_name": "Forbes",
                    })
                    data_index += 1

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Forbes")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"Forbes 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
