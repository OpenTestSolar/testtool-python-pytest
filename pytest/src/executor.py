import logging
import os
import sys
from typing import BinaryIO

from datetime import datetime, timedelta
import pytest
from pytest import TestReport
from testsolar_testtool_sdk.model.param import EntryParam
from testsolar_testtool_sdk.model.test import TestCase
from testsolar_testtool_sdk.model.testresult import TestResult, ResultType, TestCaseStep
from testsolar_testtool_sdk.reporter import Reporter

from .allure import check_allure_enabled
from .case_log import gen_logs
from .converter import selector_to_pytest, normalize_testcase_name


def run_testcases(entry: EntryParam, pipe_io: BinaryIO | None = None):
    if entry.ProjectPath not in sys.path:
        sys.path.insert(0, entry.ProjectPath)

    args = [
        f"--rootdir={entry.ProjectPath}",
        "--continue-on-collection-errors",
    ]
    args.extend([os.path.join(entry.ProjectPath, selector_to_pytest(it)) for it in entry.TestSelectors])

    allure_dir = ""
    if check_allure_enabled():
        allure_dir = os.path.join(entry.ProjectPath, "allure_results")
        args.append("--alluredir={}".format(allure_dir))

        if not os.path.isdir(allure_dir):
            os.mkdir(allure_dir)
        else:
            for f_name in os.listdir(allure_dir):
                os.remove(os.path.join(allure_dir, f_name))
    extra_args = os.environ.get("TESTSOLAR_TTP_EXTRAARGS", "")
    if extra_args:
        args.extend(extra_args.split())
    timeout = int(os.environ.get("TESTSOLAR_TTP_TIMEOUT", "0"))
    if timeout > 0:
        args.append(f"--timeout={timeout}")
    logging.info(args)

    my_plugin = PytestExecutor(
        pipe_io=pipe_io
    )
    pytest.main(args, plugins=[my_plugin])
    logging.info("pytest process exit")


class PytestExecutor:
    def __init__(self, pipe_io: BinaryIO | None = None):
        self.testcase_count = 0
        self.testdata: dict[str, TestResult] = {}
        self.skipped_testcase: dict[str, str] = {}
        self.reporter: Reporter = Reporter(pipe_io=pipe_io)

    def pytest_runtest_logstart(self, nodeid: str, location):
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

        self.reporter.report_run_case_result(test_result)

    def pytest_runtest_logreport(self, report: TestReport) -> None:
        """
        Process the TestReport produced for each of the setup, call and teardown runtest phases of an item.
        """
        logging.info(f"{report.nodeid} log report")

        testcase_name = normalize_testcase_name(report.nodeid)
        test_result = self.testdata[testcase_name]

        step_end_time = datetime.now()
        # 根据报告修改对应TestResult的值

        if report.when == "setup":
            test_result.Steps.append(
                TestCaseStep(
                    Title="Setup",
                    Logs=[gen_logs(report)],
                    StartTime=step_end_time - timedelta(report.duration),
                    EndTime=step_end_time,
                    ResultType=ResultType.FAILED if report.failed else ResultType.SUCCEED
                )
            )
            if report.failed:
                test_result.ResultType = ResultType.FAILED
        elif report.when == "call":
            test_result.Steps.append(
                TestCaseStep(
                    Title="Run TestCase",
                    Logs=[gen_logs(report)],
                    StartTime=step_end_time - timedelta(report.duration),
                    EndTime=step_end_time,
                    ResultType=ResultType.FAILED if report.failed else ResultType.SUCCEED
                )
            )
            if report.failed:
                test_result.ResultType = ResultType.FAILED
        elif report.when == "teardown":
            test_result.Steps.append(
                TestCaseStep(
                    Title="Teardown",
                    Logs=[gen_logs(report)],
                    StartTime=step_end_time - timedelta(report.duration),
                    EndTime=step_end_time,
                    ResultType=ResultType.FAILED if report.failed else ResultType.SUCCEED
                )
            )

            test_result.ResultType = ResultType.FAILED if report.failed else ResultType.SUCCEED

    def pytest_runtest_logfinish(self, nodeid: str, location):
        """
        Called at the end of running the runtest protocol for a single item.
        """
        testcase_name = normalize_testcase_name(nodeid)

        test_result = self.testdata[testcase_name]
        test_result.EndTime = datetime.now()

        self.reporter.report_run_case_result(test_result)
