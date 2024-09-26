import json
import logging
import os
import shutil
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock
from xml.dom import minidom

import pytest

from src.testsolar_pytestx.extend.coverage_extend import (
    ProjectPath,
    TestFileLines,
    TestCaseCoverage,
    Coverage,
    CoverageData,
    check_coverage_enable,
    collect_code_packages,
    filter_coverage_xml_packages,
    convert_coverage_data,
    prepare_file_path,
    get_testcase_coverage_data,
    find_coverage_db_path,
    generate_coverage_json_file,
    collect_coverage_report,
)

testdata_dir = Path(__file__).parent.parent.absolute().joinpath("testdata/testsolar_coverage")
logger = logging.getLogger(__name__)


def test_coverage_to_json():
    # 创建 ProjectPath 对象
    project_path = ProjectPath(
        projectPath="/path/to/project",
        beforeMove="/path/to/project/before",
        afterMove="/path/to/project/after",
    )

    # 创建 TestFileLines 对象
    test_file_lines1 = TestFileLines(fileName="file1.py", fileLines=[1, 2, 3])
    test_file_lines2 = TestFileLines(fileName="file2.py", fileLines=[4, 5, 6])

    # 创建 TestCaseCoverage 对象
    test_case_coverage1 = TestCaseCoverage(caseName="test_case_1", testFiles=[test_file_lines1])
    test_case_coverage2 = TestCaseCoverage(caseName="test_case_2", testFiles=[test_file_lines2])

    # 创建 Coverage 对象
    coverage = Coverage(
        coverageFile="/path/to/coverage.xml",
        coverageType="cobertura_xml",
        projectPath=project_path,
        caseCoverage=[test_case_coverage1, test_case_coverage2],
    )

    # 将 Coverage 对象序列化为 JSON
    json_output = coverage.to_json()
    expected_output = json.dumps(asdict(coverage), indent=4)

    # 验证 JSON 输出
    assert json.loads(json_output) == json.loads(expected_output)


def test_check_coverage_enable_true(monkeypatch):
    assert check_coverage_enable() is False

    monkeypatch.setenv("TESTSOLAR_TTP_ENABLECOVERAGE", "1")
    assert check_coverage_enable() is True

    monkeypatch.setenv("TESTSOLAR_TTP_ENABLECOVERAGE", "true")
    assert check_coverage_enable() is True


def test_collect_code_packages(monkeypatch):
    """
    测试 collect_code_packages 函数
    """
    # 创建临时文件目录并扫描
    temp_dir = Path(os.getcwd()) / ".test_temp_dir"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()
    (temp_dir / "__init__.py").touch()
    result = collect_code_packages([])
    assert sorted(result) == sorted(["tests", "src"])
    shutil.rmtree(temp_dir)

    monkeypatch.setenv("TESTSOLAR_TTP_COVERAGECODEPACKAGES", "")
    assert collect_code_packages(["src/tests/test_add.py"]) == ["tests"]

    # 使用 monkeypatch 确保环境变量在测试结束后恢复
    monkeypatch.delenv("TESTSOLAR_TTP_COVERAGECODEPACKAGES", raising=False)

    # 测试用例列表为空，则返回当前目录的包名
    result = collect_code_packages([])
    assert sorted(result) == sorted(["tests", "src"])

    # 设置环境变量 TESTSOLAR_TTP_COVERAGECODEPACKAGES
    monkeypatch.setenv("TESTSOLAR_TTP_COVERAGECODEPACKAGES", "src")
    result = collect_code_packages([])
    assert result == ["src"]

    # 测试用例列表中包含文件路径
    result = collect_code_packages(["src/tests/test_add.py"])
    assert result == ["src"]


@pytest.fixture
def coverage_file_path(tmpdir):
    # 假设你的测试数据目录是 testdata_dir
    original_coverage_file = testdata_dir / "coverage.xml"

    # 将原始文件复制到临时目录中
    temp_coverage_file = Path(tmpdir) / "coverage.xml"
    shutil.copy(original_coverage_file, temp_coverage_file)

    return temp_coverage_file


def test_filter_coverage_xml_packages(monkeypatch, coverage_file_path):
    # 捕获日志输出
    log_output = []

    def mock_log_info(message):
        log_output.append(message)

    monkeypatch.setattr(logger, "info", mock_log_info)

    # 调用函数
    filter_coverage_xml_packages(coverage_file_path, ["package1", "package2"])

    # 验证修改后的文件内容
    with open(coverage_file_path, "r") as f:
        dom = minidom.parse(f)
        packages = dom.getElementsByTagName("package")
        package_names = [package.getAttribute("name") for package in packages]
        assert "package1" in package_names
        assert "package2" in package_names
        assert "package3" not in package_names


