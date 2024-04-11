import json
import logging
import os
import traceback
from datetime import datetime, timedelta
from typing import BinaryIO, Sequence

import pytest
from pytest import Item, Collector, CollectReport, CallInfo, TestReport
from testsolar_testtool_sdk.model.test import TestCase
from testsolar_testtool_sdk.model.testresult import TestResult, ResultType, TestCaseStep
from testsolar_testtool_sdk.reporter import Reporter

from .allure import parse_allure_step_info
from .case_log import gen_logs
from .converter import normalize_testcase_name
from .parser import parse_case_attributes


class PytestTestSolarPlugin:
    def __init__(self, allure_path: str | None = None, pipe_io: BinaryIO | None = None):
        self._post_data = {}
        self._testcase_name = ""
        self._allure_path = allure_path
        self._testcase_count = 0
        self.collected: list[Item] = []
        self.errors = {}
        self._testdata: dict[str, TestResult] = {}
        self._skipped_testcase: dict[str, str] = {}
        self.reporter: Reporter = Reporter(pipe_io=pipe_io)

    def pytest_runtest_logstart(self, nodeid: str, location):
        """
        Called at the start of running the runtest protocol for a single item.
        """
        logging.info(f"{nodeid} start")
        pass

    def pytest_runtest_logfinish(self, nodeid: str, location):
        """
        Called at the end of running the runtest protocol for a single item.
        """
        logging.info(f"{nodeid} finish")
        pass

    def pytest_runtest_logreport(self, report: TestReport) -> None:
        """
        Process the TestReport produced for each of the setup, call and teardown runtest phases of an item.
        """
        logging.info(f"{report.nodeid} log report")

    def _clear_report(self, report):
        del report.sections[:]

    def _clear_item(self, item):
        del item._report_sections[:]

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_makereport(self, item: Item, call: CallInfo):
        out = yield
        report: TestReport = out.get_result()
        testcase_name = normalize_testcase_name(report.nodeid)
        self._testcase_name = testcase_name
        attributes = parse_case_attributes(item)
        end_time = datetime.now()
        if report.when == "setup":
            if report.skipped:
                if isinstance(report.longrepr, tuple):
                    self._skipped_testcase[self._testcase_name] = report.longrepr[2]

            setup_start_time = end_time - timedelta(report.duration)
            test_result = TestResult(
                Test=TestCase(Name=testcase_name, Attributes=attributes),
                ResultType=ResultType.RUNNING,
                Steps=[
                    TestCaseStep(
                        Title="Setup",
                        Logs=gen_logs(report),
                        StartTime=setup_start_time,
                        EndTime=end_time,
                        ResultType=ResultType.FAILED if report.failed else ResultType.SUCCEED
                    )
                ],
                StartTime=setup_start_time,
                Message="",
            )
            self._testdata[testcase_name] = test_result
            self.reporter.report_run_case_result(test_result)

            # 上报结束之后再更新状态，避免提早上报到ResultHouse
            if report.failed:
                test_result.ResultType = ResultType.FAILED
        elif report.when == "call":
            self._testcase_count += 1
            test_result = self._testdata[testcase_name]

            if not test_result:
                logging.warning("No test case result for %s", testcase_name)
            else:
                print(
                    "[%s] Testcase %s run %s, total %d testcases complete"
                    % (
                        self.__class__.__name__,
                        report.nodeid,
                        report.outcome,
                        self._testcase_count,
                    )
                )
                call_start_time = end_time - timedelta(report.duration)
                if report.failed:
                    test_result.ResultType = ResultType.FAILED

                test_result.Steps.append(TestCaseStep(
                    Title="Run TestCase",
                    Logs=gen_logs(report),
                    StartTime=call_start_time,
                    EndTime=end_time,
                    ResultType=ResultType.FAILED if report.failed else ResultType.SUCCEED
                ))
        elif report.when == "teardown":

            test_result = self._testdata[testcase_name]
            if test_result:
                if report.failed:
                    test_result.ResultType = ResultType.FAILED

                if not self._allure_path:
                    test_result.Steps.append(TestCaseStep(
                        Title="Teardown",
                        Logs=gen_logs(report),
                        StartTime=end_time - timedelta(report.duration),
                        EndTime=end_time,
                        ResultType=ResultType.FAILED if report.failed else ResultType.SUCCEED
                    ))

                    if len(test_result.Steps) <= 2:
                        for step in test_result.Steps:
                            if step.ResultType == ResultType.FAILED:
                                break
                        else:
                            test_result.ResultType = ResultType.IGNORED
                            if testcase_name not in self._skipped_testcase:
                                test_result.Message = "skip"
                            else:
                                test_result.Message = self._skipped_testcase[testcase_name]

                self.reporter.report_run_case_result(test_result)

        self._clear_item(item)
        self._clear_report(report)

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_logfinish(self, nodeid, location):
        yield

        if not self._allure_path:
            return

        files = os.listdir(self._allure_path)
        for file_name in files:
            if "result.json" not in file_name:
                continue

            with open(os.path.join(self._allure_path, file_name)) as f:
                data = json.loads(f.read())
                step_info: list[TestCaseStep] = []
                full_name = data["fullName"]
                testcase_name = ".".join(
                    self._testcase_name.replace(".py?", os.sep).split(os.sep)
                )
                if testcase_name != full_name.replace("#", "."):
                    continue

                if "steps" in data.keys():
                    step_info = parse_allure_step_info(data["steps"])
                self._post_data["steps"].extend(step_info)
                self._post_data["steps"].append(self._teardown_info)
                if self._post_testcase_run:
                    self._post_testcase_run(self._post_data)
                return
        else:
            if self._teardown_info:
                self._post_data["steps"].append(self._teardown_info)
            print("Testcase: {} has not allure report".format(self._testcase_name))
            if self._post_testcase_run:
                self._post_testcase_run(self._post_data)
            return


class SummaryOutput(object):
    def __init__(self, stream):
        self._stream = stream

    def __getattr__(self, attr):
        return getattr(self._stream, attr)

    def write(self, buffer):
        if len(buffer) > 8192:
            sep_line = "+" * 50
            warnning = "\n%s\nIgnore middle %d bytes\n%s\n" % (
                sep_line,
                len(buffer) - 8192,
                sep_line,
            )
            buffer = buffer[:4096] + warnning + buffer[-4096:]
        return self._stream.write(buffer)
