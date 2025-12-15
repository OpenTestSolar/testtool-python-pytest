import os
from pathlib import Path
import sys
from datetime import datetime, timedelta
from typing import BinaryIO, Optional, Dict, Any, List, Callable

from loguru import logger
from pytest import Item, Session

try:
    from pytest import TestReport
except ImportError:
    from _pytest.reports import TestReport

from testsolar_testtool_sdk.model.param import EntryParam
from testsolar_testtool_sdk.model.test import TestCase
from testsolar_testtool_sdk.model.testresult import (
    TestResult,
    ResultType,
    TestCaseStep,
)
from testsolar_testtool_sdk.reporter import BaseReporter, FileReporter
from enum import Enum

from .case_log import gen_logs
from .converter import selector_to_pytest, normalize_testcase_name
from .extend.allure_extend import (
    check_allure_enable,
    initialization_allure_dir,
    generate_allure_results,
)

from .extend.coverage_extend import (
    collect_coverage_report,
)
from .util import append_extra_args, append_coverage_args
from .filter import filter_invalid_selector_path
from .parser import parse_case_attributes
from .stream import pytest_main_with_output

# from .header_injection import set_current_test_nodeid
from .conftest_generator import generate_conftest_for_header_injection


class RunMode(Enum):
    SINGLE = "single"
    BATCH = "batch"


def should_enable_header_injection() -> bool:
    """判断是否需要启用请求头注入功能"""
    return os.environ.get("ENABLE_API_COLLECTING", "") == "1"


