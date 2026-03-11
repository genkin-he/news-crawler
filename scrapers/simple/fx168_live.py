# -*- coding: UTF-8 -*-
"""FX168 快讯/直播流爬虫 — 从速递页 https://www.fx168news.com/express 解析 __NEXT_DATA__"""
import json
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get

EXPRESS_URL = "https://www.fx168news.com/express"
BASE_URL = "https://www.fx168news.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.fx168news.com/",
}
MAX_ITEMS = 20


def _strip_trailing_source(text: str) -> str:
    """去掉末尾的「（新闻源）」类标注，如（央视新闻）、（路透）。"""
    if not text or not text.strip():
        return text
    out = text.strip()
    while True:
        next_out = re.sub(r"[ \t\n\r]*（[^）]+）\s*$", "", out)
        if next_out == out:
            break
        out = next_out.strip()
    return out


def _extract_next_data(html: str) -> dict | None:
    """从页面 HTML 中解析 __NEXT_DATA__ 的 JSON。"""
    marker = '__NEXT_DATA__'
    idx = html.find(marker)
    if idx == -1:
        return None
    start = html.find(">", idx) + 1
    if start <= 0:
        return None
    end = html.find("</script>", start)
    if end == -1:
        return None
    raw = html[start:end].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


class Fx168LiveScraper(BaseSimpleScraper):
    """FX168 快讯爬虫 — 请求速递页，从 __NEXT_DATA__ 取列表，无需中心 API"""

    def __init__(self, bq_client):
        super().__init__("fx168_live", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 FX168 Live（速递页）...")
            new_articles = []

            resp = _get(EXPRESS_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                self.util.error(f"速递页请求失败：HTTP {resp.status_code}")
                return self.get_stats()

            next_data = _extract_next_data(resp.text)
            if not next_data:
                self.util.error("速递页未解析到 __NEXT_DATA__")
                return self.get_stats()

            data = (next_data.get("props") or {}).get("pageProps") or {}
            page_data = data.get("data") or {}
            items = (page_data.get("express") or {}).get("items")
            if not items:
                items = page_data.get("courierList") or []

            for item in items[:MAX_ITEMS]:
                if getattr(self, "_timed_out", False):
                    break
                if item.get("isTop") != 0:
                    continue
                fast_id = item.get("fastNewsId")
                if not fast_id:
                    continue
                link = f"{BASE_URL}/express/fastnews/{fast_id}"
                if self.is_link_exists(link):
                    continue
                raw_content = (item.get("textContent") or item.get("pureTextContent") or "").strip()
                if not raw_content:
                    continue
                raw_content = _strip_trailing_source(raw_content)
                if not raw_content:
                    continue
                pub_date = item.get("publishTime") or self.util.current_time_string()
                self.mark_link_as_processed(link)
                new_articles.append({
                    "title": "",
                    "description": raw_content,
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
            self.util.error(f"FX168 Live 爬虫执行失败：{str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
