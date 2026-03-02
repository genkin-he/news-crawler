# -*- coding: UTF-8 -*-
"""HKEJ 日报头条爬虫 — 列表 headline + 详情 article-detail-wrapper"""
import sys
import os
import re

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
}
BASE_URL = "https://www1.hkej.com"
LIST_URL = "https://www1.hkej.com/dailynews/headline"


class HkejDailynewsScraper(BaseSimpleScraper):
    """HKEJ 日报头条爬虫"""

    def __init__(self, bq_client):
        super().__init__("hkej_dailynews", bq_client)

    def _get_detail(self, link: str) -> str:
        self.util.info(f"link: {link}")
        try:
            resp = _get(link, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                return ""
            raw = resp.text
            if '<div  id="article-detail-wrapper">' not in raw or "<script>var isFullArticle=" not in raw:
                return ""
            body = raw.split('<div  id="article-detail-wrapper">')[1].split("<script>var isFullArticle=")[0]
            body = re.sub(r"(\t)\1+", "", body)
            body = re.sub(r"(\n)\1+", "\n", body)
            return body.lstrip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 HKEJ Daily News...")
            new_articles = []

            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                self.util.error("列表请求失败")
                return self.get_stats()
            raw = resp.text
            opts = re.findall(r"<option value='([^']+) </option>", raw)
            for opt in opts[:4]:
                if getattr(self, "_timed_out", False):
                    break
                parts = opt.split("'>")
                if len(parts) < 2:
                    continue
                link = BASE_URL + parts[0]
                title = parts[1]
                if self.is_link_exists(link):
                    self.util.info(f"exists link: {link}")
                    break
                description = self._get_detail(link)
                if description:
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": "",
                        "pub_date": self.util.current_time_string(),
                        "kind": 1,
                        "language": "zh-HK",
                        "source_name": "信报",
                    })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 HKEJ Daily News")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"HKEJ Daily News 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
