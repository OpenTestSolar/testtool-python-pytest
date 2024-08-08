import json
import os
import shutil
import sys
import time
from typing import List, Dict
from dataclasses import dataclass, field
import coverage.data
from xml.dom import minidom


COVERAGE_DIR: str = "testsolar_coverage"


@dataclass
class CoverageData:
    """
    数据类，用于存储覆盖率数据。
    """
    name: str
    files: Dict[str, List[int]] = field(default_factory=dict)

def check_coverage_enable() -> bool:
    """
    检查是否启用覆盖率

    Returns:
        bool: 是否启用覆盖率
    """
    return os.getenv("TESTSOLAR_TTP_ENABLECOVERAGE", "") in ["1", "true"]

def compute_source_list(testcase_list: List[str]) -> List[str]:
    """
    自动计算被测代码包。

    如果 source_list 为空，则遍历当前目录，自动识别项目中的代码包。
    过滤掉以 '.' 开头的目录、没有 __init__.py 文件的目录以及测试用例目录。

    Args:
        testcase_list (List[str]): 测试用例列表。

    Returns:
        List[str]: 自动识别的代码包列表。
    """
    source_list_env: str = os.environ.get("TESTSOLAR_TTP_COVERAGESOURCELIST", "")
    if source_list_env:
        source_list: List[str] = source_list_env.strip().split(";")
    else:
        source_list = []
        
    testcase_package_list: List[str] = []
    for it in testcase_list:
        testcase_package_list.append(it.split("/")[0].strip())
    testcase_package_list = list(set(testcase_package_list))
    
    if not source_list:
        for it in os.listdir(os.getcwd()):
            if not os.path.isdir(it):
                continue
            if not os.path.exists(os.path.join(it, "__init__.py")):
                continue
            if it[0] == ".":
                # 过滤掉.开头的目录
                continue
            if testcase_list and it in testcase_package_list:
                # 过滤掉单测代码
                continue
            source_list.append(it)

    return source_list


def handle_coverage_xml(xml_path: str, save_path, source_list: List[str]) -> None:
    """
    处理 coverage.xml 文件。

    Args:
        xml_path (str): coverage.xml 文件路径。
        source_list (List[str]): 被测代码包列表。
    """
    start_time: float = time.time()
    print(f"source_list: {source_list}")
    with open(xml_path, "r") as fp:
        dom = minidom.parse(fp)
        root = dom.documentElement
        source = root.getElementsByTagName("source")[0]
        packages = root.getElementsByTagName("package")
        for package in packages:
            name = package.getAttribute("name")
            if len(source_list) > 0:
                for source in source_list:
                    if name == source or name.startswith(source + "."):
                        break
                else:
                    print("Package %s ignored" % name)
                    package.parentNode.removeChild(package)

        with open(save_path, "w") as fd:
            dom.writexml(fd)
    print("handle_coverage_xml cost time: %s" % (time.time() - start_time))


def save_testcase_coverage_data(source_list: List[str], coverage_db_path: str, save_path: str) -> None:
    """
    保存测试用例的覆盖率数据。

    Args:
        source_list (List[str]): 被测代码包列表。
        coverage_db_path (str): 覆盖率数据库文件路径。
        save_path (str): 保存路径。
    """
    start_time: float = time.time()

    if not os.path.isfile(coverage_db_path):
        raise RuntimeError(f"Coverage db {coverage_db_path} not exist")
    root_path: str = os.path.dirname(os.path.abspath(coverage_db_path))
    result: Dict[str, CoverageData] = {}
    coverage_data = coverage.data.CoverageData(basename=coverage_db_path)
    coverage_data.read()
    file_set = coverage_data.measured_files()
    for fn in file_set:
        rav_fn = fn
        if rav_fn.startswith(root_path):
            rav_fn = rav_fn[len(root_path) + 1 :]
        for source in source_list:
            if rav_fn.startswith(source):
                break
        else:
            continue

        line_map = coverage_data.contexts_by_lineno(fn)
        for line in line_map:
            test_case_list = line_map[line]
            for test_case in test_case_list:  # type: str
                if not test_case:
                    continue
                try:
                    name = test_case[: test_case.index("|")]
                except ValueError:
                    name = test_case
                items = name.split("::")
                if items[0].endswith(".py"):
                    items[0] = items[0][:-3].replace(os.sep, ".")
                name = ".".join(items)
                if name not in result:
                    result[name] = CoverageData(name=name)
                if rav_fn not in result[name].files:
                    result[name].files[rav_fn] = []
                result[name].files[rav_fn].append(line)

    with open(save_path, "w") as fp:
        json.dump({name: data.files for name, data in result.items()}, fp)
    print(f"Testcase coverage data saved to {save_path}")
    print(f"save_testcase_coverage_data cost time: {time.time() - start_time}")


def find_coverage_path(proj: str, cov_file: str) -> str:
    """
    查找覆盖率数据库文件路径。

    Args:
        proj (str): 项目路径。
        cov_file (str): 覆盖率文件名。

    Returns:
        str: 覆盖率数据库文件路径。
    """
    if os.path.isfile(os.path.join(proj, cov_file)):
        print("find coverage db file: ", cov_file)
        return cov_file
    if os.path.isfile(os.path.join(proj, ".coveragerc")):
        with open(os.path.join(proj, ".coveragerc")) as fp:
            data = fp.readlines()
            for line in data:
                if not line.strip().startswith("data_file"):
                    continue
                coverage_path = line.split("=")[1].strip()
                if os.path.isfile(coverage_path):
                    print("find coverage db file: ", coverage_path)
                    return coverage_path
    for root, _, files in os.walk(proj):
        for f_name in files:
            if f_name == ".coverage":
                print("find coverage db file: ", os.path.join(root, f_name))
                return os.path.join(root, f_name)
    return cov_file


def ensure_directory_exists_and_clear(directory: str) -> None:
    """
    确保指定的目录存在。如果目录不存在，则创建它。
    如果目录存在，则清空其内容。

    Args:
        directory (str): 要检查或创建的目录路径。
    """
    try:
        if os.path.exists(directory):
            shutil.rmtree(directory)  # 删除目录及其所有内容
            print(f"Directory '{directory}' was cleared.")
        
        os.makedirs(directory) # 创建目录
        print(f"Directory '{directory}' is ready.")
        
    except OSError as e:
        print(f"Error: {e.strerror}")


def handle_coverage(proj_path: str, source_list: List[str]) -> None:
    """
    处理覆盖率。

    Args:
        proj_path (str): 项目路径。
        source_list (List[str]): 被测代码包列表。
    """
    ensure_directory_exists_and_clear(os.path.join(proj_path, COVERAGE_DIR))
    coverage_file_path: str = os.path.join(proj_path, "coverage.xml")
    coverage_save_path: str = os.path.join(proj_path, COVERAGE_DIR, "coverage.xml")
    coverage_json_file: str = os.path.join(proj_path, COVERAGE_DIR, "testcase_coverage.json")
    if not os.path.exists(coverage_file_path):
        print("File coverage.xml not exist", file=sys.stderr)
    else:
        print("handle coverage.xml")
        handle_coverage_xml(coverage_file_path, coverage_save_path, source_list)
        coverage_db_path = find_coverage_path(proj_path, ".coverage")
        save_testcase_coverage_data(source_list, coverage_db_path, coverage_json_file)
