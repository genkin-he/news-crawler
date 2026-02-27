# -*- coding: UTF-8 -*-
"""简单爬虫基类：统一运行超时，子类实现 _run_impl()"""
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scrapers.base_scraper import BaseScraper


class BaseSimpleScraper(BaseScraper):
    """简单爬虫基类：run() 带最大超时，与 browser 爬虫一致"""

    RUN_TIMEOUT = 30  # 单次运行最大秒数，子类可覆盖

    def _run_impl(self):
        """实际爬取逻辑，子类实现。返回 get_stats() 的字典。"""
        raise NotImplementedError("子类必须实现 _run_impl()")

    def run(self):
        self._timed_out = False
        start = time.perf_counter()

        def on_timeout():
            self._timed_out = True

        result = self.util.execute_with_timeout(
            self._run_impl,
            timeout=getattr(self, "RUN_TIMEOUT", 30),
            on_timeout=on_timeout,
        )
        elapsed = time.perf_counter() - start
        self.stats["run_seconds"] = round(elapsed, 2)
        self.util.info(f"本次运行耗时 {elapsed:.2f}s")

        if result is None:
            self.util.error("运行超时")
            self.stats["errors"] += 1
        return self.get_stats()
