# -*- coding: UTF-8 -*-
"""FX168 爬虫 — 从资讯页 https://www.fx168news.com/info/001 解析 __NEXT_DATA__ 列表与详情"""
import json
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get

INFO_URL = "https://www.fx168news.com/info/001"
BASE_URL = "https://www.fx168news.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.fx168news.com/",
}
MAX_ARTICLES = 4

# 文末免责声明起头，从包含该内容的 div 起整块删掉
_FOOTER_MARKER = "1. 欢迎转载"


def _strip_fx168_footer(html: str) -> str:
    """去掉正文末尾「欢迎转载…」「所有内容仅供参考…」整块免责声明。"""
    if not html or _FOOTER_MARKER not in html:
        return html
    idx = html.find(_FOOTER_MARKER)
    pos = idx
    start = -1
    while True:
        pos = html.rfind("<div", 0, pos)
        if pos == -1:
            break
        if "border-top" in html[pos:idx]:
            start = pos
            break
    if start == -1:
        return html
    return html[:start].rstrip()


def _strip_xinshikong_blocks(html: str) -> str:
    """去掉正文中的「新时空声明」「转载自新时空」「市场有风险…」「敬告读者…」等免责/声明段。"""
    if not html:
        return html
    # 去掉含「新时空声明」的整段（只匹配单个 <p>…</p>，不跨段；允许 </span> 等在内）
    html = re.sub(
        r"<p[^>]*>(?:(?!</p>).)*?新时空声明(?:(?!</p>).)*?交易风险自担(?:(?!</p>).)*</p>",
        "",
        html,
        flags=re.DOTALL,
    )
    # 去掉「本文转载自新时空，原文链接:…」整段（单段）
    html = re.sub(
        r"<p[^>]*>(?:(?!</p>).)*?本文转载自新时空，原文链接:(?:(?!</p>).)*?</p>",
        "",
        html,
        flags=re.DOTALL,
    )
    # 去掉「市场有风险，投资需谨慎。本文为AI…不构成个人投资建议。」整段（可能单独成 <p> 或纯文本）
    html = re.sub(
        r"<p[^>]*>\s*（市场有风险，投资需谨慎。本文为AI基于第三方数据生成，仅供参考，不构成个人投资建议。）\s*</p>",
        "",
        html,
    )
    html = re.sub(
        r"（市场有风险，投资需谨慎。本文为AI基于第三方数据生成，仅供参考，不构成个人投资建议。）",
        "",
        html,
    )
    # 去掉含「敬告读者：本文为转载发布…FX168财经仅提供信息发布平台…」整段（可能在 <p> 或纯文本）
    html = re.sub(
        r"<p[^>]*>(?:(?!</p>).)*?敬告读者(?:(?!</p>).)*?信息发布平台(?:(?!</p>).)*</p>",
        "",
        html,
        flags=re.DOTALL,
    )
    html = re.sub(
        r"敬告读者：本文为转载发布[\s\S]*?细微删改。?\s*",
        "",
        html,
    )
    html = re.sub(r"\n+", "\n", html).strip()
    # 去掉删除内容后残留的空 <p></p>
    html = re.sub(r"<p>\s*</p>", "", html)
    return html.strip()


def _extract_next_data(html: str) -> dict | None:
    """从页面 HTML 中解析 __NEXT_DATA__ 的 JSON。"""
    marker = "__NEXT_DATA__"
    idx = html.find(marker)
    if idx == -1:
        return None
    start = html.find(">", idx) + 1
    if start <= 0:
        return None
    end = html.find("</script>", start)
    if end == -1:
        return None
    raw = html[start:end].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


class Fx168Scraper(BaseSimpleScraper):
    """FX168 爬虫 — 请求 /info/001 取列表，请求文章页取详情正文"""

    def __init__(self, bq_client):
        super().__init__("fx168", bq_client)

    def _get_detail(self, link: str) -> str:
        """请求文章页，从 __NEXT_DATA__.getNewsDetailData.newsContent 取正文。"""
        self.util.info(f"detail: {link}")
        try:
            resp = _get(link, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                return ""
            next_data = _extract_next_data(resp.text)
            if not next_data:
                return ""
            data = (next_data.get("props") or {}).get("pageProps") or {}
            detail = (data.get("data") or {}).get("getNewsDetailData") or {}
            return (detail.get("newsContent") or "").strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 FX168（资讯页）...")
            new_articles = []

            resp = _get(INFO_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                self.util.error(f"资讯页请求失败：HTTP {resp.status_code}")
                return self.get_stats()

            next_data = _extract_next_data(resp.text)
            if not next_data:
                self.util.error("资讯页未解析到 __NEXT_DATA__")
                return self.get_stats()

            page_data = (next_data.get("props") or {}).get("pageProps") or {}
            data = page_data.get("data") or {}
            info_list = data.get("infoListData") or {}
            items = info_list.get("items") or []

            for item in items[:MAX_ARTICLES]:
                if getattr(self, "_timed_out", False):
                    break
                url_code = (item.get("urlCode") or "").strip()
                if not url_code:
                    continue
                link = f"{BASE_URL}/article/{url_code}"
                if self.is_link_exists(link):
                    self.util.info(f"exists link: {link}")
                    continue
                title = (item.get("newsTitle") or "").strip()
                if not title:
                    continue
                pub_date = item.get("firstPublishTime") or self.util.current_time_string()
                description = _strip_fx168_footer(
                    _strip_xinshikong_blocks(self._get_detail(link))
                )
                if description:
                    self.mark_link_as_processed(link)
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": "",
                        "pub_date": pub_date,
                        "kind": 1,
                        "language": "zh-CN",
                        "source_name": "FX168",
                    })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 FX168")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"FX168 爬虫执行失败：{str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
