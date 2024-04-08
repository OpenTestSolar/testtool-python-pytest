import argparse
import json
import os
import re
import shlex
import struct
import sys
import time
import traceback
import pytest

try:
    # Python 3
    from urllib.parse import quote, unquote
except ImportError:
    # Python 2
    from urllib import quote, unquote


class MyPlugin:
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


def normalize_testcase_name(name):
    """ test_directory/test_module.py::TestExampleClass::test_example_function[datedrive]
        -> test_directory/test_module.py?TestExampleClass/test_example_function/[datedrive]
    """
    assert "::" in name
    name = name.replace("::", "?", 1).replace("::", "/").replace("[", "/[")
    if "[" in name:
        name = decode_datadrive(name)
    return name


def encode_datadrive(name):
    if sys.version_info[0] >= 3:
        name = name.encode("unicode_escape").decode()
    else:
        if not isinstance(name, bytes):
            name = name.encode("utf-8")
        name = name.encode("string-escape")
    return name


def decode_datadrive(name):
    if sys.version_info[0] >= 3:
        if re.search(r"\\u\w{4}", name):
            name = name.encode().decode("unicode_escape")
    else:
        name = name.decode("string-escape")
        name = name.decode("string-escape") # need decode twice
    return name


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


def selector_to_pytest(test_selector):
    """translate from test selector format to pytest format"""
    pos = test_selector.find("?")
    if pos < 0:
        # TODO: Check is valid path
        return test_selector
    testcase = test_selector[pos + 1 :]
    if "&" in testcase:
        testcase_attrs = testcase.split("&")
        for attr in testcase_attrs:
            if  "name=" in attr:
                testcase = attr[5:]
                break
            elif "=" not in attr:
                testcase = attr
                break
    else:
        if testcase.startswith("name="):
            testcase = testcase[5:]
    if "/[" in testcase:
        testcase = encode_datadrive(testcase.replace("/[", "["))
    return test_selector[:pos] + "::" + testcase.replace("/", "::")


def parse_case_attributes(item):
    """parse testcase attributes"""
    attributes = {"description": (item.function.__doc__ or "").strip()}
    if not item.own_markers:
        return attributes
    for mark in item.own_markers:
        if not mark.args and mark.name != "attributes":
            attributes["tag"] = mark.name
        elif mark.args and mark.name == "owner":
            attributes["owner"] = mark.args[0]
        elif mark.name == "extra_attributes":
            extra_attr = {}
            for key in mark.args[0]:
                if mark.args[0][key] is None:
                    continue
                extra_attr[key] = mark.args[0][key]
            if not attributes.get("extra_attributes"):
                attributes["extra_attributes"] = []
            attributes["extra_attributes"].append(extra_attr)
    return attributes

def collect_testcases(proj_path, testcases, fd=None):
    if proj_path not in sys.path:
        sys.path.insert(0, proj_path)
    testcase_list = [
        os.path.join(proj_path, selector_to_pytest(it)) for it in testcases
    ]
    print(
        "[Load] try to load testcases: %s"
        % (str(testcase_list))
    )
    my_plugin = MyPlugin()
    exit_code = pytest.main(
        ["--rootdir=%s" % proj_path, "--collect-only"] + testcase_list,
        plugins=[my_plugin],
    )

    to_report_testcases = []
    if exit_code != 0:
        print("[Load] collect testcases exit_code: {}".format(exit_code))

    for item in my_plugin.collected:
        if hasattr(item, "path") and hasattr(item, "cls"):
            path = str(item.path)[len(proj_path) + 1 :]
            name = item.name
            if item.cls:
                name = item.cls.__name__ + "/" + name
            if name.endswith("]"):
                name = name.replace("[", "/[")
        elif hasattr(item, "nodeid"):
            path, _, name = normalize_testcase_name(item.nodeid).partition("?")
        else:
            path = item.location[0]
            # TODO: 感觉这里也少了replace("[", "/[")的逻辑？
            name = item.location[2].replace(".", "/")
        # support: @pytest.mark.attributes({"key":"value"})
        attributes = parse_case_attributes(item)
        name = decode_datadrive(name)
        to_report_testcases.append([path, name, attributes])

    for item in my_plugin.errors:
        to_report_testcases.append([item, "", {"error": my_plugin.errors[item]}])

    print(
        "[Load] collected testcases {}".format(to_report_testcases)
    )
    
    if fd:
        ipc_send(fd, to_report_testcases)
    return to_report_testcases


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

    my_plugin = MyPlugin(
        pre_testcase_run=pre_testcase_run,
        post_testcase_run=post_testcase_run,
        allure_path=allure_dir,
    )
    pytest.main(args, plugins=[my_plugin])
    time.sleep(0.01)
    print("pytest process exit")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="pytestx", description="pytest tool wrapper")
    parser.add_argument(
        "--action",
        help="current run action",
        choices=("collect", "run"),
        required=True,
    )
    parser.add_argument("--proj-path", help="project root path", required=True)
    parser.add_argument("--testcases", help="testcase list")
    parser.add_argument("--ipc-fd", help="ipc fd", type=int)
    args = parser.parse_args()

    testcase_list = shlex.split(args.testcases)
    if args.action == "collect":
        collect_testcases(args.proj_path, testcase_list, args.ipc_fd)
    elif args.action == "run":
        run_testcases(args.proj_path, testcase_list, args.ipc_fd)
    if args.ipc_fd:
        os.close(args.ipc_fd)
