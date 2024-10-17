import pytest

@pytest.skip(reason="no way of currently testing this")
def test_skip_error():
    assert 3 == 4
