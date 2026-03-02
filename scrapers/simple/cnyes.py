# -*- coding: UTF-8 -*-
"""CnYes 财联社爬虫 — API 列表 + 详情 #article-container"""
import sys
import os
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://news.cnyes.com/",
}
API_URL = "https://api.cnyes.com/media/api/v1/newslist/all?page=1&limit=30"


class CnyesScraper(BaseSimpleScraper):
    """CnYes 财联社爬虫"""

    def __init__(self, bq_client):
        super().__init__("cnyes", bq_client)

    def _get_detail(self, link: str) -> str:
        self.util.info(f"link: {link}")
        try:
            resp = _get(link, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            node = soup.select_one("#article-container")
            if not node:
                return ""
            for el in node.select("script, style, [id*=-ad-]"):
                el.decompose()
            for img in node.find_all("img"):
                alt = img.get("alt", "")
                src = img.get("src", "")
                if "_next/image" in src:
                    try:
                        parsed = urlparse(src)
                        qs = parse_qs(parsed.query)
                        if "url" in qs:
                            src = qs["url"][0]
                    except Exception:
                        pass
                img.attrs.clear()
                if alt:
                    img["alt"] = alt
                if src:
                    img["src"] = src
            return str(node).strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 CnYes...")
            new_articles = []

            resp = _get(API_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                self.util.error("API 请求失败")
                return self.get_stats()
            data = resp.json()
            items = (data.get("items") or {}).get("data") or []

            for item in items[:6]:
                if getattr(self, "_timed_out", False):
                    break
                news_id = item.get("newsId")
                link = f"https://news.cnyes.com/news/id/{news_id}"
                if self.is_link_exists(link):
                    self.util.info(f"exists link: {link}")
                    continue
                title = (item.get("title") or "").strip()
                if not title:
                    continue
                pub_ts = item.get("publishAt")
                pub_date = self.util.convert_utc_to_local(pub_ts) if pub_ts else self.util.current_time_string()
                description = self._get_detail(link)
                if description:
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": "",
                        "pub_date": pub_date,
                        "kind": 1,
                        "language": "zh-HK",
                        "source_name": "钜亨网",
                    })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 CnYes")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"CnYes 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
