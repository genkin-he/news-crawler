# -*- coding: UTF-8 -*-
"""Nasdaq 新闻爬虫 — API 列表 + requests 详情，可部署到 Cloud Functions"""
import sys
import os
import json
import gzip

import urllib.request
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "accept-encoding": "gzip, deflate, br",
}
BASE_URL = "https://www.nasdaq.com"
API_URL = "https://www.nasdaq.com/api/news/topic/latestnews?offset=0&limit=10"


class NasdaqScraper(BaseSimpleScraper):
    """Nasdaq 新闻爬虫"""

    def __init__(self, bq_client):
        super().__init__("nasdaq", bq_client)
        self._current_links = []

    def _get_detail(self, link: str) -> str:
        if link in self._current_links:
            return ""
        self.util.info(f"link: {link}")
        self._current_links.append(link)
        try:
            req = urllib.request.Request(link, None, HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status != 200:
                    return ""
                if resp.headers.get("Content-Encoding") == "gzip":
                    body = gzip.GzipFile(fileobj=resp).read().decode("utf-8")
                else:
                    body = resp.read().decode("utf-8")
                soup = BeautifulSoup(body, "lxml")
                node = soup.select_one(".body__content")
                if not node:
                    return ""
                for el in node.select(".ads__inline, .body__disclaimerscript, .video__inline, .taboola-placeholder"):
                    el.decompose()
                return str(node).strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Nasdaq...")
            self._current_links = []
            new_articles = []

            req = urllib.request.Request(API_URL, None, HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status != 200:
                    self.util.error("API 请求失败")
                    return self.get_stats()
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                data = json.loads(raw.decode("utf-8"))
            rows = (data.get("data") or {}).get("rows") or []

            for post in rows[:5]:
                if getattr(self, "_timed_out", False):
                    break
                link = BASE_URL + (post.get("url") or "")
                if not link or link == BASE_URL:
                    continue
                if self.is_link_exists(link):
                    self.util.info(f"exists link: {link}")
                    continue
                title = (post.get("title") or "").strip()
                author = (post.get("publisher") or "").strip()
                if not title:
                    continue
                description = self._get_detail(link)
                if description:
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": author,
                        "pub_date": self.util.current_time_string(),
                        "kind": 1,
                        "language": "en",
                        "source_name": "nasdaq",
                    })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Nasdaq")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"Nasdaq 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
