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
from scrapers.simple.koreatimes import KoreatimesScraper
from scrapers.simple.coindesk import CoindeskScraper
from scrapers.simple.nasdaq import NasdaqScraper
from scrapers.simple.cleantechnica import CleantechnicaScraper
from scrapers.simple.channelnewsasia import ChannelnewsasiaScraper
from scrapers.simple.thehill import ThehillScraper
from scrapers.simple.straitstimes import StraitstimesScraper
from scrapers.simple.vietnamnews import VietnamnewsScraper
from scrapers.simple.afp import AfpScraper
from scrapers.simple.asiaone import AsiaoneScraper
from scrapers.simple.bastillepost import BastillepostScraper
from scrapers.simple.bioon import BioonScraper
from scrapers.simple.biopharmadive import BiopharmadiveScraper
from scrapers.simple.business_standard import BusinessStandardScraper
from scrapers.simple.businesstimes import BusinesstimesScraper
from scrapers.simple.businesstimes_news import BusinesstimesNewsScraper
from scrapers.simple.businesstoday import BusinesstodayScraper
from scrapers.simple.c114 import C114Scraper
from scrapers.simple.cabotwealth import CabotwealthScraper
from scrapers.simple.cnyes import CnyesScraper
from scrapers.simple.digitalcommerce360 import Digitalcommerce360Scraper
from scrapers.simple.dotdotnews import DotdotnewsScraper
from scrapers.simple.eeetimes import EetimesScraper
from scrapers.simple.etf import EtfScraper
from scrapers.simple.fiercepharma import FiercepharmaScraper
from scrapers.simple.forex import ForexScraper
from scrapers.simple.fx168 import Fx168Scraper
from scrapers.simple.fx168_live import Fx168LiveScraper
from scrapers.simple.hibor import HiborScraper
from scrapers.simple.hk01 import Hk01Scraper
from scrapers.simple.hkej_dailynews import HkejDailynewsScraper
from scrapers.simple.hkej_instantnews import HkejInstantnewsScraper
from scrapers.simple.in_en import InEnScraper
from scrapers.simple.infoq import InfoqScraper
from scrapers.simple.insidermonkey import InsidermonkeyScraper
from scrapers.simple.investing_cn import InvestingCnScraper
from scrapers.simple.investing_us import InvestingUsScraper
from scrapers.simple.investinglive import InvestingliveScraper
from scrapers.simple.investors import InvestorsScraper
from scrapers.simple.jin10_articles import Jin10ArticlesScraper
from scrapers.simple.jinwucj import JinwucjScraper
from scrapers.simple.jinwucj_hk import JinwucjHkScraper
from scrapers.simple.leinews import LeinewsScraper
from scrapers.simple.lieyun import LieyunScraper
from scrapers.simple.marketscreener import MarketscreenerScraper
from scrapers.simple.mingpao import MingpaoScraper
from scrapers.simple.moneymorning import MoneymorningScraper
from scrapers.simple.morningstar import MorningstarScraper
from scrapers.simple.nbcnews import NbcnewsScraper
from scrapers.simple.now import NowScraper
from scrapers.simple.now_finance import NowFinanceScraper
from scrapers.simple.on import OnScraper
from scrapers.simple.orangenews import OrangenewsScraper
from scrapers.simple.panewslab import PanewslabScraper
from scrapers.simple.pharmexec import PharmexecScraper
from scrapers.simple.pingwest import PingwestScraper
from scrapers.simple.pingwest_status import PingwestStatusScraper
from scrapers.simple.reporterosdelsur import ReporterosdelsurScraper
from scrapers.simple.retailtouchpoints import RetailtouchpointsScraper
from scrapers.simple.sbr import SbrScraper
from scrapers.simple.seeitmarket import SeeitmarketScraper
from scrapers.simple.seekalpha import SeekalphaScraper
from scrapers.simple.seekalpha_articles import SeekalphaArticlesScraper
from scrapers.simple.simplywall import SimplywallScraper
from scrapers.simple.sina_us_stock import SinaUsStockScraper
from scrapers.simple.stheadline import StheadlineScraper
from scrapers.simple.stockinvest import StockinvestScraper
from scrapers.simple.stocktitan import StocktitanScraper
from scrapers.simple.talkmarkets import TalkmarketsScraper
from scrapers.simple.technews import TechnewsScraper
from scrapers.simple.timeweekly import TimeweeklyScraper
from scrapers.simple.tipranks import TipranksScraper
from scrapers.simple.tipranks_announcements import TipranksAnnouncementsScraper
from scrapers.simple.tipranks_others import TipranksOthersScraper
from scrapers.simple.tradingview import TradingviewScraper
from scrapers.simple.tvb import TvbScraper
from scrapers.simple.unusualwhales import UnusualwhalesScraper
from scrapers.simple.wallstreetcn import WallstreetcnScraper
from scrapers.simple.yahoo_finance_asia import YahooFinanceAsiaScraper
from scrapers.simple.yahoo_finance_us import YahooFinanceUsScraper
from scrapers.simple.yahoo_sg import YahooSgScraper
from scrapers.simple.yahoo_us import YahooUsScraper
from scrapers.simple.taipeitimes import TaipeitimesScraper
from scrapers.simple.forbes import ForbesScraper
from scrapers.simple.geekwire import GeekwireScraper
from scrapers.simple.marketpulse import MarketpulseScraper
from scrapers.simple.rollingout import RollingoutScraper
from scrapers.simple.scmp import ScmpScraper
from scrapers.simple.startuphub import StartuphubScraper
from scrapers.simple.statementdog import StatementdogScraper
from scrapers.simple.thebambooworks import ThebambooworksScraper
from scrapers.simple.techi import TechiScraper
from scrapers.simple.theregister import TheregisterScraper
from scrapers.simple.traderslog import TraderslogScraper
from scrapers.simple.udn import UdnScraper
from scrapers.simple.aibusiness import AibusinessScraper
from scrapers.simple.yicaiglobal import YicaiglobalScraper
from scrapers.simple.benzinga import BenzingaScraper
from scrapers.simple.businesswire import BusinesswireScraper
from scrapers.simple.cmcmarkets import CmcmarketsScraper
from scrapers.simple.coinlive_articles import CoinliveArticlesScraper
from scrapers.simple.cww import CwwScraper
from scrapers.simple.driveteslacanada import DriveteslacanadaScraper
from scrapers.simple.fidelity import FidelityScraper
from scrapers.simple.finet_live import FinetLiveScraper
from scrapers.simple.fx168_news_api import Fx168NewsApiScraper
from scrapers.simple.moneycontrol import MoneycontrolScraper
from scrapers.simple.qq import QqScraper
from scrapers.simple.sherwood import SherwoodScraper
from scrapers.simple.telegraph import TelegraphScraper

