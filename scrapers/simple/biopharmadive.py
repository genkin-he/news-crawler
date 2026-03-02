# -*- coding: UTF-8 -*-
"""BioPharma Dive 爬虫 — requests + BeautifulSoup，可部署到 Cloud Functions"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
}
BASE_URL = "https://www.biopharmadive.com/"


class BiopharmadiveScraper(BaseSimpleScraper):
    """BioPharma Dive 爬虫"""

    def __init__(self, bq_client):
        super().__init__("biopharmadive", bq_client)

    def _get_detail(self, link: str) -> str:
        self.util.info(f"link: {link}")
        try:
            resp = _get(link, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            node = soup.select_one(".article-body") or soup.select_one(".body")
            if not node:
                nodes = soup.select(".content__text")
                node = nodes[0] if nodes else None
            if not node:
                return ""
            for el in node.select(".hybrid-ad-wrapper"):
                el.decompose()
            return str(node).strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 BioPharma Dive...")
            new_articles = []

            resp = _get(BASE_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                self.util.error("列表请求失败")
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            items = soup.select(".feed__item")[:4]

            for item in items:
                if getattr(self, "_timed_out", False):
                    break
                title_links = item.select(".feed__title > a")
                if not title_links:
                    continue
                href = (title_links[0].get("href") or "").strip()
                link = "https://www.biopharmadive.com" + href if href.startswith("/") else href
                title = title_links[0].get_text().strip()
                if not link or not title or self.is_link_exists(link):
                    if link and self.is_link_exists(link):
                        self.util.info(f"exists link: {link}")
                        break
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
                        "source_name": "biopharmadive",
                    })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 BioPharma Dive")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"BioPharma Dive 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
