# -*- coding: UTF-8 -*-
"""Cloud Functions 入口：简单爬虫(crawl_news) + 无头浏览器爬虫(crawl_news_browser)"""
import functions_framework
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Any
import json
import sys
import yaml
import traceback

from utils.bigquery_client import BigQueryClient
from utils.spider_util import SpiderUtil

# 测试模式用：不连接 BigQuery，仅做逻辑跑通
class MockBigQueryClient:
    """测试模式下使用的假 BigQuery 客户端，不依赖 GCP 与网络"""

    def link_exists(self, link: str, source: Optional[str] = None) -> bool:
        return False

    def insert_article(self, article: Dict) -> bool:
        SpiderUtil(name="test").info("save_article: " + json.dumps(article, ensure_ascii=False, indent=2))
        return True

    def insert_articles(self, articles: List[Dict]) -> bool:
        SpiderUtil(name="test").info("save_articles: " + json.dumps(articles, ensure_ascii=False, indent=2))
        return True


# 简单爬虫（仅 requests/BeautifulSoup，无浏览器，可部署到 Cloud Functions）
from scrapers.simple.techcrunch import TechCrunchScraper
from scrapers.simple.apnews import APNewsScraper
from scrapers.simple.coinlive import CoinliveScraper
from scrapers.simple.stcn import StcnScraper

SCRAPER_REGISTRY: Dict[str, type] = {
    'techcrunch': TechCrunchScraper,
    'apnews': APNewsScraper,
    'coinlive': CoinliveScraper,
    'stcn': StcnScraper,
}


def _run_crawl(request: Any, scraper_registry: Dict[str, type]) -> tuple:
    """
    公共爬取逻辑。sources=all 时使用注册表 keys，无需在 config 中再配一份。
    """
    request_json = request.get_json(silent=True) or {}
    sources_param = request_json.get('sources', 'all')
    test_mode = request_json.get('test', False)

    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    if sources_param == 'all':
        sources = list(scraper_registry.keys())
    else:
        sources = [s.strip() for s in sources_param.split(',')]
        sources = [s for s in sources if s in scraper_registry]

    if not sources:
        return {
            'success': False,
            'error': '没有找到可用的新闻源',
            'available_sources': list(scraper_registry.keys())
        }, 400

    util = SpiderUtil(name="crawl")
    util.info(f"开始爬取新闻源: {', '.join(sources)}")
    util.info(f"测试模式: {test_mode}")

    if test_mode:
        bq_client = MockBigQueryClient()
        util.info("测试模式：未连接 BigQuery，不会写入数据")
    else:
        bq_client = BigQueryClient(log_util=util)
        # 按源一次性拉取最新 20 条 URL 初始化内存，后续存在性检查只查内存
        link_cache = {}
        for source in sources:
            links = bq_client.get_latest_urls(source, limit=20)
            link_cache[source] = set(links)
        bq_client.set_link_cache(link_cache)
        util.info(f"已加载各源最新 URL 到内存: {[(s, len(link_cache[s])) for s in sources]}")

    results = {}
    errors = []
    max_workers = config.get('concurrency', {}).get('max_workers', 5)
    timeout = config.get('concurrency', {}).get('timeout_per_scraper', 60)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for source in sources:
            scraper_class = scraper_registry.get(source)
            if scraper_class:
                try:
                    scraper = scraper_class(bq_client)
                    future = executor.submit(scraper.run)
                    futures[future] = source
                except Exception as e:
                    errors.append(f"{source}: 初始化失败 - {str(e)}")
                    util.error(f"初始化爬虫失败 [{source}]: {str(e)}")

        for future in as_completed(futures, timeout=max_workers * timeout):
            source = futures[future]
            try:
                result = future.result(timeout=timeout)
                results[source] = result
                util.info(f"爬虫 [{source}] 完成: {result}")
            except Exception as e:
                error_msg = f"{source}: {str(e)}"
                errors.append(error_msg)
                util.error(f"爬虫执行失败 [{source}]: {str(e)}")
                util.error(traceback.format_exc())
                results[source] = {'new_articles': 0, 'skipped': 0, 'errors': 1}

    total_new_articles = sum(r.get('new_articles', 0) for r in results.values())
    total_skipped = sum(r.get('skipped', 0) for r in results.values())
    total_errors = sum(r.get('errors', 0) for r in results.values())

    response = {
        'success': len(errors) == 0 and total_errors == 0,
        'total_new_articles': total_new_articles,
        'total_skipped': total_skipped,
        'total_errors': total_errors,
        'results': results,
        'errors': errors,
        'test_mode': test_mode
    }
    util.info(f"爬取完成: 新文章 {total_new_articles}，跳过 {total_skipped}，错误 {total_errors}")
    return response, 200


@functions_framework.http
def crawl_news(request):
    """
    简单爬虫 Cloud Function（requests/BeautifulSoup，无浏览器）。

    请求参数（JSON body）：
    - sources: 逗号分隔或 "all"，默认 "all"
    - test: true 时不写 BigQuery、不依赖 GCP
    """
    try:
        return _run_crawl(request, SCRAPER_REGISTRY)
    except Exception as e:
        SpiderUtil(name="crawl").error(traceback.format_exc())
        return {'success': False, 'error': str(e), 'traceback': traceback.format_exc()}, 500


@functions_framework.http
def crawl_news_browser(request):
    """
    无头浏览器爬虫 Cloud Function（需 playwright/selenium 等，使用 requirements-browser.txt 部署）。

    请求参数同 crawl_news：sources、test。
    """
    try:
        # 懒加载：避免简单爬虫部署时导入 playwright 等重依赖
        from scrapers.browser import SCRAPER_REGISTRY_BROWSER
        return _run_crawl(request, SCRAPER_REGISTRY_BROWSER)
    except Exception as e:
        SpiderUtil(name="crawl").error(traceback.format_exc())
        return {'success': False, 'error': str(e), 'traceback': traceback.format_exc()}, 500


# 本地测试入口
if __name__ == '__main__':
    class MockRequest:
        def get_json(self, silent=False):
            return {'sources': 'all', 'test': True}

    log = SpiderUtil(name="main")
    use_browser = len(sys.argv) > 1 and sys.argv[1] == 'browser'
    if use_browser:
        log.info("本地测试：无头浏览器爬虫 (crawl_news_browser)")
        result, status = crawl_news_browser(MockRequest())
    else:
        log.info("本地测试：简单爬虫 (crawl_news)，传参 browser 可测无头浏览器爬虫")
        result, status = crawl_news(MockRequest())
    log.info(f"状态码: {status}")
    log.info(f"结果: {result}")
