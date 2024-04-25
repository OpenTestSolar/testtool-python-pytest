import pytest

from bad_import import unkown


@pytest.mark.attributes({"tag": ["AA", "BB"], "owner": "root"})
def test_answer():
    assert 4 == 4
