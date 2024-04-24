import os
from datetime import datetime
from typing import List, Dict, Any
from dataclasses import dataclass, field
from typing import List, Dict
from datetime import datetime

import json
from dacite import from_dict
from testsolar_testtool_sdk.model.testresult import (
    TestCaseLog,
    LogLevel,
    TestResult,
    ResultType,
    TestCaseStep,
)


@dataclass
class AllureData:
    name: str
    status: str
    steps: List[str] = field(default_factory=list)
    start: datetime
    stop: datetime
    uuid: str
    historyId: str
    testCaseId: str
    fullName: str
    labels: List[str] = field(default_factory=list)

    @staticmethod
    def from_json(data: Dict[str, Any]) -> "AllureData":
        return AllureData(
            name=data["name"],
            status=data["status"],
            steps=data.get("steps", []),
            start=datetime.fromtimestamp(data["start"] / 1000.0),
            stop=datetime.fromtimestamp(data["stop"] / 1000.0),
            uuid=data["uuid"],
            historyId=data["historyId"],
            testCaseId=data["testCaseId"],
            fullName=data["fullName"],
            labels=data.get("labels", []),
        )


def check_allure_enable() -> bool:
    return os.getenv("TESTSOLAR_TTP_ENABLEALLURE", "") == ""


def initialization_allure_dir(allure_dir):
    if not os.path.isdir(allure_dir):
        os.mkdir(allure_dir)
    else:
        for file_name in os.listdir(allure_dir):
            os.remove(os.path.join(allure_dir, file_name))


def generate_allure_results(
    test_data: Dict[str, TestResult], file_name: str
) -> Dict[str, TestResult]:
    print("Start to generate allure results")
    with open(file_name) as fp:
        allure_data = from_dict(data_class=AllureData, data=json.loads(fp.read()))
        full_name = allure_data.fullName.replace("#", ".")
        for testcase_name in test_data.keys():
            testcase_format_name = ".".join(
                testcase_name.replace(".py?", os.sep).split(os.sep)
            )
            if full_name != testcase_format_name:
                continue
            if allure_data.steps:
                step_info = gen_allure_step_info(allure_data.steps)
            test_data[testcase_name].Steps.clear()
            test_data[testcase_name].Steps.extend(step_info)
    return test_data


def format_allure_time(timestamp: float):
    return datetime.fromtimestamp(timestamp / 1000)


def gen_allure_step_info(steps: Any, index: int = 0) -> List[TestCaseStep]:
    print("Gen allure step")
    case_steps = []
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

            log = "\n"
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
                Time=step["start"],
                Level=LogLevel.ERROR if result == "failed" else LogLevel.INFO,
                Content=log,
            )
            step_info = TestCaseStep(
                Title="{}: {}".format(".".join(list(str(index))), step["name"]),
                Logs=[log_info],
                StartTime=step["start"],
                EndTime=step["stop"],
                ResultType=result_type,
            )

            print("Get allure step from json file: ", step_info)
            case_steps.append(step_info)
            if "steps" in step:
                case_steps.extend(gen_allure_step_info(step["steps"], index * 10))
    return case_steps
