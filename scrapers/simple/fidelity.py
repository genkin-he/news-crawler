# -*- coding: UTF-8 -*-
"""Fidelity — 列表页内嵌 JSON + 详情页正文"""
import sys
import os
import json

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "zh-CN,zh;q=0.9",
    "referer": "https://www.fidelity.com/",
}
BASE_URL = "https://www.fidelity.com"
OVERVIEW_URL = "https://www.fidelity.com/news/overview"
VARIABLE_NAMES = ["companyNews", "international", "investingIdeas", "technology", "topNews ", "usEconomy", "newsUS"]


class FidelityScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("fidelity", bq_client)

    def _extract_js_var(self, body: str, var_name: str):
        try:
            parts = body.split("var " + var_name + "= ")
            if len(parts) < 2:
                return None
            raw = parts[1].split("</script>")[0].strip().rstrip(";")
            return json.loads(raw) if raw else None
        except (IndexError, ValueError, json.JSONDecodeError):
            return None

    def _get_detail(self, link: str) -> str:
        try:
            resp = _get(link, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                return ""
            resp.encoding = "utf-8"
            var_data = self._extract_js_var(resp.text, "articlejson ")
            if not isinstance(var_data, dict):
                return ""
            story = var_data.get("story", {})
            return (story.get("text") or "").strip()
        except Exception as e:
            self.util.error(f"get_detail {link}: {e}")
            return ""

    def _parse_article(self, article_data: dict, var_name: str) -> dict:
        try:
            if var_name != "topNews ":
                link = article_data.get("link", "")
            else:
                guid = article_data.get("guid", "")
                link = f"{BASE_URL}/news/article/top-news/{guid}" if guid else ""
            if not link or not link.startswith("http"):
                link = BASE_URL + link if link and link.startswith("/") else ""
            if not link:
                return None
            title = (article_data.get("title") or "").strip()
            if not title:
                return None
            pub_date = self.util.current_time_string()
            pub_str = article_data.get("pubDate")
            if pub_str:
                try:
                    pub_date = self.util.parse_time(pub_str, "%Y-%m-%dT%H:%M:%S.%f%z")
                except (ValueError, TypeError):
                    try:
                        pub_date = self.util.parse_time(pub_str, "%Y-%m-%dT%H:%M:%S%z")
                    except (ValueError, TypeError):
                        pass
            description = self._get_detail(link)
            if not description:
                return None
            return {
                "title": title,
                "description": description,
                "link": link,
                "author": "",
                "pub_date": pub_date,
                "kind": 1,
                "language": "en",
                "source_name": "Fidelity",
            }
        except Exception as e:
            self.util.error(f"parse_article: {e}")
            return None

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Fidelity...")
            new_articles = []
            seen_links = set()
            resp = _get(OVERVIEW_URL, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                return self.get_stats()
            resp.encoding = "utf-8"
            body = resp.text
            for var_name in VARIABLE_NAMES:
                if getattr(self, "_timed_out", False):
                    break
                var_data = self._extract_js_var(body, var_name)
                if not isinstance(var_data, list):
                    continue
                for article_data in var_data[:2]:
                    if not isinstance(article_data, dict):
                        continue
                    parsed = self._parse_article(article_data, var_name)
                    if not parsed or parsed["link"] in seen_links or self.is_link_exists(parsed["link"]):
                        continue
                    seen_links.add(parsed["link"])
                    new_articles.append(parsed)
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles[:40])
        except Exception as e:
            self.util.error(f"Fidelity 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
