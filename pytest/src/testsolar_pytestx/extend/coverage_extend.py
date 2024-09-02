from dataclasses import dataclass, field, asdict
from typing import List, Dict
import json
import os
import configparser
import sys
import time
import uuid
from xml.dom import minidom
import coverage
from loguru import logger
from pathlib import Path

COVERAGE_DIR: str = "testsolar_coverage"


@dataclass
class TestFileLines:
    """
    数据类，用于存储测试文件名称和行号。
    """

    __test__ = False

    fileName: str
    fileLines: List[int]


@dataclass
class TestCaseCoverage:
    """
    数据类，用于存储测试用例覆盖率。
    """

    __test__ = False

    caseName: str
    testFiles: List[TestFileLines] = field(default_factory=list)


@dataclass
class ProjectPath:
    """
    数据类，用于存储项目路径信息。
    """

    projectPath: str
    beforeMove: str = ""
    afterMove: str = ""


@dataclass
class Coverage:
    """
    数据类，用于存储覆盖率信息。
    """

    coverageFile: str
    coverageType: str
    projectPath: ProjectPath
    caseCoverage: List[TestCaseCoverage] = field(default_factory=list)

    def to_json(self) -> str:
        """
        将 Coverage 对象序列化为 JSON 字符串。

        Returns:
            str: 序列化后的 JSON 字符串。
        """
        return json.dumps(asdict(self), indent=4)


@dataclass
class CoverageData:
    """
    数据类，用于存储单个测试用例的覆盖率数据。
    """

    name: str
    files: Dict[str, List[int]] = field(default_factory=dict)


def check_coverage_enable() -> bool:
    """
    检查是否启用覆盖率。

    Returns:
        bool: 是否启用覆盖率。
    """
    return os.getenv("TESTSOLAR_TTP_ENABLECOVERAGE", "") in ["1", "true"]


def collect_code_packages(testcase_list: List[str]) -> List[str]:
    """
    自动计算被测代码包。

    如果 code_package 为空，则遍历当前目录，自动识别项目中的代码包。
    过滤掉以 '.' 开头的目录、没有 __init__.py 文件的目录以及测试用例目录。

    Args:
        testcase_list (List[str]): 测试用例列表。

    Returns:
        List[str]: 自动识别的代码包列表。
    """
    code_package_env: str = os.environ.get("TESTSOLAR_TTP_COVERAGECODEPACKAGES", "")
    if code_package_env:
        code_package: List[str] = code_package_env.strip().split(";")
    else:
        code_package = []

    # 如果测试用例列表不为空，则过滤掉测试用例目录
    testcase_package_list: List[str] = []
    for it in testcase_list:
        testcase_package_list.append(it.split("/")[0].strip())
    testcase_package_list = list(set(testcase_package_list))

    # 如果没有找到覆盖率包目录，则根据当前目录下的所有目录来筛选
    if not code_package:
        for it in os.listdir(os.getcwd()):
            if not os.path.isdir(it):
                continue
            if not os.path.exists(Path(it) / "__init__.py"):
                continue
            if it[0] == ".":
                continue
            if testcase_list and it in testcase_package_list:
                continue
            code_package.append(it)

    return code_package


def filter_coverage_xml_packages(xml_path: Path, code_package: List[str]) -> None:
    """
    过滤 coverage.xml 文件中非测试覆盖包目录。

    Args:
        xml_path (str): coverage.xml 文件路径。
        code_package (List[str]): 被测代码包列表。
    """
    start_time: float = time.time()
    logger.info(f"code_package: {code_package}")
    with open(xml_path, "r") as fp:
        dom = minidom.parse(fp)
        root = dom.documentElement
        source = root.getElementsByTagName("source")[0]
        packages = root.getElementsByTagName("package")
        for package in packages:
            name = package.getAttribute("name")
            if len(code_package) > 0:
                for source in code_package:
                    if name == source or name.startswith(source + "."):
                        break
                else:
                    logger.info("Package %s ignored" % name)
                    package.parentNode.removeChild(package)

        with open(xml_path, "w") as fd:
            dom.writexml(fd)
    logger.info("filter_coverage_xml_packages cost time: %s" % (time.time() - start_time))


