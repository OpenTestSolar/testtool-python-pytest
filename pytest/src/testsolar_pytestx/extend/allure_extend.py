import os
import shutil
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, field

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
class StatusDetails:
    message: Optional[str] = None
    trace: Optional[str] = None


@dataclass
class Parameter:
    name: str
    value: str


@dataclass
class Step:
    name: str
    status: str
    start: int
    stop: int
    parameters: Optional[List[Parameter]] = field(default_factory=list)
    steps: Optional[List["Step"]] = field(
        default_factory=list
    )  # Note the forward reference for recursive type
    statusDetails: Optional[StatusDetails] = None


@dataclass
class AllureData:
    name: str
    status: str
    start: int
    stop: int
    uuid: str
    historyId: str
    testCaseId: str
    fullName: str
    steps: List[Step] = field(default_factory=list)
    labels: List[Dict[str, str]] = field(default_factory=list)


def check_allure_enable() -> bool:
    return os.getenv("TESTSOLAR_TTP_ENABLEALLURE", "") != ""


def initialization_allure_dir(allure_dir: str) -> None:
    """
    初始化 Allure 报告目录。
    如果指定的目录存在，则删除该目录及其所有内容。然后重新创建一个空目录。
    """
    # 检查目录是否存在
    if os.path.isdir(allure_dir):
        # 目录存在，删除目录及其所有内容
        shutil.rmtree(allure_dir)
    # 创建一个新的空目录
    os.makedirs(allure_dir, exist_ok=True)


def generate_allure_results(test_data: Dict[str, TestResult], file_name: str) -> None:
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


def format_allure_time(timestamp: float) -> datetime:
    return datetime.fromtimestamp(timestamp / 1000)


def gen_allure_step_info(steps: List[Step], index: int = 0) -> List[TestCaseStep]:
    print("Gen allure step")
    case_steps = []
    for step in steps:
        index += 1
        result = step.status
        result_type: ResultType
        if result == "passed":
            result_type = ResultType.SUCCEED
        elif result == "skipped":
            result_type = ResultType.IGNORED
        else:
            result_type = ResultType.FAILED

        log = "\n"
        if step.parameters:
            for param in step.parameters:
                log += "%-30s%-20s\n" % (
                    "key: {}".format(param.name),
                    "value: {}".format(param.value),
                )
        if step.statusDetails:
            if step.statusDetails.message and step.statusDetails.trace:
                log += step.statusDetails.message + step.statusDetails.trace
        log_info = TestCaseLog(
            Time=format_allure_time(step.start),
            Level=LogLevel.ERROR if result == "failed" else LogLevel.INFO,
            Content=log,
        )
        step_info = TestCaseStep(
            Title="{}: {}".format(".".join(list(str(index))), step.name),
            Logs=[log_info],
            StartTime=format_allure_time(step.start),
            EndTime=format_allure_time(step.stop),
            ResultType=result_type,
        )

        print("Get allure step from json file: ", step_info)
        case_steps.append(step_info)
        if step.steps:
            case_steps.extend(gen_allure_step_info(step.steps, index * 10))
    return case_steps