class PytestExecutor:
    def __init__(
        self,
        reporter: BaseReporter,
        comment_fields: Optional[List[str]] = None,
        data_drive_key: Optional[str] = None,
    ) -> None:
        self.reporter: BaseReporter = reporter
        self.testcase_count = 0
        self.testdata: Dict[str, TestResult] = {}
        self.skipped_testcase: Dict[str, str] = {}
        self.comment_fields = comment_fields
        self.data_drive_key = data_drive_key

    def pytest_runtest_logstart(self, nodeid: str, location: Any) -> None:
        """
        Called at the start of running the runtest protocol for a single item.
        """
        logger.info(f"{nodeid} start")

        # 通知ResultHouse用例开始运行
        testcase_name = normalize_testcase_name(nodeid, self.data_drive_key)

        # 设置当前测试用例的nodeid到上下文
        # 注意：这里使用处理后的 testcase_class_name，与 conftest.py 中的格式可能不同
        # conftest.py 中使用原始 nodeid，这里使用处理后的名称
        # if should_enable_header_injection():
        #     testcase_class_name = testcase_name.split("?", 1)[-1]
        #     set_current_test_nodeid(testcase_class_name)

        test_result = TestResult(
            Test=TestCase(Name=testcase_name),
            ResultType=ResultType.RUNNING,
            StartTime=datetime.utcnow(),
            Message="",
        )

        self.testdata[testcase_name] = test_result

        self.reporter.report_case_result(test_result)

    def pytest_runtest_setup(self, item: Item) -> None:
        """
        Called to perform the setup phase for a test item.
        """

        # 在Setup阶段将用例的属性解析出来并设置到Test中
        testcase_name = normalize_testcase_name(item.nodeid, self.data_drive_key)
        test_result = self.testdata[testcase_name]
        if test_result:
            test_result.Test.Attributes = parse_case_attributes(item, self.comment_fields)

    def _get_result_type_by_report(self, report: TestReport) -> ResultType:
        result_type: ResultType
        if report.failed:
            result_type = ResultType.FAILED
        elif report.skipped:
            result_type = ResultType.IGNORED
        else:
            result_type = ResultType.SUCCEED
        # 针对pytest-rerunfailures进行兼容
        # 如果report.outcome == "rerun"，则表示当前用例执行失败需要被重试
        if report.outcome == "rerun":  # type: ignore
            result_type = ResultType.FAILED
        return result_type

    def pytest_runtest_logreport(self, report: TestReport) -> None:
        """
        Process the TestReport produced for each of the setup, call and teardown runtest phases of an item.
        """
        logger.info(f"S {report.nodeid} log report")

        testcase_name = normalize_testcase_name(report.nodeid, self.data_drive_key)
        test_result = self.testdata[testcase_name]

        step_end_time = datetime.utcnow()

        result_type: ResultType = self._get_result_type_by_report(report=report)

        if report.when == "setup":
            test_result.Steps.append(
                TestCaseStep(
                    Title="Setup",
                    Logs=[gen_logs(report)],
                    StartTime=step_end_time - timedelta(seconds=report.duration),
                    EndTime=step_end_time,
                    ResultType=result_type,
                )
            )

            test_result.ResultType = result_type

            if report.skipped and isinstance(report.longrepr, tuple):
                file, line, reason = report.longrepr
                logger.info(f"Skipped {file}:{line}: {reason}")
                test_result.Message = reason[:1000]

            logger.info(f"{report.nodeid} setup result type: {result_type}")

        elif report.when == "call":
            test_result.Steps.append(
                TestCaseStep(
                    Title="Run TestCase",
                    Logs=[gen_logs(report)],
                    StartTime=step_end_time - timedelta(seconds=report.duration),
                    EndTime=step_end_time,
                    ResultType=result_type,
                )
            )

            if not test_result.Message and report.failed:
                # 避免错误信息过长，因此仅获取前面最多1000个字符
                test_result.Message = report.longreprtext[:1000]

            test_result.ResultType = result_type

            logger.info(f"{report.nodeid} call result type: {result_type}")

        elif report.when == "teardown":
            test_result.Steps.append(
                TestCaseStep(
                    Title="Teardown",
                    Logs=[gen_logs(report)],
                    StartTime=step_end_time - timedelta(seconds=report.duration),
                    EndTime=step_end_time,
                    ResultType=result_type,
                )
            )
            if not test_result.is_final():
                test_result.ResultType = result_type

            logger.info(f"{report.nodeid} teardown result type: {result_type}")

        logger.info(f"E {report.nodeid} log report")

    def _correct_result_type(
        self, steps: List[TestCaseStep], original_result_type: ResultType, testcase_name: str
    ) -> ResultType:
        """校正测试结果类型"""
        result_type = original_result_type
        for step in steps:
            if step.ResultType == ResultType.FAILED and result_type == ResultType.SUCCEED:
                logger.info(
                    f"{testcase_name} result type corrected to FAILED due to failed step: {step.Title}"
                )
                result_type = ResultType.FAILED
                break
        return result_type

    def pytest_runtest_logfinish(self, nodeid: str, location: Any) -> None:
        """
        Called at the end of running the runtest protocol for a single item.
        """
        logger.info(f"S {nodeid} runtest_logfinish")
        testcase_name = normalize_testcase_name(nodeid, self.data_drive_key)

        test_result = self.testdata[testcase_name]
        test_result.EndTime = datetime.utcnow()
        # 上报前预先校正一遍测试结果
        test_result.ResultType = self._correct_result_type(
            test_result.Steps, test_result.ResultType, testcase_name
        )
        self.testcase_count += 1
        logger.info(
            f"Testcase {nodeid} finished with result type {test_result.ResultType}, total {self.testcase_count} testcases complete"
        )
        # 检查是否allure报告，如果是在统一生成json文件后再上报
        enable_allure = check_allure_enable()
        if not enable_allure:
            self.reporter.report_case_result(test_result)

            # 上报完成后测试记录就没有用了，删除以节省内存
            self.testdata.pop(testcase_name, None)

        # 清除当前测试用例的nodeid
        # if should_enable_header_injection():
        #     set_current_test_nodeid(None)

        logger.info(f"E {nodeid} runtest_logfinish")

    def pytest_sessionfinish(self, session: Session, exitstatus: int) -> None:
        """
        allure json报告在所有用例运行完才能生成, 故在运行用例结束后生成result并上报
        """
        logger.info(f"S {session.nodeid} session finish")
        enable_allure = check_allure_enable()
        if not enable_allure:
            return
        allure_dir = session.config.option.allure_report_dir
        for file_name in os.listdir(allure_dir):
            if not file_name.endswith("result.json"):
                continue
            generate_allure_results(self.testdata, os.path.join(allure_dir, file_name), allure_dir)
        for _, test_result in self.testdata.items():
            self.reporter.report_case_result(test_result)
        logger.info(f"E {session.nodeid} session finish")


