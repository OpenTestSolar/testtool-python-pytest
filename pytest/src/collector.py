import logging
import os
import sys
import traceback
from typing import BinaryIO, Sequence

import pytest
from pytest import Item, Collector, CollectReport
from testsolar_testtool_sdk.model.load import LoadResult, LoadError
from testsolar_testtool_sdk.model.param import EntryParam
from testsolar_testtool_sdk.model.test import TestCase
from testsolar_testtool_sdk.reporter import Reporter

from .converter import selector_to_pytest
from .parser import parse_case_attributes
from .pytestx import normalize_testcase_name


def collect_testcases(entry_param: EntryParam, pipe_io: BinaryIO | None = None) -> None:
    if entry_param.ProjectPath not in sys.path:
        sys.path.insert(0, entry_param.ProjectPath)
    testcase_list = [
        os.path.join(entry_param.ProjectPath, selector_to_pytest(it)) for it in entry_param.TestSelectors
    ]
    logging.info(f"[Load] try to load testcases: {testcase_list}")
    my_plugin = PytestCollector()
    args = [
        f"--rootdir={entry_param.ProjectPath}",
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
        logging.warning(f"[Load] collect testcases exit_code: {exit_code}")

    for item in my_plugin.collected:
        if hasattr(item, "path") and hasattr(item, "cls"):
            rel_path = os.path.relpath(item.path, entry_param.ProjectPath)
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
        load_result.Tests.append(TestCase(
            Name=full_name,
            Attributes=attributes
        ))

    load_result.Tests.sort(key=lambda x: x.Name)

    for item in my_plugin.errors:
        load_result.LoadErrors.append(LoadError(
            name="load error",
            message=str(my_plugin.errors.get(item))
        ))

    load_result.LoadErrors.sort(key=lambda x: x.name)

    logging.info(f"[Load] collect testcase count: {len(load_result.Tests)}")
    logging.info(f"[Load] collect load error count: {len(load_result.LoadErrors)}")

    reporter = Reporter(pipe_io=pipe_io)
    reporter.report_load_result(load_result)


class PytestCollector:
    def __init__(self, pipe_io: BinaryIO | None = None):
        self.collected: list[Item] = []
        self.errors = {}
        self.reporter: Reporter = Reporter(pipe_io=pipe_io)

    def pytest_collection_modifyitems(self, items: Sequence[Item | Collector]) -> None:
        for item in items:
            if isinstance(item, Item):
                self.collected.append(item)

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
