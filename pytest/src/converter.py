import re
import sys


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
    if "/[" in testcase:
        testcase = encode_datadrive(testcase.replace("/[", "["))
    return path + "::" + testcase.replace("/", "::")


def encode_datadrive(name):
    if sys.version_info[0] >= 3:
        name = name.encode("unicode_escape").decode()
    else:
        if not isinstance(name, bytes):
            name = name.encode("utf-8")
        name = name.encode("string-escape")
    return name


def decode_datadrive(name):
    if sys.version_info[0] >= 3:
        if re.search(r"\\u\w{4}", name):
            name = name.encode().decode("unicode_escape")
    else:
        name = name.decode("string-escape")
        name = name.decode("string-escape")  # need decode twice
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
    )  # 数据驱动值前面加上/
    if "[" in name:
        name = decode_datadrive(name)

    return name
