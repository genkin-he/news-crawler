# -*- coding: UTF-8 -*-
"""证券时报快讯（stcn）— 纯 requests 请求列表 API，无需浏览器，可部署到 Cloud Functions"""
import sys
import os
from datetime import timezone

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper

# 带上 X-Requested-With 后同一 URL 返回 JSON 而非 HTML
STCN_LIST_URL = "https://www.stcn.com/article/list.html?type=kx"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.stcn.com/",
    "X-Requested-With": "XMLHttpRequest",
}


class StcnScraper(BaseSimpleScraper):
    """证券时报快讯，直接请求列表 API，仅用 requests，可跑在 Cloud Functions"""

    def __init__(self, bq_client):
        super().__init__("stcn", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 STCN 快讯...")
            response = requests.get(STCN_LIST_URL, headers=HEADERS, timeout=15)
            response.raise_for_status()
            json_data = response.json()
            articles_data = json_data.get("data", [])
            self.util.info(f"获取到 {len(articles_data)} 条快讯")

            new_articles = []
            for item in articles_data[:15]:
                if getattr(self, "_timed_out", False):
                    break
                link = "https://www.stcn.com{}".format((item.get("url") or "").strip())
                if not link or link == "https://www.stcn.com":
                    continue
                if self.is_link_exists(link):
                    self.util.info(f"exists link: {link}")
                    self.stats["skipped"] += 1
                    continue

                show_time = item.get("show_time")
                if show_time is not None:
                    try:
                        ts = float(show_time)
                        if ts > 1e12:
                            ts = ts / 1000
                        pub_date = self.util.convert_utc_to_local(ts, tz=timezone.utc)
                    except (TypeError, ValueError):
                        pub_date = self.util.current_time_string()
                else:
                    pub_date = self.util.current_time_string()

                title = (item.get("title") or "").strip()
                description = (item.get("content") or "").strip()
                if not title:
                    continue

                new_articles.append({
                    "title": title,
                    "description": description,
                    "link": link,
                    "author": "",
                    "pub_date": pub_date,
                    "kind": 2,
                    "language": "zh-CN",
                    "source_name": "证券时报",
                })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 STCN 快讯")
            else:
                self.util.info("无新增快讯")

        except Exception as e:
            self.util.error(f"STCN 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1

        return self.get_stats()
