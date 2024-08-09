import json
from unittest.mock import patch, mock_open, MagicMock
from typing import List, Dict
import os
from pathlib import Path


from testsolar_pytestx.extend.coverage_extend import (
    check_coverage_enable,
    compute_source_list,
    handle_coverage_xml,
    get_testcase_coverage_data,
    find_coverage_path,
    handle_coverage,
    CoverageData
)  # 请将 'your_module' 替换为你的模块名称


testdata_dir = Path(__file__).parent.parent.absolute().joinpath("testdata")

def test_check_coverage_enable_true(monkeypatch):
    monkeypatch.setenv("TESTSOLAR_TTP_ENABLECOVERAGE", "1")
    assert check_coverage_enable() is True

def test_check_coverage_enable_false(monkeypatch):
    monkeypatch.setenv("TESTSOLAR_TTP_ENABLECOVERAGE", "0")
    assert check_coverage_enable() is False

def test_compute_source_list_with_env(monkeypatch):
    monkeypatch.setenv("TESTSOLAR_TTP_COVERAGESOURCELIST", "package1;package2")
    testcase_list = ["test.package1", "test.package2"]
    expected = ["package1", "package2"]
    assert compute_source_list(testcase_list) == expected

def test_compute_source_list_without_env(monkeypatch):
    monkeypatch.setattr(os, 'listdir', lambda _: ["package1", "package2", ".git"])
    monkeypatch.setattr(os.path, 'isdir', lambda x: x in ["package1", "package2", "test"])
    monkeypatch.setattr(os.path, 'exists', lambda x: x.endswith("__init__.py"))
    testcase_list = ["test.package1", "test.package2"]
    expected = ["package1", "package2"]
    result = compute_source_list(testcase_list)
    assert "test" not in result
    assert set(result) == set(expected)

@patch("builtins.open", new_callable=mock_open, read_data="<coverage></coverage>")
@patch("xml.dom.minidom.parse")
def test_handle_coverage_xml(mock_parse, mock_open):
    mock_dom = MagicMock()
    mock_parse.return_value = mock_dom
    mock_dom.documentElement = MagicMock()
    mock_dom.documentElement.getElementsByTagName.return_value = [MagicMock()]
    source_list = ["package1", "package2"]
    handle_coverage_xml("coverage.xml", source_list)

@patch("coverage.data.CoverageData.read")
@patch("coverage.data.CoverageData.measured_files", return_value=["/path/to/package1/file1.py"])
@patch("coverage.data.CoverageData.contexts_by_lineno", return_value={10: ["test.package1::test_func|context"]})
@patch("builtins.open", new_callable=mock_open)
@patch("os.path.isfile", return_value=True)
def test_get_testcase_coverage_data(mock_isfile, mock_open, mock_contexts, mock_files, mock_read):
    source_list = ["package1"]
    coverage_db_path = "/tmp/to/coverage_db"
    get_testcase_coverage_data(source_list, coverage_db_path)


def test_find_coverage_path_with_cov_file(monkeypatch):
    monkeypatch.setattr(os.path, 'isfile', lambda x: x == "/path/to/proj/coverage_db")
    assert find_coverage_path("/path/to/proj", "coverage_db") == "coverage_db"

def test_find_coverage_path_with_coveragerc(monkeypatch):
    monkeypatch.setattr(os.path, 'isfile', lambda x: x == "/path/to/proj/.coveragerc")
    monkeypatch.setattr("builtins.open", mock_open(read_data="data_file = /path/to/coverage_db"))
    assert find_coverage_path("/path/to/proj", "coverage_db") == "coverage_db"

def test_find_coverage_path_with_walk(monkeypatch):
    monkeypatch.setattr(os, 'walk', lambda x: [("/path/to/proj", [], [".coverage"])])
    monkeypatch.setattr(os.path, 'isfile', lambda x: False)
    assert find_coverage_path("/path/to/proj", "coverage_db") == "/path/to/proj/.coverage"

@patch("os.path.exists", return_value=True)
@patch("shutil.rmtree")
@patch("os.makedirs")
@patch("testsolar_pytestx.extend.coverage_extend.find_coverage_path", return_value="/path/to/proj/.coverage")
@patch("testsolar_pytestx.extend.coverage_extend.get_testcase_coverage_data", return_value={
    "test_case_1": {
        "file1.py": [1, 2, 3],
        "file2.py": [4, 5, 6]
    },
    "test_case_2": {
        "file3.py": [7, 8, 9],
        "file4.py": [10, 11, 12]
    }
})
def test_handle_coverage(mock_get_testcase_coverage_data, mock_find_coverage_path, mock_makedirs, mock_rmtree, mock_exists):
    source_list = ["package1"]
    
    # 运行 handle_coverage 函数
    handle_coverage(testdata_dir, source_list)

    # 验证文件操作
    mock_find_coverage_path.assert_called_once_with(testdata_dir, ".coverage")
    mock_get_testcase_coverage_data.assert_called_once()

    # 验证 JSON 内容
    coverage_json_file = testdata_dir / "testsolar_coverage" / "testsolar_coverage.json"
    with open(coverage_json_file, "r") as f:
        written_data = json.load(f)
    
    assert written_data["coverageFile"] == str(testdata_dir / "coverage.xml")
    assert written_data["coverageType"] == "cobertura_xml"
    assert written_data["projectPath"]["projectPath"] == str(testdata_dir)
    assert "caseCoverage" in written_data
    assert len(written_data["caseCoverage"]) == 2
    assert written_data["caseCoverage"][0]["caseName"] == "test_case_1"
    assert written_data["caseCoverage"][1]["caseName"] == "test_case_2"
