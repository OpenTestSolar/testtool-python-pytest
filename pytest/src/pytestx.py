import json
import os
import time
import traceback
from typing import BinaryIO, Sequence, Optional

import pytest
from pytest import Item, Collector, CollectReport, CallInfo, TestReport

from testsolar_testtool_sdk.reporter import Reporter, ReportType
from testsolar_testtool_sdk.model.testresult import TestResult, ResultType, TestCaseStep
from testsolar_testtool_sdk.model.test import TestCase

from .case_log import gen_logs
from .converter import normalize_testcase_name
from .parser import parse_case_attributes
from .allure import parse_allure_step_info


class PytestTestSolarPlugin:
    def __init__(self, allure_path=None, pipe_io: BinaryIO = None):
        self._post_data = {}
        self._testcase_name = ""
        self._allure_path = allure_path
        self._testcase_count = 0
        self.collected: list[Item | Collector] = []
        self.errors = {}
        self._testdata: dict[str, TestResult] = {}
        self._skipped_testcase: dict[str, str] = {}
        self.reporter: Reporter = Reporter(reporter_type=ReportType.Pipeline, pipe_io=pipe_io)

    def pytest_collection_modifyitems(self, items: Sequence[Item | Collector]) -> None:
        self.collected.extend(items)

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
        end_time = time.time()
        if report.when == "setup":
            if report.outcome == "skipped":
                if isinstance(report.longrepr, tuple):
                    self._skipped_testcase[self._testcase_name] = report.longrepr[2]

            setup_start_time = end_time - report.duration
            self.reporter.report_run_case_result(TestResult(
                Test=TestCase(Name=testcase_name, Attributes=attributes),
                ResultType=ResultType.FAILED if report.failed else ResultType.SUCCEED,
                Steps=[
                    TestCaseStep(
                        Title="Setup",
                        Logs=gen_logs(report),
                        StartTime=setup_start_time,
                        EndTime=end_time,
                    )
                ],
                StartTime=setup_start_time,
                Message="",
            ))
            if self._pre_testcase_run:
                setup_start_time = end_time - report.duration
                self._testdata[testcase_name] = {
                    "startTime": setup_start_time,
                    "failed": report.failed,
                    "steps": [
                        {
                            "title": "Setup",
                            "logs": gen_logs(report),
                            "startTime": setup_start_time,
                            "endTime": end_time,
                            "resultType": "failed" if report.failed else "succeed",
                        }
                    ],
                }

                self._pre_testcase_run({"test": {"name": testcase_name}})
        elif report.when == "call":
            self._testcase_count += 1

            print(
                "[%s] Testcase %s run %s, total %d testcases complete"
                % (
                    self.__class__.__name__,
                    report.nodeid,
                    report.outcome,
                    self._testcase_count,
                )
            )
            call_start_time = end_time - report.duration
            if report.outcome == "failed":
                self._testdata[testcase_name]["failed"] = True
            testcase = {}

            self._testdata[testcase_name]["steps"].append(
                {
                    "title": "Run TestCase",
                    "logs": gen_logs(report),
                    "startTime": call_start_time,
                    "endTime": end_time,
                    "resultType": "failed" if report.failed else "succeed",
                }
            )
        elif report.when == "teardown":
            if report.outcome == "failed":
                self._testdata[testcase_name]["failed"] = True
            testcase = self._testdata.pop(testcase_name, None)
            self._teardown_info = {
                "title": "Teardown",
                "logs": gen_logs(report),
                "startTime": end_time - report.duration,
                "endTime": end_time,
                "resultType": "failed" if report.failed else "succeed",
            }
            self._post_data = {
                "test": {"name": testcase_name, "attributes": attributes},
                "resultType": "failed" if testcase["failed"] else "succeed",
                "startTime": testcase.get("startTime"),
                "endTime": end_time,
                "steps": testcase["steps"],
            }
            if not self._allure_path:
                self._post_data["steps"].append(self._teardown_info)
                if len(self._post_data["steps"]) <= 2:
                    for step in self._post_data["steps"]:
                        if step["resultType"] == "failed":
                            break
                    else:
                        # skiped
                        self._post_data["resultType"] = "ignored"
                        if self._testcase_name not in self._skipped_testcase:
                            self._post_data["message"] = "skip"
                        else:
                            self._post_data["message"] = self._skipped_testcase[self._testcase_name]
                if self._post_testcase_run:
                    self._post_testcase_run(self._post_data)

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
                step_info = []
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
