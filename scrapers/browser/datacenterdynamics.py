# -*- coding: UTF-8 -*-
"""Data Center Dynamics 无头浏览器爬虫 — RSS 列表 + Playwright 详情页取完整正文"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.browser.base_browser_scraper import BaseBrowserScraper

HEADERS = {
    "accept": "application/xml,text/xml,*/*;q=0.9",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
}
RSS_URL = "https://www.datacenterdynamics.com/en/rss/news"
MAX_ARTICLES = 10


def _text_from_tag(tag) -> str:
    if tag is None:
        return ""
    if hasattr(tag, "get_text"):
        return (tag.get_text() or "").strip()
    return (str(tag) or "").strip()


def _fetch_rss_items():
    """用 requests 拉取 RSS，返回 [(link, title), ...]。"""
    resp = requests.get(RSS_URL, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        return []
    if "<rss" not in resp.text[:500] and "<item" not in resp.text[:1000]:
        soup = BeautifulSoup(resp.text, "lxml")
    else:
        soup = BeautifulSoup(resp.text, "lxml-xml")
    items = soup.select("item")[:MAX_ARTICLES]
    if not items:
        items = soup.select("channel item")[:MAX_ARTICLES]
    out = []
    for item in items:
        link = _text_from_tag(item.find("link"))
        if not link or not link.startswith("http"):
            link = _text_from_tag(item.find("guid"))
        title = _text_from_tag(item.find("title"))
        if link and link.startswith("http") and title:
            out.append((link, title))
    return out


class DatacenterdynamicsScraper(BaseBrowserScraper):
    """Data Center Dynamics 浏览器版：RSS 取列表，Playwright 打开详情页取 div.block-text 完整正文"""

    RUN_TIMEOUT = 120

    def __init__(self, bq_client):
        super().__init__("datacenterdynamics", bq_client)

    def _get_detail(self, link: str, page) -> str:
        """用 Playwright 打开详情页，等待并提取所有 div.block-text 内段落。"""
        self.util.info(f"link: {link}")
        try:
            page.goto(link, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_selector("div.block-text", timeout=15000)
            blocks = page.query_selector_all("div.block-text")
            parts = []
            for block in blocks:
                html_fragment = block.inner_html()
                if not html_fragment or not html_fragment.strip():
                    continue
                soup = BeautifulSoup(html_fragment, "lxml")
                for el in soup.select("script, style, .ad, .advertisement"):
                    el.decompose()
                for p in soup.select("p"):
                    t = (p.get_text() or "").strip()
                    if t:
                        parts.append(t)
            if parts:
                return "<p>" + "</p><p>".join(parts) + "</p>"
            return ""
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Data Center Dynamics (browser)...")
            new_articles = []
            rss_items = _fetch_rss_items()
            if not rss_items:
                self.util.error("RSS 未获取到条目")
                return self.get_stats()

            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.firefox.launch(
                    headless=self.util.get_crawler_headless(default=True),
                    slow_mo=200,
                )
                context = browser.new_context()
                page = context.new_page()

                try:
                    for link, title in rss_items:
                        if getattr(self, "_timed_out", False):
                            break
                        if self.is_link_exists(link):
                            continue
                        detail_page = context.new_page()
                        try:
                            description = self._get_detail(link, detail_page)
                            if description:
                                new_articles.append({
                                    "title": title,
                                    "description": description,
                                    "link": link,
                                    "author": "",
                                    "pub_date": self.util.current_time_string(),
                                    "kind": 1,
                                    "language": "en",
                                    "source_name": "Data Center Dynamics",
                                })
                        finally:
                            detail_page.close()
                finally:
                    context.close()
                    browser.close()

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Data Center Dynamics")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"Data Center Dynamics 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
