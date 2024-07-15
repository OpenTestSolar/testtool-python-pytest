import pytest


@pytest.mark.parametrize("test_input,expected", [("3+5", 8), ("2+4", 6), ("6*9", 42)])
def test_eval(test_input, expected):
    assert eval(test_input) == expected


@pytest.mark.parametrize("test_input", ["中文-分号+[id:32]"])
def test_special_data_drive_name(test_input):
    assert "bad" not in test_input
