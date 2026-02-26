# -*- coding: UTF-8 -*-
"""CoinLive 爬虫"""
import requests
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.base_scraper import BaseScraper

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "accept": "*/*",
    "Referer": "https://www.coinlive.com/",
}

class CoinliveScraper(BaseScraper):
    """CoinLive 加密货币新闻爬虫"""

    def __init__(self, bq_client):
        super().__init__('coinlive', bq_client)
        self.base_url = "https://www.coinlive.com/"
        self.api_url = "https://api.coinlive.com/api/v1/news-letter/list?page=1&size=10"

    def run(self):
        """执行爬虫"""
        try:
            self.util.info("开始爬取 CoinLive...")
            new_articles = []

            response = requests.get(self.api_url, headers=headers, timeout=15)
            if response.status_code == 200:
                body = response.json()
                posts = body.get("data", {}).get("list", [])

                for index, post in enumerate(posts):
                    if index >= 4:
                        break

                    try:
                        article_id = post.get("id")
                        title = post.get("title", "").strip()
                        link = post.get("url")
                        description = post.get("brief", "").strip()
                        pub_date = self.util.convert_utc_to_local(post.get("published_at"))

                        # 检查链接是否已存在
                        if self.is_link_exists(link):
                            self.util.info(f"exists link: {link}")
                            self.stats['skipped'] += 1
                            continue

                        if description:
                            new_articles.append({
                                "id": str(article_id),
                                "title": title,
                                "description": description,
                                "link": link,
                                "author": "",
                                "pub_date": pub_date,
                                "kind": 2,
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
                self.util.log_action_error(f"request error: {response.status_code}")
                self.stats['errors'] += 1

        except Exception as e:
            self.util.error(f"爬虫执行失败: {str(e)}")
            self.stats['errors'] += 1

        return self.get_stats()
