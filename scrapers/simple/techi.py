# -*- coding: UTF-8 -*-
"""Techi 爬虫 — requests + RSS/BeautifulSoup"""
import sys
import os
import xml.etree.ElementTree as ET
import time

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
RSS_URL = "https://www.techi.com/category/instruments/feed/"


def _parse_rss(xml_content):
    try:
        root = ET.fromstring(xml_content)
        items = []
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el = item.find("link")
            if title_el is not None and link_el is not None:
                title = (title_el.text or "").strip()
                link = (link_el.text or "").strip()
                if title and link:
                    items.append({"title": title, "link": link})
        return items
    except Exception:
        return []


class TechiScraper(BaseSimpleScraper):
    """Techi 爬虫"""

    def __init__(self, bq_client):
        super().__init__("techi", bq_client)

    def _get_detail(self, link: str) -> str:
        try:
            resp = _get(link, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            node = soup.select_one("div.post-content")
            if not node:
                return ""
            for el in node.select("script, style, iframe, noscript"):
                el.decompose()
            return str(node).strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Techi...")
            new_articles = []
            resp = _get(RSS_URL, headers=HEADERS, timeout=15, allow_redirects=True)
            if resp.status_code != 200:
                self.util.error("RSS 请求失败")
                return self.get_stats()
            items = _parse_rss(resp.text)
            data_index = 0
            for item in items:
                if getattr(self, "_timed_out", False) or data_index >= 5:
                    break
                link = item["link"]
                title = item["title"]
                if not title or self.is_link_exists(link):
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
                        "source_name": "TECHi",
                    })
                    data_index += 1
                    time.sleep(0.5)

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles[:10])
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Techi")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"Techi 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
