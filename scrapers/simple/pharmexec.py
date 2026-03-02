# -*- coding: UTF-8 -*-
"""Pharm Exec — RSS 列表，正文 #block-content"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
RSS_URL = "https://www.pharmexec.com/rss"


class PharmexecScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("pharmexec", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Pharm Exec...")
            new_articles = []
            resp = _get(RSS_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            soup = BeautifulSoup(resp.content, "xml")
            for item in soup.find_all("item")[:5]:
                if getattr(self, "_timed_out", False):
                    break
                link_el = item.find("link")
                title_el = item.find("title")
                pub_el = item.find("pubDate")
                if not link_el or not link_el.string:
                    continue
                link = link_el.string.strip().replace("onclive", "pharmexec")
                if self.is_link_exists(link):
                    break
                title = (title_el.string or "").strip() if title_el else ""
                if not title:
                    continue
                pub_date = self.util.current_time_string()
                if pub_el and pub_el.string:
                    try:
                        pub_date = self.util.parse_time(pub_el.string.strip(), "%a, %d %b %Y %H:%M:%S GMT")
                    except Exception:
                        pass
                desc = ""
                try:
                    r2 = _get(link, headers=HEADERS, timeout=10)
                    if r2.status_code == 200:
                        s2 = BeautifulSoup(r2.text, "lxml")
                        block = s2.select_one("#block-content")
                        if block:
                            for el in block.select("astro-island, article"):
                                el.decompose()
                            desc = str(block).strip()
                except Exception:
                    pass
                if not desc:
                    desc = title
                new_articles.append({
                    "title": title,
                    "description": desc or title,
                    "link": link,
                    "author": "",
                    "pub_date": pub_date,
                    "kind": 1,
                    "language": "en",
                    "source_name": "pharmexec",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"Pharm Exec 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
