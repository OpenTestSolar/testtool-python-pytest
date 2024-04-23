import os
from datetime import datetime, timedelta
from typing import List

import json
from pytest import TestReport
from testsolar_testtool_sdk.model.testresult import TestCaseLog, LogLevel, TestResult, ResultType, TestCaseStep


def gen_logs(report: TestReport) -> TestCaseLog:
    logs: List[str] = []
    if report.capstdout:
        logs.append(report.capstdout)
    if report.capstderr:
        logs.append(report.capstderr)
    if report.caplog:
        logs.append(report.caplog)

    log = "\n".join(logs)

    if report.failed:
        error_log = report.longreprtext
        if error_log:
            log += "\n\n"
            log += error_log

    return TestCaseLog(
        Time=datetime.now() - timedelta(report.duration),
        Level=LogLevel.ERROR if report.failed else LogLevel.INFO,
        Content=log,
    )


def generate_allure_results(test_data: dict[str, TestResult], file_name: str) -> dict[str, TestResult]:
    with open(file_name) as fp:
        data = json.loads(fp.read())
        full_name = data["fullName"].replace("#", ".")
        for testcase_name in test_data.keys():
            testcase_format_name = ".".join(
                testcase_name.replace(".py?", os.sep).split(os.sep)
            )
            if full_name != testcase_format_name:
                continue
            if "steps" in data.keys():
                step_info = gen_allure_step_info(data["steps"])
            test_data[testcase_name].Steps.clear()
            test_data[testcase_name].Steps.extend(step_info)
    return test_data



def format_allure_time(timestamp: float):
    return datetime.fromtimestamp(timestamp)

def gen_allure_step_info(steps: any, index=None) -> List[TestCaseStep]:
    case_steps: TestCaseStep = []
    if not index:
        index = 0
    if isinstance(steps, list):
        for step in steps:
            index += 1
            result = step["status"]
            result_type: ResultType
            if result == "passed":
                result_type = ResultType.SUCCEED
            elif result == "skiped":
                result_type = ResultType.IGNORED
            else:
                result_type = ResultType.FAILED

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
            log_info = TestCaseLog(
                        Time=format_allure_time(step["start"]),
                        Level=LogLevel.ERROR if result == "failed" else LogLevel.INFO,
                        Content=log,
                    )
            step_info = TestCaseStep(
                    Title="{}： {}".format(".".join(list(str(index))), step["name"]),
                    Logs=[log_info],
                    StartTime=format_allure_time(step["start"]),
                    EndTime=format_allure_time(step["stop"]),
                    ResultType=result_type,
                )
            case_steps.append(step_info)
            if "steps" in step:
                case_steps.extend(gen_allure_step_info(step["steps"], index * 10))
    return case_steps