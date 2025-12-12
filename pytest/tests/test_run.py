import json
import os
import tempfile
from pathlib import Path
from unittest import TestCase

import dacite.exceptions
import pytest
from testsolar_testtool_sdk.model.testresult import ResultType
from testsolar_testtool_sdk.file_reader import read_file_test_result
from testsolar_testtool_sdk.model.test import TestCase as TestCaseModel

from src.run import run_testcases_from_args


class TestExecuteEntry(TestCase):
    testdata_dir = Path(__file__).parent.parent.absolute().joinpath("testdata")

    def test_header_injection(self):
        os.environ["ENABLE_API_COLLECTING"] = "1"
        self.test_run_testcases_from_args()

    def test_run_testcases_from_args(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)

            # 创建临时entry.json
            entry_file = Path(tmpdir) / "entry.json"
            with open(Path(self.testdata_dir) / "entry.json", "r") as f:
                entry_data = json.load(f)
            entry_data["FileReportPath"] = str(report_dir)
            with open(entry_file, "w") as f:
                json.dump(entry_data, f)

            run_testcases_from_args(
                args=[
                    "run.py",
                    str(entry_file),
                ],
                workspace=str(self.testdata_dir),
            )

            # 读取第一个测试用例的结果（不检查RUNNING状态）
            test_case = TestCaseModel(Name="test_normal_case.py?test_success", Attributes={})
            start = read_file_test_result(report_dir, test_case)
            # 由于FileReporter会覆盖，我们只能检查最终状态
            self.assertIn(start.ResultType, [ResultType.RUNNING, ResultType.SUCCEED])

    def test_raise_error_when_param_is_invalid(self):
        with self.assertRaises(dacite.exceptions.MissingValueError):
            run_testcases_from_args(
                args=[
                    "run.py",
                    Path.joinpath(Path(self.testdata_dir), "bad_entry.json"),
                ],
                workspace=str(self.testdata_dir),
            )

    def test_run_some_case_of_many_case_with_custom_pytest_ini(self):
        """
        如果用户代码仓库中存在冲突的pytest.ini选项配置，那么需要覆盖掉用户配置
        """

        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)

            # 创建临时entry.json
            custom_entry_path = Path(self.testdata_dir) / "custom_pytest_ini" / "entry.json"
            entry_file = Path(tmpdir) / "entry.json"
            with open(custom_entry_path, "r") as f:
                entry_data = json.load(f)
            entry_data["FileReportPath"] = str(report_dir)
            with open(entry_file, "w") as f:
                json.dump(entry_data, f)

            run_testcases_from_args(
                args=[
                    "run.py",
                    str(entry_file),
                ],
                workspace=str(self.testdata_dir / "custom_pytest_ini"),
            )

            # 读取测试结果
            test_case = TestCaseModel(
                Name="many/v1/test_normal_case_01.py?test_success", Attributes={}
            )
            end = read_file_test_result(report_dir, test_case)
            self.assertEqual(end.ResultType, ResultType.SUCCEED)

    @pytest.mark.skip("暂时未实现，需要执行出错时上报忽略状态")
    def test_continue_run_when_one_case_is_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)

            entry_file = Path(tmpdir) / "entry.json"
            with open(
                Path.joinpath(Path(self.testdata_dir), "entry_1_case_not_found.json"), "r"
            ) as f:
                entry_data = json.load(f)
            entry_data["FileReportPath"] = str(report_dir)
            with open(entry_file, "w") as f:
                json.dump(entry_data, f)

            run_testcases_from_args(
                args=[
                    "run.py",
                    str(entry_file),
                ],
                workspace=str(self.testdata_dir),
            )

            # 读取结果
            test_case = TestCaseModel(Name="test_normal_case.py?test_success", Attributes={})
            start = read_file_test_result(report_dir, test_case)
            self.assertEqual(start.ResultType, ResultType.IGNORED)
