# -*- coding: UTF-8 -*-
"""亿欧 iyiou 无头浏览器爬虫 — Playwright 渲染列表与详情（列表页为 JS 渲染）"""

import json
import os
import random
import re
import sys

import requests
from bs4 import BeautifulSoup

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from scrapers.browser.base_browser_scraper import BaseBrowserScraper

LIST_URL = "https://www.iyiou.com/news"
MAX_ARTICLES = 3

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
        if "本文由小欧AI基于亿欧数据生成" in text or (
            "小欧AI" in text and "亿欧数据" in text
        ):
            p.decompose()
    return str(soup).strip()


def _extract_initial_state(html: str) -> dict | None:
    """
    从亿欧详情页 HTML 中解析 window.__INITIAL_STATE__ 的 JSON。
    详情页服务端会注入 articleModule.postInfo（含 postContent 正文），无需执行 JS。
    """
    marker = "window.__INITIAL_STATE__"
    idx = html.find(marker)
    if idx == -1:
        return None
    start = html.find("=", idx) + 1
    if start <= 0:
        return None
    # 跳过空白，找到第一个 {
    while start < len(html) and html[start] in " \t\n\r":
        start += 1
    if start >= len(html) or html[start] != "{":
        return None
    # 括号匹配提取完整 JSON（避免字符串内的 } 干扰）
    depth = 0
    in_string = None
    escape = False
    i = start
    while i < len(html):
        c = html[i]
        if escape:
            escape = False
            i += 1
            continue
        if c == "\\" and in_string:
            escape = True
            i += 1
            continue
        if in_string:
            if c == in_string:
                in_string = None
            i += 1
            continue
        if c in ('"', "'"):
            in_string = c
            i += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start : i + 1])
                except json.JSONDecodeError:
                    return None
        i += 1
    return None


def _get_detail_from_initial_state(html: str) -> str:
    """
    从详情页 HTML 的 __INITIAL_STATE__.articleModule.postInfo 中取出正文 HTML。
    成功则返回已去噪的正文，否则返回空串。
    """
    state = _extract_initial_state(html)
    if not state:
        return ""
    article = state.get("articleModule") or {}
    post_info = article.get("postInfo") or {}
    content = post_info.get("postContent") or ""
    if not content or not isinstance(content, str):
        return ""
    return _strip_iyiou_noise(content.strip())


# 验证码弹窗文案
CAPTCHA_TEXT = "安全验证"
# 自动拖动尝试后等待验证结果的时间（秒）
CAPTCHA_AFTER_DRAG_WAIT_SEC = 2


