# -*- coding: UTF-8 -*-
"""金吾财经香港 — POST API 列表，content 即正文

页面 https://sky.szfiu.com/info/hk 为 SPA，列表数据来自接口 pro-app-sky-api.szfiu.com/news/v1/list。
接口返回 body.list[]，每项含 id, title, content, pubDate；详情页链接为 /info/hk/details/{id}。
"""
import sys
import os

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

API_URL = "https://pro-app-sky-api.szfiu.com/news/v1/list"
BASE_URL = "https://sky.szfiu.com"

# 模拟从「金吾财讯」香港资讯页发起的 CORS 请求，降低被限流/超时概率
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": BASE_URL,
    "Referer": f"{BASE_URL}/info/hk",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site",
}


class JinwucjHkScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("jinwucj_hk", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 金吾财经香港...")
            new_articles = []
            resp = _post(API_URL, headers=HEADERS, json={"pageNum": 1, "pageSize": 10}, timeout=30)
            if resp.status_code != 200:
                self.util.error(f"金吾香港 API 状态码: {resp.status_code}")
                self.stats["errors"] += 1
                return self.get_stats()
            try:
                body = resp.json()
            except ValueError as e:
                self.util.error(f"金吾香港 API JSON 解析失败: {e}")
                self.stats["errors"] += 1
                return self.get_stats()
            posts = (body.get("body") or {}).get("list")
            if not isinstance(posts, list):
                posts = []
            for post in posts[:4]:
                if getattr(self, "_timed_out", False):
                    break
                id_ = post.get("id")
                if id_ is None:
                    continue
                link = f"{BASE_URL}/info/hk/details/{id_}"
                if self.is_link_exists(link):
                    break
                title = (post.get("title") or "").strip()
                desc = (post.get("content") or "").strip()
                if not title or not desc:
                    continue
                new_articles.append({"title": title, "description": desc, "link": link, "author": "", "pub_date": post.get("pubDate") or self.util.current_time_string(), "kind": 1, "language": "zh-CN", "source_name": "金吾资讯"})
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except requests.exceptions.Timeout as e:
            self.util.error(f"金吾财经香港 请求超时: {e}")
            self.stats["errors"] += 1
        except Exception as e:
            self.util.error(f"金吾财经香港 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
