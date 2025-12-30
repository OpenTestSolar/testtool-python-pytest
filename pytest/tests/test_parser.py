import pytest
from unittest.mock import MagicMock
from src.testsolar_pytestx.parser import (
    parse_case_attributes,
    handle_str_param,
    scan_comment_fields,
)


def test_handle_str_param():
    desc = """
    description: This is a test function
    owner: test_owner
    tag: test_tag
    """
    expected = {
        "description": "This is a test function",
        "owner": "test_owner",
        "tag": "test_tag",
    }
    assert handle_str_param(desc) == expected


def test_scan_comment_fields():
    desc = """
    description: This is a test function
    owner: test_owner
    tag: test_tag
    coding_testcase_id: 123,456
    """
    desc_fields = ["description", "owner", "coding_testcase_id"]
    expected = {
        "description": "This is a test function",
        "owner": "test_owner",
        "coding_testcase_id": '["123", "456"]',
    }
    assert scan_comment_fields(desc, desc_fields) == expected


def test_parse_case_attributes():
    # Mocking a pytest Item
    item = MagicMock()
    item.function.__doc__ = """
    description: This is a test function
    owner: test_owner
    tag: test_tag
    coding_testcase_id: 123,456
    """
    item.own_markers = []

    comment_fields = ["description", "owner", "coding_testcase_id"]
    expected = {
        "description": "This is a test function",
        "owner": "test_owner",
        "coding_testcase_id": '["123", "456"]',
        "tags": "[]",
    }
    assert parse_case_attributes(item, comment_fields) == expected


if __name__ == "__main__":
    pytest.main()
