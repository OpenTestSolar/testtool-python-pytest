import io
import os
from pathlib import Path
from unittest import TestCase

from testsolar_testtool_sdk.model.testresult import ResultType
from testsolar_testtool_sdk.pipe_reader import read_test_result

from src.run import run_testcases_from_args


class TestExecuteEntry(TestCase):
    testdata_dir: str = str(
        Path(__file__).parent.parent.absolute().joinpath("testdata")
    )

    def test_run_testcases_from_args(self):
        os.environ["TESTSOLAR_TTP_ENABLEALLURE"] = "1"
        pipe_io = io.BytesIO()
        run_testcases_from_args(
            args=[
                "run.py",
                Path.joinpath(Path(self.testdata_dir), "allure_entry.json"),
            ],
            workspace=self.testdata_dir,
            pipe_io=pipe_io,
        )

        # testcase running
        pipe_io.seek(0)
        start = read_test_result(pipe_io)
        self.assertEqual(start.ResultType, ResultType.RUNNING)
        self.assertEqual(start.Test.Name, "allure/allure_step_test.py?test_step")

        # testcase finish
        stop = read_test_result(pipe_io)
        self.assertEqual(stop.ResultType, ResultType.SUCCEED)
        self.assertEqual(stop.Test.Name, "allure/allure_step_test.py?test_step")
        self.assertEqual(stop.Message, "")
        self.assertEqual(type(stop.Steps), list)
        self.assertEqual(len(stop.Steps), 5)
