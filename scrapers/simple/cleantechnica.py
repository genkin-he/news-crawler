# -*- coding: UTF-8 -*-
"""CleanTechnica 爬虫 — requests + BeautifulSoup，可部署到 Cloud Functions"""
import sys
import os
import urllib.request

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
}
LIST_URL = "https://cleantechnica.com/category/clean-transport-2/electric-vehicles/"


class CleantechnicaScraper(BaseSimpleScraper):
    """CleanTechnica 电动/清洁技术新闻爬虫"""

    def __init__(self, bq_client):
        super().__init__("cleantechnica", bq_client)
        self._current_links = []

    def _get_detail(self, link: str) -> str:
        if link in self._current_links:
            return ""
        self.util.info(f"link: {link}")
        self._current_links.append(link)
        try:
            req = urllib.request.Request(link, None, HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status != 200:
                    return ""
                body = resp.read().decode("utf-8", errors="ignore")
                soup = BeautifulSoup(body, "lxml")
                node = soup.select_one(".cm-entry-summary")
                if not node:
                    return ""
                for el in node.select("hr, div, figure"):
                    el.decompose()
                for em in node.find_all("em"):
                    if em.get_text() and "Support CleanTechnica's work through" in em.get_text():
                        em.decompose()
                        break
                return str(node).strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 CleanTechnica...")
            self._current_links = []
            new_articles = []

            req = urllib.request.Request(LIST_URL, None, HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status != 200:
                    self.util.error("列表请求失败")
                    return self.get_stats()
                body = resp.read().decode("utf-8", errors="ignore")
            soup = BeautifulSoup(body, "lxml")
            items = soup.select("article h2 a")[:5]

            for a in items:
                if getattr(self, "_timed_out", False):
                    break
                link = (a.get("href") or "").strip()
                title = (a.get_text() or "").strip()
                if not link or not title:
                    continue
                if self.is_link_exists(link):
                    self.util.info(f"exists link: {link}")
                    continue
                description = self._get_detail(link)
                if description:
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": "",
                        "pub_date": self.util.current_time_string(),
                        "kind": 1,
                        "language": "en",
                        "source_name": "cleantechnica",
                    })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 CleanTechnica")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"CleanTechnica 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
