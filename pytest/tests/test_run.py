from pathlib import Path
from unittest import TestCase

import dacite.exceptions
import pytest
from testsolar_testtool_sdk.model.testresult import ResultType
from testsolar_testtool_sdk.model.test import TestCase as SdkTestCase
from testsolar_testtool_sdk.file_reader import read_file_test_result

from src.run import run_testcases_from_args


class TestExecuteEntry(TestCase):
    testdata_dir = Path(__file__).parent.parent.absolute().joinpath("testdata")

    def test_run_testcases_from_args(self):
        run_testcases_from_args(
            args=[
                "run.py",
                Path.joinpath(Path(self.testdata_dir), "entry_run.json"),
            ],
            workspace=str(self.testdata_dir),
        )

        start = read_file_test_result(
            report_path=Path("./"), case=SdkTestCase(Name="test_normal_case.py?test_success")
        )
        self.assertEqual(start.ResultType, ResultType.SUCCEED)

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

        run_testcases_from_args(
            args=[
                "run.py",
                str(Path(self.testdata_dir) / "custom_pytest_ini" / "entry.json"),
            ],
            workspace=str(self.testdata_dir / "custom_pytest_ini"),
        )

        end = read_file_test_result(
            report_path=Path("./"),
            case=SdkTestCase(Name="many/v1/test_normal_case_01.py?test_success"),
        )
        self.assertEqual(end.ResultType, ResultType.SUCCEED)

    @pytest.mark.skip("暂时未实现，需要执行出错时上报忽略状态")
    def test_continue_run_when_one_case_is_not_found(self):
        run_testcases_from_args(
            args=[
                "run.py",
                Path.joinpath(Path(self.testdata_dir), "entry_1_case_not_found.json"),
            ],
            workspace=str(self.testdata_dir),
        )

        start = read_file_test_result(
            report_path=Path("./"),
            case=SdkTestCase(Name="test_normal_case.py?test_success[not_found_1]"),
        )
        self.assertEqual(start.ResultType, ResultType.IGNORED)
