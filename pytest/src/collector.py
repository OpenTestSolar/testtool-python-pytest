import os
import sys
from typing import BinaryIO

import pytest
from loguru import logger
from testsolar_testtool_sdk.model.load import LoadResult, LoadError
from testsolar_testtool_sdk.model.param import EntryParam
from testsolar_testtool_sdk.model.test import TestCase
from testsolar_testtool_sdk.reporter import Reporter, ReportType

from .converter import selector_to_pytest
from .parser import parse_case_attributes
from .pytestx import PytestTestSolarPlugin
from .pytestx import normalize_testcase_name


def collect_testcases(entry_param: EntryParam, pipe_io: BinaryIO = None) -> None:
    if entry_param.project_path not in sys.path:
        sys.path.insert(0, entry_param.project_path)
    testcase_list = [
        os.path.join(entry_param.project_path, selector_to_pytest(it)) for it in entry_param.test_selectors
    ]
    logger.info(f"[Load] try to load testcases: {testcase_list}")
    my_plugin = PytestTestSolarPlugin()
    args = [
        f"--rootdir={entry_param.project_path}",
        "--collect-only",
        "--continue-on-collection-errors",
        "-v"
    ]
    args.extend(testcase_list)

    exit_code = pytest.main(args, plugins=[my_plugin])

    load_result: LoadResult = LoadResult(
        Tests=[],
        LoadErrors=[],
    )

    if exit_code != 0:
        logger.error(f"[Load] collect testcases exit_code: {exit_code}")

    for item in my_plugin.collected:
        if hasattr(item, "path") and hasattr(item, "cls"):
            rel_path = os.path.relpath(item.path, entry_param.project_path)
            name = item.name
            if item.cls:
                name = item.cls.__name__ + "/" + name
            full_name = f"{rel_path}?{name}"
        elif hasattr(item, "nodeid"):
            full_name = normalize_testcase_name(item.nodeid)
        else:
            rel_path = item.location[0]
            name = item.location[2].replace(".", "/")
            full_name = f"{rel_path}?{name}"

        if full_name.endswith(']'):
            full_name = full_name.replace('[', "/[")

        attributes = parse_case_attributes(item)
        load_result.tests.append(TestCase(
            Name=full_name,
            Attributes=attributes
        ))

    load_result.tests.sort(key=lambda x: x.name)

    for item in my_plugin.errors:
        load_result.load_errors.append(LoadError(
            name="load error",
            message=str(my_plugin.errors.get(item))
        ))

    load_result.load_errors.sort(key=lambda x: x.name)

    logger.info(f"[Load] collect testcase count: {len(load_result.tests)}")
    logger.info(f"[Load] collect load error count: {len(load_result.load_errors)}")

    reporter = Reporter(reporter_type=ReportType.Pipeline, pipe_io=pipe_io)
    reporter.report_load_result(load_result)
