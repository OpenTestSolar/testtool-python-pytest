# -*- coding: utf-8 -*-

import argparse
import json
import locale
import os
import struct
import sys
import time
import traceback
import unittest
import unittest.result
from datetime import datetime

from django.test.runner import DiscoverRunner

default_locale = locale.getdefaultlocale()
if default_locale:
    default_encoding = default_locale[1] or "utf8"
else:
    default_encoding = "utf8"

orig_stdout = sys.stdout
orig_stderr = sys.stderr


def log(*args, file=None):
    if not args:
        return
    buffer = "[%s][Django] " % datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    args = [str(arg) for arg in args]
    buffer += " ".join(args)
    if file is None:
        file = orig_stdout
    file.write(buffer + "\n")


class DjangoUnitTestResult(unittest.result.TestResult):
    def __init__(
        self, stream=None, descriptions=None, verbosity=None, post_testcase_run=None
    ):
        super(DjangoUnitTestResult, self).__init__(stream, descriptions, verbosity)
        self.buffer = True
        self._post_testcase_run = post_testcase_run
        self._tests = {}

    def _get_test_name(self, test):
        return "%s?%s/%s" % (
            test.__class__.__module__.replace(".", "/") + ".py",
            test.__class__.__name__,
            test._testMethodName,
        )

    def _report_testresult(self, testname):
        if not self._post_testcase_run:
            return
        testresult = self._tests.get(testname)
        if not testresult:
            log("TestCase %s result not found" % testname)
            return
        logs = []
        stdout = testresult["stdout"]
        if stdout:
            logs.append(
                {
                    "time": testresult["start_time"],
                    "level": 2,
                    "content": stdout,
                }
            )
        stderr = testresult["stderr"]
        if stderr:
            level = 3
            if testresult["result"] == "failed":
                level = 4
            logs.append(
                {
                    "time": testresult["start_time"],
                    "level": level,
                    "content": stderr,
                }
            )
        steps = [
            {
                "title": "Default",
                "startTime": testresult["start_time"],
                "logs": logs,
            }
        ]
        testresult = {
            "test": {"name": testname},
            "resultType": testresult["result"],
            "startTime": testresult["start_time"],
            "endTime": testresult["end_time"],
            "steps": steps,
        }
        self._post_testcase_run(testresult)

    def _get_output(self):
        stdout = stderr = ""
        if self._stdout_buffer:
            self._stdout_buffer.seek(0)
            stdout = self._stdout_buffer.read()
        if self._stderr_buffer:
            self._stderr_buffer.seek(0)
            stderr = self._stderr_buffer.read()
        return stdout, stderr

    def getDescription(self, test):
        pass

    def startTest(self, test):
        super(DjangoUnitTestResult, self).startTest(test)
        testname = self._get_test_name(test)
        log("Start run testcase", testname)
        self._tests[testname] = {"start_time": time.time(), "result": ""}

    def addSuccess(self, test):
        super(DjangoUnitTestResult, self).addSuccess(test)
        testname = self._get_test_name(test)
        log("TestCase %s run success" % testname)
        self._tests[testname]["result"] = "succeed"
        self._tests[testname]["end_time"] = time.time()
        (
            self._tests[testname]["stdout"],
            self._tests[testname]["stderr"],
        ) = self._get_output()
        self._report_testresult(testname)

    def addError(self, test, err):
        super(DjangoUnitTestResult, self).addError(test, err)
        testname = self._get_test_name(test)
        log("TestCase %s run failed" % (testname))
        self._tests[testname]["result"] = "failed"
        self._tests[testname]["end_time"] = time.time()
        self._tests[testname]["error"] = self._exc_info_to_string(err, test)
        (
            self._tests[testname]["stdout"],
            self._tests[testname]["stderr"],
        ) = self._get_output()
        self._report_testresult(testname)

    def addFailure(self, test, err):
        super(DjangoUnitTestResult, self).addFailure(test, err)
        testname = self._get_test_name(test)
        log("TestCase %s run failed" % (testname))
        self._tests[testname]["result"] = "failed"
        self._tests[testname]["end_time"] = time.time()
        self._tests[testname]["error"] = self._exc_info_to_string(err, test)
        (
            self._tests[testname]["stdout"],
            self._tests[testname]["stderr"],
        ) = self._get_output()
        if not self._tests[testname]["stderr"]:
            self._tests[testname]["stderr"] = (
                "".join(traceback.format_exception(*err))
            ).strip()
        self._report_testresult(testname)

    def addSkip(self, test, reason):
        super(DjangoUnitTestResult, self).addSkip(test, reason)
        log("addSkip", test)

    def addExpectedFailure(self, test, err):
        super(DjangoUnitTestResult, self).addExpectedFailure(test, err)
        log("addExpectedFailure")

    def addUnexpectedSuccess(self, test):
        super(DjangoUnitTestResult, self).addUnexpectedSuccess(test)
        log("addUnexpectedSuccess")

    def printErrors(self):
        pass

    def printErrorList(self, flavour, errors):
        pass


class DjangoUnitTestRunner(object):
    resultclass = DjangoUnitTestResult

    def __init__(
        self,
        verbosity=1,
        failfast=False,
        buffer=False,
        resultclass=None,
        warnings=None,
        fd=None,
    ):
        self.verbosity = verbosity
        self.failfast = failfast
        self.buffer = buffer
        if resultclass is not None:
            self.resultclass = resultclass
        self._fd = fd

    def run(self, test):
        "Run the given test case or test suite."
        result = DjangoUnitTestResult(
            post_testcase_run=lambda it: post_testcase_run(it, self._fd)
        )
        try:
            test(result)
        finally:
            pass
        return result