class IyiouScraper(BaseBrowserScraper):
    """亿欧浏览器版：Playwright 加载列表页与详情页，解析 .info-item / .post-body"""

    def __init__(self, bq_client):
        super().__init__("iyiou", bq_client)

    def _is_captcha_visible(self, page) -> bool:
        """当前页是否出现拖动验证码弹窗。"""
        try:
            return page.get_by_text(CAPTCHA_TEXT, exact=False).first.is_visible()
        except Exception:
            return False

    def _try_auto_solve_captcha(self, page) -> bool:
        """
        尝试自动完成滑块验证：定位滑块并向右拖动一段距离，然后检查验证是否消失。
        拼图类验证需精确缺口位置，本方法只做一次简单拖动，成功率有限。
        返回 True 表示验证已通过，False 表示仍显示验证或拖动失败。
        """
        try:
            # 常见滑块选择器：滑块把手、可拖动元素（按优先级尝试）
            slider_selectors = [
                "[class*='slider'] [class*='button']",
                "[class*='slider'] [class*='handle']",
                "[class*='slide'] [class*='btn']",
                ".nc-lang-cnt .btn_slide",  # 阿里/网易常见
                "[class*='captcha'] [class*='slide']",
                "div[class*='slider']",
                "button[class*='slide']",
            ]
            slider = None
            for sel in slider_selectors:
                try:
                    loc = page.locator(sel)
                    if loc.count() > 0 and loc.first.is_visible():
                        slider = loc.first
                        break
                except Exception:
                    continue
            if not slider or not slider.is_visible():
                return False
            box = slider.bounding_box()
            if not box:
                return False
            # 向右拖动约 280px（多数滑块轨道宽度在此范围），带小幅随机
            dx = 260 + random.randint(0, 40)
            x0 = box["x"] + box["width"] / 2
            y0 = box["y"] + box["height"] / 2
            x1 = x0 + dx
            page.mouse.move(x0, y0)
            page.mouse.down()
            page.mouse.move(x1, y0, steps=random.randint(12, 25))
            page.mouse.up()
            page.wait_for_timeout(int(CAPTCHA_AFTER_DRAG_WAIT_SEC * 1000))
            return not self._is_captcha_visible(page)
        except Exception as e:
            self.util.error(f"自动滑块尝试失败: {e}")
            return False

    def _handle_captcha_if_present(self, page, context: str) -> bool:
        """
        若出现验证码：尝试自动完成一次；自动完成不了则直接跳过（不等待用户）。
        未出现验证码或已通过则返回 True，否则返回 False。
        """
        if not self._is_captcha_visible(page):
            return True
        self.util.info(f"{context}: 检测到安全验证（拖动滑块）")
        if self._try_auto_solve_captcha(page):
            self.util.info("验证已自动通过")
            return True
        self.util.error("无法自动通过验证，跳过本次")
        return False

    # 详情页 HTTP 默认 Cookie（与浏览器一致以降低触发验证码概率；过期后可设 IYIOU_HTTP_COOKIE 覆盖或走浏览器回退）
    _DETAIL_HTTP_DEFAULT_COOKIE = (
        "eo_uid=39a75f60f94952fbc97581e45b25d6b6b13433d80bc95c8e; "
        "UM_distinctid=19c9ecff715922-044c86760e6694-1b525631-16a7f0-19c9ecff7162755; "
        "Hm_lvt_b48c2d42838a5c5e03026a8b94ece8d8=1772190956; "
        "HMACCOUNT=7C51DB1AB5F84054; "
        "cna=a24f7be029514c80a40b68870e710e64; "
        "eo_fid=-1736754225; "
        "x-waf-captcha-referer=; "
        "CNZZDATA1281422169=841997452-1772190955-https%253A%252F%252Fwww.iyiou.com%252F%7C1773042016; "
        "Hm_lpvt_b48c2d42838a5c5e03026a8b94ece8d8=1773042016; "
        "w_tsfp=ltvuV0MF2utBvS0Q7qnpkEmuFzAjdjw4h0wpEaR0f5thQLErU5mC0oZ+vMvxMXLd48xnvd7DsZoyJTLYCJI3dwMQEMmRJ4ATiFmQloYniowQBBYzEp7fWwUaK7J26TAVKXhCNxS00jA8eIUd379yilkMsyN1zap3TO14fstJ019E6KDQmI5uDW3HlFWQRzaLbjcMcuqPr6g18L5a5TrZ4Q+tflN9Ar9HgxGQ0nkaCHF16RfpIbpUMEirdp/+SqA="
    )

    # 详情页 HTTP 请求头，尽量贴近浏览器以降低触发验证码概率（Cookie 过期后可能需更新或走浏览器回退）
    _DETAIL_HTTP_HEADERS = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "cache-control": "no-cache",
        "dnt": "1",
        "pragma": "no-cache",
        "priority": "u=0, i",
        "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    }

    def _get_detail_via_http(self, link: str) -> str:
        """
        用 requests 拉取详情页 HTML，从 window.__INITIAL_STATE__.articleModule.postInfo.postContent 取正文。
        使用与浏览器一致的 headers（含可选 Cookie）以尽量不触发验证码；失败或页面无该数据时返回空串。
        """
        try:
            headers = dict(self._DETAIL_HTTP_HEADERS)
            cookie = (
                os.environ.get("IYIOU_HTTP_COOKIE", "").strip()
                or self._DETAIL_HTTP_DEFAULT_COOKIE
            )
            if cookie:
                headers["cookie"] = cookie
            resp = requests.get(link, timeout=15, headers=headers)
            resp.raise_for_status()
            return _get_detail_from_initial_state(resp.text)
        except Exception as e:
            self.util.info(f"详情 HTTP 拉取失败 {link}: {e}")
            return ""

    def _get_detail(self, link: str, page) -> str:
        self.util.info(f"link: {link}")
        try:
            page.goto(link, wait_until="domcontentloaded", timeout=15000)
            if not self._handle_captcha_if_present(page, "详情页"):
                return ""
            page.wait_for_selector(
                ".post-body, article .content, .article-content, .entry-content",
                timeout=12000,
            )
            html = page.content()
            soup = BeautifulSoup(html, "lxml")
            nodes = soup.select(".post-body")
            if not nodes:
                body = soup.select_one(
                    "article .content, .article-content, .entry-content"
                )
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
                browser = p.firefox.launch(
                    headless=self.util.get_crawler_headless(default=True),
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                    locale="zh-CN",
                )
                page = context.new_page()

                try:
                    page.goto(LIST_URL, wait_until="domcontentloaded", timeout=15000)
                    page.wait_for_selector(
                        ".info-item a, a[href*='/news/']", timeout=15000
                    )
                    if not self._handle_captcha_if_present(page, "列表页"):
                        entries = []
                    else:
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
                                link = "https://www.iyiou.com" + (
                                    link if link.startswith("/") else "/" + link
                                )
                            title = (a.get_text() or "").strip()
                            if link and title and link not in seen:
                                seen.add(link)
                                entries.append((link, title))
                        if not entries:
                            for a in soup.select("a[href*='/news/']"):
                                href = (a.get("href") or "").strip()
                                if not href.startswith("http"):
                                    href = "https://www.iyiou.com" + (
                                        href if href.startswith("/") else "/" + href
                                    )
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
                            break
                        # 优先用 HTTP 从 __INITIAL_STATE__ 取正文，不触发浏览器与验证码
                        desc = self._get_detail_via_http(link)
                        if not desc:
                            detail_page = context.new_page()
                            try:
                                desc = self._get_detail(link, detail_page)
                            finally:
                                detail_page.close()
                        if desc:
                            self.mark_link_as_processed(link)
                            new_articles.append(
                                {
                                    "title": title,
                                    "description": desc,
                                    "link": link,
                                    "author": "",
                                    "pub_date": self.util.current_time_string(),
                                    "kind": 1,
                                    "language": "zh-CN",
                                    "source_name": "亿欧网",
                                }
                            )
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
