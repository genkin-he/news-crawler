# -*- coding: UTF-8 -*-
"""Investors.com — RSS 列表 + 详情 .post-content"""
import sys
import os
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/127.0.0.0 Safari/537.36", "accept": "text/html,application/xhtml+xml,application/rss+xml,*/*;q=0.8"}
FEED_URL = "https://www.investors.com/tag/all-news-and-stock-ideas/feed/"


class InvestorsScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("investors", bq_client)

    def _parse_rss(self, xml_text: str) -> list:
        try:
            root = ET.fromstring(xml_text)
            out = []
            for item in root.findall(".//item"):
                t = item.find("title")
                l = item.find("link")
                if t is not None and l is not None and (t.text or "").strip() and (l.text or "").strip():
                    out.append({"title": (t.text or "").strip(), "link": (l.text or "").strip()})
            return out
        except Exception:
            return []

    def _get_detail(self, link: str) -> str:
        self.util.info(f"link: {link}")
        try:
            r = _get(link, headers=HEADERS, timeout=12)
            if r.status_code != 200:
                return ""
            soup = BeautifulSoup(r.text, "lxml")
            node = soup.select_one("div.post-content")
            if not node:
                return ""
            for el in node.select(".video-player-container, script, .adunit, .subscribe-widget"):
                el.decompose()
            return str(node).strip()
        except Exception as e:
            self.util.error(f"detail {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Investors.com...")
            new_articles = []
            resp = _get(FEED_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            items = self._parse_rss(resp.text)[:3]
            for item in items:
                if getattr(self, "_timed_out", False):
                    break
                link = item["link"]
                if self.is_link_exists(link):
                    continue
                title = item["title"]
                desc = self._get_detail(link)
                if desc:
                    new_articles.append({"title": title, "description": desc, "link": link, "author": "", "pub_date": self.util.current_time_string(), "kind": 1, "language": "en-US", "source_name": "Investors"})
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"Investors 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
