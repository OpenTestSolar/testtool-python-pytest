

import pytest


@pytest.mark.parametrize("test_input,expected", [("3+5", 8), ("2+4", 6), ("6*9", 42)])
@pytest.mark.coding_testcase_id({"2+4-6": "123", "6*9-42": "456", "3+5-8": "789"})
def test_eval(test_input, expected):
    assert eval(test_input) == expected
