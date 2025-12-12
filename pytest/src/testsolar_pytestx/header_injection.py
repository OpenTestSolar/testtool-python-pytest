"""
HTTP请求头注入模块

该模块用于在pytest测试执行过程中，自动向HTTP请求注入测试用例标识信息。
支持requests和httplib/http.client两种HTTP库。
"""

import threading
from typing import Optional, Callable, Any, Dict

from loguru import logger


# ============ 上下文管理 ============
# 用于存储当前测试用例的nodeid
_test_context = threading.local()

# 原始请求方法引用
_original_requests_request: Optional[Callable[..., Any]] = None
_original_httplib_request: Optional[Callable[..., Any]] = None
_original_httpx_client_request: Optional[Callable[..., Any]] = None
_original_httpx_async_client_request: Optional[Callable[..., Any]] = None


def get_current_test_nodeid() -> Optional[str]:
    """获取当前测试用例的nodeid"""
    return getattr(_test_context, "nodeid", None)


def set_current_test_nodeid(nodeid: Optional[str]) -> None:
    """设置当前测试用例的nodeid"""
    _test_context.nodeid = nodeid


# ============ Header 注入逻辑 ============
def _inject_header_to_dict(headers: Optional[Dict[str, Any]], nodeid: str) -> Dict[str, Any]:
    """
    向请求头字典注入X-Testsolar-Testcase

    Args:
        headers: 原始请求头字典
        nodeid: 测试用例的nodeid

    Returns:
        注入后的请求头字典
    """
    if headers is None:
        headers = {}
    elif not isinstance(headers, dict):
        # 如果headers不是dict，创建新dict
        headers = dict(headers)
    else:
        # 创建副本避免修改原始dict
        headers = headers.copy()

    headers["X-Testsolar-Testcase"] = nodeid
    return headers


# ============ Monkey Patch 实现 ============
def _patch_requests() -> None:
    """Patch requests库的Session.request方法"""
    try:
        import requests  # type: ignore[import]

        global _original_requests_request

        if _original_requests_request is not None:
            # 已经patch过了
            return

        _original_requests_request = requests.Session.request

        def _patched_request(self: Any, method: str, url: str, **kwargs: Any) -> Any:
            nodeid = get_current_test_nodeid()
            if nodeid:
                headers = kwargs.get("headers")
                kwargs["headers"] = _inject_header_to_dict(headers, nodeid)

            return _original_requests_request(self, method, url, **kwargs)

        requests.Session.request = _patched_request
        logger.info("Successfully patched requests.Session.request")

    except ImportError:
        logger.debug("requests library not installed, skip patching")
    except Exception as e:
        logger.error(f"Failed to patch requests: {e}")


def _patch_httplib() -> None:
    """Patch httplib/http.client的HTTPConnection.request方法"""
    try:
        # Python 2/3 兼容
        try:
            import http.client as httplib
        except ImportError:
            import httplib  # type: ignore

        global _original_httplib_request

        if _original_httplib_request is not None:
            # 已经patch过了
            return

        _original_httplib_request = httplib.HTTPConnection.request

        def _patched_httplib_request(
            self: Any,
            method: str,
            url: str,
            body: Any = None,
            headers: Any = None,
            **kwargs: Any,
        ) -> Any:
            # 通过判定函数检查是否需要注入
            final_headers: Any = headers
            nodeid = get_current_test_nodeid()
            if nodeid:
                # httplib的headers参数默认是{}而不是None
                if final_headers is None:
                    final_headers = {"X-Testsolar-Testcase": nodeid}
                else:
                    # 创建副本避免修改原始headers
                    new_headers = dict(final_headers)
                    new_headers["X-Testsolar-Testcase"] = nodeid
                    final_headers = new_headers

            return _original_httplib_request(self, method, url, body, final_headers, **kwargs)

        httplib.HTTPConnection.request = _patched_httplib_request  # type: ignore[method-assign]
        logger.info("Successfully patched httplib.HTTPConnection.request")

    except ImportError:
        logger.debug("httplib library not available, skip patching")
    except Exception as e:
        logger.error(f"Failed to patch httplib: {e}")


def _patch_httpx() -> None:
    """Patch httpx库的Client.request和AsyncClient.request方法"""
    try:
        import httpx  # type: ignore[import]

        global _original_httpx_client_request
        global _original_httpx_async_client_request

        # Patch Sync Client
        if _original_httpx_client_request is None:
            _original_httpx_client_request = httpx.Client.request

            def _patched_httpx_request(self: Any, method: str, url: str, **kwargs: Any) -> Any:
                nodeid = get_current_test_nodeid()
                if nodeid:
                    headers = kwargs.get("headers")
                    kwargs["headers"] = _inject_header_to_dict(headers, nodeid)

                if _original_httpx_client_request:
                    return _original_httpx_client_request(self, method, url, **kwargs)
                return None

            httpx.Client.request = _patched_httpx_request
            logger.info("Successfully patched httpx.Client.request")

        # Patch Async Client
        if _original_httpx_async_client_request is None:
            _original_httpx_async_client_request = httpx.AsyncClient.request

            async def _patched_httpx_async_request(
                self: Any, method: str, url: str, **kwargs: Any
            ) -> Any:
                nodeid = get_current_test_nodeid()
                if nodeid:
                    headers = kwargs.get("headers")
                    kwargs["headers"] = _inject_header_to_dict(headers, nodeid)

                if _original_httpx_async_client_request:
                    return await _original_httpx_async_client_request(self, method, url, **kwargs)
                return None

            httpx.AsyncClient.request = _patched_httpx_async_request
            logger.info("Successfully patched httpx.AsyncClient.request")

    except ImportError:
        logger.debug("httpx library not installed, skip patching")
    except Exception as e:
        logger.error(f"Failed to patch httpx: {e}")


# ============ 公共接口 ============
def initialize_header_injection() -> None:
    """
    初始化HTTP请求头注入功能

    注意：此函数可以被多次调用（在主进程和xdist子进程中），
    内部会检查是否已经patch过，避免重复patch
    """

    logger.info("Initializing API header injection...")
    _patch_requests()
    _patch_httplib()
    _patch_httpx()
