import io
from src.collector import collect_testcases
from pathlib import Path

from testsolar_testtool_sdk.model.param import EntryParam
from testsolar_testtool_sdk.pipe_reader import read_load_result


def test_collect_testcases():
    testdata_dir = Path(__file__).parent.absolute().joinpath('testdata')
    entry = EntryParam(
        Context={},
        TaskId='aa',
        ProjectPath=str(testdata_dir),
        TestSelectors=['normal_case.py?test_answer', 'aa/bb/cc/class_test.py', 'data_drive.py', 'error_load.py'],
        Collectors=[''],
        FileReportPath=''
    )

    pipe_io = io.BytesIO()
    collect_testcases(entry, pipe_io)
    pipe_io.seek(0)

    re = read_load_result(pipe_io)

    assert len(re.tests) == 5
    assert len(re.load_errors) == 1

    assert re.tests[0].name == 'aa/bb/cc/class_test.py?TestCompute/test_add'

    assert re.tests[1].name == 'data_drive.py?test_eval/[2+4-6]'
    assert re.tests[2].name == 'data_drive.py?test_eval/[3+5-8]'
    assert re.tests[3].name == 'data_drive.py?test_eval/[6*9-42]'

    assert re.tests[4].name == 'normal_case.py?test_answer'
    assert re.tests[4].attrs['owner'] == 'foo'
    assert re.tests[4].attrs['description'] == '测试获取答案'
    assert re.tests[4].attrs['tag'] == 'high'
    assert re.tests[4].attrs['extra_attributes'] == '[{"env": ["AA", "BB"]}]'
