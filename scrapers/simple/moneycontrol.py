# -*- coding: UTF-8 -*-
"""MoneyControl — 列表 + 详情正文"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "zh-CN,zh;q=0.9",
}
LIST_URL = "https://www.moneycontrol.com/news/business/markets/"


class MoneycontrolScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("moneycontrol", bq_client)

    def _get_detail(self, link: str) -> str:
        if "videos" in link:
            return ""
        try:
            resp = _get(link, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                return ""
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "lxml")
            content = soup.select(".content_wrapper")
            if not content:
                sel = soup.select(".disBdy")
                if not sel:
                    return ""
                return str(sel[0]).strip()
            body = content[0]
            for el in body.select("[class*=-ad], .related_stories_left_block, script, style, .social_icons_list"):
                el.decompose()
            return str(body).strip()
        except Exception as e:
            self.util.error(f"get_detail {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 MoneyControl...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "lxml")
            nodes = soup.select("#cagetory h2 > a")
            for node in nodes[:5]:
                if getattr(self, "_timed_out", False):
                    break
                link = (node.get("href") or "").strip()
                title = (node.get_text() or "").strip()
                if not link or not title or self.is_link_exists(link):
                    continue
                description = self._get_detail(link)
                if description:
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": "MoneyControl",
                        "pub_date": self.util.current_time_string(),
                        "kind": 1,
                        "language": "en",
                        "source_name": "moneycontrol",
                    })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"MoneyControl 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
