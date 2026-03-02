# -*- coding: UTF-8 -*-
"""FX168 爬虫 — 使用 FX168 API 列表 + 详情"""
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
LIST_API = "https://centerapi.fx168api.com/cms/api/cmsnews/news/getNewsByChannel"
DETAIL_API = "https://centerapi.fx168api.com/cms/api/cmsnews/news/getNewsDetail"


class Fx168Scraper(BaseSimpleScraper):
    """FX168 爬虫"""

    def __init__(self, bq_client):
        super().__init__("fx168", bq_client)

    def _get_detail(self, news_id: str) -> str:
        self.util.info(f"detail id: {news_id}")
        try:
            h = {**FX168_HEADERS, "_pcc": DEFAULT_PCC}
            resp = _get(DETAIL_API, params={"newsId": news_id}, headers=h, timeout=15)
            if resp.status_code != 200:
                return ""
            data = resp.json()
            return (data.get("data") or {}).get("newsContent") or ""
        except Exception as e:
            self.util.error(f"获取详情失败 {news_id}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 FX168...")
            new_articles = []

            headers = {**FX168_HEADERS, "_pcc": DEFAULT_PCC}
            resp = _get(LIST_API, params={"pageNo": 1, "pageSize": 10, "channelCodes": "001001"}, headers=headers, timeout=15)
            if resp.status_code != 200:
                self.util.error("API 请求失败")
                return self.get_stats()
            data = resp.json()
            items = (data.get("data") or {}).get("items") or []

            for item in items[:4]:
                if getattr(self, "_timed_out", False):
                    break
                url_code = item.get("urlCode")
                link = f"https://www.fx168news.com/article/{url_code}"
                if self.is_link_exists(link):
                    self.util.info(f"exists link: {link}")
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

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 FX168")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"FX168 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
