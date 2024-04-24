import logging
import functools

from typing import Callable, Any, Tuple, Dict

from .global_setup_extend import global_setup_extend
from .global_cleanup_extend import global_cleanup_extend


def global_extend(func: Callable[[Any, Any], Any]) -> Callable[[Any, Any], Any]:
    @functools.wraps(func)
    def wrapper(*args: Tuple[Any, ...], **kwargs: Dict[str, Any]) -> Any:
        # 在函数执行前打印日志

        try:
            logging.info("run global setup extend...")
            global_setup_extend()
            # 执行函数

            result = func(*args, **kwargs)
        finally:
            # 在函数执行后打印日志
            logging.info("run global cleanup extend...")
            global_cleanup_extend()

        return result

    return wrapper
