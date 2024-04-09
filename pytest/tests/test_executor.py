import io
from pathlib import Path

from testsolar_testtool_sdk.model.param import EntryParam

from src.executor import run_testcases


def test_run_testcases():
    testdata_dir = Path(__file__).parent.absolute().joinpath('testdata')
    entry = EntryParam(
        Context={},
        TaskId='aa',
        ProjectPath=str(testdata_dir),
        TestSelectors=['normal_case.py', 'aa/bb/cc/class_test.py', 'data_drive.py', 'error_load.py'],
        Collectors=[''],
        FileReportPath=''
    )

    pipe_io = io.BytesIO()
    run_testcases(entry, pipe_io)
    pipe_io.seek(0)
