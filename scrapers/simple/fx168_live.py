# -*- coding: UTF-8 -*-
"""FX168 快讯/直播流爬虫 — API 列表，无详情"""
import sys
import os

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

FX168_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Origin": "https://www.fx168news.com",
    "Referer": "https://www.fx168news.com/",
    "Site-Channel": "001",
}
DEFAULT_PCC = "JFhozD8+sNQAc2XDrpuzsX4S4ZooL+hKuc4x4u+So/iPVUW8z8wwiwHMxQM7TQgC1eXoyIB3xLO1TVELr0Z28lka/bckuowSjTx1KUyCIRX6xdsEu+N+EBWF0SW/BYapjIIfXNUXibDEMoJEzBYFf/kcsq7oC4O8Ju/rWrLs9io="
LIST_API = "https://centerapi.fx168api.com/cms/api/cmsFastNews/fastNews/getList"


class Fx168LiveScraper(BaseSimpleScraper):
    """FX168 快讯爬虫 — 仅列表，title 用 textContent"""

    def __init__(self, bq_client):
        super().__init__("fx168_live", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 FX168 Live...")
            new_articles = []

            headers = {**FX168_HEADERS, "_pcc": DEFAULT_PCC}
            resp = _get(
                LIST_API,
                params={"fastChannelId": "001", "pageNo": 1, "pageSize": 20, "appCategory": "web", "direct": "down"},
                headers=headers,
                timeout=15,
            )
            if resp.status_code != 200:
                self.util.error("API 请求失败")
                return self.get_stats()
            data = resp.json()
            items = (data.get("data") or {}).get("items") or []

            for item in items:
                if getattr(self, "_timed_out", False):
                    break
                if item.get("isTop") != 0:
                    continue
                fast_id = item.get("fastNewsId")
                link = f"https://www.fx168news.com/express/fastnews/{fast_id}"
                if self.is_link_exists(link):
                    continue
                text = (item.get("textContent") or "").strip()
                if not text:
                    continue
                pub_date = item.get("publishTime") or self.util.current_time_string()
                new_articles.append({
                    "title": text[:200] if len(text) > 200 else text,
                    "description": "",
                    "link": link,
                    "author": "",
                    "pub_date": pub_date,
                    "kind": 2,
                    "language": "zh-CN",
                    "source_name": "FX168",
                })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 条 FX168 Live")
            else:
                self.util.info("无新增")
        except Exception as e:
            self.util.error(f"FX168 Live 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