def test_convert_coverage_data():
    # 准备输入数据
    result = {"test_case1": CoverageData(name="test_case1", files={"file1.py": [1, 2]})}
    rav_fn = "file2.py"
    line_map = [3, 4, 5, 6]
    context_map = {
        3: ["test_case2|context"],
        4: ["test_case2|context", "test_case3|context"],
        5: ["test_case3|context"],
        6: ["test_case4"],  # 触发 ValueError
    }

    # 调用方法
    updated_result = convert_coverage_data(result, rav_fn, line_map, context_map)

    # 验证结果
    expected_result = {
        "test_case1": CoverageData(name="test_case1", files={"file1.py": [1, 2]}),
        "test_case2": CoverageData(name="test_case2", files={"file2.py": [3, 4]}),
        "test_case3": CoverageData(name="test_case3", files={"file2.py": [4, 5]}),
        "test_case4": CoverageData(name="test_case4", files={"file2.py": [6]}),
    }

    assert updated_result == expected_result


def test_convert_coverage_data_path_handling():
    # 准备输入数据
    result = {}
    rav_fn = "path/to/file2.py"
    line_map = [7]
    context_map = {7: ["path.to.test_case5|context"]}

    # 调用方法
    updated_result = convert_coverage_data(result, rav_fn, line_map, context_map)

    # 验证结果
    expected_result = {
        "path.to.test_case5": CoverageData(
            name="path.to.test_case5", files={"path/to/file2.py": [7]}
        )
    }

    assert updated_result == expected_result


def test_prepare_file_path():
    # 测试用例1：文件路径以根路径开头
    fn = "/root/path/to/file.py"
    root_path = "/root/path"
    expected_result = "to/file.py"
    assert prepare_file_path(fn, root_path) == expected_result

    # 测试用例2：文件路径不以根路径开头
    fn = "/another/path/to/file.py"
    root_path = "/root/path"
    expected_result = "/another/path/to/file.py"
    assert prepare_file_path(fn, root_path) == expected_result

    # 测试用例3：文件路径与根路径相同
    fn = "/root/path"
    root_path = "/root/path"
    expected_result = ""
    assert prepare_file_path(fn, root_path) == expected_result

    # 测试用例4：根路径为空字符串
    fn = "/path/to/file.py"
    root_path = ""
    expected_result = "path/to/file.py"
    assert prepare_file_path(fn, root_path) == expected_result

    # 测试用例5：文件路径为空字符串
    fn = ""
    root_path = "/root/path"
    expected_result = ""
    assert prepare_file_path(fn, root_path) == expected_result


def test_get_testcase_coverage_data(monkeypatch):
    # 假设你的测试数据目录是 test_data_path
    test_data_path = Path(testdata_dir)  # 请根据实际情况修改
    coverage_db_path = test_data_path / ".coverage"

    # 检查文件是否存在
    assert coverage_db_path.is_file(), f"Coverage db {coverage_db_path} does not exist"

    # 调用方法
    result = get_testcase_coverage_data(["/data/tests/addition_mod"], coverage_db_path)

    # 验证结果
    expected_result = {
        "uttest.test_add.test_add_param": CoverageData(
            name="uttest.test_add.test_add_param",
            files={"/data/tests/addition_mod/add.py": [11, 12]},
        ),
        "uttest.test_add.test_add_dict": CoverageData(
            name="uttest.test_add.test_add_dict",
            files={"/data/tests/addition_mod/add.py": [11, 13, 15, 17, 18, 19, 20, 21]},
        ),
        "uttest.test_add.test_add_2_numbers": CoverageData(
            name="uttest.test_add.test_add_2_numbers",
            files={"/data/tests/addition_mod/add.py": [11, 12]},
        ),
    }
    assert result == expected_result


class TestCoverageFinder:
    def test_find_coverage_db_path_root(self):
        # 测试根目录存在 cov_file
        result = find_coverage_db_path(str(testdata_dir), ".coverage_db")
        assert result == Path(testdata_dir) / ".coverage_db"

        # 测试根目录不存在 cov_file，测试使用 .coverage 文件
        test_dir = Path(testdata_dir).parent
        result = find_coverage_db_path(str(test_dir), "")
        assert result == Path(testdata_dir) / ".coverage"

        test_dir = Path(testdata_dir).parent / "aa"
        result = find_coverage_db_path(str(test_dir), "")
        assert result == Path("")


