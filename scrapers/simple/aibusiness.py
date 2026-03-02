# -*- coding: UTF-8 -*-
"""AI Business 爬虫 — requests + BeautifulSoup/JSON"""
import sys
import os
import time

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper

HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "zh-CN,zh;q=0.9",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
}
BASE_URL = "https://aibusiness.com"
LIST_URL = "https://aibusiness.com/latest-news"


def _extract_text_from_item(item, data_list):
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        text = item.get("_931") or item.get("text") or item.get("_177")
        if isinstance(text, str):
            return text
        if isinstance(text, dict):
            return _extract_text_from_item(text, data_list)
        if isinstance(text, int) and 0 <= text < len(data_list):
            return _extract_text_from_item(data_list[text], data_list)
    return None


class AibusinessScraper(BaseSimpleScraper):
    """AI Business 爬虫"""

    def __init__(self, bq_client):
        super().__init__("aibusiness", bq_client)

    def _get_detail(self, link: str, session: requests.Session) -> str:
        try:
            session.get(link, headers=HEADERS, timeout=10, allow_redirects=True)
            time.sleep(0.5)
            data_url = link.rstrip("/") + ".data" if not link.endswith(".data") else link
            if not data_url.endswith(".data"):
                data_url = data_url + ".data"
            resp = session.get(
                data_url,
                headers={**HEADERS, "accept": "*/*", "referer": LIST_URL},
                timeout=10,
                allow_redirects=True,
            )
            if resp.status_code != 200:
                return ""
            data = resp.json()
            if not isinstance(data, list) or len(data) == 0:
                return ""
            body_json_indices = None
            for item in data:
                if isinstance(item, dict) and "bodyJson" in item:
                    body_json_indices = item["bodyJson"]
                    break
            if not body_json_indices or not isinstance(body_json_indices, list):
                return ""

            def get_item(idx):
                if isinstance(idx, int) and 0 <= idx < len(data):
                    return data[idx]
                return None

            paragraphs = []
            for idx in body_json_indices:
                item = get_item(idx)
                if not item or not isinstance(item, dict):
                    continue
                if item.get("_177") != "paragraph" and "paragraph" not in str(item.get("_177", "")).lower():
                    continue
                content = item.get("content", [])
                if not isinstance(content, list):
                    continue
                text_parts = []
                for c in content:
                    if isinstance(c, int):
                        t = _extract_text_from_item(get_item(c), data)
                        if t:
                            text_parts.append(t)
                    elif isinstance(c, dict):
                        t = _extract_text_from_item(c, data)
                        if t:
                            text_parts.append(t)
                if text_parts:
                    paragraphs.append(" ".join(text_parts))
            if not paragraphs:
                return ""
            return "<div class=\"article-content\">\n" + "\n".join("<p>{}</p>".format(p) for p in paragraphs) + "\n</div>"
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 AI Business...")
            session = requests.Session()
            session.headers.update(HEADERS)
            session.get(BASE_URL, headers=HEADERS, timeout=10, allow_redirects=True)
            resp = session.get(LIST_URL, headers={**HEADERS, "referer": BASE_URL}, timeout=12, allow_redirects=True)
            if resp.status_code != 200:
                self.util.error("列表请求失败")
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            all_items = []
            seen = set()
            for selector in ["a.ArticlePreview-Title", "a.ContentCard-Title", "a.ListPreview-Title"]:
                for node in soup.select(selector):
                    href = (node.get("href") or "").strip()
                    title = node.get_text().strip()
                    if not href or not title:
                        continue
                    if not href.startswith("http"):
                        href = BASE_URL + href if href.startswith("/") else BASE_URL + "/" + href
                    if href not in seen:
                        seen.add(href)
                        all_items.append({"link": href, "title": title})
            new_articles = []
            data_index = 0
            for item in all_items[:8]:
                if getattr(self, "_timed_out", False) or data_index >= 8:
                    break
                link = item["link"]
                title = item["title"]
                if self.is_link_exists(link):
                    continue
                description = self._get_detail(link, session)
                if description:
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": "",
                        "pub_date": self.util.current_time_string(),
                        "kind": 1,
                        "language": "en",
                        "source_name": "AI Business",
                    })
                    data_index += 1

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles[:10])
                self.util.info(f"成功爬取 {len(new_articles)} 篇 AI Business")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"AI Business 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
