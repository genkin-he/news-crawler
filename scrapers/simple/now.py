# -*- coding: UTF-8 -*-
"""NOW 新闻 — API getNewsListv2 列表，正文 .newsLeading；不传 proxy"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://news.now.com/home/finance",
}
API_URLS = [
    "https://newsapi1.now.com/pccw-news-api/api/getNewsListv2?category=121&pageSize=20&pageNo=1",
    "https://newsapi1.now.com/pccw-news-api/api/getNewsListv2?category=502&pageSize=20&pageNo=1",
]


class NowScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("now", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 NOW...")
            new_articles = []
            for api_url in API_URLS:
                if getattr(self, "_timed_out", False):
                    break
                resp = _get(api_url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    continue
                items = resp.json() or []
                for item in items[:5]:
                    if getattr(self, "_timed_out", False):
                        break
                    nid = item.get("newsId")
                    title = (item.get("title") or "").strip()
                    link = f"https://news.now.com/home/technology/player?newsId={nid}" if nid else ""
                    if not link or not title or self.is_link_exists(link):
                        if link and self.is_link_exists(link):
                            break
                        continue
                    desc = ""
                    try:
                        r2 = _get(link, headers=HEADERS, timeout=10)
                        if r2.status_code == 200:
                            soup = BeautifulSoup(r2.text, "lxml")
                            lead = soup.select_one(".newsLeading")
                            if lead:
                                for el in lead.select(".imagesCollection"):
                                    el.decompose()
                                desc = str(lead).strip()
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
                        "source_name": "now 新闻",
                    })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"NOW 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
