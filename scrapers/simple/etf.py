# -*- coding: UTF-8 -*-
"""ETF.com 爬虫 — requests + BeautifulSoup，支持 curl_cffi"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
}
LIST_URL = "https://www.etf.com/news"
BASE_URL = "https://www.etf.com"


class EtfScraper(BaseSimpleScraper):
    """ETF.com 爬虫"""

    def __init__(self, bq_client):
        super().__init__("etf", bq_client)

    def _get_detail(self, link: str) -> str:
        self.util.info(f"link: {link}")
        try:
            resp = _get(link, headers=HEADERS, timeout=18)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            bodies = soup.select(".etf_articles__body")
            if len(bodies) < 3:
                return ""
            node = bodies[2]
            for el in node.select(".caas-da"):
                el.decompose()
            return str(node).strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 ETF.com...")
            new_articles = []

            try:
                resp = _get(LIST_URL, headers=HEADERS, timeout=22)
            except Exception as e:
                self.util.error(f"ETF.com 列表请求失败: {e}")
                self.stats["errors"] += 1
                return self.get_stats()
            if resp.status_code != 200:
                self.util.error(f"ETF.com 列表请求失败: HTTP {resp.status_code}")
                self.stats["errors"] += 1
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            items = soup.select(".image-card")[:2]

            for node in items:
                if getattr(self, "_timed_out", False):
                    break
                title_links = node.select(".image-card__title > a")
                if not title_links:
                    continue
                href = (title_links[0].get("href") or "").strip()
                link = BASE_URL + href if href.startswith("/") else href
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
                        "source_name": "ETF.com",
                    })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 ETF.com")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"ETF.com 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
