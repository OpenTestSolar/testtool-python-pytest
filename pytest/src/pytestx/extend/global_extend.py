import logging
import functools

from typing import Callable

from .global_setup_extend import global_setup_extend
from .global_cleanup_extend import global_cleanup_extend


def global_extend(func: Callable) -> Callable:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
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
