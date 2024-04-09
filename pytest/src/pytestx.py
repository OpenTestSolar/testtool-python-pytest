import json
import os
import struct
import sys
import time
import traceback

import pytest

from .converter import normalize_testcase_name, selector_to_pytest
from .parser import parse_case_attributes


class PytestTestSolarPlugin:
    def __init__(self, pre_testcase_run=None, post_testcase_run=None, allure_path=None):
        self._post_data = {}
        self._testcase_name = ""
        self._allure_path = allure_path
        self._pre_testcase_run = pre_testcase_run
        self._post_testcase_run = post_testcase_run
        self._testcase_count = 0
        self.collected = []
        self.errors = {}
        self._testdata = {}
        self._session = None
        self._skipped_testcase = {}

    def pytest_sessionstart(self, session):
        self._session = session

    def pytest_collection_modifyitems(self, items):
        for item in items:
            self.collected.append(item)

    def pytest_collectreport(self, report):
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

    def _gen_logs(self, report):
        logs = []
        if report.capstdout:
            logs.append(report.capstdout)
        if report.capstderr:
            logs.append(report.capstderr)
        if report.caplog:
            logs.append(report.caplog)

        log = "\n".join(logs)
        error_log = ""
        if report.outcome == "failed":
            error_log = report.longreprtext
            if error_log:
                if log:
                    log += "\n\n"
                log += error_log
        logs = []
        if log:
            logs.append(
                {
                    "content": log,
                    "level": 4 if error_log else 2,
                    "time": time.time() - report.duration,
                }
            )
        return logs

    @pytest.hookimpl(hookwrapper=True, tryfirst=True)
    def pytest_runtest_makereport(self, item, call):
        out = yield
        report = out.get_result()
        testcase_name = normalize_testcase_name(report.nodeid)
        self._testcase_name = testcase_name
        attributes = parse_case_attributes(item)
        end_time = time.time()
        if report.when == "setup":
            if report.outcome == "skipped":
                if isinstance(report.longrepr, tuple):
                    self._skipped_testcase[self._testcase_name] = report.longrepr[2]
            if self._pre_testcase_run:
                setup_start_time = end_time - report.duration
                self._testdata[testcase_name] = {
                    "startTime": setup_start_time,
                    "failed": report.failed,
                    "steps": [
                        {
                            "title": "Setup",
                            "logs": self._gen_logs(report),
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
                    "logs": self._gen_logs(report),
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
                "logs": self._gen_logs(report),
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


def ipc_send(fd, item):
    buffer = json.dumps(item)
    if not isinstance(buffer, bytes):
        buffer = buffer.encode()
    buffer = struct.pack("!I", len(buffer)) + buffer
    os.write(fd, buffer)


def gen_allure_log(content, result, log_time):
    logs = []
    if content:
        logs.append(
            {
                "content": content,
                "level": 2 if result else 4,
                "time": format_allure_time(log_time),
            }
        )
    return logs


def format_allure_time(result_time):
    return result_time / 1000


def parse_allure_step_info(steps, index=None):
    case_steps = []
    if not index:
        index = 0
    if isinstance(steps, list):
        for step in steps:
            index += 1
            result = step["status"]
            if result == "passed":
                result = True
            else:
                result = False
            log = ""
            if "parameters" in step.keys():
                for param in step["parameters"]:
                    for key in param:
                        log += "%-30s%-20s\n" % (
                            "key: {}".format(key),
                            "value: {}".format(param[key]),
                        )
            if "statusDetails" in step.keys():
                if "message" and "trace" in step["statusDetails"]:
                    log += (
                            step["statusDetails"]["message"]
                            + step["statusDetails"]["trace"]
                    )
            step_info = {
                "title": "{}： {}".format(".".join(list(str(index))), step["name"]),
                "logs": gen_allure_log(log, result, step["start"]),
                "startTime": format_allure_time(step["start"]),
                "endTime": format_allure_time(step["stop"]),
                "resultType": "succeed" if result else "failed",
            }
            case_steps.append(step_info)
            if "steps" in step:
                case_steps.extend(parse_allure_step_info(step["steps"], index * 10))
    return case_steps


def check_allure_enabled():
    enable_allure = os.environ.get("TESTSOLAR_TTP_ENABLEALLURE", "")
    return enable_allure == "true"


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


def run_testcases(proj_path, testcase_list, fd=None):
    if proj_path not in sys.path:
        sys.path.insert(0, proj_path)
    args = [selector_to_pytest(it) for it in testcase_list]
    args.append("--rootdir=%s" % proj_path)
    # args.append("-s") # disable capture
    allure_dir = ""
    if check_allure_enabled():
        allure_dir = os.path.join(proj_path, "allure_results")
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
        args.append("--timeout=%d" % timeout)
    print(args)

    def pre_testcase_run(testcase):
        if fd:
            ipc_send(fd, ["pre_testcase_run", testcase])

    def post_testcase_run(testcase):
        if fd:
            ipc_send(fd, ["post_testcase_run", testcase])

    my_plugin = PytestTestSolarPlugin(
        pre_testcase_run=pre_testcase_run,
        post_testcase_run=post_testcase_run,
        allure_path=allure_dir,
    )
    pytest.main(args, plugins=[my_plugin])
    time.sleep(0.01)
    print("pytest process exit")
