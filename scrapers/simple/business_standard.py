# -*- coding: UTF-8 -*-
"""Business Standard 爬虫 — 编码 API 列表 + 详情页 #parent_top_div，支持 curl_cffi"""
import sys
import os
import json
from datetime import datetime

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get

ENCODING_CHARS = "95867qrstuvwxyzabcdefghijklmnop01234JKLMNOPQRSTUVWXYZABCDEFGHI"


def _encode_list_params(params: dict) -> str:
    if len(ENCODING_CHARS) < 62:
        raise ValueError("编码字符集必须至少包含 62 个唯一字符")
    json_str = json.dumps(params, separators=(",", ":"))
    # 构建: DDLL{json}bs255T
    day = str(datetime.now().day).zfill(2)
    length = str(len(json_str)).zfill(2)
    full = f"{day}{length}{json_str}bs255T"
    encoded = ""
    for char in full:
        code = ord(char)
        encoded += ENCODING_CHARS[code // 62] + ENCODING_CHARS[code % 62]
    return encoded


HEADERS = {
    "accept": "application/json",
    "accept-language": "zh-CN,zh;q=0.9",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "origin": "https://www.business-standard.com",
    "referer": "https://www.business-standard.com/",
}
BASE_URL = "https://www.business-standard.com"
API_BASE = "https://apibs.business-standard.com/article/latest-news"


class BusinessStandardScraper(BaseSimpleScraper):
    """Business Standard 爬虫"""

    def __init__(self, bq_client):
        super().__init__("business_standard", bq_client)

    def _get_detail(self, link: str) -> str:
        self.util.info(f"link: {link}")
        try:
            resp = _get(link, headers=HEADERS, timeout=18)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            parent = soup.select("#parent_top_div")
            if not parent:
                return ""
            node = parent[0]
            for el in node.select(".storyadsprg, .recommendsection, .mb-20 > style"):
                el.decompose()
            return str(node).strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Business Standard...")
            new_articles = []

            encoded = _encode_list_params({"page": 0, "limit": 10, "offset": 0})
            url = f"{API_BASE}?listData={encoded}"
            try:
                resp = _get(url, headers=HEADERS, timeout=20)
            except Exception as e:
                self.util.error(f"Business Standard API 请求失败: {e}")
                self.stats["errors"] += 1
                return self.get_stats()
            if resp.status_code != 200:
                self.util.error(f"Business Standard API 请求失败: HTTP {resp.status_code}")
                self.stats["errors"] += 1
                return self.get_stats()
            try:
                result = resp.json().get("data") or []
            except (ValueError, TypeError) as e:
                self.util.error(f"Business Standard API JSON 解析失败: {e}")
                self.stats["errors"] += 1
                return self.get_stats()

            for item in result[:4]:
                if getattr(self, "_timed_out", False):
                    break
                article_url = (item.get("article_url") or "").strip()
                link = BASE_URL + article_url if article_url.startswith("/") else article_url
                if self.is_link_exists(link):
                    self.util.info(f"exists link: {link}")
                    break
                title = (item.get("heading1") or "").strip()
                if not title:
                    continue
                pub_date = item.get("published_date")
                if isinstance(pub_date, (int, float)):
                    try:
                        from datetime import datetime as dt
                        pub_date = dt.fromtimestamp(int(pub_date)).strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, TypeError):
                        pub_date = self.util.current_time_string()
                else:
                    pub_date = pub_date or self.util.current_time_string()
                description = self._get_detail(link)
                if description:
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": "",
                        "pub_date": pub_date,
                        "kind": 1,
                        "language": "en",
                        "source_name": "Business Standard",
                    })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Business Standard")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"Business Standard 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
