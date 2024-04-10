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

    assert len(re.Tests) == 5
    assert len(re.LoadErrors) == 1

    assert re.Tests[0].Name == 'aa/bb/cc/class_test.py?TestCompute/test_add'

    assert re.Tests[1].Name == 'data_drive.py?test_eval/[2+4-6]'
    assert re.Tests[2].Name == 'data_drive.py?test_eval/[3+5-8]'
    assert re.Tests[3].Name == 'data_drive.py?test_eval/[6*9-42]'

    assert re.Tests[4].Name == 'normal_case.py?test_answer'
    assert re.Tests[4].Attributes['owner'] == 'foo'
    assert re.Tests[4].Attributes['description'] == '测试获取答案'
    assert re.Tests[4].Attributes['tag'] == 'high'
    assert re.Tests[4].Attributes['extra_attributes'] == '[{"env": ["AA", "BB"]}]'
