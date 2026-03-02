# -*- coding: UTF-8 -*-
"""Insider Monkey 爬虫 — requests + BeautifulSoup"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "zh-CN,zh;q=0.9",
    "referer": "https://www.insidermonkey.com/blog/category/news/",
}
BASE_URL = "https://www.insidermonkey.com"
LIST_URL = "https://www.insidermonkey.com/blog/category/news/"


class InsidermonkeyScraper(BaseSimpleScraper):
    """Insider Monkey 爬虫"""

    def __init__(self, bq_client):
        super().__init__("insidermonkey", bq_client)

    def _get_detail(self, link: str) -> str:
        self.util.info(f"link: {link}")
        try:
            resp = _get(link, headers=HEADERS, timeout=12)
            resp.encoding = "utf-8"
            if resp.status_code != 200:
                return ""
            if "Access Restricted" in resp.text or "challenge-container" in resp.text:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            wrappers = soup.select(".entry-content, .post-content, .article-content, .content")
            if not wrappers:
                return ""
            node = wrappers[0]
            for el in node.select("script, style, .ad, .advertisement, .ads, .social-share, .related-posts"):
                el.decompose()
            return str(node).strip().replace("\n", "").replace("\r", "")
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Insider Monkey...")
            new_articles = []

            try:
                resp = _get(LIST_URL, headers=HEADERS, timeout=22)
            except Exception as e:
                self.util.error(f"Insider Monkey 列表请求失败: {e}")
                self.stats["errors"] += 1
                return self.get_stats()
            resp.encoding = "utf-8"
            if resp.status_code not in (200, 202):
                self.util.error(f"Insider Monkey 列表请求失败: HTTP {resp.status_code}")
                self.stats["errors"] += 1
                return self.get_stats()
            if "Access Restricted" in resp.text or "challenge-container" in resp.text:
                self.util.error("站点受 WAF 限制，跳过")
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            nodes = soup.select("h2 a, h3 a, .entry-title a, .post-title a, .article-title a")[:5]

            for node in nodes:
                if getattr(self, "_timed_out", False):
                    break
                href = (node.get("href") or "").strip()
                link = href if href.startswith("http") else BASE_URL + href
                title = node.get_text().strip().replace("\n", "")
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
                        "source_name": "insidermonkey",
                    })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Insider Monkey")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"Insider Monkey 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
