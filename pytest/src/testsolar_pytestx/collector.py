import os
import sys
import traceback
from typing import BinaryIO, Sequence, Optional, List, Dict, Union

import pytest
from pytest import Item, Collector, CollectReport
from testsolar_testtool_sdk.model.load import LoadResult, LoadError
from testsolar_testtool_sdk.model.param import EntryParam
from testsolar_testtool_sdk.model.test import TestCase
from testsolar_testtool_sdk.reporter import Reporter

from .converter import (
    selector_to_pytest,
    pytest_to_selector,
)
from .filter import filter_invalid_selector_path
from .parser import parse_case_attributes


def collect_testcases(
    entry_param: EntryParam, pipe_io: Optional[BinaryIO] = None
) -> None:
    if entry_param.ProjectPath not in sys.path:
        sys.path.insert(0, entry_param.ProjectPath)

    load_result: LoadResult = LoadResult(
        Tests=[],
        LoadErrors=[],
    )

    valid_selectors, load_errors = filter_invalid_selector_path(
        workspace=entry_param.ProjectPath,
        selectors=entry_param.TestSelectors,
    )

    load_result.LoadErrors.extend(load_errors)

    pytest_paths = [selector_to_pytest(test_selector=it) for it in valid_selectors]
    testcase_list = [
        os.path.join(entry_param.ProjectPath, it) for it in pytest_paths if it
    ]

    my_plugin = PytestCollector(pipe_io)
    args = [
        f"--rootdir={entry_param.ProjectPath}",
        "--collect-only",
        "--continue-on-collection-errors",
        "-v",
    ]
    args.extend(testcase_list)

    print(f"[Load] try to collect testcases: {args}")
    exit_code = pytest.main(args, plugins=[my_plugin])

    if exit_code != 0:
        print(f"[Warn][Load] collect testcases exit_code: {exit_code}")

    for item in my_plugin.collected:
        full_name = pytest_to_selector(item, entry_param.ProjectPath)
        attributes = parse_case_attributes(item)
        load_result.Tests.append(TestCase(Name=full_name, Attributes=attributes))

    load_result.Tests.sort(key=lambda x: x.Name)

    for k, v in my_plugin.errors.items():
        load_result.LoadErrors.append(
            LoadError(
                name=f"load error of selector: [{k}]",
                message=v,
            )
        )

    load_result.LoadErrors.sort(key=lambda x: x.name)

    print(f"[Load] collect testcase count: {len(load_result.Tests)}")
    print(f"[Load] collect load error count: {len(load_result.LoadErrors)}")

    reporter = Reporter(pipe_io=pipe_io)
    reporter.report_load_result(load_result)


class PytestCollector:
    def __init__(self, pipe_io: Optional[BinaryIO] = None):
        self.collected: List[Item] = []
        self.errors: Dict[str, str] = {}
        self.reporter: Reporter = Reporter(pipe_io=pipe_io)

    def pytest_collection_modifyitems(
        self, items: Sequence[Union[Item, Collector]]
    ) -> None:
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
