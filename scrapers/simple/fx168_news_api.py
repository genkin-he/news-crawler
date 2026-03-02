# -*- coding: UTF-8 -*-
"""FX168 News API — centerapi 频道列表 + 详情"""
import sys
import os

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Origin": "https://www.fx168news.com",
    "Referer": "https://www.fx168news.com/",
    "Site-Channel": "001",
}
DEFAULT_PCC = "JFhozD8+sNQAc2XDrpuzsX4S4ZooL+hKuc4x4u+So/iPVUW8z8wwiwHMxQM7TQgC1eXoyIB3xLO1TVELr0Z28lka/bckuowSjTx1KUyCIRX6xdsEu+N+EBWF0SW/BYapjIIfXNUXibDEMoJEzBYFf/kcsq7oC4O8Ju/rWrLs9io="
LIST_API = "https://centerapi.fx168api.com/cms/api/cmsnews/news/getNewsByChannel"
DETAIL_API = "https://centerapi.fx168api.com/cms/api/cmsnews/news/getNewsDetail"


class Fx168NewsApiScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("fx168_news_api", bq_client)

    def _get_detail(self, news_id: str) -> str:
        try:
            h = {**HEADERS, "_pcc": DEFAULT_PCC}
            resp = _get(DETAIL_API, params={"newsId": news_id}, headers=h, timeout=12)
            if resp.status_code != 200:
                return ""
            data = resp.json()
            return (data.get("data") or {}).get("newsContent") or ""
        except Exception as e:
            self.util.error(f"get_detail {news_id}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 FX168 News API...")
            new_articles = []
            h = {**HEADERS, "_pcc": DEFAULT_PCC}
            resp = _get(LIST_API, params={"pageNo": 1, "pageSize": 10, "channelCodes": "001001"}, headers=h, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            data = resp.json()
            items = (data.get("data") or {}).get("items") or []
            for item in items[:5]:
                if getattr(self, "_timed_out", False):
                    break
                url_code = item.get("urlCode")
                link = f"https://www.fx168news.com/article/{url_code}" if url_code else ""
                if not link or self.is_link_exists(link):
                    continue
                news_id = item.get("newsId")
                title = (item.get("newsTitle") or "").strip()
                pub_date = item.get("firstPublishTime") or self.util.current_time_string()
                if not title:
                    continue
                description = self._get_detail(news_id)
                if description:
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": "",
                        "pub_date": pub_date,
                        "kind": 1,
                        "language": "zh-CN",
                        "source_name": "FX168",
                    })
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"FX168 News API 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
