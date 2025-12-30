import pytest

pytestmark = [
    pytest.mark.mod_tag,
    pytest.mark.slow(reason="ignored for tags"),
    pytest.mark.owner("module_owner"),
    pytest.mark.extra_attributes({"layer": "module", "none": None}),
]


@pytest.mark.class_tag
@pytest.mark.owner("class_owner")
class TestMarkLayers:
    @pytest.mark.func_tag
    @pytest.mark.owner("func_owner")
    def test_layers(self):
        assert True


@pytest.mark.coding_testcase_id({"case1": "CID-001"})
@pytest.mark.parametrize("x", [pytest.param(1, id="case1")])
def test_coding_id_layers(x):
    assert x == 1
