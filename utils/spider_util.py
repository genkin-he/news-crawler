from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import threading
import time
import traceback
import random
from typing import Dict, Optional
import ftfy


class SpiderUtil:
    def __init__(self, notify=True, name=None):
        # 日志前缀：优先使用传入的 name，否则从调用栈取文件名
        if name is not None:
            self.current_file = name
        else:
            stack = traceback.extract_stack()
            filename = os.path.basename(stack[-2].filename)
            self.current_file = filename.split(".")[0]
        self.path = "./news/scripts/util/urls.json"
        self.notify = notify
        # Google Cloud 会采集 stdout，输出 JSON 带 severity 时会在 Logging 中显示为 ERROR/INFO
        self._structured_log = bool(os.getenv("K_SERVICE") or os.getenv("FUNCTION_TARGET"))

    def info(self, message):
        if self._structured_log:
            print(json.dumps({"severity": "INFO", "message": f"[{self.current_file}] {message}"}, ensure_ascii=False))
        else:
            print(f"[\033[32m{self.current_file}\033[0m] {message}")

    def error(self, message):
        if self._structured_log:
            print(json.dumps({"severity": "ERROR", "message": f"[{self.current_file}] {message}"}, ensure_ascii=False))
        else:
            print(f"[\033[31m{self.current_file}\033[0m] {message}")

    def should_run_by_minute(self, divisor=10):
        """
        检查当前分钟数是否能被指定数字整除
        Args:
            divisor: 除数，默认为 10
        Returns:
            bool: 如果当前分钟数能被除数整除则返回 True，否则返回 False
        """
        current_time = datetime.now()
        current_minute = current_time.minute
        if current_minute % divisor == 0:
            self.info("当前分钟数 {} 能被{}整除，可以执行任务".format(current_minute, divisor))
            return True
        else:
            self.info("当前分钟数 {} 不能被{}整除，跳过执行".format(current_minute, divisor))
            return False

    # history_posts 已废弃，改用 BigQuery 去重

    def fix_text(self, text):
        """
        解析文本，将文本中的特殊字符转换为标准字符
        """
        return ftfy.fix_text(text)

    def parse_time(self, time_str, format):
        """
        将给定的时间字符串解析为本地时间，并返回格式化后的时间字符串。

        参数：
        time_str (str): 要解析的时间字符串。
        format (str): 时间字符串的格式。

        返回：
        str: 格式化后的本地时间字符串。
        """
        timeObj = datetime.strptime(time_str, format)
        local_time = timeObj + timedelta(hours=8)
        return local_time.strftime("%Y-%m-%d %H:%M:%S")

    def has_chinese(self, string):
        """
        检查字符串中是否包含中文字符。

        参数：
        string (str): 要检查的字符串。

        返回：
        bool: 如果字符串中包含中文字符，返回 True；否则返回 False。
        """
        for ch in string:
            if "\u4e00" <= ch <= "\u9fff":
                return True
        return False

    def current_time(self):
        """
        获取当前的本地时间，时区为 UTC+8。

        返回：
        datetime: 当前的本地时间。
        """
        return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))

    def md5(self, string):
        """
        计算给定字符串的 MD5 哈希值。

        参数：
        string (str): 要计算哈希值的字符串。

        返回：
        str: 字符串的 MD5 哈希值。
        """
        return hashlib.md5(string.encode()).hexdigest()

    def current_time_string(self):
        """
        获取当前的本地时间字符串，格式为"YYYY-MM-DD HH:MM:SS"。

        返回：
        str: 当前的本地时间字符串。
        """
        return self.current_time().strftime("%Y-%m-%d %H:%M:%S")

    def convert_utc_to_local(self, timestamp, tz=timezone.utc):
        """
        将传入的时间戳转换为本地时间（UTC+8），并返回格式化后的时间字符串。

        参数：
        timestamp (int/str): 要转换的时间戳，可以是整数或字符串。

        返回：
        str: 格式化后的本地时间字符串，格式为"YYYY-MM-DD HH:MM:SS"。
        """
        if isinstance(timestamp, str):
            timestamp = float(timestamp)
        utc_time = datetime.fromtimestamp(timestamp, tz)
        local_time = utc_time.astimezone(timezone(timedelta(hours=8)))
        return local_time.strftime("%Y-%m-%d %H:%M:%S")

    def append_to_temp_file(self, file_path, data):
        try:
            dir_path = os.path.dirname(file_path)
            if dir_path and not os.path.isdir(dir_path):
                os.makedirs(dir_path, exist_ok=True)
            if not os.path.exists(file_path):
                with open(file_path, "w") as file:
                    pass
            with open(file_path, "a") as file:
                file.write(data)
        except Exception as e:
            # 捕获异常并打印错误信息
            self.error(f"写入临时文件过程中发生错误：{str(e)}")

    def log_action_error(self, error_message):
        error_message = f"#{self.current_file} {error_message}"
        # 打印错误信息
        self.error(error_message)
        # 将错误信息追加到临时文件中
        if self.notify:
            # 定义临时文件路径
            temp_file_path = "./tmp/action_errors.log"
            # 如果错误信息长度超过 100，截取前 100 个字符并换行
            if len(error_message) > 100:
                error_message = error_message[:100] + "\n"
            self.append_to_temp_file(temp_file_path, error_message + "\n")
        return

    def get_env_variable(self, key, fallback):
        """
        获取环境变量的值，如果不存在则返回默认值

        参数：
        key (str): 环境变量的键
        fallback (str): 如果环境变量不存在时返回的默认值

        返回：
        str: 环境变量的值或默认值
        """
        return os.getenv(key, fallback)

    def get_crawler_headless(self, default: bool = True) -> bool:
        """
        是否以无头模式运行浏览器（从环境变量 CRAWLER_HEADLESS 读取，通用方法）。

        参数：
        default (bool): 环境变量未设置或无法解析时的默认值

        返回：
        bool: True 表示无头模式，False 表示有界面
        """
        raw = os.getenv("CRAWLER_HEADLESS", str(default)).strip().lower()
        return raw in ("1", "true", "yes")

    def execute_with_timeout(self, func, *args, timeout=10, on_timeout=None, **kwargs):
        """
        接受一个函数，执行这个函数并设置超时时间，同时统计函数的执行时间。

        参数：
        func (callable): 要执行的函数
        *args: 传递给函数的位置参数
        timeout (int): 超时时间，单位为秒
        on_timeout (callable): 超时时的回调（无参），用于通知业务层“已超时”，便于工作线程跳过写入等
        **kwargs: 传递给函数的关键字参数

        返回：
        执行结果（若在超时内完成）；None 若超时
        """
        stack = traceback.extract_stack()
        filename = os.path.basename(stack[-2].filename)
        lineno = stack[-2].lineno

        self.info(f"{filename}#{lineno} start executing...")

        class FuncThread(threading.Thread):
            def __init__(self, func, *args, **kwargs):
                threading.Thread.__init__(self)
                self.func = func
                self.args = args
                self.kwargs = kwargs
                self.result = None
                self.execution_time = None

            def run(self):
                start_time = time.time()
                try:
                    self.result = self.func(*self.args, **self.kwargs)
                except Exception as e:
                    traceback.print_exc()
                    self._log_action_error(f"#{lineno} error: {repr(e)}\n")
                finally:
                    end_time = time.time()
                    self.execution_time = end_time - start_time

            def _log_action_error(self, error_message):
                self._outer.log_action_error(error_message)

        thread_kwargs = {k: v for k, v in kwargs.items() if k != "on_timeout"}
        thread = FuncThread(func, *args, **thread_kwargs)
        thread._outer = self
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            if callable(on_timeout):
                on_timeout()
            return None
        self.info(
            f"Function #{filename}#{lineno} executed in {thread.execution_time:.3f} seconds."
        )
        return thread.result

    # write_json_to_file 已废弃，改用 BigQuery 客户端

    def contains_language(self, text, languages=None):
        """
        判断文本是否包含指定的语言字符。

        参数：
        text (str): 要检查的文本
        languages (list): 要检查的语言列表，支持以下值：
            'japanese' - 日语
            'korean' - 韩语
            'french' - 法语
            'spanish' - 西班牙语
            默认为 ['japanese']

        返回：
        bool: 如果文本包含指定语言的字符，返回 True；否则返回 False
        """
        if not text:
            return False

        # 默认检查中文和英文
        if languages is None:
            languages = ["japanese"]

        for ch in text:
            # 检查日语
            if "japanese" in languages and (
                "\u3040" <= ch <= "\u309f"  # 平假名
                or "\u30a0" <= ch <= "\u30ff"  # 片假名
                or "\u4e00" <= ch <= "\u9fff"  # 汉字
            ):
                return True
            # 检查韩语
            if "korean" in languages and "\uac00" <= ch <= "\ud7a3":
                return True
            # 检查法语/西班牙语（主要检查特殊字符）
            if (
                "french" in languages or "spanish" in languages
            ) and ch in "éèêëàâäôöûüçñ":
                return True

        return False

    _proxy_pools = None  # 类变量用于存储代理池

    @property
    def proxy_pools(self):
        """懒加载代理池"""
        if self._proxy_pools is None:
            try:
                with open("./news/scripts/util/proxy_pool.json", "r") as f:
                    self._proxy_pools = json.load(f)
            except Exception as e:
                self.info(f"加载代理池失败：{str(e)}")
                self._proxy_pools = []
        return self._proxy_pools

    def get_random_proxy(self, region: str = "GLOBAL") -> Optional[Dict[str, str]]:
        """从代理池中根据地区随机选择一个代理"""
        try:
            region_proxies = [
                proxy for proxy in self.proxy_pools if proxy.get("region") == region
            ]
            if not region_proxies:
                self.info(f"没有找到 {region} 地区的代理")
                return None
            return random.choice(region_proxies)
        except Exception as e:
            self.info(f"获取随机代理时发生错误：{str(e)}")
            return None
