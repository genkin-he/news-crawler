# -*- coding: UTF-8 -*-
"""AP News 爬虫"""
import re
import requests
from bs4 import BeautifulSoup
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.base_scraper import BaseScraper

headers = {
    "accept": 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    "accept-language": 'zh-CN,zh;q=0.9',
    "user-agent": 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
}

class APNewsScraper(BaseScraper):
    """AP News 财经市场爬虫"""

    def __init__(self, bq_client):
        super().__init__('apnews', bq_client)
        self.base_url = "https://apnews.com"
        self.target_url = "https://apnews.com/hub/financial-markets"

    def get_detail(self, link):
        """获取文章详情"""
        self.util.info(f"link: {link}")

        try:
            response = requests.get(link, headers=headers, timeout=15)
            if response.status_code == 200:
                response.encoding = 'utf-8'
                resp = response.text

                if "Access Restricted" in resp:
                    raise Exception("Connection reset by peer")

                body = BeautifulSoup(resp, "lxml")
                content_wrappers = body.select(".RichTextStoryBody")

                if len(content_wrappers) == 0:
                    return ""

                soup = content_wrappers[0]

                # 删除广告元素
                ad_elements = soup.select("div")
                for element in ad_elements:
                    element.decompose()

                # 删除最后两个 p 标签
                p_elements = soup.select("p")
                if len(p_elements) >= 2:
                    p_elements[-1].decompose()
                    p_elements[-2].decompose()

                result = str(soup)
                result = result.replace('\n', '').replace('\r', '')
                return result
            else:
                self.util.error(f"request: {link} error: {response}")
                return ""

        except Exception as e:
            self.util.error(f"request: {link} error: {str(e)}")
            if "Access Restricted" in str(e):
                raise
            self.stats['errors'] += 1
            return ""

    def run(self):
        """执行爬虫：只处理时间戳为「x mins ago」的条目，其余过滤"""
        # 只认 "N min ago" / "N mins ago"，其余（Yesterday、February 21 等）跳过
        mins_ago_re = re.compile(r"\d+\s*min(s)?\s*ago", re.I)

        try:
            self.util.info("开始爬取 AP News...")
            new_articles = []

            response = requests.get(self.target_url, headers=headers, timeout=15)
            if response.status_code == 200:
                response.encoding = 'utf-8'
                body = response.text
                soup = BeautifulSoup(body, "lxml")
                items = soup.select(".PageList-items-item")

                self.util.info(f"列表条目: {len(items)}")

                for item in items:
                    try:
                        time_el = item.select_one(".Timestamp-template")
                        time_text = (time_el.get_text(strip=True) or "") if time_el else ""
                        if not mins_ago_re.search(time_text):
                            continue

                        link_el = item.select_one("h3.PagePromo-title a")
                        if not link_el or not link_el.get("href"):
                            continue
                        link = str(link_el["href"])
                        title = str(link_el.get_text(strip=True) or "").replace("\n", "")

                        if self.is_link_exists(link):
                            self.util.info(f"exists link: {link}")
                            self.stats["skipped"] += 1
                            continue

                        description = self.get_detail(link)
                        if description:
                            new_articles.append({
                                "title": title,
                                "description": description,
                                "link": link,
                                "author": "apnews",
                                "pub_date": self.util.current_time_string(),
                                "kind": 1,
                                "language": "en",
                                "source_name": "美联社",
                            })

                    except Exception as e:
                        error_msg = str(e)
                        if "Access Restricted" in error_msg:
                            self.util.error("访问受限，停止爬取")
                            break
                        self.util.error(f"解析文章失败: {error_msg}")
                        self.stats["errors"] += 1
                        continue

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
