# -*- coding: UTF-8 -*-
"""Korea Times 加密货币频道 — 纯 requests + BeautifulSoup，列表与详情均服务端渲染，可部署到 Cloud Functions"""
import sys
import os
import re

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper

LIST_URL = "https://www.koreatimes.co.kr/economy/cryptocurrency"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}
ERROR_PAGE_MARKERS = ("Service Error", "unexpected server error", "Go to Homepage")
MAX_ARTICLES = 10
REQUEST_TIMEOUT = 15


def _is_error_page(html: str) -> bool:
    return any(m in html for m in ERROR_PAGE_MARKERS)


def _extract_detail_html(soup: BeautifulSoup) -> str:
    """从详情页 soup 中提取正文，与 browser 版逻辑一致。"""
    wrap = soup.select_one("[class*='EditorContents_wrap']")
    if not wrap:
        return ""
    content = wrap.select_one("[class*='EditorContents_contents']")
    if not content:
        return ""
    for tag in content.find_all("script") + content.find_all("style") + content.find_all("input") + content.find_all("iframe"):
        tag.decompose()
    for tag in content.find_all(id=re.compile(r"koreatimes_inarticle", re.I)):
        tag.decompose()
    for tag in content.find_all("div", class_=lambda c: c and ("module-articles" in c or "editor-img-box" in c)):
        tag.decompose()
    return str(content).strip()


class KoreatimesScraper(BaseSimpleScraper):
    """Korea Times 加密货币频道，列表与详情均为服务端渲染，仅用 requests + BeautifulSoup，可跑在 Cloud Functions"""

    def __init__(self, bq_client):
        super().__init__("koreatimes", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Korea Times 加密货币...")
            session = requests.Session()
            session.headers.update(HEADERS)

            # 列表页
            list_resp = session.get(LIST_URL, timeout=REQUEST_TIMEOUT)
            list_resp.raise_for_status()
            if _is_error_page(list_resp.text):
                self.util.error("列表页返回错误页，跳过本次爬取")
                return self.get_stats()

            list_soup = BeautifulSoup(list_resp.text, "lxml")
            cards = list_soup.select("[class*='SectionModule_item']")
            self.util.info(f"找到 {len(cards)} 篇文章")

            new_articles = []
            for card in cards[:MAX_ARTICLES]:
                if getattr(self, "_timed_out", False):
                    break
                link_el = card.select_one("a[href*='/economy/cryptocurrency/202']")
                if not link_el or not link_el.get("href", "").strip():
                    continue
                href = link_el.get("href", "").strip()
                link = "https://www.koreatimes.co.kr{}".format(href if href.startswith("/") else "/" + href)
                if self.is_link_exists(link):
                    self.util.info(f"exists link: {link}")
                    self.stats["skipped"] += 1
                    continue

                title_el = card.select_one("h2, h3")
                title = (title_el.get_text(separator=" ").strip() if title_el else "") or ""
                if not title:
                    continue

                # 详情页
                self.util.info(f"link: {link}")
                try:
                    detail_resp = session.get(link, timeout=REQUEST_TIMEOUT)
                    detail_resp.raise_for_status()
                    if _is_error_page(detail_resp.text):
                        self.util.error(f"详情页为错误页，跳过: {link}")
                        continue
                    detail_soup = BeautifulSoup(detail_resp.text, "lxml")
                    description = _extract_detail_html(detail_soup)
                    if not description:
                        continue
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": "",
                        "pub_date": self.util.current_time_string(),
                        "kind": 1,
                        "language": "en",
                        "source_name": "Korea Times",
                    })
                except Exception as e:
                    self.util.error(f"获取详情失败 {link}: {e}")
                    self.stats["errors"] += 1

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Korea Times")
            else:
                self.util.info("无新增文章")

        except Exception as e:
            self.util.error(f"Korea Times 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1

        return self.get_stats()
