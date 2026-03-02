# -*- coding: UTF-8 -*-
"""EE Times 爬虫 — 优先 RSS（单请求），详情多选择器 + RSS description 回退"""
import html
import re
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
}
LIST_URLS = [
    "https://www.eetimes.com/category/breaking-news/",
    "https://www.eetimes.com/category/news/",
]
BASE_URL = "https://www.eetimes.com"
ARTICLE_URL_RE = re.compile(
    r"^https://www\.eetimes\.com/(?!category/)[^/]+/?$",
    re.I,
)
MAX_ARTICLES_PER_RUN = 10
REQUEST_TIMEOUT = 25
# 优先用 RSS（单次请求），列表页常超时
FEED_URL = "https://www.eetimes.com/category/news-analysis/feed/"

from scrapers.simple.http_client import get as _get


def _normalize_link(href: str) -> str:
    """归一化链接便于去重（统一带尾部斜杠）。"""
    if not href or not href.strip():
        return ""
    s = href.strip().rstrip("/")
    if not s.startswith("https://www.eetimes.com/"):
        return ""
    if "/category/" in s:
        return ""
    return s + "/"


def _extract_list_entries(soup: BeautifulSoup):
    """从分类列表页解析出 (link, title) 列表，仅包含正文页链接。"""
    entries = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        norm = _normalize_link(href)
        if not norm or norm in seen:
            continue
        if not ARTICLE_URL_RE.match(norm):
            continue
        seen.add(norm)
        title = (a.get_text() or "").strip()
        if len(title) < 3:
            continue
        entries.append((norm, title))
    return entries


def _rss_description_to_html(item) -> str:
    """从 RSS item 的 description 得到可作正文的 HTML 片段。"""
    desc_el = item.find("description")
    if desc_el is None:
        return ""
    raw = (desc_el.get_text() if hasattr(desc_el, "get_text") else str(desc_el)).strip()
    if not raw:
        return ""
    unescaped = html.unescape(raw)
    text = re.sub(r"<[^>]+>", " ", unescaped)
    text = re.sub(r"\s+", " ", text).strip()
    return f"<p>{text}</p>" if text else ""


# 详情页正文选择器（按顺序尝试，站点可能 JS 渲染导致首屏无 .article-body）
BODY_SELECTORS = [
    ".article-body",
    ".entry-content",
    ".post-content",
    "article",
    "main",
    "[class*='article-body']",
    "[class*='post__body']",
    "[class*='content']",
]


class EetimesScraper(BaseSimpleScraper):
    """EE Times 爬虫 — 解析 breaking-news / news 列表页 HTML，列表超时时回退 RSS"""

    RUN_TIMEOUT = 90  # 列表页常较慢，给足时间并允许 RSS 回退

    def __init__(self, bq_client):
        super().__init__("eeetimes", bq_client)

    def _get_detail(self, link: str) -> str:
        self.util.info(f"link: {link}")
        try:
            resp = _get(link, headers=HEADERS, timeout=18)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            for sel in BODY_SELECTORS:
                body = soup.select_one(sel)
                if not body:
                    continue
                for el in body.select("script, style, .ad, .advertisement"):
                    el.decompose()
                text = body.get_text(separator=" ", strip=True)
                if len(text) < 150:
                    continue
                parts = []
                for p in body.select("p"):
                    t = (p.get_text() or "").strip()
                    if t:
                        parts.append(t)
                if parts:
                    return "<p>" + "</p><p>".join(parts) + "</p>"
                return "<p>" + text + "</p>"
            return ""
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 EE Times（优先 RSS）...")
            new_articles = []
            collected = {}  # link -> title，去重

            # 1) 优先 RSS：单次请求，成功率高
            if not getattr(self, "_timed_out", False):
                try:
                    resp = _get(FEED_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
                    if resp.status_code == 200:
                        if "<?xml" in resp.text[:100] or "<rss" in resp.text[:200]:
                            feed_soup = BeautifulSoup(resp.text, "lxml-xml")
                        else:
                            feed_soup = BeautifulSoup(resp.text, "lxml")
                        for item in feed_soup.select("item")[:MAX_ARTICLES_PER_RUN]:
                            link_el = item.find("link")
                            if link_el is None:
                                continue
                            link = (link_el.get_text() if hasattr(link_el, "get_text") else str(link_el)).strip()
                            if not link or "/category/" in link:
                                continue
                            link = _normalize_link(link) or link
                            title_el = item.find("title")
                            title = (title_el.get_text() if title_el and hasattr(title_el, "get_text") else (str(title_el) if title_el else "")).strip()
                            rss_desc = _rss_description_to_html(item)
                            if title:
                                collected[link] = (title, rss_desc)
                        if collected:
                            self.util.info("已从 RSS 获取列表")
                except Exception as e:
                    self.util.error(f"RSS 请求失败: {e}")

            # 2) RSS 无结果时再试列表页
            if not collected and not getattr(self, "_timed_out", False):
                for list_url in LIST_URLS:
                    if getattr(self, "_timed_out", False):
                        break
                    try:
                        resp = _get(list_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
                        if resp.status_code != 200:
                            self.util.error(f"列表页请求失败: {list_url} -> {resp.status_code}")
                            continue
                        soup = BeautifulSoup(resp.text, "lxml")
                        for link, title in _extract_list_entries(soup):
                            collected[link] = (title, "")
                    except (requests.exceptions.Timeout, Exception) as e:
                        self.util.error(f"列表页失败 {list_url}: {e}")
                        continue

            for link, value in list(collected.items())[:MAX_ARTICLES_PER_RUN]:
                if getattr(self, "_timed_out", False):
                    break
                if self.is_link_exists(link):
                    continue
                title, rss_desc = value if isinstance(value, tuple) else (value, "")
                description = self._get_detail(link)
                if not description and rss_desc:
                    description = rss_desc
                if description:
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": "",
                        "pub_date": self.util.current_time_string(),
                        "kind": 1,
                        "language": "en",
                        "source_name": "Eetimes",
                    })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 EE Times")
            else:
                self.util.info("无新增文章")
        except requests.exceptions.Timeout as e:
            self.util.error(f"EE Times 请求超时: {e}")
            self.stats["errors"] += 1
        except Exception as e:
            self.util.error(f"EE Times 爬虫执行失败: {str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
