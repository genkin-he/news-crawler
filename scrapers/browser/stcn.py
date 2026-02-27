# -*- coding: UTF-8 -*-
"""证券时报快讯（stcn）无头浏览器爬虫 - Playwright 拦截 XHR 获取 JSON"""
import os
import sys
from datetime import timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.browser.base_browser_scraper import BaseBrowserScraper
from utils.bigquery_client import BigQueryClient


class StcnScraper(BaseBrowserScraper):
    """证券时报 stcn.com 快讯，需 Playwright 等待 XHR 返回 JSON"""

    def __init__(self, bq_client: BigQueryClient):
        super().__init__("stcn", bq_client)

    def _run_impl(self):
        try:
            self.util.info("开始爬取 STCN 快讯...")
            from playwright.sync_api import sync_playwright

            new_articles = []

            with sync_playwright() as p:
                browser = p.firefox.launch(headless=self.util.get_crawler_headless(default=True), slow_mo=300)
                context = browser.new_context()
                page = context.new_page()

                try:
                    with page.expect_response(
                        lambda r: "article/list.html?type=kx" in r.url
                        and r.status == 200
                        and "application/json" in (r.headers.get("content-type") or "")
                    ) as resp_holder:
                        self.util.info("访问 STCN 快讯列表...")
                        page.goto(
                            "https://www.stcn.com/article/list.html?type=kx",
                            timeout=15000,
                        )
                        page.wait_for_load_state("networkidle")

                    response = resp_holder.value
                    json_data = response.json()
                    articles_data = json_data.get("data", [])
                    self.util.info(f"获取到 {len(articles_data)} 条快讯")

                    for item in articles_data[:15]:
                        if getattr(self, "_timed_out", False):
                            break
                        link = "https://www.stcn.com{}".format(item.get("url", ""))
                        if not link or link == "https://www.stcn.com":
                            continue
                        if self.is_link_exists(link):
                            self.util.info(f"exists link: {link}")
                            self.stats["skipped"] += 1
                            continue

                        show_time = item.get("show_time")
                        if show_time is not None:
                            try:
                                ts = float(show_time)
                                if ts > 1e12:
                                    ts = ts / 1000
                                pub_date = self.util.convert_utc_to_local(
                                    ts, tz=timezone.utc
                                )
                            except (TypeError, ValueError):
                                pub_date = self.util.current_time_string()
                        else:
                            pub_date = self.util.current_time_string()

                        title = item.get("title", "").strip()
                        description = (item.get("content") or "").strip()
                        if not title:
                            continue

                        new_articles.append({
                            "title": title,
                            "description": description,
                            "link": link,
                            "author": "",
                            "pub_date": pub_date,
                            "kind": 2,
                            "language": "zh-CN",
                            "source_name": "证券时报",
                        })
                finally:
                    context.close()
                    browser.close()

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 STCN 快讯")
            else:
                self.util.info("无新增快讯")

        except Exception as e:
            self.util.error(f"STCN 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1

        return self.get_stats()
