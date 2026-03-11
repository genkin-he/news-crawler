# -*- coding: UTF-8 -*-
"""Statement Dog 爬虫 — requests + BeautifulSoup"""
import sys
import os

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.simple.base_simple_scraper import BaseSimpleScraper
from scrapers.simple.http_client import get as _get, post as _post

LIST_URL = "https://statementdog.com/news/latest"

HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'zh-CN,zh;q=0.9',
    'cache-control': 'max-age=0',
    'if-none-match': 'W/"809c58081575ba6851f3e11365bca706"',
    'priority': 'u=0, i',
    'referer': 'https://statementdog.com/news',
    'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
    "cookie": 'statementdog_device_id=S2lrNHB1YnVnTTh0aGcyZFJTUk1idko2aWxpVHVwVXVla0taelRITHdIbkFjVFd0b0xwT1F4RUpDYTJrK0ZUUC0tc05yanVZYzc3dEk3VDFRMVRNRXYyZz09--70223dcbb8258ed7870f735b8375fee5dbe00a3e; easy_ab=da74befb-e996-48aa-b43f-f4fa29b8c555; _ga=GA1.1.1162741084.1761903112; aws_news_and_reports_impression={%22news%22:[%2214889%22%2C%2214895%22]}; AMP_0ab77a441f=JTdCJTIyZGV2aWNlSWQlMjIlM0ElMjI1M2M0ZjI0Ny0xMmNiLTRmYTktOGYwOC04YzAzNDAxMWNlMzMlMjIlMkMlMjJzZXNzaW9uSWQlMjIlM0ExNzYxOTAzMTEyMjI3JTJDJTIyb3B0T3V0JTIyJTNBZmFsc2UlMkMlMjJwYWdlQ291bnRlciUyMiUzQTAlN0Q=; g_state={"i_l":0,"i_ll":1761903155667,"i_b":"kPoPB9X9G83Lv2DUNR/m/hGcAX2IKd4X/48g4F9SKBI"}; _statementdog_session_v2=akihw9gs8S0IKfGTqxAfuoRpQUC%2FU6AhX5JM6%2Fw732eZXl08YobxXoPd9s1hho%2FuBrMit0tgKDohz4wm6n3te35MoGIKW3EjT4IeKMwRLZQDPaAZSULvs3F5wiKkM3GlA4INkRgE9njYog1xrQWVZ7kG%2B7CTdIFpwUMnRoMgiZwBCdD6lgQjtFui3Xt6NUfCf30jjQglB%2FLE8JI3Dc09bS5TUTJy7WGhgf9WtP%2FLDzpikow0O8PYXgURdvpTQwuUdotY%2BXbQD88KrpQtpFEd5MN4CUQAOH3JfP4N4U02rcKbPH59LUR8bDSmXin6tTOZedEQmD2J--mLiShGX2EErFQmW%2B--KPRGfez2zuhjVJKMx3FexQ%3D%3D; _ga_K9Y9Y589MM=GS2.1.s1761903111$o1$g1$t1761903156$j15$l0$h0',
}

class StatementdogScraper(BaseSimpleScraper):
    """Statement Dog 爬虫"""

    def __init__(self, bq_client):
        super().__init__("statementdog", bq_client)

    def _get_detail(self, link: str) -> str:
        try:
            resp = _get(link, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            node = soup.select_one(".main-news-content")
            if not node:
                return ""
            for el in node.select(".main-news-title, .main-news-time, .main-news-tag-section, script, picture, .main-news-editors"):
                el.decompose()
            return str(node).strip()
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {e}")
            return ""

    def _run_impl(self):
        try:
            self.util.info("开始爬取 Statement Dog...")
            new_articles = []
            resp = _get(LIST_URL, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                self.util.error("列表请求失败")
                return self.get_stats()
            soup = BeautifulSoup(resp.text, "lxml")
            for node in soup.select(".statementdog-news-list-item-link")[:5]:
                if getattr(self, "_timed_out", False):
                    break
                link = (node.get("href") or "").strip()
                title = (node.get("data-title") or "").strip()
                if not link or not title or self.is_link_exists(link):
                    continue
                description = self._get_detail(link)
                if description:
                    self.mark_link_as_processed(link)
                    new_articles.append({
                        "title": title,
                        "description": description,
                        "link": link,
                        "author": "",
                        "pub_date": self.util.current_time_string(),
                        "kind": 1,
                        "language": "zh-HK",
                        "source_name": "财报狗",
                    })

            if getattr(self, "_timed_out", False):
                self.util.info("已超时，跳过写入")
            elif new_articles:
                self.save_articles(new_articles)
                self.util.info(f"成功爬取 {len(new_articles)} 篇 Statement Dog")
            else:
                self.util.info("无新增文章")
        except Exception as e:
            self.util.error(f"Statement Dog 爬虫执行失败：{str(e)}")
            self.stats["errors"] += 1
        return self.get_stats()
