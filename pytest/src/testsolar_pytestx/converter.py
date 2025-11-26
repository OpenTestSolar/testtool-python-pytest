import re
import os
from typing import Tuple, Optional
from pytest import Item
from loguru import logger

CASE_DRIVE_SEPARATOR = "→"


def selector_to_pytest(test_selector: str) -> str:
    """translate from test selector format to pytest format"""
    path, _, testcase = test_selector.partition("?")

    if not testcase:  # tests/hello_test.py
        return path

    if "&" in testcase:
        testcase_attrs = testcase.split("&")
        for attr in testcase_attrs:
            if "name=" in attr:  # tests/hello_test.py?name=xxxTest&tag=prod
                testcase = attr[5:]
                break
            elif "=" not in attr:  # tests/hello_test.py?xxxTest&
                testcase = attr
                break
        else:  # tests/hello_test.py?test_hello_world&tag=prod
            return path
    else:
        if testcase.startswith("name="):  # tests/hello_test.py?name=xxxTest
            testcase = testcase[5:]
        elif "=" in testcase:  # tests/hello_test.py?tag=prod
            return path

    case, datadrive = extract_case_and_datadrive(testcase)

    if datadrive:
        datadrive = encode_datadrive(datadrive)

    case = case.replace("/", "::")
    # 数据驱动里面的/不用替换为::
    result = f"{path}::{case}"
    if datadrive:
        result += datadrive

    return result


def extract_case_and_datadrive(case_selector: str) -> Tuple[str, str]:
    """
    Extract case and datadrive from test case selector

    从用例名称中拆分用例和数据驱动名称，pytest的数据驱动为最终的/[....]，如果不存在则返回空即可
    """
    if case_selector.endswith("]"):
        if case_selector.count("/[") > 1:
            logger.warning(
                f"Selector {case_selector} has more than 1 `/[` .Please fix your case drive data."
            )
        else:
            # 以]结尾，并且前面有/[，那么确实是一个数据驱动
            # 例子： testa/testb.py?case_name/[data/myf9:y678]
            case, _, drive_data = case_selector.partition("/[")
            if drive_data:
                return case, f"[{drive_data}"
    elif CASE_DRIVE_SEPARATOR in case_selector:
        # 数据驱动在用例名称里面
        # 例子： testa/testb.py?case_name→data
        case, _, drive_key = case_selector.partition(CASE_DRIVE_SEPARATOR)
        return case, ""

    return case_selector, ""


def pytest_to_selector(item: Item, project_path: str) -> str:
    """
    translate from pytest format to test selector format
    """

    if hasattr(item, "path") and hasattr(item, "cls") and item.path:
        rel_path = os.path.relpath(item.path, project_path)
        # 统一使用正斜杠，确保跨平台一致性
        rel_path = rel_path.replace(os.sep, "/")
        name = item.name
        if item.cls:
            name = item.cls.__name__ + "/" + name
        name = decode_datadrive(name)
        full_name = f"{rel_path}?{name}"
    elif hasattr(item, "nodeid") and item.nodeid:
        full_name = normalize_testcase_name(item.nodeid)
    else:
        rel_path, _, name = item.location
        # 统一使用正斜杠，确保跨平台一致性
        rel_path = rel_path.replace(os.sep, "/")
        name = name.replace(".", "/")
        name = decode_datadrive(name)
        full_name = f"{rel_path}?{name}"

    return full_name


def disable_encode_backslash() -> bool:
    # 考虑到在encode之后单个反斜杠会被转义为双反斜杠，这种场景下会导致pytest无法找到对应的用例，因此考虑将encode之后的双反斜杠转换回单反斜杠
    return os.getenv("TESTSOLAR_TTP_IGNOREENCODEBACKSLASH", "").lower() == "true"


def encode_datadrive(name: str) -> str:
    if name.endswith("]") and "[" in name:
        name = name.encode("unicode_escape").decode()
        name = name.replace("/[", "[")
        if disable_encode_backslash():
            name = name.replace("\\\\", "\\")
    return name


def decode_datadrive(name: str) -> str:
    """
    将数据驱动转换为utf8字符，对用户来说可读性更好。

    原因：pytest by default escapes any non-ascii characters used in unicode strings for the parametrization because it has several downsides.

    https://docs.pytest.org/en/7.0.x/how-to/parametrize.html

    test_include[\u4e2d\u6587-\u4e2d\u6587\u6c49\u5b57] -> test_include[中文-中文汉字]
    test_include[\U0001f604] -> test_include[😊]

    用例名称中不允许出现[，因此如果有，一定是数据驱动的开头
    """
    if name.endswith("]"):
        start_index = name.find("[")
        if start_index != -1:
            name = name.replace(name[start_index], "/[", 1)

        if re.search(r"\\u\w{4}", name):
            name = name.encode().decode("unicode_escape")

        if re.search(r"\\U\w{8}", name):
            name = name.encode().decode("unicode_escape")

    return name


def normalize_testcase_name(name: str, sub_case_key: Optional[str] = None) -> str:
    """test_directory/test_module.py::TestExampleClass::test_example_function[datedrive]
    -> test_directory/test_module.py?TestExampleClass/test_example_function/[datedrive]
    """
    assert "::" in name
    # 统一使用正斜杠，确保跨平台一致性
    name = name.replace(os.sep, "/")
    name = name.replace("::", "?", 1).replace(  # 第一个分割符是文件，因此替换为?
        "::", "/"
    )  # 后续的分割符是测试用例名称，替换为/
    name = decode_datadrive(name)
    if sub_case_key:
        name += CASE_DRIVE_SEPARATOR + sub_case_key
    if "?" in name:
        path = name.split("?", 1)[0]
        case_name = name.split("?", 1)[-1]
        return "?".join([path, case_name])
    return name
