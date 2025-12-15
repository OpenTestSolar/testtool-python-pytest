import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional
from loguru import logger
from pathlib import Path

from dacite import from_dict
from testsolar_testtool_sdk.model.testresult import (
    TestCaseLog,
    LogLevel,
    TestResult,
    ResultType,
    TestCaseStep,
)


# 定义数据类，用于表示Allure报告中的各种结构
@dataclass
class StatusDetails:
    message: Optional[str] = None
    trace: Optional[str] = None


@dataclass
class Parameter:
    name: str
    value: str


@dataclass
class Attachments:
    name: str
    source: str
    type: str


@dataclass
class Step:
    name: str
    status: str
    start: int
    stop: int
    parameters: Optional[List[Parameter]] = field(default_factory=list)  # type: ignore
    steps: Optional[List["Step"]] = field(default_factory=list)  # type: ignore
    statusDetails: Optional[StatusDetails] = None
    attachments: Optional[List[Attachments]] = None


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
    attachments: Optional[List[Attachments]] = None


def check_allure_enable() -> bool:
    """
    检查环境变量以确定是否启用Allure报告。
    """
    return os.getenv("TESTSOLAR_TTP_ENABLEALLURE", "") in ["1", "true"]


def initialization_allure_dir(allure_dir: str) -> None:
    """
    初始化 Allure 报告目录。如果指定的目录存在，则删除该目录及其所有内容。然后重新创建一个空目录。

    :param allure_dir: Allure 报告目录路径
    """
    logger.info(f"Initializing Allure directory: {allure_dir}")
    if Path(allure_dir).exists():
        logger.info(f"Directory {allure_dir} exists. Removing it.")
        try:
            shutil.rmtree(allure_dir)
        except (OSError, FileNotFoundError) as e:
            logger.warning(f"Failed to remove existing directory {allure_dir}: {e}")

    try:
        os.makedirs(allure_dir, exist_ok=True)
        logger.info(f"Directory {allure_dir} created.")
    except OSError as e:
        logger.error(f"Failed to create directory {allure_dir}: {e}")


def generate_allure_results(
    test_data: Dict[str, TestResult], file_name: str, attachment_dir: str
) -> None:
    """
    生成 Allure 报告结果。

    :param test_data: 测试数据字典
    :param file_name: 包含 Allure 报告的 JSON 文件的名称
    :param attachment_dir: 附件目录
    """
    logger.info("Start to generate allure results")
    logger.debug(f"Reading Allure data from file: {file_name}")
    with open(file_name) as fp:
        allure_data = from_dict(data_class=AllureData, data=json.loads(fp.read()))
        full_name = allure_data.fullName.replace("#", ".")
        logger.debug(f"Parsed Allure data for test case: {full_name}")

        for testcase_name in test_data.keys():
            logger.info(f"Processing test case: {testcase_name}")
            step_info: List[TestCaseStep] = []
            testcase_format_name = ".".join(
                testcase_name.replace(".py?", os.sep).replace("/[", "[").split(os.sep)
            )
            logger.debug(f"Formatted test case name: {testcase_format_name}")

            # 处理参数化测试用例：提取基础名称进行匹配
            testcase_base_name = (
                testcase_format_name.split("[")[0]
                if "[" in testcase_format_name
                else testcase_format_name
            )

            if full_name != testcase_format_name:
                if full_name == testcase_base_name:
                    logger.info(
                        f"Test case {testcase_format_name} is a parameterized case, matched base name: {full_name}"
                    )
                elif full_name in testcase_format_name and testcase_format_name.endswith(
                    allure_data.name
                ):
                    logger.info(
                        f"Test case {testcase_format_name} was datadrive case , continue to get result!!"
                    )
                else:
                    logger.info(
                        f"Test case name {full_name} does not match {testcase_format_name}. Skipping."
                    )
                    continue

            if allure_data.steps:
                logger.info(f"Generating step info for test case {full_name}")
                step_info = gen_allure_step_info(allure_data.steps, attachment_dir)

            if allure_data.attachments:
                logger.info(f"Processing attachments for test case {full_name}")
                for attachment in allure_data.attachments:
                    attachment_path = Path(attachment_dir).joinpath(attachment.source)
                    logger.debug(f"Attachment path: {str(attachment_path)}")

                    if Path(attachment_path).is_file():
                        logger.info(f"Reading attachment: {attachment_path}")
                        with open(attachment_path, "r", encoding="utf-8", errors="ignore") as f:
                            log_content = f.read()
                            log_info = TestCaseLog(
                                Time=format_allure_time(allure_data.start),
                                Level=LogLevel.INFO,
                                Content=f"Attachment {attachment.name}:\n{log_content}",
                            )
                            step_info.append(
                                TestCaseStep(
                                    Title="Testcase Stdout:",
                                    Logs=[log_info],
                                    StartTime=format_allure_time(allure_data.start),
                                    EndTime=format_allure_time(allure_data.stop),
                                    ResultType=ResultType.SUCCEED
                                    if allure_data.status == "passed"
                                    else ResultType.FAILED,
                                )
                            )
            test_data[testcase_name].Steps.clear()
            test_data[testcase_name].Steps.extend(step_info)
            logger.info(f"Finished processing test case: {testcase_name}")


def format_allure_time(timestamp: float) -> datetime:
    """
    格式化 Allure 时间戳。

    :param timestamp: 时间戳
    :return: 格式化的日期时间对象
    """
    formatted_time = datetime.fromtimestamp(timestamp / 1000)
    logger.debug(f"Formatted timestamp {timestamp} to {formatted_time}")
    return formatted_time


def gen_allure_step_info(
    steps: List[Step], attachment_dir: str, index: int = 0
) -> List[TestCaseStep]:
    """
    生成 Allure 步骤信息。

    :param steps: 步骤列表
    :param attachment_dir: 附件目录
    :param index: 步骤索引
    :return: 测试用例步骤列表
    """
    logger.info("Generating allure step info")
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
        if step.attachments:
            for attachment in step.attachments:
                attachment_path = Path(attachment_dir).joinpath(attachment.source)
                logger.debug(f"Attachment path: {str(attachment_path)}")

                if Path(attachment_path).exists():
                    logger.info(f"Reading attachment: {attachment_path}")
                    with open(attachment_path, "r") as f:
                        log += f"\n{attachment.name}:\n" + f.read() + "\n\n"

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

        logger.info(f"Generated step info: {step_info}")
        case_steps.append(step_info)
        if step.steps:
            case_steps.extend(gen_allure_step_info(step.steps, attachment_dir, index * 10))
    return case_steps
