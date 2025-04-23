import os
from unittest import TestCase
from unittest.mock import MagicMock

from src.testsolar_pytestx.converter import (
    selector_to_pytest,
    pytest_to_selector,
    extract_case_and_datadrive,
)


class InnerClass:
    pass


class Test(TestCase):
    def test_selector_to_pytest_without_datadrive(self):
        re = selector_to_pytest("/data/tests/tests/test_data_drive_zh_cn.py?aa/bb/test_include")
        self.assertEqual(re, "/data/tests/tests/test_data_drive_zh_cn.py::aa::bb::test_include")

    def test_selector_to_pytest_with_tag(self):
        re = selector_to_pytest("hello_test?tag=ready&tag=-skip")
        self.assertEqual(re, "hello_test")
        re = selector_to_pytest("hello_test?tag=ready")
        self.assertEqual(re, "hello_test")
        re = selector_to_pytest("hello_test?name=HelloTest&tag=ready")
        self.assertEqual(re, "hello_test::HelloTest")
        re = selector_to_pytest("hello_test?HelloTest&tag=ready")
        self.assertEqual(re, "hello_test::HelloTest")

    def test_selector_to_pytest_with_datadrive(self):
        re = selector_to_pytest(
            "/data/tests/tests/test_data_drive_zh_cn.py?aa/bb/test_include/[#?/-#?^$%!]"
        )
        self.assertEqual(
            re,
            "/data/tests/tests/test_data_drive_zh_cn.py::aa::bb::test_include[#?/-#?^$%!]",
        )

        re = selector_to_pytest(
            "/data/tests/tests/test_data_drive_with_backslash.py?test_backslash/[\\n]"
        )
        self.assertEqual(
            re,
            "/data/tests/tests/test_data_drive_with_backslash.py::test_backslash[\\\\n]",
        )

        os.environ["TESTSOLAR_TTP_IGNOREENCODEBACKSLASH"] = "true"
        re = selector_to_pytest(
            "/data/tests/tests/test_data_drive_with_backslash.py?test_backslash/[\\n]"
        )
        self.assertEqual(
            re,
            "/data/tests/tests/test_data_drive_with_backslash.py::test_backslash[\\n]",
        )

    def test_selector_to_pytest_with_utf8_string(self):
        re = selector_to_pytest(
            "/data/tests/tests/test_data_drive_zh_cn.py?aa/bb/test_include/[中文-中文汉字]"
        )
        self.assertEqual(
            re,
            "/data/tests/tests/test_data_drive_zh_cn.py::aa::bb::test_include[\\u4e2d\\u6587-\\u4e2d\\u6587\\u6c49\\u5b57]",
        )

        re = selector_to_pytest(
            "/data/tests/tests/test_data_drive_zh_cn.py?aa/bb/test_include/[中文-[中文]汉字]"
        )
        self.assertEqual(
            re,
            "/data/tests/tests/test_data_drive_zh_cn.py::aa::bb::test_include[\\u4e2d\\u6587-[\\u4e2d\\u6587]\\u6c49\\u5b57]",
        )

    def test_pytest_path_cls_to_selector(self):
        mock = MagicMock()
        mock.nodeid = None
        mock.path = "/data/tests/tests/test_data_drive_zh_cn.py"
        mock.name = "test_include[2-8]"
        mock.cls = InnerClass

        re = pytest_to_selector(mock, "/data/tests/")

        self.assertEqual(re, "tests/test_data_drive_zh_cn.py?InnerClass/test_include/[2-8]")

    def test_pytest_node_id_to_selector_without_datadrive(self):
        mock = MagicMock()
        mock.nodeid = "tests/test_data_drive_zh_cn.py::test_include"
        mock.path = None
        mock.cls = None

        re = pytest_to_selector(mock, "/data/tests/")

        self.assertEqual(re, "tests/test_data_drive_zh_cn.py?test_include")

    def test_pytest_node_id_to_selector_with_datadrive(self):
        mock = MagicMock()
        mock.nodeid = "/data/tests/tests/test_data_drive_zh_cn.py::test_include[#?-/[中文:203]]"
        mock.path = None
        mock.cls = None

        re = pytest_to_selector(mock, "/data/tests/")

        self.assertEqual(
            re,
            "/data/tests/tests/test_data_drive_zh_cn.py?test_include/[#?-/[中文:203]]",
        )

    def test_pytest_location_to_selector(self):
        mock = MagicMock()
        mock.nodeid = None
        mock.path = None
        mock.cls = None
        mock.location = ("tests/test_data_drive_zh_cn.py", 22, "test_include[AA-BB]")

        re = pytest_to_selector(mock, "/data/tests/")

        self.assertEqual(re, "tests/test_data_drive_zh_cn.py?test_include/[AA-BB]")


class TestExtractCaseAndDataDrive:
    # 测试正常的数据驱动情况
    def test_extract_case_and_datadrive_with_datadrive(self):
        assert extract_case_and_datadrive("a/b/c/[data]") == ("a/b/c", "[data]")

    # 测试数据驱动包含特殊字符的情况
    def test_extract_case_and_datadrive_special_chars(self):
        assert extract_case_and_datadrive("a/b/c/[data→test]") == (
            "a/b/c",
            "[data→test]",
        )

    # 测试数据驱动在用例名称内部的情况
    def test_extract_case_and_datadrive_inside_name(self):
        assert extract_case_and_datadrive("a/b/c/data→[test]") == (
            "a/b/c/data→[test]",
            "",
        )
        assert extract_case_and_datadrive("a/b/c/data→/[test]") == (
            "a/b/c/data→",
            "[test]",
        )

    # 测试没有数据驱动的情况
    def test_extract_case_and_datadrive_no_datadrive(self):
        assert extract_case_and_datadrive("a/b/c") == ("a/b/c", "")

    # 测试只有用例名称的情况
    def test_extract_case_and_datadrive_only_case(self):
        assert extract_case_and_datadrive("case") == ("case", "")

    # 测试复杂路径的情况
    def test_extract_case_and_datadrive_complex_path(self):
        assert extract_case_and_datadrive("a/b/c/d/e/[data]") == ("a/b/c/d/e", "[data]")

    # 测试数据驱动在路径的最后一部分但不是有效数据驱动的情况
    def test_extract_case_and_datadrive_invalid_datadrive(self):
        assert extract_case_and_datadrive("a/b/c/d/e/[data") == ("a/b/c/d/e/[data", "")
