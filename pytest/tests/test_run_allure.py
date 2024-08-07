import io
import os
from datetime import datetime
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, mock_open

import pytest
from testsolar_testtool_sdk.model.test import TestCase as TestSolar_TestCase
from testsolar_testtool_sdk.model.testresult import (
    TestResult,
)
from testsolar_testtool_sdk.pipe_reader import read_test_result

from run import run_testcases_from_args
from testsolar_pytestx.extend.allure_extend import (
    generate_allure_results,
    gen_allure_step_info,
    format_allure_time,
    ResultType,
    Step,
)

allure_json = """
{
  "name": "test_case_1",
  "status": "passed",
  "start": 1622547800000,
  "stop": 1622547900000,
  "uuid": "12345",
  "historyId": "67890",
  "testCaseId": "abcde",
  "fullName": "test_module.test_case_1",
  "steps": [
    {
      "name": "step1",
      "status": "passed",
      "start": 1622547800000,
      "stop": 1622547810000,
      "parameters": [],
      "steps": [],
      "statusDetails": null
    },
    {
      "name": "step2",
      "status": "skipped",
      "start": 1622547800000,
      "stop": 1622547810000,
      "parameters": [],
      "steps": [],
      "statusDetails": null
    },
    {
      "name": "step3",
      "status": "failed",
      "start": 1622547800000,
      "stop": 1622547810000,
      "parameters": [],
      "steps": [],
      "statusDetails": 
        {
          "message": "step3 failed",
          "trace": "trace info"
        }
    }
  ],
  "labels": []
}
"""


@pytest.fixture
def test_data():
    return {
        "test_module.test_case_1": TestResult(
            Test=TestSolar_TestCase(Name="test_module.test_case_1", Attributes={}),
            StartTime=datetime.now(),
            ResultType=ResultType.SUCCEED,
            Message="",
            Steps=[],
        ),
        "test_module.test_case_2": TestResult(
            Test=TestSolar_TestCase(Name="test_module.test_case_2", Attributes={}),
            StartTime=datetime.now(),
            ResultType=ResultType.SUCCEED,
            Message="",
            Steps=[],
        ),
    }


class TestAllureResults:
    def test_generate_allure_results(self, test_data):
        with patch("builtins.open", mock_open(read_data=allure_json)):
            generate_allure_results(test_data, "dummy_file.json")

        assert len(test_data["test_module.test_case_1"].Steps) == 3
        assert test_data["test_module.test_case_1"].Steps[0].Title == "1: step1"
        assert (
            test_data["test_module.test_case_1"].Steps[0].ResultType
            == ResultType.SUCCEED
        )

    def test_gen_allure_step_info(self):
        steps = [
            Step(
                name="step1",
                status="passed",
                start=1622547800000,
                stop=1622547810000,
                parameters=[],
                steps=[],
                statusDetails=None,
            )
        ]
        result = gen_allure_step_info(steps)
        assert len(result) == 1
        assert result[0].Title == "1: step1"
        assert result[0].ResultType == ResultType.SUCCEED

    def test_format_allure_time(self):
        timestamp = 1622547800000
        result = format_allure_time(timestamp)
        assert result == datetime.fromtimestamp(timestamp / 1000)


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
