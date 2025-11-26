import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from testsolar_testtool_sdk.model.param import EntryParam
from testsolar_testtool_sdk.model.testresult import ResultType, LogLevel
from testsolar_testtool_sdk.file_reader import read_file_test_result
from testsolar_testtool_sdk.model.test import TestCase

from src.testsolar_pytestx.executor import run_testcases, append_extra_args


def convert_to_datetime(raw: str) -> datetime:
    dt = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S.%fZ")
    return dt


class ExecutorTest(unittest.TestCase):
    testdata_dir = Path(__file__).parent.parent.absolute().joinpath("testdata")

    def test_run_success_testcase_with_logs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)
            entry = EntryParam(
                TaskId="aa",
                ProjectPath=str(self.testdata_dir),
                TestSelectors=[
                    "test_normal_case.py?name=test_success&tag=A&priority=High",
                ],
                FileReportPath=str(report_dir),
            )

            current_time = datetime.utcnow()

            run_testcases(entry)

            test_case = TestCase(Name="test_normal_case.py?test_success", Attributes={})
            end = read_file_test_result(report_dir, test_case)
            self.assertEqual(end.Test.Name, "test_normal_case.py?test_success")
            self.assertEqual(end.Test.Attributes["tags"], '["high"]')
            self.assertEqual(end.Test.Attributes["owner"], "foo")
            elapse: timedelta = convert_to_datetime(str(end.StartTime)) - current_time
            self.assertLess(elapse.total_seconds(), 0.2)
            elapse_end: timedelta = convert_to_datetime(str(end.EndTime)) - current_time
            self.assertLess(elapse_end.total_seconds(), 0.2)
            self.assertGreater(elapse_end.total_seconds(), 0)
            self.assertEqual(end.ResultType, ResultType.SUCCEED)

            self.assertEqual(len(end.Steps), 3)

            # 检查Setup的时间是否符合要求
            step1 = end.Steps[0]
            self.assertEqual(step1.Title, "Setup")
            elapse = convert_to_datetime(str(step1.StartTime)) - current_time
            self.assertLess(elapse.total_seconds(), 0.2)
            self.assertGreater(elapse.total_seconds(), 0)
            elapse = convert_to_datetime(str(step1.EndTime)) - current_time
            self.assertLess(elapse.total_seconds(), 0.2)
            self.assertGreater(elapse.total_seconds(), 0)

            # 检查Log的时间是否符合要求
            self.assertEqual(len(step1.Logs), 1)
            self.assertEqual(step1.ResultType, ResultType.SUCCEED)
            log = step1.Logs[0]
            self.assertEqual(log.Level, LogLevel.INFO)
            self.assertIn("this is setup", log.Content)
            elapse = convert_to_datetime(str(log.Time)) - current_time
            self.assertGreater(elapse.total_seconds(), 0)
            self.assertLess(elapse.total_seconds(), 0.2)

            # 检查 Run TestCase 时间是否符合要求
            step2 = end.Steps[1]
            self.assertEqual(step2.Title, "Run TestCase")
            elapse = convert_to_datetime(str(step2.StartTime)) - current_time
            self.assertLess(elapse.total_seconds(), 0.2)
            self.assertGreater(elapse.total_seconds(), 0)
            elapse = convert_to_datetime(str(step2.EndTime)) - current_time
            self.assertLess(elapse.total_seconds(), 0.2)
            self.assertGreater(elapse.total_seconds(), 0)

            self.assertEqual(len(step2.Logs), 1)
            self.assertEqual(step2.Logs[0].Level, LogLevel.INFO)
            self.assertEqual(step2.ResultType, ResultType.SUCCEED)
            self.assertIn("this is print sample output", step2.Logs[0].Content)

            # 检查 Teardown 是否是否符合要求
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
            elapse = convert_to_datetime(str(step3.StartTime)) - current_time
            self.assertLess(elapse.total_seconds(), 0.2)
            self.assertGreater(elapse.total_seconds(), 0)
            elapse = convert_to_datetime(str(step3.EndTime)) - current_time
            self.assertLess(elapse.total_seconds(), 0.2)
            self.assertGreater(elapse.total_seconds(), 0)

    def test_run_success_testcase_with_one_invalid_selector(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)
            entry = EntryParam(
                TaskId="aa",
                ProjectPath=str(self.testdata_dir),
                TestSelectors=[
                    "test_normal_case.py?name=test_success",
                    "test_invalid_case.py?test_success",
                ],
                FileReportPath=str(report_dir),
            )

            run_testcases(entry)

    def test_run_failed_testcase_with_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)
            entry = EntryParam(
                TaskId="aa",
                ProjectPath=str(self.testdata_dir),
                TestSelectors=[
                    "test_normal_case.py?test_failed&priority=High",
                ],
                FileReportPath=str(report_dir),
            )

            run_testcases(entry)

            test_case = TestCase(Name="test_normal_case.py?test_failed", Attributes={})
            end = read_file_test_result(report_dir, test_case)
            self.assertEqual(end.ResultType, ResultType.FAILED)
            self.assertEqual(len(end.Steps), 3)
            self.assertIn("testdata/test_normal_case.py", end.Message)

            step2 = end.Steps[1]
            self.assertEqual(len(step2.Logs), 1)
            self.assertEqual(step2.Logs[0].Level, LogLevel.ERROR)
            self.assertEqual(step2.ResultType, ResultType.FAILED)
            self.assertIn("E       assert 4 == 6", step2.Logs[0].Content)

    def test_run_failed_testcase_with_raise_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)
            entry = EntryParam(
                TaskId="aa",
                ProjectPath=str(self.testdata_dir),
                TestSelectors=[
                    "test_normal_case.py?test_raise_error",
                ],
                FileReportPath=str(report_dir),
            )

            run_testcases(entry)

            test_case = TestCase(Name="test_normal_case.py?test_raise_error", Attributes={})
            end = read_file_test_result(report_dir, test_case)
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
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)
            entry = EntryParam(
                TaskId="aa",
                ProjectPath=str(self.testdata_dir),
                TestSelectors=[
                    "test_skipped.py?test_filtered",
                ],
                FileReportPath=str(report_dir),
            )

            run_testcases(entry)

            test_case = TestCase(Name="test_skipped.py?test_filtered", Attributes={})
            end = read_file_test_result(report_dir, test_case)
            self.assertEqual(end.ResultType, ResultType.IGNORED)
            self.assertEqual(len(end.Steps), 2)
            self.assertEqual(end.Message, "Skipped: no way of currently testing this")

    def test_run_datadrive_with_single_value(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)
            entry = EntryParam(
                TaskId="aa",
                ProjectPath=str(self.testdata_dir),
                TestSelectors=[
                    "test_data_drive.py?test_eval/[2+4-6]",
                ],
                FileReportPath=str(report_dir),
            )

            run_testcases(entry)

            test_case = TestCase(Name="test_data_drive.py?test_eval/[2+4-6]", Attributes={})
            end = read_file_test_result(report_dir, test_case)
            self.assertEqual(end.ResultType, ResultType.SUCCEED)
            self.assertEqual(len(end.Steps), 3)

    def test_run_datadrive_with_utf8_str(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)
            entry = EntryParam(
                TaskId="aa",
                ProjectPath=str(self.testdata_dir),
                TestSelectors=[
                    "test_data_drive_zh_cn.py?test_include/[中文-中文汉字]",
                ],
                FileReportPath=str(report_dir),
            )

            run_testcases(entry)

            test_case = TestCase(
                Name="test_data_drive_zh_cn.py?test_include/[中文-中文汉字]", Attributes={}
            )
            end = read_file_test_result(report_dir, test_case)
            self.assertEqual(end.ResultType, ResultType.SUCCEED)
            self.assertEqual(len(end.Steps), 3)

    def test_split_args_with_space(self):
        args = []

        with mock.patch.dict(
            "os.environ",
            {"TESTSOLAR_TTP_EXTRAARGS": '-m "not p3" -t timeout -l "fast iu897 nuh"'},
            clear=True,
        ):
            append_extra_args(args)

            self.assertEqual(len(args), 6)
            self.assertEqual(args[0], "-m")
            self.assertEqual(args[1], "not p3")
            self.assertEqual(args[2], "-t")
            self.assertEqual(args[3], "timeout")
            self.assertEqual(args[4], "-l")
            self.assertEqual(args[5], "fast iu897 nuh")

    def test_run_not_exist_selector(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)
            entry = EntryParam(
                TaskId="aa",
                ProjectPath=str(self.testdata_dir),
                TestSelectors=[
                    "test_normal_case.py?name=not_exist",
                ],
                FileReportPath=str(report_dir),
            )

            run_testcases(entry)

            test_case = TestCase(Name="test_normal_case.py?name=not_exist", Attributes={})
            result = read_file_test_result(report_dir, test_case)
            self.assertEqual(result.ResultType, ResultType.FAILED)
            self.assertEqual(result.Test.Name, "test_normal_case.py?name=not_exist")

    def test_run_testcase_with_emoji_data_drive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_dir = Path(tmpdir)
            entry = EntryParam(
                TaskId="aa",
                ProjectPath=str(self.testdata_dir),
                TestSelectors=[
                    "test_emoji_data_drive.py?test_emoji_data_drive_name/[\U0001f604]",
                ],
                FileReportPath=str(report_dir),
            )

            run_testcases(entry)

            test_case = TestCase(
                Name="test_emoji_data_drive.py?test_emoji_data_drive_name/[😄]", Attributes={}
            )
            end = read_file_test_result(report_dir, test_case)
            self.assertEqual(
                end.Test.Name,
                "test_emoji_data_drive.py?test_emoji_data_drive_name/[😄]",
            )
