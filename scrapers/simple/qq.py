# -*- coding: UTF-8 -*-
"""QQ 财经 — API 列表 + 详情正文"""
import sys
import os
import json

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9",
    "content-type": "application/json;charset=UTF-8",
    "Referer": "https://news.qq.com/",
}
API_URL = "https://i.news.qq.com/web_feed/getPCList"
REQUEST_BODY = {
    "base_req": {"from": "pc"},
    "forward": "1",
    "qimei36": "0_PYwE5ijzdmaCM",
    "device_id": "0_PYwE5ijzdmaCM",
    "flush_num": 1,
    "channel_id": "news_news_finance",
    "item_count": 12,
    "is_local_chlid": "0",
}
CONTENT_SELECTORS = [".rich_media_content", ".article-content-wrap", "#article-content"]


class QqScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("qq", bq_client)

    def _get_detail(self, link: str) -> str:
        try:
            resp = _get(link, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            for sel in CONTENT_SELECTORS:
                body = soup.select_one(sel)
                if body:
                    for el in body.select("style, script"):
                        el.decompose()
                    wrap = body.select_one(".comps-contentify-wrap")
                    if wrap:
                        qnt = wrap.select(".qnt-p")
                        if qnt:
                            last = qnt[-1]
                            if last.find_all("img") and len(last.contents) == len(last.find_all("img")):
                                last.decompose()
                    return str(body).strip()
            return ""
        except Exception as e:
            self.util.error(f"get_detail {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 QQ 财经...")
            new_articles = []
            resp = _post(API_URL, headers=HEADERS, data=json.dumps(REQUEST_BODY), timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            data = resp.json()
            posts = data.get("data") or []
            for post in posts[:5]:
                if getattr(self, "_timed_out", False):
                    break
                link_info = post.get("link_info") or {}
                link = (link_info.get("url") or "").strip()
                if not link or post.get("articletype") != "0":
                    continue
                pub_date = post.get("publish_time") or self.util.current_time_string()
                if self.is_link_exists(link):
                    continue
                title = (post.get("title") or "").strip()
                if not title:
                    continue
                description = self._get_detail(link)
                if description:
                    media = post.get("media_info") or {}
                    medal = media.get("medal_info") or {}
                    author = (medal.get("medal_name") or "").strip()
                    pic_info = post.get("pic_info") or {}
                    big_img = (pic_info.get("big_img") or [""])[0]
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": author,
                        "pub_date": pub_date,
                        "kind": 1,
                        "language": "zh-CN",
                        "source_name": "腾讯新闻-财经",
                    })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles[:15])
        except Exception as e:
            self.util.error(f"QQ 财经 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
