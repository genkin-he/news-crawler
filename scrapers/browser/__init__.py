# -*- coding: UTF-8 -*-
"""无头浏览器爬虫注册表（playwright/selenium 等）。仅被 crawl_news_browser 使用。"""
from scrapers.browser.stcn import StcnScraper
from scrapers.browser.koreatimes import KoreatimesScraper

SCRAPER_REGISTRY_BROWSER = {
    "stcn": StcnScraper,
    "koreatimes": KoreatimesScraper,
}
