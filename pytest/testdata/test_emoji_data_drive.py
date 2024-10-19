import pytest

@pytest.mark.parametrize("test_input", ["\U0001f604"])
def test_emoji_data_drive_name(test_input):
    assert "bad" not in test_input

