# -*- coding: UTF-8 -*-
"""CWW 通信世界网 — 列表 + 详情正文"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "zh-CN,zh;q=0.9",
}
LIST_URL = "https://www.cww.net.cn/subjects/nav/rollList/3009"


class CwwScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("cww", bq_client)

    def _get_detail(self, link: str) -> str:
        try:
            resp = _get(link, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            content = soup.select_one("#divContentDiv")
            if not content:
                return ""
            for el in content.select("script,style"):
                el.decompose()
            return str(content).strip()
        except Exception as e:
            self.util.error(f"get_detail {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 CWW...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            nodes = soup.select("#newsList li")
            for node in nodes[:5]:
                if getattr(self, "_timed_out", False):
                    break
                a_list = node.select("a")
                slh = node.select(".slh")
                if not a_list or not slh:
                    continue
                link = (a_list[0].get("href") or "").strip()
                title = (slh[0].get_text() or "").strip()
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
                        "language": "zh-CN",
                        "source_name": "CWW",
                    })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"CWW 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
