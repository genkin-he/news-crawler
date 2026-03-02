# -*- coding: UTF-8 -*-
"""Stock Titan — RSS 列表，正文 .article"""
import sys
import os
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/142.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
RSS_URL = "https://www.stocktitan.net/rss"


class StocktitanScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("stocktitan", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Stock Titan...")
            new_articles = []
            resp = _get(RSS_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            resp.encoding = "utf-8"
            root = ET.fromstring(resp.text)
            items = []
            for item in root.findall(".//item"):
                if len(items) >= 5:
                    break
                title_el = item.find("title")
                link_el = item.find("link")
                pub_el = item.find("pubDate")
                if title_el is not None and link_el is not None and (title_el.text or "").strip() and (link_el.text or "").strip():
                    items.append({
                        "title": (title_el.text or "").strip(),
                        "link": (link_el.text or "").strip(),
                        "pub_date": (pub_el.text or "").strip() if pub_el is not None and pub_el.text else "",
                    })
            for it in items:
                if getattr(self, "_timed_out", False):
                    break
                link = it["link"]
                title = it["title"]
                if self.is_link_exists(link):
                    break
                desc = ""
                try:
                    r2 = _get(link, headers=HEADERS, timeout=10)
                    if r2.status_code == 200 and "Access Restricted" not in (r2.text or ""):
                        r2.encoding = "utf-8"
                        s2 = BeautifulSoup(r2.text, "lxml")
                        art = s2.select(".article")
                        if art:
                            soup = art[0]
                            for el in soup.select(".article-rhea-tools,.share-social-group,.adthrive-ad,#faq-container,script,#PURL,.article-title,time"):
                                el.decompose()
                            desc = str(soup).replace("\n", "").replace("\r", "")
                except Exception:
                    pass
                if not desc:
                    desc = title
                pub_date = it["pub_date"] or self.util.current_time_string()
                new_articles.append({
                    "title": title,
                    "description": desc or title,
                    "link": link,
                    "author": "stocktitan",
                    "pub_date": pub_date,
                    "kind": 1,
                    "language": "en",
                    "source_name": "StockTitan",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"Stock Titan 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
