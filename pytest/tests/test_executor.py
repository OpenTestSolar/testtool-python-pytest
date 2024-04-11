import io
from pathlib import Path
import unittest

from testsolar_testtool_sdk.model.param import EntryParam
from testsolar_testtool_sdk.model.testresult import ResultType, LogLevel
from testsolar_testtool_sdk.pipe_reader import read_test_result

from src.executor import run_testcases


class ExecutorTest(unittest.TestCase):
    testdata_dir: str = str(Path(__file__).parent.parent.absolute().joinpath("testdata"))

    def test_run_success_testcase_with_logs(self):
        entry = EntryParam(
            TaskId="aa",
            ProjectPath=self.testdata_dir,
            TestSelectors=[
                "normal_case.py?test_success",
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
        self.assertEqual(step3.Logs[0].Content, """this is setup
this is print sample output
this is teardown
""")

    def test_run_success_testcase_with_one_invalid_selector(self):
        entry = EntryParam(
            TaskId="aa",
            ProjectPath=self.testdata_dir,
            TestSelectors=[
                "normal_case.py?test_success",
                "invalid_case.py?test_success",
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
            Context={},
            TaskId="aa",
            ProjectPath=self.testdata_dir,
            TestSelectors=[
                "normal_case.py?test_failed",
                "invalid_case.py?test_success",
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
