# -*- coding: UTF-8 -*-
"""Yicai Global 爬虫 — requests + API/BeautifulSoup"""
import sys
import os
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "zh-CN,zh;q=0.9",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
}
BASE_URL = "https://www.yicaiglobal.com"
API_URL = "https://www.yicaiglobal.com/api/getNewsList"
CATEGORY_IDS = [3, 4, 5]


class YicaiglobalScraper(BaseSimpleScraper):
    """Yicai Global 爬虫"""

    def __init__(self, bq_client):
        super().__init__("yicaiglobal", bq_client)

    def _get_detail(self, link: str) -> str:
        try:
            resp = _get(link, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            node = soup.select_one("#news-body")
            if not node:
                return ""
            for el in node.select("script, style, iframe, noscript"):
                el.decompose()
            return str(node).strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Yicai Global...")
            new_articles = []
            for category_id in CATEGORY_IDS:
                if getattr(self, "_timed_out", False):
                    break
                try:
                    resp = _get(
                        API_URL,
                        headers=HEADERS,
                        params={"type": "", "id": category_id, "pagesize": 10, "page": 1},
                        timeout=12,
                    )
                    if resp.status_code != 200:
                        continue
                    result = resp.json()
                    news_list = result if isinstance(result, list) else result.get("data", [])
                    count = 0
                    for news_item in news_list:
                        if getattr(self, "_timed_out", False) or count >= 2:
                            break
                        title = (news_item.get("NewsTitle") or "").strip()
                        url = (news_item.get("NewsUrl") or "").strip()
                        if not title or not url:
                            continue
                        full_url = urljoin(BASE_URL, url)
                        if self.is_link_exists(full_url):
                            continue
                        description = self._get_detail(full_url)
                        if description:
                            new_articles.append({
                                "title": title,
                                "description": description,
                                "link": full_url,
                                "author": "",
                                "pub_date": self.util.current_time_string(),
                                "kind": 1,
                                "language": "en",
                                "source_name": "Yicai",
                            })
                            count += 1
                except Exception as e:
                    self.util.error(f"Category {category_id}: {e}")

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles[:20])
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Yicai Global")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"Yicai Global 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
