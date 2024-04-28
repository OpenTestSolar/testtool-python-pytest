import io
import unittest
from pathlib import Path

from testsolar_testtool_sdk.model.param import EntryParam
from testsolar_testtool_sdk.model.testresult import ResultType, LogLevel
from testsolar_testtool_sdk.pipe_reader import read_test_result

from src.testsolar_pytestx.executor import run_testcases


class ExecutorTest(unittest.TestCase):
    testdata_dir: str = str(
        Path(__file__).parent.parent.absolute().joinpath("testdata")
    )

    def test_run_success_testcase_with_logs(self):
        entry = EntryParam(
            TaskId="aa",
            ProjectPath=self.testdata_dir,
            TestSelectors=[
                "test_normal_case.py?name=test_success&tag=A&priority=High",
            ],
            FileReportPath="",
        )

        pipe_io = io.BytesIO()
        run_testcases(entry, pipe_io)
        pipe_io.seek(0)

        start = read_test_result(pipe_io)
        self.assertEqual(start.ResultType, ResultType.RUNNING)

        end = read_test_result(pipe_io)
        self.assertEqual(end.Test.Name, "test_normal_case.py?test_success")
        self.assertEqual(end.Test.Attributes["tag"], "high")
        self.assertEqual(end.Test.Attributes["owner"], "foo")
        self.assertEqual(end.ResultType, ResultType.SUCCEED)
        self.assertEqual(len(end.Steps), 3)

        step1 = end.Steps[0]
        self.assertEqual(step1.Title, "Setup")
        self.assertEqual(len(step1.Logs), 1)
        self.assertEqual(step1.Logs[0].Level, LogLevel.INFO)
        self.assertEqual(step1.ResultType, ResultType.SUCCEED)
        self.assertIn("this is setup", step1.Logs[0].Content)

        step2 = end.Steps[1]
        self.assertEqual(step2.Title, "Run TestCase")
        self.assertEqual(len(step2.Logs), 1)
        self.assertEqual(step2.Logs[0].Level, LogLevel.INFO)
        self.assertEqual(step2.ResultType, ResultType.SUCCEED)
        self.assertIn("this is print sample output", step2.Logs[0].Content)

        step3 = end.Steps[2]
        self.assertEqual(step3.Title, "Teardown")
        self.assertEqual(len(step3.Logs), 1)
        self.assertEqual(step3.Logs[0].Level, LogLevel.INFO)
        self.assertEqual(step3.ResultType, ResultType.SUCCEED)
        self.assertEqual(
            step3.Logs[0].Content,
            """this is setup
this is print sample output
this is teardown
""",
        )

    def test_run_success_testcase_with_one_invalid_selector(self):
        entry = EntryParam(
            TaskId="aa",
            ProjectPath=self.testdata_dir,
            TestSelectors=[
                "test_normal_case.py?name=test_success",
                "test_invalid_case.py?test_success",
            ],
            FileReportPath="",
        )

        pipe_io = io.BytesIO()
        run_testcases(entry, pipe_io)
        pipe_io.seek(0)

        start = read_test_result(pipe_io)
        self.assertEqual(start.ResultType, ResultType.RUNNING)

    def test_run_failed_testcase_with_log(self):
        entry = EntryParam(
            TaskId="aa",
            ProjectPath=self.testdata_dir,
            TestSelectors=[
                "test_normal_case.py?test_failed&priority=High",
            ],
            FileReportPath="",
        )

        pipe_io = io.BytesIO()
        run_testcases(entry, pipe_io)
        pipe_io.seek(0)

        start = read_test_result(pipe_io)
        self.assertEqual(start.ResultType, ResultType.RUNNING)

        end = read_test_result(pipe_io)
        self.assertEqual(end.ResultType, ResultType.FAILED)
        self.assertEqual(len(end.Steps), 3)
        self.assertIn("testdata/test_normal_case.py", end.Message)

        step2 = end.Steps[1]
        self.assertEqual(len(step2.Logs), 1)
        self.assertEqual(step2.Logs[0].Level, LogLevel.ERROR)
        self.assertEqual(step2.ResultType, ResultType.FAILED)
        self.assertIn("E       assert 4 == 6", step2.Logs[0].Content)

    def test_run_failed_testcase_with_raise_error(self):
        entry = EntryParam(
            TaskId="aa",
            ProjectPath=self.testdata_dir,
            TestSelectors=[
                "test_normal_case.py?test_raise_error",
            ],
            FileReportPath="",
        )

        pipe_io = io.BytesIO()
        run_testcases(entry, pipe_io)
        pipe_io.seek(0)

        start = read_test_result(pipe_io)
        self.assertEqual(start.ResultType, ResultType.RUNNING)

        end = read_test_result(pipe_io)
        self.assertEqual(end.ResultType, ResultType.FAILED)
        self.assertEqual(len(end.Steps), 3)

        step2 = end.Steps[1]
        self.assertEqual(len(step2.Logs), 1)
        self.assertEqual(step2.Logs[0].Level, LogLevel.ERROR)
        self.assertEqual(step2.ResultType, ResultType.FAILED)
        self.assertIn(
            "E       RuntimeError: this is raise runtime error", step2.Logs[0].Content
        )

    def test_run_skipped_testcase(self):
        entry = EntryParam(
            TaskId="aa",
            ProjectPath=self.testdata_dir,
            TestSelectors=[
                "test_skipped.py?test_filtered",
            ],
            FileReportPath="",
        )

        pipe_io = io.BytesIO()
        run_testcases(entry, pipe_io)
        pipe_io.seek(0)

        start = read_test_result(pipe_io)
        self.assertEqual(start.ResultType, ResultType.RUNNING)

        end = read_test_result(pipe_io)
        self.assertEqual(end.ResultType, ResultType.IGNORED)
        self.assertEqual(len(end.Steps), 2)
        self.assertEqual(end.Message, "Skipped: no way of currently testing this")

    def test_run_datadrive_with_single_value(self):
        entry = EntryParam(
            TaskId="aa",
            ProjectPath=self.testdata_dir,
            TestSelectors=[
                "test_data_drive.py?test_eval/[2+4-6]",
            ],
            FileReportPath="",
        )

        pipe_io = io.BytesIO()
        run_testcases(entry, pipe_io)
        pipe_io.seek(0)

        start = read_test_result(pipe_io)
        self.assertEqual(start.ResultType, ResultType.RUNNING)

        end = read_test_result(pipe_io)
        self.assertEqual(end.ResultType, ResultType.SUCCEED)
        self.assertEqual(len(end.Steps), 3)

    def test_run_datadrive_with_utf8_str(self):
        entry = EntryParam(
            TaskId="aa",
            ProjectPath=self.testdata_dir,
            TestSelectors=[
                "test_data_drive_zh_cn.py?test_include/[中文-中文汉字]",
            ],
            FileReportPath="",
        )

        pipe_io = io.BytesIO()
        run_testcases(entry, pipe_io)
        pipe_io.seek(0)

        start = read_test_result(pipe_io)
        self.assertEqual(start.ResultType, ResultType.RUNNING)

        end = read_test_result(pipe_io)
        self.assertEqual(end.ResultType, ResultType.SUCCEED)
        self.assertEqual(len(end.Steps), 3)
