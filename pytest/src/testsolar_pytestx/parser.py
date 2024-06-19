import json
from typing import Dict, List
from pytest import Item


# 支持 @pytest.mark.attributes({"key":"value"}) 这种用法
#
# 解析属性包括：
# - description
# - tag
# - owner
# - extra_attributes
def parse_case_attributes(item: Item, desc_fields: List[str]) -> Dict[str, str]:
    """parse testcase attributes"""
    desc: str = (str(item.function.__doc__) or "").strip()  # type: ignore
    attributes: Dict[str, str] = {
        "description": desc
    }
    if desc_fields:
        attributes = scan_desc_fields(desc, desc_fields, attributes)

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


def scan_desc_fields(desc: str, desc_fields: List[str], attributes: Dict[str, str]) -> Dict[str, str]:
    """add desc attr to attributes"""
    for line in desc.splitlines():
        for field in desc_fields:
            if field not in line:
                continue
            field_value: List = attributes.get(field, [])
            value = handle_str_param(line)
            field_value.extend(value.split(","))
            attributes[field] = json.dumps(field_value)
    return attributes


def handle_str_param(line: str) -> str:
    """handle string parameter"""
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