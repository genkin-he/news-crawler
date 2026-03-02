# -*- coding: UTF-8 -*-
"""Rolling Out 爬虫 — 列表页或 RSS 回退 + BeautifulSoup"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper

HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
}
LIST_URL = "https://rollingout.com/category/tech/"
RSS_URL = "https://rollingout.com/feed/"
REQUEST_TIMEOUT = 20

from scrapers.simple.http_client import get as _get


def _parse_rss_feed(soup: BeautifulSoup):
    """从 RSS 解析出 [(link, title), ...]。"""
    items = []
    for item in soup.select("item")[:10]:
        link_el = item.find("link")
        title_el = item.find("title")
        if link_el is None or title_el is None:
            continue
        link = (link_el.get_text() if hasattr(link_el, "get_text") else (link_el.text or "")).strip()
        title = (title_el.get_text() if hasattr(title_el, "get_text") else (title_el.text or "")).strip()
        if link and title:
            items.append((link, title))
    return items


class RollingoutScraper(BaseSimpleScraper):
    """Rolling Out 爬虫"""

    def __init__(self, bq_client):
        super().__init__("rollingout", bq_client)

    def _get_detail(self, link: str) -> str:
        try:
            resp = _get(link, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            node = soup.select_one("div.standard-markdown") or soup.select_one("div.elementor-widget-theme-post-content")
            if not node:
                return ""
            for el in node.select("script, style, iframe, noscript, div"):
                el.decompose()
            return str(node).strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Rolling Out...")
            new_articles = []
            entries = []  # [(link, title), ...]

            try:
                resp = _get(LIST_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "lxml")
                    nodes = soup.select("h3.elementor-post__title a")[:5]
                    for node in nodes:
                        link = (node.get("href") or "").strip()
                        title = (node.get_text() or "").strip()
                        if link and title:
                            entries.append((link, title))
                else:
                    self.util.error(f"列表请求失败: HTTP {resp.status_code}")
            except Exception as e:
                self.util.error(f"列表请求失败: {e}")

            if not entries:
                try:
                    resp = _get(RSS_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
                    if resp.status_code == 200:
                        if "<rss" in resp.text[:500] or "<item" in resp.text[:1000]:
                            feed_soup = BeautifulSoup(resp.text, "lxml-xml")
                        else:
                            feed_soup = BeautifulSoup(resp.text, "lxml")
                        entries = _parse_rss_feed(feed_soup)
                        if entries:
                            self.util.info("已从 RSS 获取列表")
                except Exception as e:
                    self.util.error(f"RSS 回退失败: {e}")

            if not entries:
                return self.get_stats()

            for link, title in entries[:5]:
                if getattr(self, "_timed_out", False):
                    break
                if self.is_link_exists(link):
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
                        "source_name": "Rolling Out",
                    })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Rolling Out")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"Rolling Out 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
