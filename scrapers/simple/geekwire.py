# -*- coding: UTF-8 -*-
"""GeekWire 爬虫 — requests + RSS/BeautifulSoup"""
import sys
import os
import xml.etree.ElementTree as ET

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
FEED_URLS = [
    "https://www.geekwire.com/amazon/feed/",
    "https://www.geekwire.com/microsoft/feed/",
    "https://www.geekwire.com/ai/feed/",
    "https://www.geekwire.com/tech-moves/feed/",
]
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"


def _clean_content_encoded(content):
    if not content:
        return content
    try:
        soup = BeautifulSoup(content, "lxml")
        for el in soup.find_all(["figure", "div"]):
            el.decompose()
        body = soup.find("body")
        return body.decode_contents().strip() if body else str(soup).strip()
    except Exception:
        return content


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
            if not title or not link:
                continue
            content_encoded = None
            enc = item.find(f".//{{{CONTENT_NS}}}encoded")
            if enc is not None and enc.text:
                content_encoded = _clean_content_encoded(enc.text.strip())
            items.append({"title": title, "link": link, "content": content_encoded})
        return items
    except Exception:
        return []


class GeekwireScraper(BaseSimpleScraper):
    """GeekWire 爬虫"""

    def __init__(self, bq_client):
        super().__init__("geekwire", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 GeekWire...")
            new_articles = []
            for feed_url in FEED_URLS:
                if getattr(self, "_timed_out", False):
                    break
                try:
                    resp = _get(feed_url, headers=HEADERS, timeout=12)
                    if resp.status_code != 200:
                        continue
                    rss_items = _parse_rss(resp.text)[:3]
                    for item in rss_items:
                        if getattr(self, "_timed_out", False):
                            break
                        link = item["link"]
                        title = item["title"]
                        content = item.get("content")
                        if self.is_link_exists(link) or not title:
                            continue
                        description = content or ""
                        if description:
                            new_articles.append({
                                "title": title,
                                "description": description,
                                "link": link,
                                "author": "",
                                "pub_date": self.util.current_time_string(),
                                "kind": 1,
                                "language": "en",
                                "source_name": "GeekWire",
                            })
                except Exception as e:
                    self.util.error(f"Feed {feed_url}: {e}")

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 GeekWire")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"GeekWire 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