def convert_coverage_data(
    result: Dict[str, CoverageData],
    rav_fn: str,
    line_map: List[int],
    context_map: Dict[int, List[str]],
) -> Dict[str, CoverageData]:
    """
    转换覆盖率数据。

    Args:
        result (Dict[str, CoverageData]): 当前的覆盖率数据字典。
        rav_fn (str): 文件路径。
        line_map (List[int]): 覆盖的行号列表。
        context_map (Dict[int, List[str]]): 行号与测试用例的映射。

    Returns:
        Dict[str, CoverageData]: 更新后的覆盖率数据字典。
    """
    for line in line_map:
        test_case_list = context_map.get(line, [])
        for test_case in test_case_list:
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
    return result


def get_testcase_coverage_data(
    code_package: List[str], coverage_db_path: Path
) -> Dict[str, CoverageData]:
    """
    获取测试用例的覆盖率数据。

    Args:
        code_package (List[str]): 被测代码包列表。
        coverage_db_path (str): 覆盖率数据库文件路径。

    Returns:
        Dict[str, CoverageData]: 包含覆盖率数据的字典。
    """
    if not os.path.isfile(coverage_db_path):
        raise RuntimeError(f"Coverage db {coverage_db_path} not exist")
    root_path: str = os.path.dirname(os.path.abspath(coverage_db_path))
    result: Dict[str, CoverageData] = {}

    # 加载覆盖率数据并获取计量的文件
    cov = coverage.Coverage(data_file=coverage_db_path)
    cov.load()
    file_set = cov.get_data().measured_files()
    logger.info("Coverage data loaded")

    for fn in file_set:
        rav_fn = prepare_file_path(fn, root_path)
        if not is_file_in_code_package(rav_fn, code_package):
            continue

        line_map = cov.get_data().lines(fn)
        context_map = cov.get_data().contexts_by_lineno(fn)
        if line_map is not None:
            try:
                result = convert_coverage_data(result, rav_fn, line_map, context_map)
            except Exception as e:
                logger.error(f"Error processing file {fn}: {e}")

    return result


def prepare_file_path(fn: str, root_path: str) -> str:
    """
    准备文件路径。

    Args:
        fn (str): 文件路径。
        root_path (str): 根路径。

    Returns:
        str: 处理后的文件路径。
    """
    if fn.startswith(root_path):
        fn = fn[len(root_path) + 1 :]
    return fn


def is_file_in_code_package(fn: str, code_package: List[str]) -> bool:
    """
    检查文件是否在代码包中。

    Args:
        fn (str): 文件路径。
        code_package (List[str]): 代码包列表。

    Returns:
        bool: 如果文件在代码包中，则返回 True；否则返回 False。
    """
    for source in code_package:
        if fn.startswith(source):
            return True
    return False


def find_coverage_db_path(proj: str, cov_file: str) -> Path:
    """
    查找覆盖率数据库文件路径。

    Args:
        proj (str): 项目路径。
        cov_file (str): 覆盖率文件名。

    Returns:
        Path: 覆盖率数据库文件路径。如果未找到，返回空路径。
    """
    # 检查是否根目录存在db文件
    coverage_db_path = Path(proj) / cov_file
    if coverage_db_path.is_file():
        logger.info("Found coverage db file: {}", coverage_db_path)
        return coverage_db_path

    # 查找 .coveragerc 文件 data_file 配置
    coveragerc_file_path = Path(proj) / ".coveragerc"
    if coveragerc_file_path.is_file():
        config = configparser.ConfigParser()
        config.read(coveragerc_file_path)

        # 检查 [run] 部分中的 data_file 配置项
        if "run" in config and "data_file" in config["run"]:
            coverage_path = Path(config["run"]["data_file"].strip())
            if coverage_path.is_file():
                logger.info("Found coverage db file: {}", coverage_path)
                return coverage_path

    # 遍历项目目录，查找 .coverage 文件
    for root, _, files in os.walk(proj):
        for f_name in files:
            if f_name == ".coverage":
                coverage_path = Path(root) / f_name
                logger.info("Found coverage db file: {}", coverage_path)
                return coverage_path

    # 如果未找到覆盖率数据库文件，返回空路径
    return Path("")


