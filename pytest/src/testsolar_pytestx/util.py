import os
import shlex
from typing import List
from loguru import logger
from pathlib import Path

from .extend.coverage_extend import check_coverage_enable, collect_code_packages


def append_coverage_args(
    args: List[str], valid_selectors: List[str], file_report_path: str
) -> List[str]:
    """
    将覆盖率参数添加到命令行数组中，并返回被测代码包列表

    Args:
        args (List[str]): 命令行参数列表
        valid_selectors (List[str]): 有效的用例列表
        file_report_path (str): 文件报告路径

    Returns:
        List[str]: 被测代码包列表
    """
    enable_coverage: bool = check_coverage_enable()
    code_package: List[str] = []
    coverage_file_path = Path(file_report_path) / "coverage.xml"

    if enable_coverage:
        # 自动计算和识别项目中的代码包
        code_package = collect_code_packages(valid_selectors)
        if code_package:
            # 如果找到了代码包，添加覆盖率相关的参数
            args.extend(
                [
                    "--cov=.",  # 指定要测量覆盖率的目录为当前目录
                    f"--cov-report=xml:{coverage_file_path}",  # 生成 XML 格式的覆盖率报告，并保存到 此进程唯一的目录中
                    "--cov-context=test",  # 在覆盖率报告中添加测试用例名称作为上下文信息
                ]
            )
        else:
            # 如果没有找到代码包，记录警告日志，表示不会收集覆盖率数据
            logger.warning("No source files found, coverage will not be collected")

    return code_package


def append_extra_args(args: List[str]) -> None:
    """
    将用户配置的额外参数作为命令行数组传递给pytest

    注意用户配置的字符串中可能存在空格类型参数，比如 -m "not m3"，因此需要使用shlex.split来分割参数
    """
    extra_args = os.environ.get("TESTSOLAR_TTP_EXTRAARGS", "")
    if extra_args:
        args.extend(shlex.split(extra_args))
