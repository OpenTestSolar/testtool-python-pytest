import json
import re
from typing import Dict, Iterable, List, Optional, Set

from _pytest.mark.structures import Mark
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


def _get_desc(item: Item) -> str:
    try:
        doc = item.function.__doc__  # type: ignore
    except AttributeError:
        return ""
    return str(doc).strip() if doc else ""


def _iter_markers(item: Item) -> List[Mark]:
    try:
        return list(item.iter_markers())
    except AttributeError:
        return list(item.own_markers or [])


def _is_tag_mark(mark: Mark) -> bool:
    if mark.name in {"attributes"}:
        return False
    if mark.args or mark.kwargs:
        return False
    return True


def _collect_tags(markers: Iterable[Mark]) -> List[str]:
    """从 markers 中提取 tags（去重），只收集“无 args 且无 kwargs”的 mark.name。

    示例：
        pytestmark = [pytest.mark.mod_tag]

        @pytest.mark.class_tag
        class TestX:
            @pytest.mark.func_tag
            def test_ok(self):
                pass

        => tags 包含：mod_tag / class_tag / func_tag

    反例（不会进 tags）：
        @pytest.mark.slow(reason="too slow")  # 有 kwargs
        @pytest.mark.owner("alice")          # 有 args
        @pytest.mark.attributes({"k": "v"})  # 显式排除
    """
    tags: List[str] = []
    seen: Set[str] = set()
    for mark in markers:
        name_str = str(mark.name)
        if not _is_tag_mark(mark) or name_str in seen:
            continue
        seen.add(name_str)
        tags.append(name_str)
    return tags


def _try_set_owner(attributes: Dict[str, str], mark: Mark) -> None:
    """解析 owner：仅支持 `@pytest.mark.owner("alice")`。

    示例：
        @pytest.mark.owner("alice")
        def test_ok():
            pass

        => attributes["owner"] == "alice"
    """
    if "owner" in attributes:
        return
    if mark.name != "owner" or not mark.args:
        return
    attributes["owner"] = str(mark.args[0])


def _try_set_extra_attributes(attributes: Dict[str, str], mark: Mark) -> None:
    """解析 extra_attributes：仅支持 `@pytest.mark.extra_attributes({"k": "v"})`。

    示例：
        @pytest.mark.extra_attributes({"env": "AA", "skip": None})
        def test_ok():
            pass

        => attributes["extra_attributes"] == '[{"env": "AA"}]'  # None 会被过滤
    """
    if mark.name != "extra_attributes" or not mark.args:
        return
    data = mark.args[0]
    if not isinstance(data, dict):
        return
    attr_list = [{k: v} for k, v in data.items() if v is not None]
    attributes["extra_attributes"] = json.dumps(attr_list)


def _try_set_coding_testcase_id(attributes: Dict[str, str], item: Item, mark: Mark) -> None:
    """解析 coding_testcase_id：面向参数化用例，通过参数 id 映射到外部用例 ID。

    示例：
        @pytest.mark.coding_testcase_id({"case1": "CID-001"})
        @pytest.mark.parametrize("x", [pytest.param(1, id="case1")])
        def test_p(x):
            pass

        => item.name == "test_p[case1]"
        => attributes["coding_testcase_id"] == "CID-001"
    """
    if mark.name != "coding_testcase_id" or not mark.args:
        return
    if "[" not in item.name:
        return
    data = mark.args[0]
    if not isinstance(data, dict):
        return
    case_data_name = item.name.split("[", 1)[1][:-1]
    if case_data_name in data:
        attributes["coding_testcase_id"] = str(data[case_data_name])


def parse_case_attributes(item: Item, comment_fields: Optional[List[str]] = None) -> Dict[str, str]:
    """parse testcase attributes"""
    desc = _get_desc(item)
    attributes: Dict[str, str] = {"description": desc}
    if comment_fields:
        attributes.update(scan_comment_fields(desc, comment_fields))

    markers = _iter_markers(item)
    for mark in markers:
        _try_set_owner(attributes, mark)
        _try_set_extra_attributes(attributes, mark)
        _try_set_coding_testcase_id(attributes, item, mark)

    attributes["tags"] = json.dumps(_collect_tags(markers))
    return attributes


def handle_str_param(desc: str) -> Dict[str, str]:
    """handle string parameter

    解析注释中单行 a = b 或 a: b 为 (a, b)形式方便后续处理
    """
    results: Dict[str, str] = {}
    pattern = re.compile(r".*?(\w+)\s*[:=]\s*(.+)")
    for line in desc.splitlines():
        match = pattern.match(line)
        if match:
            key, value = match.groups()
            results[key.strip()] = value.strip()
    return results


def scan_comment_fields(desc: str, desc_fields: List[str]) -> Dict[str, str]:
    """
    从函数的注释中解析额外字段
    """
    all_fields = handle_str_param(desc)
    results: Dict[str, str] = {}
    for key, value in all_fields.items():
        if key not in desc_fields:
            continue
        if "," in value:
            mutil_value = [v.strip() for v in value.split(",")]
            results[key] = json.dumps(mutil_value)
        else:
            results[key] = value
    return results
