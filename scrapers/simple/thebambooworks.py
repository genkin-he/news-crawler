# -*- coding: UTF-8 -*-
"""The Bamboo Works 爬虫 — RSS + BeautifulSoup，支持 curl_cffi 回退"""
import sys
import os
import re
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper

HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "zh-CN,zh;q=0.9",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
}
RSS_URLS = [
    "https://thebambooworks.com/cn/category/%E5%BF%AB%E8%AE%AF/feed/",
    "https://thebambooworks.com/cn/feed/",
    "https://thebambooworks.com/feed/",
]
REQUEST_TIMEOUT = 20

from scrapers.simple.http_client import get as _get


def _parse_rss(xml_content):
    try:
        root = ET.fromstring(xml_content)
        items = []
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el = item.find("link")
            if title_el is None or link_el is None:
                continue
            title = (title_el.text or "").strip()
            link = (link_el.text or "").strip()
            if title and link:
                items.append({"title": title, "link": link})
        return items
    except Exception:
        return []


class ThebambooworksScraper(BaseSimpleScraper):
    """The Bamboo Works 爬虫"""

    def __init__(self, bq_client):
        super().__init__("thebambooworks", bq_client)

    def _get_detail(self, link: str) -> str:
        try:
            resp = _get(link, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "html.parser")
            node = soup.select_one("#entry-content-container, .entry-content")
            if not node:
                return ""
            for el in node.select(
                ".addtoany_share_save_container, .post-tags, .leaky_paywall_message_wrap, "
                ".umResizer, script, style, .related-posts, .author-box, .comments-area"
            ):
                el.decompose()
            for p in node.find_all("p"):
                if p.get_text() and "欲订阅" in p.get_text():
                    p.decompose()
            html = str(node)
            html = re.sub(r"^<div[^>]*>", "", html)
            html = re.sub(r"</div>$", "", html)
            return html.strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 The Bamboo Works...")
            new_articles = []
            items = []
            for rss_url in RSS_URLS:
                if getattr(self, "_timed_out", False):
                    break
                try:
                    resp = _get(rss_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
                    if resp.status_code != 200:
                        self.util.error(f"RSS 请求失败: {rss_url} -> HTTP {resp.status_code}")
                        continue
                    items = _parse_rss(resp.text)
                    if items:
                        break
                except Exception as e:
                    self.util.error(f"RSS 请求失败: {rss_url} -> {e}")
                    continue
            if not items:
                self.util.error("所有 RSS 地址均无法获取条目")
                return self.get_stats()
            post_count = 0
            for item in items:
                if getattr(self, "_timed_out", False) or post_count >= 2:
                    break
                link = item["link"]
                title = item["title"]
                if self.is_link_exists(link):
                    continue
                description = self._get_detail(link)
                if not description:
                    continue
                new_articles.append({
                    "title": title,
                    "description": description,
                    "link": link,
                    "author": "",
                    "pub_date": self.util.current_time_string(),
                    "kind": 1,
                    "language": "zh-CN",
                    "source_name": "BambooWorks",
                })
                post_count += 1

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 The Bamboo Works")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"The Bamboo Works 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
