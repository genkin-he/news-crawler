# -*- coding: UTF-8 -*-
"""HK01 爬虫 — API 列表 + 详情 article#article-content-section"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "accept": "application/json",
    "accept-language": "zh-CN,zh;q=0.9",
}
LIST_API = "https://web-data.api.hk01.com/v2/feed/category/396?limit=12&bucketId=00000"


class Hk01Scraper(BaseSimpleScraper):
    """HK01 财经爬虫"""

    def __init__(self, bq_client):
        super().__init__("hk01", bq_client)

    def _get_detail(self, link: str) -> str:
        self.util.info(f"link: {link}")
        try:
            resp = _get(link, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            article = soup.select_one("article#article-content-section")
            if not article:
                return ""
            parts = [str(p) for p in article.find_all("p")]
            return "\n".join(parts)
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 HK01...")
            new_articles = []

            resp = _get(LIST_API, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                self.util.error("API 请求失败")
                return self.get_stats()
            data = resp.json()
            items = data.get("items") or []

            for item in items:
                if getattr(self, "_timed_out", False):
                    break
                d = item.get("data") or {}
                link = (d.get("publishUrl") or "").strip()
                if not link or self.is_link_exists(link):
                    continue
                title = (d.get("title") or "").strip()
                if not title:
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
                        "language": "zh-HK",
                        "source_name": "香港01",
                    })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 HK01")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"HK01 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
