# -*- coding: UTF-8 -*-
"""InfoQ 爬虫 — POST getList + getDetail/content_url 详情"""
import sys
import os
import json
from datetime import datetime

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://www.infoq.cn",
    "Referer": "https://www.infoq.cn/topic/%20industrynews",
}
LIST_API = "https://www.infoq.cn/public/v1/article/getList"
DETAIL_API = "https://www.infoq.cn/public/v1/article/getDetail"


def _build_body_from_content(paragraphs: list) -> str:
    """将 content JSON 转为 HTML"""
    html = []
    for p in paragraphs or []:
        ptype = p.get("type")
        if ptype == "paragraph":
            text = ""
            for c in p.get("content") or []:
                if c.get("type") == "text" and c.get("text"):
                    text += c.get("text", "")
            if text:
                html.append(f"<p>{text}</p>")
        elif ptype == "heading":
            for c in p.get("content") or []:
                if c.get("type") == "text" and c.get("text"):
                    html.append(f"<h2>{c['text']}</h2>")
                    break
        elif ptype == "image" and p.get("attrs", {}).get("src"):
            html.append(f"<p><img src=\"{p['attrs']['src']}\"/></p>")
    return "<div>" + "".join(html) + "</div>" if html else ""


class InfoqScraper(BaseSimpleScraper):
    """InfoQ 爬虫"""

    def __init__(self, bq_client):
        super().__init__("infoq", bq_client)

    def _get_detail(self, uuid: str) -> str:
        self.util.info(f"id: {uuid}")
        try:
            resp = _post(DETAIL_API, headers=HEADERS, json={"uuid": uuid}, timeout=12)
            if resp.status_code != 200:
                return ""
            data = resp.json()
            content_url = (data.get("data") or {}).get("content_url")
            if not content_url:
                return ""
            r2 = _get(content_url, headers=HEADERS, timeout=12)
            if r2.status_code != 200:
                return ""
            body = r2.json()
            return _build_body_from_content(body.get("content"))
        except Exception as e:
            self.util.error(f"获取详情失败 {uuid}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 InfoQ...")
            new_articles = []

            payload = {"type": 1, "ptype": 0, "size": 5, "id": 11}
            resp = _post(LIST_API, headers=HEADERS, json=payload, timeout=15)
            if resp.status_code != 200:
                self.util.error("列表请求失败")
                return self.get_stats()
            posts = (resp.json().get("data")) or []

            for post in posts:
                if getattr(self, "_timed_out", False):
                    break
                uuid = post.get("uuid")
                title = (post.get("article_title") or "").strip()
                _type = "news" if post.get("sub_type") == 4 else "article"
                link = f"https://www.infoq.cn/{_type}/{uuid}"
                if self.is_link_exists(link) or not title:
                    continue
                pub_ts = post.get("publish_time")
                try:
                    pub_date = datetime.fromtimestamp(pub_ts / 1000.0).strftime("%Y-%m-%d %H:%M:%S") if pub_ts else self.util.current_time_string()
                except (TypeError, ValueError):
                    pub_date = self.util.current_time_string()
                description = self._get_detail(uuid)
                if description:
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": "",
                        "pub_date": pub_date,
                        "kind": 1,
                        "language": "zh-CN",
                        "source_name": "InfoQ",
                    })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 InfoQ")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"InfoQ 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
