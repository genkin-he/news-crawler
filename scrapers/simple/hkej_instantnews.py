# -*- coding: UTF-8 -*-
"""HKEJ 即时新闻爬虫 — 列表 + 详情 article-content"""
import sys
import os
import re

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "zh-CN,zh;q=0.9",
    "referer": "https://www.hkej.com/instantnews",
}
BASE_URL = "https://www2.hkej.com"
LIST_URL = "https://www2.hkej.com/instantnews"


class HkejInstantnewsScraper(BaseSimpleScraper):
    """HKEJ 即时新闻爬虫"""

    def __init__(self, bq_client):
        super().__init__("hkej_instantnews", bq_client)

    def _get_detail(self, link: str) -> str:
        self.util.info(f"link: {link}")
        try:
            resp = _get(link, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                return ""
            raw = resp.text
            if "<div id='article-content'>" not in raw or '<div id="hkej_sub_ex_article_nonsubscriber_ad_2014">' not in raw:
                return ""
            body = raw.split("<div id='article-content'>")[1].split('<div id="hkej_sub_ex_article_nonsubscriber_ad_2014">')[0]
            body = re.sub(r"(\t)\1+", "", body)
            body = re.sub(r"(\n)\1+", "\n", body)
            return body.lstrip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 HKEJ Instant News...")
            new_articles = []

            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                self.util.error("列表请求失败")
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            item1 = soup.select("h4.hkej_hl-news_topic_2014 a")
            item2 = soup.select("h3 a")
            items = (item1 + item2)[:8]

            for a in items:
                if getattr(self, "_timed_out", False):
                    break
                href = (a.get("href") or "").strip()
                link = BASE_URL + href if href.startswith("/") else href
                title = a.get_text().strip()
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
                        "language": "zh-HK",
                        "source_name": "信报",
                    })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 HKEJ Instant News")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"HKEJ Instant News 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
