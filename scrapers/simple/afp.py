# -*- coding: UTF-8 -*-
"""AFP 爬虫 — MSN API 列表 + 详情 JSON，可部署到 Cloud Functions"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9",
    "origin": "https://www.msn.com",
    "referer": "https://www.msn.com/",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
}
LIST_URL = "https://assets.msn.com/service/news/feed/pages/fullchannelpage?ProviderId=vid-3kv7h73mtcdhywg28d4f9ihgi4xcniq2ubb83iikdu3qwmbd73pa&activityId=690c608f-d29a-43bf-b4e1-222920da80b2&apikey=0QfOX3Vn51YCzitbLaRkTTBadtWpgTN8NZLW0C1SEM&cm=zh-hk&it=web&memory=8&scn=ANON&timeOut=2000&user=m-3FCB06CABFAB62603EFD10E6BEAA63E2"
DETAIL_BASE = "https://assets.msn.com/content/view/v2/Detail/zh-hk/"


class AfpScraper(BaseSimpleScraper):
    """AFP 新闻爬虫（MSN API）"""

    def __init__(self, bq_client):
        super().__init__("afp", bq_client)
        self._fetched_ids = set()

    def _get_detail(self, article_id: str) -> str:
        if article_id in self._fetched_ids:
            return ""
        self.util.info(f"article_id: {article_id}")
        self._fetched_ids.add(article_id)
        try:
            resp = _get(DETAIL_BASE + article_id, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                return ""
            data = resp.json()
            body = data.get("body", "")
            if not body:
                return ""
            soup = BeautifulSoup(body, "lxml")
            for el in soup.select("img"):
                el.decompose()
            if soup.body:
                return soup.body.decode_contents().strip()
            if soup.html and soup.html.body:
                return soup.html.body.decode_contents().strip()
            s = str(soup).strip()
            for tag in ("<html>", "</html>", "<body>", "</body>"):
                s = s.replace(tag, "")
            return s.strip()
        except Exception as e:
            self.util.error(f"详情请求异常 {article_id}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 法新社...")
            self._fetched_ids = set()
            new_articles = []
            count = 0

            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                self.util.error(f"列表请求失败: {resp.status_code}")
                return self.get_stats()
            data = resp.json()
            all_items = []
            for section in data.get("sections", []):
                for card in section.get("cards", []):
                    if card.get("type") != "ProviderFeed":
                        continue
                    for sub in card.get("subCards", []):
                        cid = sub.get("id", "").strip()
                        title = (sub.get("title") or "").strip()
                        url = (sub.get("url") or "").strip()
                        if cid and title and url:
                            all_items.append({"id": cid, "title": title, "url": url})

            for item in all_items[:6]:
                if getattr(self, "_timed_out", False) or count >= 5:
                    break
                link = item["url"]
                if self.is_link_exists(link):
                    self.util.info(f"exists link: {link}")
                    continue
                title = item["title"]
                description = self._get_detail(item["id"])
                if not description:
                    continue
                count += 1
                new_articles.append({
                    "title": title,
                    "description": description,
                    "link": link,
                    "author": "",
                    "pub_date": self.util.current_time_string(),
                    "kind": 1,
                    "language": "zh-HK",
                    "source_name": "法新社",
                })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 法新社")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"法新社 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