class TestGenerateCoverageJsonFile:
    @pytest.fixture
    def setup_test_environment(self):
        proj_path = Path(tempfile.TemporaryDirectory().name)
        proj_path.mkdir()

        coverage_file_path = proj_path / "coverage.xml"
        coverage_file_path.touch()

        coverage_json_file = proj_path / "coverage.json"

        cov_file_info = {
            "test_case1": CoverageData(name="test_case1", files={"file1.py": [1, 2, 3]}),
            "test_case2": CoverageData(name="test_case2", files={"file2.py": [4, 5, 6]}),
        }

        return proj_path, coverage_file_path, cov_file_info, coverage_json_file

    def test_generate_coverage_json_file(self, setup_test_environment, monkeypatch):
        (
            proj_path,
            coverage_file_path,
            cov_file_info,
            coverage_json_file,
        ) = setup_test_environment

        # 调用方法
        generate_coverage_json_file(
            proj_path=proj_path,
            coverage_file_path=coverage_file_path,
            cov_file_info=cov_file_info,
            coverage_json_file=coverage_json_file,
        )

        # 验证生成的 JSON 文件是否正确
        with open(coverage_json_file, "r") as f:
            data = json.load(f)

        expected_data = {
            "coverageFile": str(coverage_file_path),
            "coverageType": "cobertura_xml",
            "projectPath": {
                "projectPath": str(proj_path),
                "beforeMove": "",
                "afterMove": "",
            },
            "caseCoverage": [
                {
                    "caseName": "test_case1",
                    "testFiles": [{"fileName": "file1.py", "fileLines": [1, 2, 3]}],
                },
                {
                    "caseName": "test_case2",
                    "testFiles": [{"fileName": "file2.py", "fileLines": [4, 5, 6]}],
                },
            ],
        }

        assert data == expected_data


class TestCollectCoverageReport:
    @pytest.fixture
    def setup_test_environment(self, tmpdir):
        proj_path = Path(tmpdir) / "projtest"
        proj_path.mkdir()

        file_report_path = "report"
        report_path = proj_path / file_report_path
        report_path.mkdir()

        coverage_file_path = report_path / "coverage.xml"
        coverage_file_path.touch()

        coverage_db_path = proj_path / ".coverage"
        coverage_db_path.touch()

        return proj_path, file_report_path, coverage_file_path, coverage_db_path

    def test_collect_coverage_report(self, setup_test_environment, monkeypatch):
        (
            proj_path,
            file_report_path,
            coverage_file_path,
            coverage_db_path,
        ) = setup_test_environment

        # Mock dependencies
        filter_coverage_xml_packages = MagicMock()
        find_coverage_db_path = MagicMock(return_value=coverage_db_path)
        get_testcase_coverage_data = MagicMock(
            return_value={"test_case1": {"name": "test_case1", "files": {"file1.py": [1, 2, 3]}}}
        )
        generate_coverage_json_file = MagicMock()

        monkeypatch.setattr(
            "src.testsolar_pytestx.extend.coverage_extend.filter_coverage_xml_packages",
            filter_coverage_xml_packages,
        )
        monkeypatch.setattr(
            "src.testsolar_pytestx.extend.coverage_extend.find_coverage_db_path",
            find_coverage_db_path,
        )
        monkeypatch.setattr(
            "src.testsolar_pytestx.extend.coverage_extend.get_testcase_coverage_data",
            get_testcase_coverage_data,
        )
        monkeypatch.setattr(
            "src.testsolar_pytestx.extend.coverage_extend.generate_coverage_json_file",
            generate_coverage_json_file,
        )

        # Mock logger
        logger = MagicMock()
        monkeypatch.setattr("src.testsolar_pytestx.extend.coverage_extend.logger", logger)

        # Call the method
        collect_coverage_report(proj_path, file_report_path, ["package1", "package2"])

        # Assert calls
        filter_coverage_xml_packages.assert_called_once_with(
            coverage_file_path, ["package1", "package2"]
        )
        find_coverage_db_path.assert_called_once_with(proj_path, ".coverage")
        get_testcase_coverage_data.assert_called_once_with(
            ["package1", "package2"], coverage_db_path
        )
        generate_coverage_json_file.assert_called_once()

        logger.info.assert_called_with("collect coverage report done")

    def test_collect_coverage_report_no_coverage_file(self, setup_test_environment, monkeypatch):
        proj_path, file_report_path, coverage_file_path, _ = setup_test_environment

        # Remove the coverage.xml file to test the error case
        os.remove(coverage_file_path)

        # Mock logger
        logger = MagicMock()
        monkeypatch.setattr("src.testsolar_pytestx.extend.coverage_extend.logger", logger)

        # Call the method
        collect_coverage_report(proj_path, file_report_path, ["package1", "package2"])

        # Assert that error log is called
        logger.error.assert_called_once_with("File coverage.xml not exist", file=sys.stderr)
