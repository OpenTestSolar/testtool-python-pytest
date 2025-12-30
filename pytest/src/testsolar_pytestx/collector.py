import os
import sys
import traceback
from collections import defaultdict
from pathlib import Path
from typing import BinaryIO, Sequence, Optional, List, Dict, Union, Callable, Set
from loguru import logger
from pytest import Item, Collector

try:
    from pytest import CollectReport
except ImportError:
    from _pytest.reports import CollectReport  # 兼容pytest低版本

from testsolar_testtool_sdk.model.load import LoadResult, LoadError
from testsolar_testtool_sdk.model.param import EntryParam
from testsolar_testtool_sdk.model.test import TestCase
from testsolar_testtool_sdk.reporter import BaseReporter, FileReporter

from .converter import selector_to_pytest, pytest_to_selector, CASE_DRIVE_SEPARATOR
from .filter import filter_invalid_selector_path
from .parser import parse_case_attributes
from .util import append_extra_args
from .stream import pytest_main_with_output


class PytestCollector:
    def __init__(self, report_file_path: Path):
        self.collected: List[Item] = []
        self.errors: Dict[str, str] = {}
        self.reporter: BaseReporter = FileReporter(report_file_path)

    def pytest_collection_modifyitems(self, items: Sequence[Union[Item, Collector]]) -> None:
        for item in items:
            if isinstance(item, Item):
                self.collected.append(item)

    def pytest_collectreport(self, report: CollectReport) -> None:
        if report.failed:
            path = report.fspath
            if path in self.errors:
                return
            path = os.path.splitext(path)[0].replace(os.path.sep, ".")
            try:
                __import__(path)
            except Exception as e:
                print(e)
                self.errors[report.fspath] = traceback.format_exc()

    def pytest_collection_finish(self, session) -> None:  # type: ignore
        """
        在pytest_collection_modifyitems没有被调用的情况下兜底执行.
        """
        if not self.collected:
            for item in session.items:
                if isinstance(item, Item):
                    self.collected.append(item)

    def pytest_internalerror(self, excrepr) -> None:  # type: ignore
        if (
            excrepr.reprcrash
            and excrepr.reprcrash.path
            and excrepr.reprtraceback
            and excrepr.reprtraceback.reprentries
        ):
            self.errors[excrepr.reprcrash.path] = "\n".join(
                excrepr.reprtraceback.reprentries[0].lines
            )


