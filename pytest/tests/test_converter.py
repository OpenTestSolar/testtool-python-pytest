from unittest import TestCase
from unittest.mock import MagicMock

from src.testsolar_pytestx.converter import selector_to_pytest, pytest_to_selector


class InnerClass:
    pass


class Test(TestCase):
    def test_selector_to_pytest_without_datadrive(self):
        re = selector_to_pytest(
            "/data/tests/tests/test_data_drive_zh_cn.py?aa/bb/test_include"
        )
        self.assertEqual(
            re, "/data/tests/tests/test_data_drive_zh_cn.py::aa::bb::test_include"
        )

    def test_selector_to_pytest_with_datadrive(self):
        re = selector_to_pytest(
            "/data/tests/tests/test_data_drive_zh_cn.py?aa/bb/test_include/[#?-#?^$%!]"
        )
        self.assertEqual(
            re,
            "/data/tests/tests/test_data_drive_zh_cn.py::aa::bb::test_include[#?-#?^$%!]",
        )

    def test_selector_to_pytest_with_utf8_string(self):
        re = selector_to_pytest(
            "/data/tests/tests/test_data_drive_zh_cn.py?aa/bb/test_include/[中文-中文汉字]"
        )
        self.assertEqual(
            re,
            "/data/tests/tests/test_data_drive_zh_cn.py::aa::bb::test_include[\\u4e2d\\u6587-\\u4e2d\\u6587\\u6c49\\u5b57]",
        )

    def test_pytest_path_cls_to_selector(self):
        mock = MagicMock()
        mock.nodeid = None
        mock.path = "/data/tests/tests/test_data_drive_zh_cn.py"
        mock.name = "test_include[2-8]"
        mock.cls = InnerClass

        re = pytest_to_selector(mock, "/data/tests/")

        self.assertEqual(
            re, "tests/test_data_drive_zh_cn.py?InnerClass/test_include/[2-8]"
        )

    def test_pytest_node_id_to_selector_without_datadrive(self):
        mock = MagicMock()
        mock.nodeid = "tests/test_data_drive_zh_cn.py::test_include"
        mock.path = None
        mock.cls = None

        re = pytest_to_selector(mock, "/data/tests/")

        self.assertEqual(re, "tests/test_data_drive_zh_cn.py?test_include")

    def test_pytest_node_id_to_selector_with_datadrive(self):
        mock = MagicMock()
        mock.nodeid = (
            "/data/tests/tests/test_data_drive_zh_cn.py::test_include[#?-#?^$%!]"
        )
        mock.path = None
        mock.cls = None

        re = pytest_to_selector(mock, "/data/tests/")

        self.assertEqual(
            re, "/data/tests/tests/test_data_drive_zh_cn.py?test_include/[#?-#?^$%!]"
        )

    def test_pytest_location_to_selector(self):
        mock = MagicMock()
        mock.nodeid = None
        mock.path = None
        mock.cls = None
        mock.location = ("tests/test_data_drive_zh_cn.py", 22, "test_include[AA-BB]")

        re = pytest_to_selector(mock, "/data/tests/")

        self.assertEqual(re, "tests/test_data_drive_zh_cn.py?test_include/[AA-BB]")