def run_testcases(
    entry: EntryParam,
    pipe_io: Optional[BinaryIO] = None,
    case_comment_fields: Optional[List[str]] = None,
    run_mode: Optional[RunMode] = RunMode.BATCH,
    extra_run_function: Optional[Callable[[str, str, List[str]], str]] = None,
) -> None:
    if entry.ProjectPath not in sys.path:
        sys.path.insert(0, entry.ProjectPath)

    # 如果启用了 header injection，生成 conftest.py 以支持 xdist
    # 这确保了 xdist worker 进程也能正确初始化 header injection
    if should_enable_header_injection():
        conftest_path = generate_conftest_for_header_injection(entry.ProjectPath)
        if conftest_path:
            logger.info(f"Generated conftest.py for header injection at {conftest_path}")

    valid_selectors, _ = filter_invalid_selector_path(
        workspace=entry.ProjectPath,
        selectors=entry.TestSelectors,
    )

    if not valid_selectors:
        raise ValueError("No valid selectors found")

    args = [
        f"--rootdir={entry.ProjectPath}",
        "--continue-on-collection-errors",
        "-v",
    ]

    # check allure
    enable_allure = check_allure_enable()
    if enable_allure:
        print("Start allure test")
        # 通过给allure_results增加当前进程pid来生成唯一的路径，避免并发冲突
        process_id = os.getpid()
        allure_dir = os.path.join(entry.ProjectPath, f"allure_results_{process_id}")
        args.append("--alluredir={}".format(allure_dir))
        initialization_allure_dir(allure_dir)

    code_packages: List[str] = append_coverage_args(args, valid_selectors, entry.FileReportPath)

    append_extra_args(args)

    reporter: BaseReporter = FileReporter(report_path=Path(entry.FileReportPath))
    exit_code = 0
    captured_stderr = ""
    if run_mode == RunMode.SINGLE:
        for it in valid_selectors:
            serial_args = args.copy()

            if extra_run_function is None:
                logger.error(
                    "[Error] Extra run function is not set, Please check extra_run_function"
                )
                return
            data_drive_key = extra_run_function(it, entry.ProjectPath, serial_args)
            logger.info(f"Pytest single run args: {serial_args}")
            my_plugin = PytestExecutor(
                reporter=reporter,
                comment_fields=case_comment_fields,
                data_drive_key=data_drive_key,
            )
            _, captured_stderr, exit_code = pytest_main_with_output(
                args=serial_args, plugin=my_plugin
            )
    else:
        # 注意：传递给pytest中的用例必须在执行时能找到，否则pytest会报错
        # TODO: pytest执行出错时，将用例都设置为IGNORED，并设置错误原因
        args.extend(
            [
                os.path.join(entry.ProjectPath, selector_to_pytest(it)) if it != "." else "."
                for it in valid_selectors
            ]
        )
        logger.info(f"Pytest run args: {args}")
        my_plugin = PytestExecutor(reporter=reporter, comment_fields=case_comment_fields)
        _, captured_stderr, exit_code = pytest_main_with_output(args=args, plugin=my_plugin)
    if exit_code != 0:
        if exit_code == 5:
            logger.warning("all testcases has been filtered")
        else:
            # 若pytest没有成功执行，则将本批次的用例结果统一设置为FAILED，并将标准错误流作为用例错误日志上报
            msg = f"Pytest run exit with code {exit_code}"
            logger.error(msg)
            if my_plugin.testcase_count == 0:
                for selector in valid_selectors:
                    test_result = TestResult(
                        Test=TestCase(Name=selector),
                        ResultType=ResultType.FAILED,
                        StartTime=datetime.utcnow(),
                        Message=captured_stderr or msg,
                    )
                    reporter.report_case_result(test_result)
                return
    if len(code_packages) > 0:
        # 如果存在需要采集覆盖率的代码包，则生成覆盖率报告
        collect_coverage_report(entry.ProjectPath, entry.FileReportPath, code_packages)
    logger.info("pytest process exit")
