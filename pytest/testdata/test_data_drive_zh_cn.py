import pytest


@pytest.mark.parametrize(
    "test_input,expected",
    [
        ("#?", "#?^$%!/"),
        ("中文", "中文汉字"),
        ("파일을 찾을 수 없습니다", "ファイルが見つかりません"),
    ],
)
def test_include(test_input: str, expected: str):
    """
    测试包含UTF-8字符的数据驱动用例
    """
    assert test_input in expected
