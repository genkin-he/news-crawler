# -*- coding: UTF-8 -*-
"""简单爬虫统一 HTTP 客户端：优先 curl_cffi（浏览器指纹），失败回退 requests"""
import requests

try:
    from curl_cffi import requests as curl_requests
    _CURL_AVAILABLE = True
except ImportError:
    _CURL_AVAILABLE = False


def get(url: str, headers=None, timeout: int = 18, **kwargs):
    """GET 请求，优先 curl_cffi impersonate chrome，失败则 requests。"""
    headers = headers or {}
    if _CURL_AVAILABLE:
        try:
            return curl_requests.get(
                url, headers=headers, timeout=timeout, impersonate="chrome", **kwargs
            )
        except Exception:
            pass
    return requests.get(url, headers=headers, timeout=timeout, **kwargs)


def post(url: str, data=None, headers=None, timeout: int = 18, **kwargs):
    """POST 请求，优先 curl_cffi impersonate chrome，失败则 requests。"""
    headers = headers or {}
    if _CURL_AVAILABLE:
        try:
            return curl_requests.post(
                url, data=data, headers=headers, timeout=timeout,
                impersonate="chrome", **kwargs
            )
        except Exception:
            pass
    return requests.post(url, data=data, headers=headers, timeout=timeout, **kwargs)