def collect_testcases(
    entry_param: EntryParam,
    pipe_io: Optional[BinaryIO] = None,
    case_comment_fields: Optional[List[str]] = None,
    extra_load_function: Optional[Callable[[str, LoadResult, Dict[str, List[str]]], None]] = None,
) -> None:
    if entry_param.ProjectPath not in sys.path:
        sys.path.insert(0, entry_param.ProjectPath)

    show_workspace_files(entry_param.ProjectPath)

    load_result: LoadResult = LoadResult(
        Tests=[],
        LoadErrors=[],
    )

    # 检查是否启用 RUN_ALL_CASES 模式
    run_all_cases = os.getenv("TESTSOLAR_TTP_RUNALLCASES", "").lower() in ["1", "true"]
    if run_all_cases:
        logger.info("[Load] 执行一条命令运行当前项目的所有用例")
        load_result.Tests.extend(
            [TestCase(Name=selector, Attributes={}) for selector in entry_param.TestSelectors]
        )
        reporter = FileReporter(Path(entry_param.FileReportPath))
        reporter.report_load_result(load_result)
        return

    # 检查是否启用 FILEMODE 模式
    file_mode = os.getenv("TESTSOLAR_TTP_FILEEXECUTEMODE", "").lower() in ["1", "true"]
    if file_mode:
        logger.info("[Load] 以文件模式运行当前用例")
        collect_testcases_file_mode(entry_param, load_result)
        return

    valid_selectors, load_errors = filter_invalid_selector_path(
        workspace=entry_param.ProjectPath,
        selectors=entry_param.TestSelectors,
    )

    load_result.LoadErrors.extend(load_errors)

    case_drive_records: Dict[str, List[str]] = defaultdict(list)
    pytest_paths: List[str] = []
    for selector in valid_selectors:
        # 扫描用例是否是基础用例，如果是存入 case_drive_records，方便后续扩展
        if CASE_DRIVE_SEPARATOR in selector:
            case_name, _, drive_key = selector.partition(CASE_DRIVE_SEPARATOR)
            case_drive_records[case_name].append(drive_key)

            pytest_paths.append(selector_to_pytest(test_selector=case_name))
        else:
            pytest_paths.append(selector_to_pytest(test_selector=selector))

    testcase_list = [os.path.join(entry_param.ProjectPath, it) for it in pytest_paths if it]

    my_plugin = PytestCollector(Path(entry_param.FileReportPath))
    args = [
        f"--rootdir={entry_param.ProjectPath}",
        "--collect-only",
        "--continue-on-collection-errors",
        "-v",
        "--trace-config",
    ]
    append_extra_args(args)

    args.extend(testcase_list)
    logger.info(f"[Load] try to collect testcases: {args}")
    _, captured_stderr, exit_code = pytest_main_with_output(args=args, plugin=my_plugin)
    if exit_code != 0:
        # 若加载用例失败，则将本批次的用例结果统一作为loaderror上报，并将标准错误流作为用例错误日志上报
        logger.warning(f"[Warn][Load] collect testcases exit_code: {exit_code}")
        if len(my_plugin.collected) == 0 and len(my_plugin.errors.items()) == 0:
            for selector in valid_selectors:
                load_result.LoadErrors.append(
                    LoadError(
                        name=selector,
                        message=captured_stderr,
                    )
                )

    for item in my_plugin.collected:
        full_name = pytest_to_selector(item, entry_param.ProjectPath)
        attributes = parse_case_attributes(item, case_comment_fields)
        load_result.Tests.append(TestCase(Name=full_name, Attributes=attributes))

    # 增加额外功能，方便外部接入
    if extra_load_function:
        extra_load_function(entry_param.ProjectPath, load_result, case_drive_records)

    for k, v in my_plugin.errors.items():
        load_result.LoadErrors.append(
            LoadError(
                name=k,
                message=v,
            )
        )

    logger.info(f"[Load] collect testcase count: {len(load_result.Tests)}")
    logger.info(f"[Load] collect load error count: {len(load_result.LoadErrors)}")

    reporter = FileReporter(Path(entry_param.FileReportPath))
    reporter.report_load_result(load_result)


def collect_testcases_file_mode(entry_param: EntryParam, load_result: LoadResult) -> None:
    """
    文件模式：只解析到文件层级，不解析里面的类和方法
    扫描传进来的testselector对应的文件：
    - 如果是tests，则扫描tests目录下所有pytest相关的测试文件
    - 如果是.，则扫描整个项目目录下符合pytest规范的文件
    - 排除隐藏目录、文件和缓存文件
    """
    valid_selectors, load_errors = filter_invalid_selector_path(
        workspace=entry_param.ProjectPath,
        selectors=entry_param.TestSelectors,
    )

    load_result.LoadErrors.extend(load_errors)

    # 收集所有测试文件
    test_files = set()

    for selector in valid_selectors:
        # 移除数据驱动部分
        if CASE_DRIVE_SEPARATOR in selector:
            selector = selector.split(CASE_DRIVE_SEPARATOR)[0]

        # 提取路径部分（去掉查询参数）
        path_part, _, _ = selector.partition("?")

        # 构建完整路径
        project_path_obj = Path(entry_param.ProjectPath)
        full_path = project_path_obj / path_part

        if full_path.is_file():
            # 如果是文件，直接添加
            if _is_pytest_test_file(str(full_path)):
                test_files.add(path_part)
        elif full_path.is_dir():
            # 如果是目录，扫描目录下的所有测试文件
            discovered_files = _scan_pytest_files(str(full_path), entry_param.ProjectPath)
            test_files.update(discovered_files)
        elif path_part == ".":
            # 如果是根目录，扫描整个项目
            discovered_files = _scan_pytest_files(entry_param.ProjectPath, entry_param.ProjectPath)
            test_files.update(discovered_files)
        else:
            # 尝试转换为pytest路径处理（兼容原有逻辑）
            pytest_path = selector_to_pytest(test_selector=selector)
            if pytest_path:
                # 提取文件路径部分（去掉类名和方法名）
                file_path = pytest_path.split("::")[0]
                full_file_path = project_path_obj / file_path
                if full_file_path.exists() and _is_pytest_test_file(str(full_file_path)):
                    test_files.add(file_path)

    # 为每个测试文件创建一个测试用例
    project_path_obj = Path(entry_param.ProjectPath)
    for file_path in sorted(test_files):
        # 检查文件是否存在
        full_file_path = project_path_obj / file_path
        if full_file_path.exists():
            # 将文件路径转换为选择器格式
            load_result.Tests.append(TestCase(Name=file_path, Attributes={}))
        else:
            load_result.LoadErrors.append(
                LoadError(
                    name=file_path,
                    message=f"Test file not found: {full_file_path}",
                )
            )

    print(f"[Load] File mode - collected {len(load_result.Tests)} test files")
    print(f"[Load] File mode - load error count: {len(load_result.LoadErrors)}")

    reporter = FileReporter(Path(entry_param.FileReportPath))
    reporter.report_load_result(load_result)


