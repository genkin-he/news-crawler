# -*- coding: UTF-8 -*-
"""Korea Times 加密货币频道无头浏览器爬虫（样例）— Playwright + BeautifulSoup，与 simple/koreatimes 同源"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from bs4 import BeautifulSoup

from scrapers.browser.base_browser_scraper import BaseBrowserScraper
from utils.bigquery_client import BigQueryClient


# 站点返回的错误页关键词
_KOREATIMES_ERROR_PAGE_MARKERS = ("Service Error", "unexpected server error", "Go to Homepage")


def _is_koreatimes_error_page(page) -> bool:
    try:
        content = page.content()
        return any(marker in content for marker in _KOREATIMES_ERROR_PAGE_MARKERS)
    except Exception:
        return True


class KoreatimesScraper(BaseBrowserScraper):
    """Korea Times 加密货币频道（浏览器样例）：需 Playwright 渲染列表与详情页。同源 simple 版见 scrapers/simple/koreatimes.py"""

    RUN_TIMEOUT = 120

    def __init__(self, bq_client: BigQueryClient):
        super().__init__("koreatimes", bq_client)

    def _get_detail(self, link: str, page) -> str:
        """拉取文章详情页正文。"""
        self.util.info(f"link: {link}")
        try:
            page.goto(link, wait_until="domcontentloaded", timeout=10000)
            if _is_koreatimes_error_page(page):
                self.util.error(f"详情页为错误页，跳过: {link}")
                return ""
            page.wait_for_selector("[class*='EditorContents_contents']", timeout=30000)
            wrap_selector = "[class*='EditorContents_wrap']"
            detail_handles = page.query_selector_all(wrap_selector)
            if not detail_handles:
                return ""
            lxml = BeautifulSoup(detail_handles[0].inner_html(), "lxml")
            soup = lxml.select_one("[class*='EditorContents_contents']")
            if not soup:
                return ""
            for tag in soup.find_all(["script", "style", "input", "iframe"]):
                tag.decompose()
            for tag in soup.find_all(
                lambda t: t.get("id") and "koreatimes_inarticle" in (t.get("id") or "")
            ):
                tag.decompose()
            for tag in soup.find_all("div", class_=["module-articles", "editor-img-box"]):
                tag.decompose()
            return str(soup).strip()
        except Exception as e:
            self.util.error(f"Error fetching {link}: {str(e)}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Korea Times 加密货币（browser）...")
            from playwright.sync_api import sync_playwright

            new_articles = []
            list_url = "https://www.koreatimes.co.kr/economy/cryptocurrency"

            with sync_playwright() as p:
                browser = p.firefox.launch(
                    headless=self.util.get_crawler_headless(default=True),
                    slow_mo=300,
                )
                context = browser.new_context()
                page = context.new_page()

                try:
                    page.goto(list_url, wait_until="domcontentloaded", timeout=10000)
                    self.util.info("开始访问网页...")
                    if _is_koreatimes_error_page(page):
                        self.util.error("列表页返回错误页，跳过本次爬取")
                        return self.get_stats()
                    page.wait_for_selector(
                        "a[href*='/economy/cryptocurrency/202']",
                        timeout=30000,
                    )
                    self.util.info("文章内容已加载")

                    card_selector = "[class*='SectionModule_item']"
                    news_cards = page.query_selector_all(card_selector)
                    self.util.info(f"找到 {len(news_cards)} 篇文章")

                    for card in news_cards:
                        if getattr(self, "_timed_out", False):
                            break
                        try:
                            link_el = card.query_selector("a[href*='/economy/cryptocurrency/202']")
                            if not link_el:
                                continue
                            href = link_el.get_attribute("href")
                            if not href or not href.strip():
                                continue
                            link = "https://www.koreatimes.co.kr{}".format(href.strip())
                            if self.is_link_exists(link):
                                self.util.info(f"exists link: {link}")
                                self.stats["skipped"] += 1
                                continue

                            title_el = card.query_selector("h2, h3")
                            title = title_el.inner_text().strip() if title_el else ""
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
                                        "kind": 1,
                                        "language": "en",
                                        "source_name": "Korea Times",
                                    })
                            finally:
                                detail_page.close()
                        except Exception as e:
                            self.util.error(f"处理文章时出错: {e}")
                            self.stats["errors"] += 1
                            continue
                finally:
                    context.close()
                    browser.close()

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
