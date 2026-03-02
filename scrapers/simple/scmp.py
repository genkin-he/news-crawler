# -*- coding: UTF-8 -*-
"""SCMP 爬虫 — requests + BeautifulSoup/JSON"""
import sys
import os
import re
import json

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "referer": "https://www.scmp.com/",
}
BASE_URL = "https://www.scmp.com"
SECTION_URLS = [
    {"name": "business_companies", "category": "business", "url": "https://www.scmp.com/business/companies?module=Companies&pgtype=section"},
    {"name": "tech", "category": "tech", "url": "https://www.scmp.com/tech?module=oneline_menu_section_int&pgtype=section"},
    {"name": "hong_kong", "category": "hong-kong", "url": "https://www.scmp.com/news/hong-kong?module=oneline_menu_section_int&pgtype=live"},
]


class ScmpScraper(BaseSimpleScraper):
    """SCMP 爬虫"""

    def __init__(self, bq_client):
        super().__init__("scmp", bq_client)

    def _get_detail(self, link: str) -> str:
        try:
            resp = _get(link, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                return ""
            body = resp.text
            if "articleBody" in body:
                m = re.search(r'"articleBody"\s*:\s*"([^"]+)"', body)
                if m:
                    s = m.group(1).replace('\\"', '"').replace("\\n", "\n").replace("\\/", "/")
                    return s
            soup = BeautifulSoup(body, "lxml")
            content = soup.select_one("article, .article-body, .article-content, [itemprop='articleBody']")
            if content:
                for el in content.select("script, style, iframe, noscript, .ad, .advertisement"):
                    el.decompose()
                return str(content).strip()
            return ""
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _fetch_posts_from_section(self, section_config: dict) -> list:
        url = section_config["url"]
        try:
            resp = _get(url, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                return []
            body = resp.text
            posts = []
            m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', body, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(1))
                    props = data.get("props", {}).get("pageProps", {})
                    contents = props.get("contents", {})
                    if isinstance(contents, dict):
                        for edge in contents.get("edges", [])[:3]:
                            node = edge.get("node", {})
                            if node.get("headline") and node.get("urlAlias"):
                                posts.append({
                                    "title": node["headline"],
                                    "link": BASE_URL + node["urlAlias"],
                                })
                except (json.JSONDecodeError, Exception):
                    pass
            if not posts:
                soup = BeautifulSoup(body, "lxml")
                seen = set()
                for a in soup.select('a[href*="/article/"]')[:30]:
                    href = a.get("href", "")
                    if not href or href.startswith("#"):
                        continue
                    full = BASE_URL + href if href.startswith("/") else (href if href.startswith("http") else None)
                    if not full or "/article/" not in full or full in seen:
                        continue
                    seen.add(full)
                    title = a.get_text(strip=True) or a.get("aria-label") or a.get("title", "")
                    if title and len(title) > 10:
                        posts.append({"title": title[:200], "link": full})
                        if len(posts) >= 3:
                            break
            return posts[:3]
        except Exception as e:
            self.util.error(f"Fetch section {section_config['name']}: {e}")
            return []

    def _run_impl(self):
        try:
            self.util.info("开始爬取 SCMP...")
            all_posts = []
            for section in SECTION_URLS:
                if getattr(self, "_timed_out", False):
                    break
                all_posts.extend(self._fetch_posts_from_section(section))
            processed = {}
            new_articles = []
            for post in all_posts:
                if getattr(self, "_timed_out", False):
                    break
                link = post["link"]
                section_name = None
                for s in SECTION_URLS:
                    if s["category"] in link:
                        section_name = s["name"]
                        break
                if not section_name:
                    section_name = "default"
                if processed.get(section_name, 0) >= 3:
                    continue
                if self.is_link_exists(link):
                    continue
                title = post["title"]
                description = self._get_detail(link)
                if description:
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": "",
                        "pub_date": self.util.current_time_string(),
                        "kind": 1,
                        "language": "en",
                        "source_name": "南华早报",
                    })
                    processed[section_name] = processed.get(section_name, 0) + 1

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles[:20])
                self.util.info(f"成功爬取 {len(new_articles)} 篇 SCMP")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"SCMP 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
