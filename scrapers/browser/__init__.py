# -*- coding: UTF-8 -*-
"""无头浏览器爬虫注册表（playwright/selenium 等）。仅被 crawl_news_browser 使用。"""
from scrapers.browser.datacenterdynamics import DatacenterdynamicsScraper
from scrapers.browser.bloomberg import BloombergScraper
from scrapers.browser.iyiou import IyiouScraper
from scrapers.browser.infocastfn import InfocastfnScraper

SCRAPER_REGISTRY_BROWSER = {
    "datacenterdynamics": DatacenterdynamicsScraper,
    "bloomberg": BloombergScraper,
    "iyiou": IyiouScraper,
    "infocastfn": InfocastfnScraper,
}