def generate_coverage_json_file(
    proj_path: str,
    coverage_file_path: Path,
    cov_file_info: Dict[str, CoverageData],
    coverage_json_file: Path,
) -> None:
    """
    生成覆盖率 JSON 文件。

    Args:
        proj_path (str): 项目路径。
        coverage_file_path (str): 覆盖率文件路径。
        cov_file_info (Dict[str, CoverageData]): 测试用例覆盖率信息。
        coverage_json_file (str): 覆盖率 JSON 文件保存路径。
    """
    # 创建 ProjectPath 对象，存储项目路径信息
    project_path = ProjectPath(
        projectPath=str(proj_path),
        beforeMove="",
        afterMove="",  # 确保转换为字符串
    )

    # 创建 Coverage 对象，存储覆盖率信息
    coverage_data = Coverage(
        coverageFile=str(coverage_file_path),
        coverageType="cobertura_xml",
        projectPath=project_path,
    )

    # 填充测试用例覆盖率文件行信息
    if cov_file_info:
        for case_name, file_covs in cov_file_info.items():
            test_files = [
                TestFileLines(fileName=file_name, fileLines=file_lines)
                for file_name, file_lines in file_covs.files.items()
            ]
            test_case_coverage = TestCaseCoverage(caseName=case_name, testFiles=test_files)
            coverage_data.caseCoverage.append(test_case_coverage)
    else:
        logger.warning("No test case coverage data found")
        coverage_data.caseCoverage = []

    # 将 Coverage 对象序列化为 JSON 并写入文件
    with open(coverage_json_file, "w") as f:
        f.write(coverage_data.to_json())

    logger.info(f"Coverage data saved to {coverage_json_file}")


def collect_coverage_report(proj_path: str, file_report_path: str, code_package: List[str]) -> None:
    """
    处理覆盖率并生成覆盖率报告。

    Args:
        proj_path (str): 项目路径。
        code_package (List[str]): 被测代码包列表。
    """
    # 定义覆盖率文件路径和 JSON 文件路径
    coverage_file_path: Path = Path(proj_path) / file_report_path / "coverage.xml"
    coverage_json_dir = Path(proj_path) / "testsolar_coverage"
    if not coverage_json_dir.exists():
        coverage_json_dir.mkdir()
    unique_string = str(uuid.uuid4())
    coverage_json_file: Path = coverage_json_dir / f"{unique_string}.json"

    # 检查覆盖率文件是否存在
    if not os.path.exists(coverage_file_path):
        logger.error("File coverage.xml not exist", file=sys.stderr)
        return

    # 过滤 coverage.xml 文件中的包信息
    logger.info("filter coverage.xml packages")
    filter_coverage_xml_packages(coverage_file_path, code_package)

    # 查找覆盖率数据库文件路径
    coverage_db_path = find_coverage_db_path(proj_path, ".coverage")

    # 获取测试用例的覆盖率数据
    if coverage_db_path:
        cov_file_info = get_testcase_coverage_data(code_package, coverage_db_path)
    else:
        # 不存在覆盖率数据库文件，则不生成覆盖率文件行信息
        cov_file_info = {}

    # 生成覆盖率 JSON 文件
    generate_coverage_json_file(proj_path, coverage_file_path, cov_file_info, coverage_json_file)

    logger.info("collect coverage report done")
