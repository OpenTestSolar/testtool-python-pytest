import re
import os
from typing import Tuple

from pytest import Item


def selector_to_pytest(test_selector: str) -> str:
    """translate from test selector format to pytest format"""
    path, _, testcase = test_selector.partition("?")

    if not testcase:
        return path

    if "&" in testcase:
        testcase_attrs = testcase.split("&")
        for attr in testcase_attrs:
            if "name=" in attr:
                testcase = attr[5:]
                break
            elif "=" not in attr:
                testcase = attr
                break
    else:
        if testcase.startswith("name="):
            testcase = testcase[5:]

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
    splits = case_selector.rsplit("/", 1)
    if len(splits) == 2:
        if splits[1] and splits[1].startswith("[") and splits[1].endswith("]"):
            # part2确实是一个数据驱动
            return splits[0], splits[1]
        else:
            return case_selector, ""
    else:
        return case_selector, ""


def pytest_to_selector(item: Item, project_path: str) -> str:
    """
    translate from pytest format to test selector format
    """

    if hasattr(item, "path") and hasattr(item, "cls") and item.path:
        rel_path = os.path.relpath(item.path, project_path)
        name = item.name
        if item.cls:
            name = item.cls.__name__ + "/" + name
        name = decode_datadrive(name)
        full_name = f"{rel_path}?{name}"
    elif hasattr(item, "nodeid") and item.nodeid:
        full_name = normalize_testcase_name(item.nodeid)
    else:
        rel_path, _, name = item.location
        name = name.replace(".", "/")
        name = decode_datadrive(name)
        full_name = f"{rel_path}?{name}"

    return full_name


def encode_datadrive(name: str) -> str:
    if name.endswith("]") and "[" in name:
        name = name.encode("unicode_escape").decode()
        name = name.replace("/[", "[")
    return name


def decode_datadrive(name: str) -> str:
    """
    将数据驱动转换为utf8字符，对用户来说可读性更好。

    原因：pytest by default escapes any non-ascii characters used in unicode strings for the parametrization because it has several downsides.

    https://docs.pytest.org/en/7.0.x/how-to/parametrize.html

    test_include[\u4e2d\u6587-\u4e2d\u6587\u6c49\u5b57] -> test_include[中文-中文汉字]
    """
    if name.endswith("]") and "[" in name:
        name = name.replace("[", "/[")
        if re.search(r"\\u\w{4}", name):
            name = name.encode().decode("unicode_escape")

    return name


def normalize_testcase_name(name: str) -> str:
    """test_directory/test_module.py::TestExampleClass::test_example_function[datedrive]
    -> test_directory/test_module.py?TestExampleClass/test_example_function/[datedrive]
    """
    assert "::" in name
    name = (
        name.replace("::", "?", 1).replace(  # 第一个分割符是文件，因此替换为?
            "::", "/"
        )  # 后续的分割符是测试用例名称，替换为/
    )
    name = decode_datadrive(name)
    return name
