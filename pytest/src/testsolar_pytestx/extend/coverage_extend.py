from dataclasses import dataclass, field, asdict
from typing import List, Dict, Union
import json
import os
import shutil
import sys
import time
from xml.dom import minidom
import coverage
from pathlib import Path

COVERAGE_DIR: str = "testsolar_coverage"

@dataclass
class TestFileLines:
    fileName: str
    fileLines: List[int]

@dataclass
class TestCaseCoverage:
    caseName: str
    testFiles: List[TestFileLines] = field(default_factory=list)

@dataclass
class ProjectPath:
    projectPath: str
    beforeMove: str = ""
    afterMove: str = ""

@dataclass
class Coverage:
    coverageFile: str
    coverageType: str
    reportId: str
    resultHouseReportId: str
    projectPath: ProjectPath
    caseCoverage: List[TestCaseCoverage] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=4)

@dataclass
class CoverageData:
    name: str
    files: Dict[str, List[int]] = field(default_factory=dict)

def check_coverage_enable() -> bool:
    return os.getenv("TESTSOLAR_TTP_ENABLECOVERAGE", "") in ["1", "true"]

def compute_source_list(testcase_list: List[str]) -> List[str]:
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
                continue
            if testcase_list and it in testcase_package_list:
                continue
            source_list.append(it)

    return source_list

def handle_coverage_xml(xml_path: str, source_list: List[str]) -> None:
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

        with open(xml_path, "w") as fd:
            dom.writexml(fd)
    print("handle_coverage_xml cost time: %s" % (time.time() - start_time))

def get_testcase_coverage_data(source_list: List[str], coverage_db_path: str) -> Dict[str, CoverageData]:
    if not os.path.isfile(coverage_db_path):
        raise RuntimeError(f"Coverage db {coverage_db_path} not exist")
    root_path: str = os.path.dirname(os.path.abspath(coverage_db_path))
    result: Dict[str, CoverageData] = {}
    source_list = ['multiply_mod', 'addition_mod']
    cov = coverage.Coverage(data_file=coverage_db_path)
    cov.load()
    file_set = cov.get_data().measured_files()
    print("so")
    for fn in file_set:
        print("====111", fn)

        rav_fn = fn
        print("====1.5", rav_fn)
        print("====1.6", root_path)
        if rav_fn.startswith(root_path):
            print("====1.7")
            rav_fn = rav_fn[len(root_path) + 1 :]
        for source in source_list:
            print("====1.8", source)
            if rav_fn.startswith(source):
                print("=====1.9")
                break
        else:
            print("====333")
            continue

        line_map = cov.get_data().lines(fn)
        context_map = cov.get_data().contexts_by_lineno(fn)
        print("====222", line_map)
        if line_map is not None:
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

def find_coverage_path(proj: str, cov_file: str) -> str:
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
    try:
        if os.path.exists(directory):
            shutil.rmtree(directory)
            print(f"Directory '{directory}' was cleared.")
        
        os.makedirs(directory)
        print(f"Directory '{directory}' is ready.")
        
    except OSError as e:
        print(f"Error: {e.strerror}")

def handle_coverage(proj_path: str, source_list: List[str]) -> None:
    ensure_directory_exists_and_clear(os.path.join(proj_path, COVERAGE_DIR))
    coverage_file_path: str = os.path.join(proj_path, "coverage.xml")
    coverage_json_file: str = os.path.join(proj_path, COVERAGE_DIR, "testsolar_coverage.json")
    
    if not os.path.exists(coverage_file_path):
        print("File coverage.xml not exist", file=sys.stderr)
        return
    
    print("handle coverage.xml")
    handle_coverage_xml(coverage_file_path, source_list)
    coverage_db_path = find_coverage_path(proj_path, ".coverage")
    cov_file_info = get_testcase_coverage_data(source_list, coverage_db_path)

    project_path = ProjectPath(
        projectPath=str(proj_path),  # 确保转换为字符串
        beforeMove="",
        afterMove=""
    )

    coverage_data = Coverage(
        coverageFile=coverage_file_path,
        coverageType="cobertura_xml",
        reportId=os.getenv("QTA_REPORTID", ""),
        resultHouseReportId=os.getenv("QTA_RESULT_HOUSE_REPORTID", ""),
        projectPath=project_path
    )
    print("=====123123123", cov_file_info)
    for case_name, file_covs in cov_file_info.items():

        test_files = [TestFileLines(fileName=file_name, fileLines=file_lines)
                      for file_name, file_lines in file_covs.files.items()]
        test_case_coverage = TestCaseCoverage(caseName=case_name, testFiles=test_files)
        coverage_data.caseCoverage.append(test_case_coverage)

    with open(coverage_json_file, "w") as f:
        f.write(coverage_data.to_json())

    print(f"Coverage data saved to {coverage_json_file}")


if __name__ == "__main__":
    testcase_list: List[str] = ["uttest/test_add.py?test_add_2_numbers", "uttest/test_add.py?test_add_dict"]
    source_list = compute_source_list(testcase_list)
    handle_coverage(os.getcwd(), source_list)