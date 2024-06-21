import json
from typing import Dict, List, Optional
from pytest import Item


# 解析测试用例的属性字段
#
# 1. 从commit解析字段
# 支持解析注释中的额外属性
#
# 2. 从mark解析字段
# 支持 @pytest.mark.attributes({"key":"value"}) 这种用法
#
# 解析属性包括：
# - description
# - tag
# - owner
# - extra_attributes
def parse_case_attributes(item: Item, comment_fields: Optional[List[str]] = None) -> Dict[str, str]:
    """parse testcase attributes"""
    desc: str = (str(item.function.__doc__) or "").strip()  # type: ignore
    attributes: Dict[str, str] = {
        "description": desc
    }
    if comment_fields:
        attributes.update(scan_comment_fields(desc, comment_fields))

    if not item.own_markers:
        return attributes
    for mark in item.own_markers:
        if not mark.args and mark.name != "attributes":
            attributes["tag"] = mark.name
        elif mark.args and mark.name == "owner":
            attributes["owner"] = str(mark.args[0])
        elif mark.name == "extra_attributes":
            extra_attr = {}
            attr_list = []
            for key in mark.args[0]:
                if mark.args[0][key] is None:
                    continue
                extra_attr[key] = mark.args[0][key]
                attr_list.append(extra_attr)
            attributes["extra_attributes"] = json.dumps(attr_list)
    return attributes


def scan_comment_fields(desc: str, desc_fields: List[str]) -> Dict[str, str]:
    """
    从函数的注释中解析额外字段
    """
    results: Dict[str, str] = {}

    for line in desc.splitlines():
        for field in desc_fields:
            if field in line:
                value = handle_str_param(line)
                field_value.extend(value.split(","))
                attributes[field] = json.dumps(field_value)
    return results


def handle_str_param(line: str) -> Optional[Dict[str, str]]:
    """handle string parameter

    解析注释中单行 a = b 为 (a, b)形式方便后续处理
    """
    symbol: str = ""
    if ":" in line:
        symbol = ":"
    elif "=" in line:
        symbol = "="
    if symbol:
        value: str = line.split(symbol, 1)[1].strip().replace(" ", "")
        return value
    else:
        return ""
