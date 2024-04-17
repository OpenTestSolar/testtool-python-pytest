import io
import unittest
from pathlib import Path

from testsolar_testtool_sdk.model.param import EntryParam
from testsolar_testtool_sdk.pipe_reader import read_load_result

from src.pytestx.collector import collect_testcases


class CollectorTest(unittest.TestCase):
    testdata_dir: str = str(
        Path(__file__).parent.parent.absolute().joinpath("testdata")
    )

    def test_collect_testcases_when_selector_is_valid(self):
        entry = EntryParam(
            TaskId="aa",
            ProjectPath=self.testdata_dir,
            TestSelectors=[
                "normal_case.py?test_success",
                "aa/bb/cc/class_test.py",
                "data_drive.py",
                "errors/import_error.py",
                "errors/load_error.py",
            ],
            FileReportPath="",
        )

        pipe_io = io.BytesIO()
        collect_testcases(entry, pipe_io)
        pipe_io.seek(0)

        re = read_load_result(pipe_io)

        self.assertEqual(len(re.Tests), 5)
        self.assertEqual(len(re.LoadErrors), 2)

        self.assertEqual(
            re.Tests[0].Name, "aa/bb/cc/class_test.py?TestCompute/test_add"
        )
        self.assertEqual(re.Tests[1].Name, "data_drive.py?test_eval/[2+4-6]")
        self.assertEqual(re.Tests[2].Name, "data_drive.py?test_eval/[3+5-8]")
        self.assertEqual(re.Tests[3].Name, "data_drive.py?test_eval/[6*9-42]")

        self.assertEqual(re.Tests[4].Name, "normal_case.py?test_success")
        self.assertEqual(re.Tests[4].Attributes["owner"], "foo")
        self.assertEqual(re.Tests[4].Attributes["description"], "测试获取答案")
        self.assertEqual(re.Tests[4].Attributes["tag"], "high")
        self.assertEqual(
            re.Tests[4].Attributes["extra_attributes"], '[{"env": ["AA", "BB"]}]'
        )

        self.assertEqual(
            re.LoadErrors[0].name, "load error of selector: [errors/import_error.py]"
        )
        self.assertIn(
            "ModuleNotFoundError: No module named 'bad_import'",
            re.LoadErrors[0].message,
        )
        self.assertEqual(
            re.LoadErrors[1].name, "load error of selector: [errors/load_error.py]"
        )
        self.assertIn("SyntaxError: ", re.LoadErrors[1].message)

    def test_collect_testcases_when_select_not_valid(self):
        entry = EntryParam(
            TaskId="aa",
            ProjectPath=self.testdata_dir,
            TestSelectors=[
                "data_drive.py",
                "not_exist.py",
            ],
            FileReportPath="",
        )

        pipe_io = io.BytesIO()
        collect_testcases(entry, pipe_io)
        pipe_io.seek(0)

        re = read_load_result(pipe_io)

        self.assertEqual(len(re.Tests), 3)
        self.assertEqual(len(re.LoadErrors), 1)
        self.assertIn("not_exist.py does not exist, SKIP it", re.LoadErrors[0].message)

    def test_collect_testcases_with_utf8_chars(self):
        entry = EntryParam(
            TaskId="aa",
            ProjectPath=self.testdata_dir,
            TestSelectors=[
                "data_drive_zh_cn.py",
            ],
            FileReportPath="",
        )

        pipe_io = io.BytesIO()
        collect_testcases(entry, pipe_io)
        pipe_io.seek(0)

        re = read_load_result(pipe_io)

        self.assertEqual(len(re.Tests), 3)
        self.assertEqual(len(re.LoadErrors), 0)

        self.assertEqual(
            re.Tests[0].Name, "data_drive_zh_cn.py?test_include/[#?-#?^$%!/]"
        )
        self.assertEqual(
            re.Tests[1].Name, "data_drive_zh_cn.py?test_include/[中文-中文汉字]"
        )
        self.assertEqual(
            re.Tests[2].Name,
            "data_drive_zh_cn.py?test_include/[파일을 찾을 수 없습니다-ファイルが見つかりません]",
        )
