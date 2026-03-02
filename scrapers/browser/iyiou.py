# -*- coding: UTF-8 -*-
"""亿欧 iyiou 无头浏览器爬虫 — Playwright 渲染列表与详情（列表页为 JS 渲染）"""
import sys
import os

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.browser.base_browser_scraper import BaseBrowserScraper

LIST_URL = "https://www.iyiou.com/news"
MAX_ARTICLES = 5


def _strip_iyiou_noise(html: str) -> str:
    """去掉正文末尾多余段落：企业信息链接、小欧AI声明等。"""
    if not html or not html.strip():
        return html
    soup = BeautifulSoup(html, "lxml")
    for p in soup.find_all("p"):
        text = (p.get_text() or "").strip()
        raw = str(p)
        if not text:
            continue
        if "更多文中提及企业信息" in text or "data.iyiou.com/company" in raw:
            p.decompose()
            continue
        if "本文由小欧AI基于亿欧数据生成" in text or ("小欧AI" in text and "亿欧数据" in text):
            p.decompose()
    return str(soup).strip()


class IyiouScraper(BaseBrowserScraper):
    """亿欧浏览器版：Playwright 加载列表页与详情页，解析 .info-item / .post-body"""

    RUN_TIMEOUT = 90

    def __init__(self, bq_client):
        super().__init__("iyiou", bq_client)

    def _get_detail(self, link: str, page) -> str:
        self.util.info(f"link: {link}")
        try:
            page.goto(link, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_selector(".post-body, article .content, .article-content, .entry-content", timeout=12000)
            html = page.content()
            soup = BeautifulSoup(html, "lxml")
            nodes = soup.select(".post-body")
            if not nodes:
                body = soup.select_one("article .content, .article-content, .entry-content")
                if not body:
                    return ""
                for el in body.select("script, style, .caas-da"):
                    el.decompose()
                return _strip_iyiou_noise(str(body).strip())
            node = nodes[0]
            for el in node.select(".caas-da"):
                el.decompose()
            return _strip_iyiou_noise(str(node).strip())
        except Exception as e:
            self.util.error(f"detail {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 亿欧 (browser)...")
            new_articles = []
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=self.util.get_crawler_headless(default=True),
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                    locale="zh-CN",
                )
                page = context.new_page()

                try:
                    page.goto(LIST_URL, wait_until="domcontentloaded", timeout=15000)
                    page.wait_for_selector(".info-item a, a[href*='/news/']", timeout=15000)
                    html = page.content()
                    soup = BeautifulSoup(html, "lxml")
                    entries = []
                    seen = set()
                    for node in soup.select(".info-item"):
                        a = node.select_one(".webTitleShow, a[href*='/news/']")
                        if not a or not a.get("href"):
                            continue
                        link = (a.get("href") or "").strip()
                        if not link.startswith("http"):
                            link = "https://www.iyiou.com" + (link if link.startswith("/") else "/" + link)
                        title = (a.get_text() or "").strip()
                        if link and title and link not in seen:
                            seen.add(link)
                            entries.append((link, title))
                    if not entries:
                        for a in soup.select("a[href*='/news/']"):
                            href = (a.get("href") or "").strip()
                            if not href.startswith("http"):
                                href = "https://www.iyiou.com" + (href if href.startswith("/") else "/" + href)
                            if "iyiou.com" not in href or href in seen:
                                continue
                            title = (a.get_text() or "").strip()
                            if len(title) < 5:
                                continue
                            seen.add(href)
                            entries.append((href, title))
                    entries = entries[:MAX_ARTICLES]

                    for link, title in entries:
                        if getattr(self, "_timed_out", False):
                            break
                        if self.is_link_exists(link):
                            continue
                        detail_page = context.new_page()
                        try:
                            desc = self._get_detail(link, detail_page)
                            if desc:
                                new_articles.append({
                                    "title": title,
                                    "description": desc,
                                    "link": link,
                                    "author": "",
                                    "pub_date": self.util.current_time_string(),
                                    "kind": 1,
                                    "language": "zh-CN",
                                    "source_name": "亿欧网",
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
                self.util.info(f"成功爬取 {len(new_articles)} 篇 亿欧")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"亿欧 爬虫执行失败: {e}")
            self.stats["errors"] += 1
        return self.get_stats()
