import io
from pathlib import Path
from unittest import TestCase

from testsolar_testtool_sdk.pipe_reader import read_load_result

from src.load import collect_testcases_from_args


class TestCollectorEntry(TestCase):
    testdata_dir: str = str(
        Path(__file__).parent.parent.absolute().joinpath("testdata")
    )

    def test_collect_testcases_from_args(self):
        pipe_io = io.BytesIO()
        collect_testcases_from_args(
            args=["load.py", Path.joinpath(Path(self.testdata_dir), "entry.json")],
            workspace=self.testdata_dir,
            pipe_io=pipe_io,
        )

        pipe_io.seek(0)
        re = read_load_result(pipe_io)

        self.assertEqual(len(re.Tests), 5)

    def test_raise_error_when_param_is_invalid(self):
        with self.assertRaises(SystemExit):
            pipe_io = io.BytesIO()
            collect_testcases_from_args(
                args=["load.py"], workspace=self.testdata_dir, pipe_io=pipe_io
            )
