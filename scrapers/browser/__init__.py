# -*- coding: UTF-8 -*-
"""无头浏览器爬虫注册表（playwright/selenium 等）。仅被 crawl_news_browser 使用。koreatimes 为样例，同源另有 simple 版。"""
from scrapers.browser.koreatimes import KoreatimesScraper

SCRAPER_REGISTRY_BROWSER = {
    "koreatimes": KoreatimesScraper,
}
