import io
from pathlib import Path
from unittest import TestCase

from testsolar_testtool_sdk.file_reader import read_file_load_result

from src.load import collect_testcases_from_args


class TestCollectorEntry(TestCase):
    testdata_dir: str = str(Path(__file__).parent.parent.absolute().joinpath("testdata"))

    def test_collect_testcases_from_args(self):
        collect_testcases_from_args(
            args=["load.py", Path.joinpath(Path(self.testdata_dir), "entry.json")],
            workspace=self.testdata_dir,
        )

        re = read_file_load_result(Path("./load.json"))

        re.Tests.sort(key=lambda x: x.Name)
        re.LoadErrors.sort(key=lambda x: x.name)
        self.assertEqual(len(re.Tests), 7)
        self.assertEqual(
            re.Tests[4].Name,
            "test_data_drive.py?test_special_data_drive_name/%5B%E4%B8%AD%E6%96%87-%E5%88%86%E5%8F%B7%2B%5Bid%3A32%5D%5D",
        )
        self.assertEqual(
            re.Tests[6].Name,
            "test_unit_test_case.py?TestInnerCase/test_inner_case",
        )

    def test_raise_error_when_param_is_invalid(self):
        with self.assertRaises(SystemExit):
            pipe_io = io.BytesIO()
            collect_testcases_from_args(
                args=["load.py"], workspace=self.testdata_dir, pipe_io=pipe_io
            )
