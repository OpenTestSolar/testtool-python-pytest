import pytest


def inc(x):
    return x + 1


@pytest.mark.high
@pytest.mark.owner("foo")
@pytest.mark.extra_attributes({"env": ["AA", "BB"]})
def test_success():
    """
    测试获取答案
    """
    print("=" * 20)
    print("=" * 20)
    assert inc(3) == 4


@pytest.mark.low
@pytest.mark.owner("bar")
def test_failed():
    """
    测试获取答案
    """
    print("=" * 20)
    print("=" * 20)
    assert inc(3) == 6
