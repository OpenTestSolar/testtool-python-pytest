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
        os.system("python3 -m pip install allure-pytest")
        os.environ["TESTSOLAR_TTP_ENABLEALLURE"] = "1" 
        pipe_io = io.BytesIO()
        run_testcases_from_args(
            args=["run.py", Path.joinpath(Path(self.testdata_dir), "allure_entry.json")],
            workspace=self.testdata_dir,
            pipe_io=pipe_io,
        )

        pipe_io.seek(0)
        start = read_test_result(pipe_io)
        self.assertEqual(start.ResultType, ResultType.RUNNING)