def _is_pytest_test_file(file_path: str) -> bool:
    """
    判断文件是否是pytest测试文件
    pytest默认的测试文件命名规则：
    1. test_*.py - 以test_开头的.py文件
    2. *_test.py - 以_test.py结尾的.py文件（但不能只是_test.py）
    """
    file_path_obj = Path(file_path)
    if file_path_obj.suffix != ".py":
        return False

    filename = file_path_obj.name

    # 规则1: 以test_开头
    if filename.startswith("test_"):
        return True

    # 规则2: 以_test.py结尾，但不能只是_test.py
    if filename.endswith("_test.py") and filename != "_test.py":
        return True

    return False


def _scan_pytest_files(scan_path: str, project_path: str) -> Set[str]:
    """
    扫描指定路径下的所有pytest测试文件
    排除隐藏目录、文件和缓存文件
    """
    test_files = set()

    # 需要排除的目录和文件模式
    exclude_dirs = {
        "__pycache__",
        ".pytest_cache",
        ".git",
        ".svn",
        ".hg",
        "node_modules",
        ".venv",
        "venv",
        ".env",
        "env",
        ".tox",
        "build",
        "dist",
        ".coverage",
        "htmlcov",
        ".mypy_cache",
        ".idea",
        ".vscode",
    }

    exclude_patterns = {
        ".pyc",
        ".pyo",
        ".pyd",
        ".so",
        ".egg-info",
        ".coverage",
        ".DS_Store",
        "Thumbs.db",
    }

    try:
        scan_path_obj = Path(scan_path)
        project_path_obj = Path(project_path)

        def should_exclude_dir(dir_path: Path) -> bool:
            """判断是否应该排除目录"""
            dir_name = dir_path.name
            return (
                dir_name.startswith(".")  # 隐藏目录
                or dir_name in exclude_dirs  # 特定排除目录
                or dir_name.startswith("__pycache__")  # Python缓存目录
            )

        def scan_directory(current_path: Path) -> None:
            """递归扫描目录"""
            try:
                for item in current_path.iterdir():
                    if item.is_dir():
                        # 检查是否应该排除此目录
                        if not should_exclude_dir(item):
                            scan_directory(item)
                    elif item.is_file():
                        # 跳过隐藏文件和特定扩展名的文件
                        if item.name.startswith("."):
                            continue

                        if any(item.name.endswith(pattern) for pattern in exclude_patterns):
                            continue

                        # 检查是否是pytest测试文件
                        if _is_pytest_test_file(str(item)):
                            # 计算相对于项目根目录的路径
                            rel_path = item.relative_to(project_path_obj)
                            # 统一使用正斜杠
                            rel_path_str = str(rel_path).replace("\\", "/")
                            test_files.add(rel_path_str)
            except (OSError, PermissionError) as e:
                print(f"[Warning] Failed to access directory {current_path}: {e}")

        scan_directory(scan_path_obj)

    except (OSError, PermissionError) as e:
        print(f"[Warning] Failed to scan directory {scan_path}: {e}")

    return test_files


def show_workspace_files(workdir: str) -> None:
    print()
    print(f"Workspace [{workdir}] files:")
    for item in Path(workdir).iterdir():
        if item.is_file():
            print(f" - {item}")

    print()
