import logging
import os
import sys
from datetime import datetime, timedelta
from typing import BinaryIO, Optional, Dict

import pytest
from pytest import TestReport
from testsolar_testtool_sdk.model.param import EntryParam
from testsolar_testtool_sdk.model.test import TestCase
from testsolar_testtool_sdk.model.testresult import TestResult, ResultType, TestCaseStep
from testsolar_testtool_sdk.reporter import Reporter

from .case_log import gen_logs
from .converter import selector_to_pytest, normalize_testcase_name
from .filter import filter_invalid_selector_path


def run_testcases(entry: EntryParam, pipe_io: Optional[BinaryIO] = None):
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

        self.reporter.report_case_result(test_result)

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
        elif report.when == "call":
            self.testcase_count += 1

            test_result.Steps.append(
                TestCaseStep(
                    Title="Run TestCase",
                    Logs=[gen_logs(report)],
                    StartTime=step_end_time - timedelta(report.duration),
                    EndTime=step_end_time,
                    ResultType=result_type
                )
            )

            print(
                f"[{self.__class__.__name__}] Testcase {report.nodeid} run {report.outcome},"
                " total {self.testcase_count} testcases complete"
            )

            test_result.ResultType = result_type

        elif report.when == "teardown":
            test_result.Steps.append(
                TestCaseStep(
                    Title="Teardown",
                    Logs=[gen_logs(report)],
                    StartTime=step_end_time - timedelta(report.duration),
                    EndTime=step_end_time,
                    ResultType=result_type
                )
            )
            if test_result.ResultType not in [ResultType.FAILED, ResultType.LOAD_FAILED, ResultType.IGNORED, ResultType.UNKNOWN]:
                test_result.ResultType = result_type

    def pytest_runtest_logfinish(self, nodeid: str, location):
        """
        Called at the end of running the runtest protocol for a single item.
        """
        testcase_name = normalize_testcase_name(nodeid)

        test_result = self.testdata[testcase_name]
        test_result.EndTime = datetime.now()

        self.reporter.report_case_result(test_result)

        # 上报完成后测试记录就没有用了，删除以节省内存
        self.testdata.pop(testcase_name, None)
