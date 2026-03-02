# -*- coding: UTF-8 -*-
"""C114 通信网爬虫 — requests + BeautifulSoup，gbk 编码"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
}
BASE_URL = "https://www.c114.com.cn"
LIST_URL = "https://www.c114.com.cn/news/"


class C114Scraper(BaseSimpleScraper):
    """C114 通信网爬虫"""

    def __init__(self, bq_client):
        super().__init__("c114", bq_client)

    def _get_detail(self, link: str) -> str:
        self.util.info(f"link: {link}")
        try:
            resp = _get(link, headers=HEADERS, timeout=12)
            resp.encoding = "gbk"
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            nodes = soup.select(".text")
            if not nodes:
                return ""
            node = nodes[0]
            for el in node.select(".ad"):
                el.decompose()
            return str(node).strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 C114...")
            new_articles = []

            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            resp.encoding = "gbk"
            if resp.status_code != 200:
                self.util.error("列表请求失败")
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            nodes = soup.select(".content_c_list > .new_list_c")[:3]

            for node in nodes:
                if getattr(self, "_timed_out", False):
                    break
                anchors = node.select("h6 > a")
                if not anchors:
                    continue
                link = (anchors[0].get("href") or "").strip()
                title = anchors[0].get_text().strip()
                if not link or not title or self.is_link_exists(link):
                    if link and self.is_link_exists(link):
                        self.util.info(f"exists link: {link}")
                        break
                    continue
                description = self._get_detail(link)
                if description:
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": "",
                        "pub_date": self.util.current_time_string(),
                        "kind": 1,
                        "language": "zh-CN",
                        "source_name": "C114通信网",
                    })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 C114")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"C114 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
