# -*- coding: UTF-8 -*-
"""Hibor 爬虫 — 列表页 + 详情 POST ncid"""
import sys
import os
import re

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
DETAIL_HEADERS = {
    **HEADERS,
    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Referer": "https://www.hibor.com.cn/data/a667000ad4265496c8ad4a695931acbd.html",
    "x-requested-with": "XMLHttpRequest",
}
BASE_URL = "https://www.hibor.com.cn"
LIST_URL = "https://www.hibor.com.cn/elitelist.html"
DETAIL_POST_URL = "https://www.hibor.com.cn/hiborweb/DocDetail/NewContent?ncid=0f162bc8-3a7d-41ef-bf4d-dc7fc9621b56"


class HiborScraper(BaseSimpleScraper):
    """Hibor 爬虫"""

    def __init__(self, bq_client):
        super().__init__("hibor", bq_client)

    def _parse_ncid(self, link: str) -> str:
        try:
            resp = _get(link, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                return ""
            for script in BeautifulSoup(resp.text, "lxml").select("script"):
                text = script.get_text() or ""
                if "var ncid = " in text:
                    m = re.search(r"var ncid = ['\"]([^'\"]+)['\"]", text)
                    if m:
                        return m.group(1)
            return ""
        except Exception:
            return ""

    def _get_detail(self, link: str, source: str) -> str:
        self.util.info(f"link: {link}")
        ncid = self._parse_ncid(link)
        if not ncid:
            return ""
        try:
            resp = _post(DETAIL_POST_URL, data={"ncid": ncid}, headers=DETAIL_HEADERS, timeout=12)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            nodes = soup.select(".abstruct-info")
            if not nodes:
                return ""
            node = nodes[0]
            for el in node.select(".related_stories_left_block"):
                el.decompose()
            from bs4 import Tag
            p = soup.new_tag("p")
            p.string = f"来源: {source}"
            node.append(p)
            return str(node).strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Hibor...")
            new_articles = []

            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                self.util.error("列表请求失败")
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            nodes = soup.select(".trContent")[:4]

            for node in nodes:
                if getattr(self, "_timed_out", False):
                    break
                tds = node.select("td:nth-child(2) > a")
                td6 = node.select("td:nth-child(6)")
                if not tds or not td6:
                    continue
                href = (tds[0].get("href") or "").strip()
                link = BASE_URL + href if href.startswith("/") else href
                if self.is_link_exists(link):
                    self.util.info(f"exists link: {link}")
                    break
                pub_date = td6[0].get_text().strip()
                title_attr = (tds[0].get("title") or "").strip()[:-7]
                parts = title_attr.split("-")
                security_company = parts[0] if parts else ""
                title = title_attr.replace(f"{security_company}-", "", 1) if security_company else title_attr
                description = self._get_detail(link, security_company)
                if description:
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": "hibor",
                        "pub_date": pub_date,
                        "kind": 1,
                        "language": "zh-CN",
                        "source_name": "慧博研报",
                    })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Hibor")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"Hibor 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
