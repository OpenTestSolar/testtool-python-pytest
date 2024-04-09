import pytest

"this is error

@pytest.mark.attributes({'tag': ['AA', 'BB'], 'owner': 'root'})
def test_answer():
    assert inc(3) == 4
