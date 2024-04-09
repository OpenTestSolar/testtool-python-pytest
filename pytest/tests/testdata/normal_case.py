import pytest


def inc(x):
    return x + 1


@pytest.mark.high
@pytest.mark.owner('foo')
@pytest.mark.extra_attributes({'env': ['AA', 'BB']})
def test_answer():
    """
    测试获取答案
    """
    assert inc(3) == 4


