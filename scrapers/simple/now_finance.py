# -*- coding: UTF-8 -*-
"""NOW 财经 — newsList.php 列表，正文 .newsParagraphs"""
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
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
}
LIST_URL = "https://finance.now.com/news/newsList.php?type=world"


class NowFinanceScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("now_finance", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 NOW 财经...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            text = resp.text
            try:
                start, end = text.index("(") + 1, text.rindex(")")
                body = text[start:end]
                items = __import__("json").loads(body)
            except (ValueError, SyntaxError, __import__("json").JSONDecodeError):
                return self.get_stats()
            for item in (items or [])[:5]:
                if getattr(self, "_timed_out", False):
                    break
                aid = item.get("id")
                title = (item.get("title") or "").strip()
                link = f"https://finance.now.com/news/post.php?id={aid}" if aid else ""
                if not link or not title or self.is_link_exists(link):
                    if link and self.is_link_exists(link):
                        break
                    continue
                desc = ""
                try:
                    r2 = _get(link, headers=HEADERS, timeout=10)
                    if r2.status_code == 200:
                        soup = BeautifulSoup(r2.text, "lxml")
                        node = soup.select_one(".newsParagraphs")
                        if node:
                            for el in node.select(".ad"):
                                el.decompose()
                            desc = str(node).strip()
                except Exception:
                    pass
                if not desc:
                    desc = title
                new_articles.append({
                    "title": title,
                    "description": desc or title,
                    "link": link,
                    "author": "",
                    "pub_date": self.util.current_time_string(),
                    "kind": 1,
                    "language": "zh-HK",
                    "source_name": "now 财经",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"NOW 财经 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
