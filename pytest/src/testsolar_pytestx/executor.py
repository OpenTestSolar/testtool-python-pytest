import logging
import os
import sys
from datetime import datetime, timedelta
from typing import BinaryIO, Optional, Dict, Any

import pytest
from pytest import TestReport, Item, Session
from testsolar_testtool_sdk.model.param import EntryParam
from testsolar_testtool_sdk.model.test import TestCase
from testsolar_testtool_sdk.model.testresult import TestResult, ResultType, TestCaseStep
from testsolar_testtool_sdk.reporter import Reporter

from .case_log import gen_logs
from .converter import selector_to_pytest, normalize_testcase_name
from .extend.allure_extend import (
    check_allure_enable,
    initialization_allure_dir,
    generate_allure_results,
)
from .filter import filter_invalid_selector_path
from .parser import parse_case_attributes


def run_testcases(entry: EntryParam, pipe_io: Optional[BinaryIO] = None) -> None:
    if entry.ProjectPath not in sys.path:
        sys.path.insert(0, entry.ProjectPath)

    valid_selectors, _ = filter_invalid_selector_path(
        workspace=entry.ProjectPath,
        selectors=entry.TestSelectors,
    )

    args = [
        f"--rootdir={entry.ProjectPath}",
        "--continue-on-collection-errors",
        "-v",
    ]

    # check allure
    enable_allure = check_allure_enable()
    if enable_allure:
        print("Start allure test")
        allure_dir = os.path.join(entry.ProjectPath, "allure_results")
        args.append("--alluredir={}".format(allure_dir))
        initialization_allure_dir(allure_dir)

    args.extend(
        [
            os.path.join(entry.ProjectPath, selector_to_pytest(it))
            for it in valid_selectors
        ]
    )

    extra_args = os.environ.get("TESTSOLAR_TTP_EXTRAARGS", "")
    if extra_args:
        args.extend(extra_args.split())
    timeout = int(os.environ.get("TESTSOLAR_TTP_TIMEOUT", "0"))
    if timeout > 0:
        args.append(f"--timeout={timeout}")
    logging.info(args)

    my_plugin = PytestExecutor(pipe_io=pipe_io)
    pytest.main(args, plugins=[my_plugin])
    logging.info("pytest process exit")


class PytestExecutor:
    def __init__(self, pipe_io: Optional[BinaryIO] = None):
        self.testcase_count = 0
        self.testdata: Dict[str, TestResult] = {}
        self.skipped_testcase: Dict[str, str] = {}
        self.reporter: Reporter = Reporter(pipe_io=pipe_io)

    def pytest_runtest_logstart(self, nodeid: str, location: Any) -> None:
        """
        Called at the start of running the runtest protocol for a single item.
        """

        # 通知ResultHouse用例开始运行
        testcase_name = normalize_testcase_name(nodeid)

        test_result = TestResult(
            Test=TestCase(Name=testcase_name),
            ResultType=ResultType.RUNNING,
            StartTime=datetime.now(),
            Message="",
        )

        self.testdata[testcase_name] = test_result

        logging.info(f"{nodeid} start")

        self.reporter.report_case_result(test_result)

    def pytest_runtest_setup(self, item: Item) -> None:
        """
        Called to perform the setup phase for a test item.
        """

        # 在Setup阶段将用例的属性解析出来并设置到Test中
        testcase_name = normalize_testcase_name(item.nodeid)
        test_result = self.testdata[testcase_name]
        if test_result:
            test_result.Test.Attributes = parse_case_attributes(item)

    def pytest_runtest_logreport(self, report: TestReport) -> None:
        """
        Process the TestReport produced for each of the setup, call and teardown runtest phases of an item.
        """
        logging.info(f"{report.nodeid} log report")

        testcase_name = normalize_testcase_name(report.nodeid)
        test_result = self.testdata[testcase_name]

        step_end_time = datetime.now()

        result_type: ResultType
        if report.failed:
            result_type = ResultType.FAILED
        elif report.skipped:
            result_type = ResultType.IGNORED
        else:
            result_type = ResultType.SUCCEED

        if report.when == "setup":
            test_result.Steps.append(
                TestCaseStep(
                    Title="Setup",
                    Logs=[gen_logs(report)],
                    StartTime=step_end_time - timedelta(report.duration),
                    EndTime=step_end_time,
                    ResultType=result_type,
                )
            )

            test_result.ResultType = result_type

            if report.skipped and isinstance(report.longrepr, tuple):
                file, line, reason = report.longrepr
                print(f"Skipped {file}:{line}: {reason}")
                test_result.Message = reason[:1000]

        elif report.when == "call":
            self.testcase_count += 1

            test_result.Steps.append(
                TestCaseStep(
                    Title="Run TestCase",
                    Logs=[gen_logs(report)],
                    StartTime=step_end_time - timedelta(report.duration),
                    EndTime=step_end_time,
                    ResultType=result_type,
                )
            )

            print(
                f"[{self.__class__.__name__}] Testcase {report.nodeid} run {report.outcome},"
                f" total {self.testcase_count} testcases complete"
            )

            if not test_result.Message and report.failed:
                # 避免错误信息过长，因此仅获取前面最多1000个字符
                test_result.Message = report.longreprtext[:1000]

            test_result.ResultType = result_type

        elif report.when == "teardown":
            test_result.Steps.append(
                TestCaseStep(
                    Title="Teardown",
                    Logs=[gen_logs(report)],
                    StartTime=step_end_time - timedelta(report.duration),
                    EndTime=step_end_time,
                    ResultType=result_type,
                )
            )
            if not test_result.is_final():
                test_result.ResultType = result_type

    def pytest_runtest_logfinish(self, nodeid: str, location: Any) -> None:
        """
        Called at the end of running the runtest protocol for a single item.
        """
        testcase_name = normalize_testcase_name(nodeid)

        test_result = self.testdata[testcase_name]
        test_result.EndTime = datetime.now()

        # 检查是否allure报告，如果是在统一生成json文件后再上报
        enable_alure = check_allure_enable()
        if not enable_alure:
            self.reporter.report_case_result(test_result)

            # 上报完成后测试记录就没有用了，删除以节省内存
            self.testdata.pop(testcase_name, None)

    def pytest_sessionfinish(self, session: Session, exitstatus: int) -> None:
        """
        allure json报告在所有用例运行完才能生成, 故在运行用例结束后生成result并上报
        """
        enable_alure = check_allure_enable()
        if not enable_alure:
            return
        allure_dir = session.config.option.allure_report_dir
        for file_name in os.listdir(allure_dir):
            if not file_name.endswith("result.json"):
                continue
            generate_allure_results(self.testdata, os.path.join(allure_dir, file_name))
        for _, test_result in self.testdata.items():
            self.reporter.report_case_result(test_result)
