# -*- coding: UTF-8 -*-
"""on.cc 东网 — 列表 #breakingnewsContent .lastest .focus，正文 .breakingNewsContent"""
import re
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
LIST_URL = "https://hk.on.cc/hk/finance/index.html"
BASE_URL = "https://hk.on.cc"


class OnScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("on", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 on.cc...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            resp.encoding = getattr(resp, "apparent_encoding", None) or "utf-8"
            if resp.status_code != 200:
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            items = soup.select("#breakingnewsContent > .lastest > .focus")
            for node in items[:5]:
                if getattr(self, "_timed_out", False):
                    break
                a = node.select_one("h1 > a")
                if not a or not a.get("href"):
                    continue
                link = BASE_URL + a["href"].strip()
                if self.is_link_exists(link):
                    break
                title = (a.get_text() or "").strip()
                if not title:
                    continue
                desc = ""
                try:
                    r2 = _get(link, headers=HEADERS, timeout=10)
                    r2.encoding = getattr(r2, "apparent_encoding", None) or "utf-8"
                    if r2.status_code == 200:
                        s2 = BeautifulSoup(r2.text, "lxml")
                        content = s2.select_one(".breakingNewsContent")
                        if content:
                            for el in content.select("style,script,.outStreamVideoCTN,[class*='-player-']"):
                                el.decompose()
                            last_p = content.select_one(".paragraph:last-child")
                            if last_p:
                                last_p.decompose()
                            raw = str(content).strip()
                            desc = re.sub(r"[\r\n\t]+", " ", raw)
                            desc = re.sub(r" +", " ", desc).strip()
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
                    "source_name": "香港东方日报",
                })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"on.cc 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
