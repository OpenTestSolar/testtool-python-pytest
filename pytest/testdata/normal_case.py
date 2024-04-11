import sys

import pytest


def inc(x):
    return x + 1


@pytest.fixture
def print_extra_msg():
    print("this is setup")
    yield
    print("this is teardown")


@pytest.mark.high
@pytest.mark.owner("foo")
@pytest.mark.extra_attributes({"env": ["AA", "BB"]})
def test_success(print_extra_msg):
    """
    测试获取答案
    """
    print("this is print sample output")
    assert inc(3) == 4


def test_failed():
    print("this is assert output")
    assert inc(3) == 6


@pytest.mark.low
@pytest.mark.owner("bar")
def test_raise_error():
    print("this is raise output", file=sys.stderr)
    assert inc(3) == 4
    raise RuntimeError("this is raise runtime error")
