import pytest


class TestCompute:
    @pytest.mark.attributes({"a": 1, "b": 2})
    def test_add(self):
        assert 4 == 4
