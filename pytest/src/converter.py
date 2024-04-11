import re


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

    testcase = encode_datadrive(testcase)
    return path + "::" + testcase.replace("/", "::")


def encode_datadrive(name: str) -> str:
    if "/[" in name:
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
    if name.endswith(']'):
        name = name.replace('[', "/[")
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
