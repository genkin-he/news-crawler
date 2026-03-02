# -*- coding: UTF-8 -*-
"""The Hill 爬虫 — RSS + WordPress API，可部署到 Cloud Functions"""
import sys
import os
import re
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "accept": "application/json",
    "accept-language": "en-US,en;q=0.9",
}
RSS_URL = "https://thehill.com/feed/"
API_BASE = "https://thehill.com/wp-json/wp/v2/posts/"


def _extract_post_id(link: str):
    m = re.search(r"/(\d+)-[^/]+/?$", link)
    return m.group(1) if m else None


def _clean_html_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


class ThehillScraper(BaseSimpleScraper):
    """The Hill 新闻爬虫（RSS + WP API）"""

    def __init__(self, bq_client):
        super().__init__("thehill", bq_client)

    def _get_detail_via_api(self, link: str) -> str:
        post_id = _extract_post_id(link)
        if not post_id:
            return ""
        self.util.info(f"Fetching post ID: {post_id}")
        try:
            resp = _get(API_BASE + post_id, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                return ""
            data = resp.json()
            content = (data.get("content") or {}).get("rendered", "")
            if not content:
                return ""
            soup = BeautifulSoup(content, "html.parser")
            for el in soup.select(".ad-unit, .hardwall, style, script, aside, .wp-block-embed"):
                el.decompose()
            return str(soup).strip()
        except Exception as e:
            self.util.error(f"API 获取失败 {link}: {e}")
            return ""

    def _parse_rss(self, xml_content: str) -> list:
        out = []
        try:
            root = ET.fromstring(xml_content)
            ns = {"dc": "http://purl.org/dc/elements/1.1/"}
            for item in root.findall(".//item"):
                title_el = item.find("title")
                link_el = item.find("link")
                desc_el = item.find("description")
                pub_el = item.find("pubDate")
                title = (title_el.text or "").strip() if title_el is not None else ""
                link = (link_el.text or "").strip() if link_el is not None else ""
                description = _clean_html_text(desc_el.text) if desc_el is not None and desc_el.text else ""
                pub_date = (pub_el.text or "").strip() if pub_el is not None and pub_el.text else ""
                if title and link:
                    out.append({"title": title, "link": link, "description": description, "pub_date": pub_date})
        except Exception as e:
            self.util.error(f"RSS 解析失败: {e}")
        return out

    def _run_impl(self):
        try:
            self.util.info("开始爬取 The Hill...")
            new_articles = []

            rss_resp = _get(RSS_URL, headers={**HEADERS, "accept": "application/xml"}, timeout=15)
            if rss_resp.status_code != 200:
                self.util.error(f"RSS 请求失败: {rss_resp.status_code}")
                return self.get_stats()
            items = self._parse_rss(rss_resp.text)[:5]

            for item in items:
                if getattr(self, "_timed_out", False):
                    break
                link = item["link"]
                title = item["title"]
                rss_desc = item["description"]
                if self.is_link_exists(link):
                    self.util.info(f"exists link: {link}")
                    continue
                description = self._get_detail_via_api(link)
                if not description and rss_desc:
                    description = f"<p>{rss_desc}</p>"
                if not description:
                    continue
                pub_date = item.get("pub_date") or self.util.current_time_string()
                new_articles.append({
                    "title": title,
                    "description": description,
                    "link": link,
                    "author": "",
                    "pub_date": pub_date,
                    "kind": 1,
                    "language": "en",
                    "source_name": "Thehill",
                })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 The Hill")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"The Hill 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
