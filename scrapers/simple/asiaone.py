# -*- coding: UTF-8 -*-
"""AsiaOne 爬虫 — POST API 列表 + requests 详情，可部署到 Cloud Functions"""
import sys
import os
import json
import re

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "content-type": "application/json",
    "Referer": "https://www.asiaone.com/lite",
}
API_URL = "https://www.asiaone.com/_api/datacenter/summaries/search"
API_PAYLOAD = {"start": 0, "size": 10, "condition": {"category": ["money"]}}


class AsiaoneScraper(BaseSimpleScraper):
    """AsiaOne 财经爬虫"""

    def __init__(self, bq_client):
        super().__init__("asiaone", bq_client)

    def _get_detail(self, link: str) -> str:
        self.util.info(f"link: {link}")
        try:
            resp = _get(link, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            node = soup.select_one(".body")
            if not node:
                return ""
            for el in node.select("script,style,[class*=-ads],#aniBox"):
                el.decompose()
            pattern = re.compile(r"\[\[nid:\d+\]\]")
            for tag in node.find_all(string=pattern):
                tag.replace_with(re.sub(pattern, "", tag))
            return str(node).strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 AsiaOne...")
            new_articles = []

            resp = _post(API_URL, headers=HEADERS, json=API_PAYLOAD, timeout=15)
            if resp.status_code != 200:
                self.util.error("API 请求失败")
                return self.get_stats()
            data = resp.json()
            items = data.get("data") or []

            for item in items[:4]:
                if getattr(self, "_timed_out", False):
                    break
                link = item.get("url", "").strip()
                if not link:
                    continue
                if self.is_link_exists(link):
                    self.util.info(f"exists link: {link}")
                    break
                inner = item.get("data") or {}
                title = (inner.get("title") or "").strip()
                if not title:
                    continue
                description = self._get_detail(link)
                if not description:
                    continue
                new_articles.append({
                    "title": title,
                    "description": description,
                    "link": link,
                    "author": "",
                    "pub_date": self.util.current_time_string(),
                    "kind": 1,
                    "language": "en",
                    "source_name": "Asiaone",
                })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 AsiaOne")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"AsiaOne 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
