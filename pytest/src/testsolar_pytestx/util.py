import os
import shlex
from typing import List


def append_extra_args(args: List[str]) -> None:
    """
    将用户配置的额外参数作为命令行数组传递给pytest

    注意用户配置的字符串中可能存在空格类型参数，比如 -m "not m3"，因此需要使用shlex.split来分割参数
    """
    extra_args = os.environ.get("TESTSOLAR_TTP_EXTRAARGS", "")
    if extra_args:
        args.extend(shlex.split(extra_args))