class MyDiscoverRunner(DiscoverRunner):
    def __init__(self, *args, **kwargs):
        super(MyDiscoverRunner, self).__init__(*args, **kwargs)
        self._fd = kwargs.get("fd", None)

    def get_test_runner_kwargs(self):
        result = super(MyDiscoverRunner, self).get_test_runner_kwargs()
        result["fd"] = self._fd
        return result


def init_django_env(proj_root):
    """初始化django环境"""
    if proj_root not in sys.path:
        sys.path.insert(0, proj_root)
    for it in os.listdir(proj_root):
        path = os.path.join(proj_root, it)
        if os.path.isdir(path):
            if not os.path.exists(os.path.join(path, "wsgi.py")):
                continue
            settings_path = os.path.join(path, "settings.py")
            if os.path.exists(settings_path):
                os.environ["DJANGO_SETTINGS_MODULE"] = "%s.settings" % it
                break
            elif os.path.isdir(os.path.join(path, "settings")):
                for py in os.listdir(os.path.join(path, "settings")):
                    if not py.endswith(".py"):
                        continue
                    with open(os.path.join(path, "settings", py)) as fp:
                        text = fp.read()
                    if not "SECRET_KEY" in text:
                        continue
                    os.environ["DJANGO_SETTINGS_MODULE"] = "%s.settings.%s" % (
                        it,
                        py[:-3],
                    )
                    break
                else:
                    os.environ["DJANGO_SETTINGS_MODULE"] = "%s.settings" % it
                break
    else:
        raise RuntimeError("Find django settings failed")

    log("Django settings module: %s" % os.environ["DJANGO_SETTINGS_MODULE"])
    from django.apps import apps
    from django.conf import settings

    apps.populate(settings.INSTALLED_APPS)  # 初始化操作，避免加载时报错


def ipc_send(fd, item):
    buffer = json.dumps(item)
    if not isinstance(buffer, bytes):
        buffer = buffer.encode()
    buffer = struct.pack("!I", len(buffer)) + buffer
    os.write(fd, buffer)


def list_testsuite(test_suite):
    """获取testsuite中的TestCase实例列表"""
    for item in test_suite:
        if isinstance(item, unittest.TestSuite):
            for it in list_testsuite(item):
                yield it
        else:
            yield item


def collect_testcases(proj_path, test_selectors, fd=None):
    testcases = []
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover(proj_path)
    for it in list_testsuite(test_suite):
        attributes = {}
        if it.__class__.__name__ == "ModuleImportFailure":
            try:
                getattr(it, it._testMethodName)()
            except Exception as e:
                testcases.append([it._testMethodName, "", {"error": e.message}])
        elif it.__class__.__name__ == "_FailedTest":
            testcases.append(
                [it._testMethodName, "", {"error": it._exception.args[0].strip()}]
            )
        else:
            testcase_name = "%s/%s" % (it.__class__.__name__, it._testMethodName)
            testcases.append(
                [
                    it.__class__.__module__.replace(".", "/") + ".py",
                    testcase_name,
                    attributes,
                ]
            )
    if fd:
        ipc_send(fd, testcases)
    return testcases


def selector_to_django(test_selector):
    """translate from test selector format to django format"""
    if test_selector.endswith("/"):
        test_selector = test_selector[:-1]
    if "?" in test_selector:
        module, name = test_selector.split("?", 1)
    else:
        module, name = test_selector, ""
    if module.endswith(".py"):
        module = module[:-3]
    module = module.replace("/", ".")
    if name:
        return module + "." + name
    else:
        return module


def get_testcase_selector(testcase, proj):
    func_name = []
    case_name_list = testcase.split(".")
    while case_name_list:
        path = os.path.join(proj, os.sep.join(case_name_list)) + ".py"
        if os.path.isfile(path):
            return path + "?" + os.sep.join(func_name[::-1])
        else:
            func_name.append(case_name_list.pop(-1))


def pre_testcase_run(testcase, fd):
    if fd:
        ipc_send(fd, ["pre_testcase_run", testcase])


def post_testcase_run(testcase, fd):
    if fd:
        ipc_send(fd, ["post_testcase_run", testcase])


def run_testcases(proj_path, testcase_list, fd=None):
    testcase_list = [selector_to_django(case) for case in testcase_list]
    os.chdir(proj_path)
    options = {}
    if fd:
        options["fd"] = fd
    DiscoverRunner.test_runner = DjangoUnitTestRunner
    test_runner = MyDiscoverRunner(**options)
    time0 = time.time()
    failures = test_runner.run_tests(testcase_list)
    print(failures)
    log("Run %d testcases cost %.2fs" % (len(testcase_list), time.time() - time0))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="djangox", description="django tool wrapper")
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

    init_django_env(args.proj_path)
    if args.action == "collect":
        collect_testcases(args.proj_path, args.testcases.split(), args.ipc_fd)
    elif args.action == "run":
        run_testcases(args.proj_path, args.testcases.split(), args.ipc_fd)
    if args.ipc_fd:
        os.close(args.ipc_fd)
