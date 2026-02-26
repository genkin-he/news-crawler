# -*- coding: UTF-8 -*-
"""TechCrunch 爬虫"""
import urllib.request
from bs4 import BeautifulSoup
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.base_scraper import BaseScraper

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "cache-control": "no-cache",
    "pragma": "no-cache",
}

class TechCrunchScraper(BaseScraper):
    """TechCrunch 新闻爬虫"""

    def __init__(self, bq_client):
        super().__init__('techcrunch', bq_client)
        self.base_url = "https://techcrunch.com/"
        self.current_links = []

    def get_detail(self, link):
        """获取文章详情"""
        if link in self.current_links or "/video/" in link:
            return ""

        self.util.info(f"link: {link}")
        self.current_links.append(link)

        try:
            request = urllib.request.Request(link, None, headers)
            response = urllib.request.urlopen(request, timeout=15)

            if response.status == 200:
                resp = response.read().decode("utf-8")
                soup = BeautifulSoup(resp, "lxml")

                content = soup.select(".entry-content")
                if not content:
                    return ""

                soup = content[0]

                # 移除广告和不需要的元素
                ad_elements = soup.select(
                    ".ad-unit, .marfeel-experience-inline-cta, .wp-block-tc23-podcast-player"
                )
                for element in ad_elements:
                    element.decompose()

                return str(soup).strip()
            else:
                self.util.error(f"request: {link} error: {response}")
                return ""
        except Exception as e:
            self.util.error(f"获取详情失败 {link}: {str(e)}")
            self.stats['errors'] += 1
            return ""

    def run(self):
        """执行爬虫"""
        try:
            self.util.info("开始爬取 TechCrunch...")
            post_count = 0
            self.current_links = []
            new_articles = []

            # 请求主页
            request = urllib.request.Request(self.base_url, None, headers)
            response = urllib.request.urlopen(request, timeout=15)

            if response.status == 200:
                resp = response.read().decode("utf-8")
                soup = BeautifulSoup(resp, "lxml")
                nodes = soup.select(".wp-block-post-template > .wp-block-post")

                for node in nodes:
                    if post_count >= 3:
                        break

                    try:
                        link_elem = node.select(".loop-card__title > a")
                        title_elem = node.select(".loop-card__title")

                        if not link_elem or not title_elem:
                            continue

                        link = str(link_elem[0]["href"]).strip()
                        title = str(title_elem[0].text).strip()

                        # 检查链接是否已存在
                        if self.is_link_exists(link):
                            self.util.info(f"exists link: {link}")
                            self.stats['skipped'] += 1
                            break

                        # 获取详情
                        description = self.get_detail(link)
                        if description:
                            post_count += 1
                            new_articles.append({
                                "title": title,
                                "description": description,
                                "link": link,
                                "author": "TechCrunch",
                                "pub_date": self.util.current_time_string(),
                                "kind": 1,
                                "language": "en",
                            })
                    except Exception as e:
                        self.util.error(f"解析文章失败: {str(e)}")
                        self.stats['errors'] += 1
                        continue

                # 批量保存文章
                if new_articles:
                    self.save_articles(new_articles)
                    self.util.info(f"成功爬取 {len(new_articles)} 篇文章")
            else:
                self.util.log_action_error(f"request error: {response}")
                self.stats['errors'] += 1

        except Exception as e:
            self.util.error(f"爬虫执行失败: {str(e)}")
            self.stats['errors'] += 1

        return self.get_stats()
