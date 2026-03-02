# -*- coding: UTF-8 -*-
"""雷递 — POST 列表 API + 详情 API NewsContent"""
import sys
import os
import time
import json

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36", "Content-Type": "application/json"}
LIST_URL = "https://www.leinews.com/Common/YiAPP.ashx?YiAPP_Method=uNews.PC_SearchNewsInfoList&YiAPP_Action=YiAPP.APP.SHOP&YiAPP_SIKW=true"
DETAIL_URL = "https://www.leinews.com/Common/YiAPP.ashx?YiAPP_Method=uNews.PC_GetNewsInfo&YiAPP_Action=YiAPP.APP.SHOP&YiAPP_SIKW=true"


class LeinewsScraper(BaseSimpleScraper):
    def __init__(self, bq_client):
        super().__init__("leinews", bq_client)

    def _get_detail(self, news_id: str) -> str:
        self.util.info(f"detail id: {news_id}")
        try:
            from urllib.parse import quote
            q = quote('{"NewsCode":"%s"}' % news_id, safe="")
            payload = {"flag": int(round(time.time() * 1000)), "MethodName": "YiAPP.APP.SHOP%7CYiAPP.APP.SHOP.uNews.PC_GetNewsInfo", "queryparams": q, "sikw": 1}
            r = _post(DETAIL_URL, headers=HEADERS, json=payload, timeout=12)
            if r.status_code != 200:
                return ""
            data = r.json().get("data") or {}
            body = (data.get("NewsContent") or "").replace("雷递由媒体人雷建平创办，若转载请写明来源。", "")
            return body.strip()
        except Exception as e:
            self.util.error(f"detail {news_id}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 雷递...")
            new_articles = []
            payload = {"flag": int(round(time.time() * 1000)), "MethodName": "YiAPP.APP.SHOP|YiAPP.APP.SHOP.uNews.PC_SearchNewsInfoList", "queryparams": "%7B%22ShopUser%22:%2280889%22,%22ColumnCode%22:%22%22,%22page%22:%221%22,%22rows%22:%2210%22%7D", "sikw": 1}
            resp = _post(LIST_URL, headers=HEADERS, json=payload, timeout=15)
            if resp.status_code != 200:
                return self.get_stats()
            rows = (resp.json().get("data") or {}).get("data") or []
            for i, row in enumerate(rows):
                if i == 0:
                    continue
                if getattr(self, "_timed_out", False) or i > 3:
                    break
                code = row.get("NewsCode")
                link = f"https://www.leinews.com/n{code}/detail.html"
                if self.is_link_exists(link):
                    break
                title = (row.get("NewsTitle") or "").strip()
                if not title:
                    continue
                desc = self._get_detail(code)
                if desc:
                    new_articles.append({"title": title, "description": desc, "link": link, "author": "", "pub_date": self.util.current_time_string(), "kind": 1, "language": "zh-CN", "source_name": "雷帝网"})
            if not getattr(self, "_timed_out", False) and new_articles:
                self.save_articles(new_articles)
        except Exception as e:
            self.util.error(f"雷递 失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
