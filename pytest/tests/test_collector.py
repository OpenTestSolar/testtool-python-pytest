import io
import unittest
from pathlib import Path
from typing import Dict, List

from testsolar_testtool_sdk.model.param import EntryParam
from testsolar_testtool_sdk.model.load import LoadResult
from testsolar_testtool_sdk.pipe_reader import read_load_result

from src.testsolar_pytestx.collector import collect_testcases


class CollectorTest(unittest.TestCase):
    testdata_dir: str = str(Path(__file__).parent.parent.absolute().joinpath("testdata"))

    def test_collect_testcases_when_selector_is_valid(self):
        entry = EntryParam(
            TaskId="aa",
            ProjectPath=self.testdata_dir,
            TestSelectors=[
                "test_normal_case.py?test_success",
                "aa/bb/cc/test_in_sub_class.py",
                "test_data_drive.py",
                "errors/test_import_error.py",
                "errors/test_load_error.py",
            ],
            FileReportPath="",
        )

        pipe_io = io.BytesIO()
        collect_testcases(entry, pipe_io)
        pipe_io.seek(0)

        re = read_load_result(pipe_io)

        self.assertEqual(len(re.Tests), 6)
        self.assertEqual(len(re.LoadErrors), 2)
        re.Tests.sort(key=lambda x: x.Name)
        re.LoadErrors.sort(key=lambda x: x.name)
        self.assertEqual(re.Tests[0].Name, "aa/bb/cc/test_in_sub_class.py?TestCompute/test_add")
        self.assertEqual(re.Tests[1].Name, "test_data_drive.py?test_eval/%5B2%2B4-6%5D")
        self.assertEqual(re.Tests[2].Name, "test_data_drive.py?test_eval/%5B3%2B5-8%5D")
        self.assertEqual(re.Tests[3].Name, "test_data_drive.py?test_eval/%5B6%2A9-42%5D")
        self.assertEqual(
            re.Tests[4].Name,
            "test_data_drive.py?test_special_data_drive_name/%5B%E4%B8%AD%E6%96%87-%E5%88%86%E5%8F%B7%2B%5Bid%3A32%5D%5D",
        )

        self.assertEqual(re.Tests[5].Name, "test_normal_case.py?test_success")
        self.assertEqual(re.Tests[5].Attributes["owner"], "foo")
        self.assertEqual(re.Tests[5].Attributes["description"], "测试获取答案")
        self.assertEqual(re.Tests[5].Attributes["tag"], "high")
        self.assertEqual(re.Tests[5].Attributes["extra_attributes"], '[{"env": ["AA", "BB"]}]')

        self.assertEqual(
            re.LoadErrors[0].name,
            "load error of selector: [errors/test_import_error.py]",
        )
        self.assertIn(
            "ModuleNotFoundError: No module named 'bad_import'",
            re.LoadErrors[0].message,
        )
        self.assertEqual(
            re.LoadErrors[1].name, "load error of selector: [errors/test_load_error.py]"
        )
        self.assertIn("SyntaxError: ", re.LoadErrors[1].message)

    def test_collect_testcases_when_select_not_valid(self):
        entry = EntryParam(
            TaskId="aa",
            ProjectPath=self.testdata_dir,
            TestSelectors=[
                "test_data_drive.py",
                "test_not_exist.py",
            ],
            FileReportPath="",
        )

        pipe_io = io.BytesIO()
        collect_testcases(entry, pipe_io)
        pipe_io.seek(0)

        re = read_load_result(pipe_io)
        re.Tests.sort(key=lambda x: x.Name)
        re.LoadErrors.sort(key=lambda x: x.name)
        self.assertEqual(len(re.Tests), 4)
        self.assertEqual(len(re.LoadErrors), 1)
        self.assertIn("test_not_exist.py does not exist, SKIP it", re.LoadErrors[0].message)

    def test_collect_testcases_with_utf8_chars(self):
        entry = EntryParam(
            TaskId="aa",
            ProjectPath=self.testdata_dir,
            TestSelectors=[
                "test_data_drive_zh_cn.py",
            ],
            FileReportPath="",
        )

        pipe_io = io.BytesIO()
        collect_testcases(entry, pipe_io)
        pipe_io.seek(0)

        re = read_load_result(pipe_io)
        re.Tests.sort(key=lambda x: x.Name)
        re.LoadErrors.sort(key=lambda x: x.name)
        self.assertEqual(len(re.Tests), 3)
        self.assertEqual(len(re.LoadErrors), 0)

        self.assertEqual(
            re.Tests[0].Name,
            "test_data_drive_zh_cn.py?test_include/%5B%23%3F-%23%3F%5E%24%25%21/%5D",
        )
        self.assertEqual(
            re.Tests[1].Name,
            "test_data_drive_zh_cn.py?test_include/%5B%E4%B8%AD%E6%96%87-%E4%B8%AD%E6%96%87%E6%B1%89%E5%AD%97%5D",
        )
        self.assertEqual(
            re.Tests[2].Name,
            "test_data_drive_zh_cn.py?test_include/%5B%ED%8C%8C%EC%9D%BC%EC%9D%84%20%EC%B0%BE%EC%9D%84%20%EC%88%98%20%EC%97%86%EC%8A%B5%EB%8B%88%EB%8B%A4-%E3%83%95%E3%82%A1%E3%82%A4%E3%83%AB%E3%81%8C%E8%A6%8B%E3%81%A4%E3%81%8B%E3%82%8A%E3%81%BE%E3%81%9B%E3%82%93%5D",
        )

    def test_collect_testcases_with_case_drive_separator(self):
        entry = EntryParam(
            TaskId="aa",
            ProjectPath=self.testdata_dir,
            TestSelectors=[
                "test_normal_case.py?test_success→压缩机测试",
                "test_normal_case.py?test_success→解压机测试",
                "test_normal_case.py?test_success→循环机测试",
            ],
            FileReportPath="",
        )

        case_records = {}

        def loader_extend(param_1: str, param_2: LoadResult, param_3: Dict[str, List[str]]) -> None:
            case_records.update(param_3)

        pipe_io = io.BytesIO()
        collect_testcases(entry, pipe_io, extra_load_function=loader_extend)
        pipe_io.seek(0)

        re = read_load_result(pipe_io)
        re.Tests.sort(key=lambda x: x.Name)
        re.LoadErrors.sort(key=lambda x: x.name)
        self.assertEqual(len(re.Tests), 1)
        self.assertEqual(len(re.LoadErrors), 0)

        self.assertEqual(re.Tests[0].Name, "test_normal_case.py?test_success")

        self.assertEqual(len(case_records), 1)
        self.assertIn("test_normal_case.py?test_success", case_records)

        records = case_records["test_normal_case.py?test_success"]
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0], "压缩机测试")
        self.assertEqual(records[1], "解压机测试")
        self.assertEqual(records[2], "循环机测试")

    def test_collect_testcases_when_testcase_not_exist(self):
        entry = EntryParam(
            TaskId="aa",
            ProjectPath=self.testdata_dir,
            TestSelectors=[
                "test_normal_case.py?name=not_exist",
            ],
            FileReportPath="",
        )

        pipe_io = io.BytesIO()
        collect_testcases(entry, pipe_io)
        pipe_io.seek(0)

        re = read_load_result(pipe_io)
        re.Tests.sort(key=lambda x: x.Name)
        re.LoadErrors.sort(key=lambda x: x.name)
        self.assertEqual(len(re.LoadErrors), 1)

        self.assertEqual(
            re.LoadErrors[0].name,
            "test_normal_case.py?name=not_exist",
        )

    def test_collect_testcases_with_skipp_error(self):
        entry = EntryParam(
            TaskId="aa",
            ProjectPath=self.testdata_dir,
            TestSelectors=[
                "test_normal_case.py",
                "test_skipped_error.py",
            ],
            FileReportPath="",
        )

        pipe_io = io.BytesIO()
        collect_testcases(entry, pipe_io)
        pipe_io.seek(0)

        re = read_load_result(pipe_io)
        re.Tests.sort(key=lambda x: x.Name)
        re.LoadErrors.sort(key=lambda x: x.name)
        self.assertEqual(len(re.Tests), 3)
        self.assertEqual(len(re.LoadErrors), 1)

    def test_collect_testcases_with_emoji(self):
        entry = EntryParam(
            TaskId="aa",
            ProjectPath=self.testdata_dir,
            TestSelectors=[
                "test_emoji_data_drive.py",
            ],
            FileReportPath="",
        )

        pipe_io = io.BytesIO()
        collect_testcases(entry, pipe_io)
        pipe_io.seek(0)

        re = read_load_result(pipe_io)
        re.Tests.sort(key=lambda x: x.Name)
        re.LoadErrors.sort(key=lambda x: x.name)
        self.assertEqual(len(re.Tests), 1)
        self.assertEqual(len(re.LoadErrors), 0)
        self.assertEqual(
            re.Tests[0].Name,
            "test_emoji_data_drive.py?test_emoji_data_drive_name/%5B%F0%9F%98%84%5D",
        )