SCRAPER_REGISTRY: Dict[str, type] = {
    'techcrunch': TechCrunchScraper,
    'apnews': APNewsScraper,
    'coinlive': CoinliveScraper,
    'stcn': StcnScraper,
    'koreatimes': KoreatimesScraper,
    'coindesk': CoindeskScraper,
    'nasdaq': NasdaqScraper,
    'cleantechnica': CleantechnicaScraper,
    'channelnewsasia': ChannelnewsasiaScraper,
    'thehill': ThehillScraper,
    'straitstimes': StraitstimesScraper,
    'vietnamnews': VietnamnewsScraper,
    'afp': AfpScraper,
    'asiaone': AsiaoneScraper,
    'bastillepost': BastillepostScraper,
    'bioon': BioonScraper,
    'biopharmadive': BiopharmadiveScraper,
    'business_standard': BusinessStandardScraper,
    'businesstimes': BusinesstimesScraper,
    'businesstimes_news': BusinesstimesNewsScraper,
    'businesstoday': BusinesstodayScraper,
    'c114': C114Scraper,
    'cabotwealth': CabotwealthScraper,
    'cnyes': CnyesScraper,
    'digitalcommerce360': Digitalcommerce360Scraper,
    'dotdotnews': DotdotnewsScraper,
    'etf': EtfScraper,
    'fiercepharma': FiercepharmaScraper,
    'forex': ForexScraper,
    'fx168': Fx168Scraper,
    'fx168_live': Fx168LiveScraper,
    'hibor': HiborScraper,
    'hk01': Hk01Scraper,
    'hkej_dailynews': HkejDailynewsScraper,
    'hkej_instantnews': HkejInstantnewsScraper,
    'in_en': InEnScraper,
    'infoq': InfoqScraper,
    'insidermonkey': InsidermonkeyScraper,
    'investing_cn': InvestingCnScraper,
    'investing_us': InvestingUsScraper,
    'investinglive': InvestingliveScraper,
    'investors': InvestorsScraper,
    'jin10_articles': Jin10ArticlesScraper,
    'jinwucj': JinwucjScraper,
    'jinwucj_hk': JinwucjHkScraper,
    'leinews': LeinewsScraper,
    'lieyun': LieyunScraper,
    'marketscreener': MarketscreenerScraper,
    'mingpao': MingpaoScraper,
    'moneymorning': MoneymorningScraper,
    'morningstar': MorningstarScraper,
    'nbcnews': NbcnewsScraper,
    'now': NowScraper,
    'now_finance': NowFinanceScraper,
    'on': OnScraper,
    'orangenews': OrangenewsScraper,
    'panewslab': PanewslabScraper,
    'pharmexec': PharmexecScraper,
    'pingwest': PingwestScraper,
    'pingwest_status': PingwestStatusScraper,
    'reporterosdelsur': ReporterosdelsurScraper,
    'retailtouchpoints': RetailtouchpointsScraper,
    'sbr': SbrScraper,
    'seeitmarket': SeeitmarketScraper,
    'seekalpha': SeekalphaScraper,
    'seekalpha_articles': SeekalphaArticlesScraper,
    'simplywall': SimplywallScraper,
    'sina_us_stock': SinaUsStockScraper,
    'stheadline': StheadlineScraper,
    'stockinvest': StockinvestScraper,
    'stocktitan': StocktitanScraper,
    'talkmarkets': TalkmarketsScraper,
    'technews': TechnewsScraper,
    'timeweekly': TimeweeklyScraper,
    'tipranks': TipranksScraper,
    'tipranks_announcements': TipranksAnnouncementsScraper,
    'tipranks_others': TipranksOthersScraper,
    'tradingview': TradingviewScraper,
    'tvb': TvbScraper,
    'unusualwhales': UnusualwhalesScraper,
    'wallstreetcn': WallstreetcnScraper,
    'yahoo_finance_asia': YahooFinanceAsiaScraper,
    'yahoo_finance_us': YahooFinanceUsScraper,
    'yahoo_sg': YahooSgScraper,
    'yahoo_us': YahooUsScraper,
    'taipeitimes': TaipeitimesScraper,
    'forbes': ForbesScraper,
    'geekwire': GeekwireScraper,
    'marketpulse': MarketpulseScraper,
    'rollingout': RollingoutScraper,
    'scmp': ScmpScraper,
    'startuphub': StartuphubScraper,
    'statementdog': StatementdogScraper,
    'thebambooworks': ThebambooworksScraper,
    'techi': TechiScraper,
    'theregister': TheregisterScraper,
    'traderslog': TraderslogScraper,
    'udn': UdnScraper,
    'aibusiness': AibusinessScraper,
    'yicaiglobal': YicaiglobalScraper,
    'benzinga': BenzingaScraper,
    'businesswire': BusinesswireScraper,
    'cmcmarkets': CmcmarketsScraper,
    'coinlive_articles': CoinliveArticlesScraper,
    'cww': CwwScraper,
    'driveteslacanada': DriveteslacanadaScraper,
    'fidelity': FidelityScraper,
    'finet_live': FinetLiveScraper,
    'fx168_news_api': Fx168NewsApiScraper,
    'moneycontrol': MoneycontrolScraper,
    'sherwood': SherwoodScraper,
    'telegraph': TelegraphScraper,
    # 'qq': QqScraper, // 去重逻辑有问题
    'eeetimes': EetimesScraper, 
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
        # 一次 SQL 拉取各源最新 40 条 URL 初始化内存，后续存在性检查只查内存
        link_cache_raw = bq_client.get_latest_urls_bulk(sources, limit_per_source=20)
        link_cache = {s: set(link_cache_raw.get(s, [])) for s in sources}
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
            return {'sources': 'etf', 'test': True}

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
