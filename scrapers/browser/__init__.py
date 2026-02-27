# -*- coding: UTF-8 -*-
"""无头浏览器爬虫注册表（playwright/selenium 等）。仅被 crawl_news_browser 使用。STCN 已迁至 simple/，仅部署 Cloud Functions 即可跑。"""
from scrapers.browser.koreatimes import KoreatimesScraper

SCRAPER_REGISTRY_BROWSER = {
    "koreatimes": KoreatimesScraper,
}
