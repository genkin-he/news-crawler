# -*- coding: UTF-8 -*-
"""Bloomberg 无头浏览器爬虫 — Playwright 请求列表 API + 详情页 __NEXT_DATA__"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.browser.base_browser_scraper import BaseBrowserScraper

BASE_URL = "https://www.bloomberg.com"
LIST_API = "https://www.bloomberg.com/lineup-next/api/paginate?id=archive_story_list&page=phx-markets&variation=archive&type=lineup_content"
MAX_ARTICLES = 4


def _parse_next_data_body(html: str) -> str:
    """从详情页 HTML 中解析 __NEXT_DATA__ 并提取正文 HTML。与 simple 版逻辑一致。"""
    try:
        part = html.split('<script id="__NEXT_DATA__" type="application/json">')[1].split("</script>")[0]
        data = json.loads(part)
    except (IndexError, json.JSONDecodeError):
        return ""
    props = data.get("props", {}).get("pageProps", {})
    if "story" not in props:
        return ""
    content = props["story"].get("body", {}).get("content") or []
    html_out = "<div>"
    for element in content:
        if element.get("type") != "paragraph":
            continue
        paragraph = ""
        text_count = 0
        for sentence in element.get("content") or []:
            val = (sentence.get("value") or "").strip()
            if sentence.get("type") == "text":
                if val.startswith("Read more") or val.startswith("Read More") or "Want more Bloomberg" in val or "You can follow Bloomberg" in val:
                    break
                if val:
                    paragraph += sentence["value"]
                    text_count += 1
            elif sentence.get("type") == "link":
                for ele in sentence.get("content") or []:
                    if ele.get("type") == "text" and (ele.get("value") or "").strip():
                        paragraph += ele["value"]
            elif sentence.get("type") == "entity" and sentence.get("subType") == "security":
                for ele in sentence.get("content") or []:
                    if ele.get("type") == "text" and (ele.get("value") or "").strip():
                        text_count += 1
                        paragraph += ele["value"]
            elif sentence.get("type") == "br":
                paragraph += "<br />"
        if paragraph.strip() and text_count > 0:
            html_out += "<p>" + paragraph + "</p>"
    return html_out + "</div>"


class BloombergScraper(BaseBrowserScraper):
    """Bloomberg 浏览器版：Playwright 请求列表 API（带浏览器会话），详情页取 __NEXT_DATA__"""

    RUN_TIMEOUT = 120

    def __init__(self, bq_client):
        super().__init__("bloomberg", bq_client)

    def _get_detail(self, link: str, page) -> str:
        self.util.info("news: " + link)
        try:
            resp = page.goto(link, wait_until="domcontentloaded", timeout=20000)
            if not resp or resp.status != 200:
                return ""
            html = page.content()
            return _parse_next_data_body(html)
        except Exception as e:
            self.util.error(f"request {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Bloomberg (browser)...")
            new_articles = []
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=self.util.get_crawler_headless(default=True),
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
                    locale="en-US",
                )
                page = context.new_page()

                try:
                    # 先打开首页建立会话，再请求列表 API（与浏览器行为一致）
                    page.goto(BASE_URL + "/", wait_until="domcontentloaded", timeout=15000)
                    resp = page.goto(LIST_API, wait_until="domcontentloaded", timeout=15000)
                    if not resp or resp.status != 200:
                        self.util.error(f"Bloomberg 列表 API 失败: HTTP {resp.status if resp else 'none'}")
                        return self.get_stats()
                    body = resp.body().decode("utf-8")
                    data = json.loads(body)
                    items = data.get("archive_story_list", {}).get("items") or []
                    posts = []
                    for item in items:
                        url = (item.get("url") or "").strip()
                        if "/news/articles/" in url:
                            posts.append({"title": item.get("headline", ""), "link": BASE_URL + url})
                    posts = posts[:MAX_ARTICLES]

                    for post in posts:
                        if getattr(self, "_timed_out", False):
                            break
                        link = post["link"]
                        if self.is_link_exists(link):
                            self.util.info("exists link: " + link)
                            continue
                        title = post.get("title") or ""
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
                                    "source_name": "Bloomberg",
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
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Bloomberg")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"Bloomberg 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
