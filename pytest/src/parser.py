import json
from typing import Dict
from pytest import Item


# 支持 @pytest.mark.attributes({"key":"value"}) 这种用法
#
# 解析属性包括：
# - description
# - tag
# - owner
# - extra_attributes
def parse_case_attributes(item: Item) -> Dict[str, str]:
    """parse testcase attributes"""
    attributes: Dict[str, str] = {
        "description": (str(item.function.__doc__) or "").strip()  # type: ignore
    }
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
