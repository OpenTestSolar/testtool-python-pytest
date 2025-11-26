import tempfile
import json
from pathlib import Path
from unittest import TestCase

from testsolar_testtool_sdk.file_reader import read_file_load_result

from src.load import collect_testcases_from_args


class TestCollectorEntry(TestCase):
    testdata_dir: str = str(Path(__file__).parent.parent.absolute().joinpath("testdata"))

    def test_collect_testcases_from_args(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / "result.json"

            # 创建临时的entry.json，设置正确的FileReportPath
            entry_file = Path(tmpdir) / "entry.json"
            with open(Path(self.testdata_dir) / "entry.json", "r") as f:
                entry_data = json.load(f)
            entry_data["FileReportPath"] = str(report_file)
            with open(entry_file, "w") as f:
                json.dump(entry_data, f)

            collect_testcases_from_args(
                args=["load.py", str(entry_file)],
                workspace=self.testdata_dir,
            )

            re = read_file_load_result(report_file)
            re.Tests.sort(key=lambda x: x.Name)
            re.LoadErrors.sort(key=lambda x: x.name)
            self.assertEqual(len(re.Tests), 7)
            self.assertEqual(
                re.Tests[4].Name,
                "test_data_drive.py?test_special_data_drive_name/[中文-分号+[id:32]]",
            )
            self.assertEqual(
                re.Tests[6].Name,
                "test_unit_test_case.py?TestInnerCase/test_inner_case",
            )

    def test_raise_error_when_param_is_invalid(self):
        with self.assertRaises(SystemExit):
            collect_testcases_from_args(args=["load.py"], workspace=self.testdata_dir)
