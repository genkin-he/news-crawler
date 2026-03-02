# -*- coding: UTF-8 -*-
"""Infocast FN 无头浏览器爬虫 — Playwright 发 POST 列表 + 详情页 #newsBody"""
import sys
import os
import json

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.browser.base_browser_scraper import BaseBrowserScraper

LIST_POST_URL = "https://www.infocastfn.com/fn/ajax/news/InfocastNewsJsonResult"
LIST_BODY = "sEcho=5&iColumns=3&sColumns=datetime%2Cheadline%2Cid&iDisplayStart=0&iDisplayLength=20&iSortingCols=1&iSortCol_0=0&sSortDir_0=desc&bSortable_0=true&bSortable_1=true&bSortable_2=true&jcomparatorName=com.infocast.iweb.comparator.news.NewsJComparator&locale=zh_CN&numProcessingRec=&searchCriteria=%7B%22type%22:%22%22,%22stockCode%22:%22%22,%22grpCode%22:%22NwsType%22%7D"
REFERER = "https://www.infocastfn.com/web/guest/infocast-news"
MAX_ARTICLES = 5
# 站点响应慢，仅依赖 POST 列表接口（不先打开 referer 页），给足超时
LIST_TIMEOUT_MS = 55000
DETAIL_TIMEOUT_MS = 25000


class InfocastfnScraper(BaseBrowserScraper):
    """Infocast FN 浏览器版：Playwright 发列表 POST（带浏览器会话），详情页取 #newsBody"""

    RUN_TIMEOUT = 120

    def __init__(self, bq_client):
        super().__init__("infocastfn", bq_client)

    def _get_detail(self, link: str, page) -> str:
        self.util.info(f"link: {link}")
        try:
            resp = page.goto(link, wait_until="domcontentloaded", timeout=DETAIL_TIMEOUT_MS)
            if not resp or resp.status != 200:
                return ""
            page.wait_for_selector("#newsBody", timeout=DETAIL_TIMEOUT_MS)
            html = page.content()
            soup = BeautifulSoup(html, "lxml")
            nodes = soup.select("#newsBody")
            if not nodes:
                return ""
            node = nodes[0]
            for el in node.select(".ad"):
                el.decompose()
            return str(node).strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Infocast FN (browser)...")
            new_articles = []

            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=self.util.get_crawler_headless(default=True),
                )
                context = browser.new_context(
                    extra_http_headers={
                        "Accept": "application/json, text/javascript, */*; q=0.01",
                        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                        "Referer": REFERER,
                        "X-Requested-With": "XMLHttpRequest",
                    }
                )
                try:
                    # 直接发 POST（站点整体慢，不先打开 referer 页以免白等）
                    resp = context.request.post(
                        LIST_POST_URL,
                        data=LIST_BODY,
                        timeout=LIST_TIMEOUT_MS,
                    )
                    if resp.status != 200:
                        self.util.error(f"Infocast FN 列表请求失败: HTTP {resp.status}")
                        return self.get_stats()
                    try:
                        data = resp.json()
                    except json.JSONDecodeError as e:
                        self.util.error(f"Infocast FN 列表 JSON 解析失败: {e}")
                        return self.get_stats()

                    nodes = data.get("aaData") or []
                    if not isinstance(nodes, list):
                        nodes = []

                    for node in nodes[:MAX_ARTICLES]:
                        if getattr(self, "_timed_out", False):
                            break
                        if not isinstance(node, (list, tuple)) or len(node) < 3:
                            continue
                        news_id = node[2]
                        link = f"https://www.infocastfn.com/fn/ajax/news/newsDetail?newsId={news_id}&locale=zh_CN"
                        if self.is_link_exists(link):
                            self.util.info(f"exists link: {link}")
                            break
                        title = (node[1] or "").strip()
                        if not title:
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
                                    "kind": 2,
                                    "language": "zh-CN",
                                    "source_name": "汇港资讯",
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
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Infocast FN")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"Infocast FN 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
