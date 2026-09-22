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

    def test_selector_to_pytest_with_equal_sign_in_datadrive(self):
        # 回归场景：参数化数据中包含 "=" 时，不能被误判为属性筛选而退化为整个文件执行
        re = selector_to_pytest(
            "tests/test_asr_websocket.py?TestAsrWebSocket/test_sample_rate_parametrized/[0-default-sample_rate=0-False]"
        )
        self.assertEqual(
            re,
            "tests/test_asr_websocket.py::TestAsrWebSocket::test_sample_rate_parametrized[0-default-sample_rate=0-False]",
        )

        # 参数化数据同时包含 "=" 和中文全角括号
        re = selector_to_pytest(
            "tests/test_asr_websocket.py?TestAsrWebSocket/test_asr_context_type_parametrized/[no_context-type=no_context（无上下文）-False]"
        )
        self.assertEqual(
            re,
            "tests/test_asr_websocket.py::TestAsrWebSocket::test_asr_context_type_parametrized[no_context-type=no_context\\uff08\\u65e0\\u4e0a\\u4e0b\\u6587\\uff09-False]",
        )

        re = selector_to_pytest(
            "tests/test_asr_websocket.py?TestAsrWebSocket/test_voice_id_parametrized/[aaaaaaaa-voice_id=129位（超限）-True]"
        )
        self.assertEqual(
            re,
            "tests/test_asr_websocket.py::TestAsrWebSocket::test_voice_id_parametrized[aaaaaaaa-voice_id=129\\u4f4d\\uff08\\u8d85\\u9650\\uff09-True]",
        )

    def test_selector_to_pytest_with_equal_sign_in_http_datadrive(self):
        re = selector_to_pytest(
            "tests/test_asr_http.py?TestASRRecognize/test_recognize_audio_format/[summary_context-base64-pcm]"
        )
        self.assertEqual(
            re,
            "tests/test_asr_http.py::TestASRRecognize::test_recognize_audio_format[summary_context-base64-pcm]",
        )

    def test_selector_to_pytest_with_name_attr_in_datadrive(self):
        # 回归场景：数据驱动中包含 & 且参数名以 name= 结尾（demand_name=/mcn_name=/product_name=）
        # 不能被当成属性筛选，否则用例名会被截断（attr[5:]）
        re = selector_to_pytest(
            "tests/qq/settlement/test_settlement.py?TestSettlementWalletMcnSettleFlow/test_settlement_wallet_mcn_settle_flow/[demand_name=测试&author_name=频道--发布&author_id=14124598&pay_status=2-expected=code:0]"
        )
        self.assertEqual(
            re,
            "tests/qq/settlement/test_settlement.py::TestSettlementWalletMcnSettleFlow::test_settlement_wallet_mcn_settle_flow[demand_name=\\u6d4b\\u8bd5&author_name=\\u9891\\u9053--\\u53d1\\u5e03&author_id=14124598&pay_status=2-expected=code:0]",
        )

        # name= 出现在后面的参数上，同样不能截断用例名
        re = selector_to_pytest(
            "tests/qq/settlement/test_settlement.py?TestSettlementWalletAuthorPersonalSettleFlow/test_settlement_wallet_author_personal_settle_flow/[pay_status=2&demand_name=测试&demand_type=3-expected=code:0]"
        )
        self.assertEqual(
            re,
            "tests/qq/settlement/test_settlement.py::TestSettlementWalletAuthorPersonalSettleFlow::test_settlement_wallet_author_personal_settle_flow[pay_status=2&demand_name=\\u6d4b\\u8bd5&demand_type=3-expected=code:0]",
        )

        re = selector_to_pytest(
            "tests/qq/settlement/test_settlement.py?TestSettlementBfcPersonList/test_settlement_bfc_person_list/[pay_status=2&mcn_name=中国移动通信集团江苏有限公司-expected=code:0]"
        )
        self.assertTrue(
            re.startswith(
                "tests/qq/settlement/test_settlement.py::TestSettlementBfcPersonList::test_settlement_bfc_person_list[pay_status=2&mcn_name="
            )
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
