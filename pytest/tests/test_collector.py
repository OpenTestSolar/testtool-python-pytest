import json
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List

from testsolar_testtool_sdk.model.param import EntryParam
from testsolar_testtool_sdk.model.load import LoadResult
from testsolar_testtool_sdk.file_reader import read_file_load_result

from src.testsolar_pytestx.collector import (
    collect_testcases,
    collect_testcases_file_mode,
    _is_pytest_test_file,
    _scan_pytest_files,
)


class CollectorTest(unittest.TestCase):
    testdata_dir: str = str(Path(__file__).parent.parent.absolute().joinpath("testdata"))

    def test_collect_testcases_when_selector_is_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / "result.json"
            entry = EntryParam(
                TaskId="aa",
                ProjectPath=self.testdata_dir,
                TestSelectors=[
                    "test_normal_case.py?test_success",
                    "aa/bb/cc/test_in_sub_class.py",
                    "test_data_drive.py",
                    "errors/test_import_error.py",
                    "errors/test_load_error.py",
                ],
                FileReportPath=str(report_file),
            )

            collect_testcases(entry)

            re = read_file_load_result(report_file)

            self.assertEqual(len(re.Tests), 6)
            self.assertEqual(len(re.LoadErrors), 2)
            re.Tests.sort(key=lambda x: x.Name)
            re.LoadErrors.sort(key=lambda x: x.name)
            self.assertEqual(re.Tests[0].Name, "aa/bb/cc/test_in_sub_class.py?TestCompute/test_add")
            self.assertEqual(re.Tests[1].Name, "test_data_drive.py?test_eval/[2+4-6]")
            self.assertEqual(re.Tests[2].Name, "test_data_drive.py?test_eval/[3+5-8]")
            self.assertEqual(re.Tests[3].Name, "test_data_drive.py?test_eval/[6*9-42]")
            self.assertEqual(
                re.Tests[4].Name,
                "test_data_drive.py?test_special_data_drive_name/[中文-分号+[id:32]]",
            )

            self.assertEqual(re.Tests[5].Name, "test_normal_case.py?test_success")
            self.assertEqual(re.Tests[5].Attributes["owner"], "foo")
            self.assertEqual(re.Tests[5].Attributes["description"], "测试获取答案")
            self.assertEqual(re.Tests[5].Attributes["tags"], '["high"]')
            self.assertEqual(re.Tests[5].Attributes["extra_attributes"], '[{"env": ["AA", "BB"]}]')

            self.assertEqual(
                re.LoadErrors[0].name,
                "errors/test_import_error.py",
            )
            self.assertIn(
                "ModuleNotFoundError: No module named 'bad_import'",
                re.LoadErrors[0].message,
            )
            self.assertEqual(re.LoadErrors[1].name, "errors/test_load_error.py")
            self.assertIn("SyntaxError: ", re.LoadErrors[1].message)

    def test_collect_testcases_when_select_not_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / "result.json"
            entry = EntryParam(
                TaskId="aa",
                ProjectPath=self.testdata_dir,
                TestSelectors=[
                    "test_data_drive.py",
                    "test_not_exist.py",
                ],
                FileReportPath=str(report_file),
            )

            collect_testcases(entry)

            re = read_file_load_result(report_file)
            re.Tests.sort(key=lambda x: x.Name)
            re.LoadErrors.sort(key=lambda x: x.name)
            self.assertEqual(len(re.Tests), 4)
            self.assertEqual(len(re.LoadErrors), 1)
            self.assertIn("test_not_exist.py does not exist, SKIP it", re.LoadErrors[0].message)

    def test_collect_testcases_with_utf8_chars(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / "result.json"
            entry = EntryParam(
                TaskId="aa",
                ProjectPath=self.testdata_dir,
                TestSelectors=[
                    "test_data_drive_zh_cn.py",
                ],
                FileReportPath=str(report_file),
            )

            collect_testcases(entry)

            re = read_file_load_result(report_file)
            re.Tests.sort(key=lambda x: x.Name)
            re.LoadErrors.sort(key=lambda x: x.name)
            self.assertEqual(len(re.Tests), 3)
            self.assertEqual(len(re.LoadErrors), 0)

            self.assertEqual(
                re.Tests[0].Name,
                "test_data_drive_zh_cn.py?test_include/[#?-#?^$%!/]",
            )
            self.assertEqual(
                re.Tests[1].Name,
                "test_data_drive_zh_cn.py?test_include/[中文-中文汉字]",
            )
            self.assertEqual(
                re.Tests[2].Name,
                "test_data_drive_zh_cn.py?test_include/[파일을 찾을 수 없습니다-ファイルが見つかりません]",
            )

    def test_collect_testcases_with_case_drive_separator(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / "result.json"
            entry = EntryParam(
                TaskId="aa",
                ProjectPath=self.testdata_dir,
                TestSelectors=[
                    "test_normal_case.py?test_success→压缩机测试",
                    "test_normal_case.py?test_success→解压机测试",
                    "test_normal_case.py?test_success→循环机测试",
                ],
                FileReportPath=str(report_file),
            )

            case_records = {}

            def loader_extend(
                param_1: str, param_2: LoadResult, param_3: Dict[str, List[str]]
            ) -> None:
                case_records.update(param_3)

            collect_testcases(entry, extra_load_function=loader_extend)

            re = read_file_load_result(report_file)
            re.Tests.sort(key=lambda x: x.Name)
            re.LoadErrors.sort(key=lambda x: x.name)
            self.assertEqual(len(re.Tests), 1)
            self.assertEqual(len(re.LoadErrors), 0)

            self.assertEqual(re.Tests[0].Name, "test_normal_case.py?test_success")

            self.assertEqual(len(case_records), 1)
            self.assertIn("test_normal_case.py?test_success", case_records)

            records = case_records["test_normal_case.py?test_success"]
            self.assertEqual(len(records), 3)
            self.assertEqual(records[0], "压缩机测试")
            self.assertEqual(records[1], "解压机测试")
            self.assertEqual(records[2], "循环机测试")

    def test_collect_testcases_when_testcase_not_exist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / "result.json"
            entry = EntryParam(
                TaskId="aa",
                ProjectPath=self.testdata_dir,
                TestSelectors=[
                    "test_normal_case.py?name=not_exist",
                ],
                FileReportPath=str(report_file),
            )

            collect_testcases(entry)

            re = read_file_load_result(report_file)
            re.Tests.sort(key=lambda x: x.Name)
            re.LoadErrors.sort(key=lambda x: x.name)
            self.assertEqual(len(re.LoadErrors), 1)

            self.assertEqual(
                re.LoadErrors[0].name,
                "test_normal_case.py?name=not_exist",
            )

    def test_collect_testcases_with_skipp_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / "result.json"
            entry = EntryParam(
                TaskId="aa",
                ProjectPath=self.testdata_dir,
                TestSelectors=[
                    "test_normal_case.py",
                    "test_skipped_error.py",
                ],
                FileReportPath=str(report_file),
            )

            collect_testcases(entry)

            re = read_file_load_result(report_file)
            re.Tests.sort(key=lambda x: x.Name)
            re.LoadErrors.sort(key=lambda x: x.name)
            self.assertEqual(len(re.Tests), 3)
            self.assertEqual(len(re.LoadErrors), 1)

    def test_collect_testcases_with_emoji(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / "result.json"
            entry = EntryParam(
                TaskId="aa",
                ProjectPath=self.testdata_dir,
                TestSelectors=[
                    "test_emoji_data_drive.py",
                ],
                FileReportPath=str(report_file),
            )

            collect_testcases(entry)

            re = read_file_load_result(report_file)
            re.Tests.sort(key=lambda x: x.Name)
            re.LoadErrors.sort(key=lambda x: x.name)
            self.assertEqual(len(re.Tests), 1)
            self.assertEqual(len(re.LoadErrors), 0)
            self.assertEqual(
                re.Tests[0].Name,
                "test_emoji_data_drive.py?test_emoji_data_drive_name/[😄]",
            )

    def test_collect_testcases_with_coding_testcase_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / "result.json"
            entry = EntryParam(
                TaskId="aa",
                ProjectPath=self.testdata_dir,
                TestSelectors=[
                    "test_coding_id.py",
                ],
                FileReportPath=str(report_file),
            )

            collect_testcases(entry)

            re = read_file_load_result(report_file)
            re.Tests.sort(key=lambda x: x.Name)
            re.LoadErrors.sort(key=lambda x: x.name)
            self.assertEqual(len(re.Tests), 3)
            self.assertEqual(len(re.LoadErrors), 0)
            self.assertEqual(
                re.Tests[0].Name,
                "test_coding_id.py?test_eval/[2+4-6]",
            )
            self.assertEqual(re.Tests[1].Attributes["coding_testcase_id"], "789")

    def test_collect_testcases_with_mark_layers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / "result.json"
            entry = EntryParam(
                TaskId="aa",
                ProjectPath=self.testdata_dir,
                TestSelectors=["aa/bb"],  # 扫描子目录
                FileReportPath=str(report_file),
            )

            load_result = LoadResult(Tests=[], LoadErrors=[])
            collect_testcases_file_mode(entry, load_result)

            # 验证结果
            self.assertEqual(len(load_result.Tests), 1)
            self.assertEqual(len(load_result.LoadErrors), 0)
            self.assertEqual(load_result.Tests[0].Name, "aa/bb/cc/test_in_sub_class.py")

    def test_collect_testcases_file_mode_with_root_directory(self):
        """测试文件模式：扫描根目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / "result.json"
            entry = EntryParam(
                TaskId="aa",
                ProjectPath=self.testdata_dir,
                TestSelectors=["."],  # 扫描整个项目
                FileReportPath=str(report_file),
            )

            load_result = LoadResult(Tests=[], LoadErrors=[])
            collect_testcases_file_mode(entry, load_result)

            # 验证结果 - 应该找到多个测试文件
            self.assertGreater(len(load_result.Tests), 5)

            # 验证包含预期的测试文件
            test_names = [test.Name for test in load_result.Tests]
            self.assertIn("test_normal_case.py", test_names)
            self.assertIn("test_data_drive.py", test_names)

    def test_collect_testcases_file_mode_with_specific_file(self):
        """测试文件模式：指定具体文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / "result.json"
            entry = EntryParam(
                TaskId="aa",
                ProjectPath=self.testdata_dir,
                TestSelectors=["test_normal_case.py"],  # 指定具体文件
                FileReportPath=str(report_file),
            )

            load_result = LoadResult(Tests=[], LoadErrors=[])
            collect_testcases_file_mode(entry, load_result)

            # 验证结果
            self.assertEqual(len(load_result.Tests), 1)
            self.assertEqual(len(load_result.LoadErrors), 0)
            self.assertEqual(load_result.Tests[0].Name, "test_normal_case.py")

    def test_collect_testcases_file_mode_with_nonexistent_file(self):
        """测试文件模式：不存在的文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / "result.json"
            entry = EntryParam(
                TaskId="aa",
                ProjectPath=self.testdata_dir,
                TestSelectors=["nonexistent_test.py"],
                FileReportPath=str(report_file),
            )

            load_result = LoadResult(Tests=[], LoadErrors=[])
            collect_testcases_file_mode(entry, load_result)

            # 验证结果 - 应该有加载错误
            self.assertEqual(len(load_result.Tests), 0)
            self.assertEqual(len(load_result.LoadErrors), 1)

    def test_is_pytest_test_file(self):
        """测试pytest测试文件识别函数"""
        # 应该识别为测试文件的情况
        test_files = [
            "test_example.py",
            "test_normal_case.py",
            "utils_test.py",
            "my_module_test.py",
            "aa/bb/test_in_sub_class.py",
        ]

        for file_path in test_files:
            with self.subTest(file_path=file_path):
                self.assertTrue(_is_pytest_test_file(file_path))

        # 不应该识别为测试文件的情况
        non_test_files = [
            "example.py",
            "utils.py",
            "config.json",
            "README.md",
            "_test.py",  # 只有下划线开头不算
            "test.txt",  # 不是.py文件
            "testfile.py",  # 不符合test_*.py格式
            "filetest.py",  # 不符合*_test.py格式
        ]

        for file_path in non_test_files:
            with self.subTest(file_path=file_path):
                self.assertFalse(_is_pytest_test_file(file_path))

    def test_scan_pytest_files(self):
        """测试扫描pytest文件函数"""
        # 扫描测试数据目录
        test_files = _scan_pytest_files(self.testdata_dir, self.testdata_dir)

        # 验证结果
        self.assertIsInstance(test_files, set)
        self.assertGreater(len(test_files), 0)

        # 验证包含预期的测试文件
        expected_files = {
            "test_normal_case.py",
            "test_data_drive.py",
            "test_coding_id.py",
            "aa/bb/cc/test_in_sub_class.py",
        }

        for expected_file in expected_files:
            self.assertIn(expected_file, test_files)

        # 验证不包含非测试文件
        for file_path in test_files:
            self.assertTrue(_is_pytest_test_file(file_path))

    def test_scan_pytest_files_excludes_hidden_and_cache_dirs(self):
        """测试扫描pytest文件时排除隐藏目录和缓存目录"""
        # 创建临时目录结构进行测试
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # 创建测试文件结构
            (tmpdir_path / "test_valid.py").write_text("# valid test file")

            # 创建隐藏目录和缓存目录
            hidden_dir = tmpdir_path / ".hidden"
            hidden_dir.mkdir(parents=True)
            (hidden_dir / "test_hidden.py").write_text("# hidden test file")

            cache_dir = tmpdir_path / "__pycache__"
            cache_dir.mkdir(parents=True)
            (cache_dir / "test_cache.py").write_text("# cache test file")

            pytest_cache_dir = tmpdir_path / ".pytest_cache"
            pytest_cache_dir.mkdir(parents=True)
            (pytest_cache_dir / "test_pytest_cache.py").write_text("# pytest cache test file")

            # 扫描文件
            test_files = _scan_pytest_files(str(tmpdir_path), str(tmpdir_path))

            # 验证只包含有效的测试文件
            self.assertEqual(len(test_files), 1)
            self.assertIn("test_valid.py", test_files)

    def test_collect_testcases_file_mode_with_directory(self):
        """测试文件模式：扫描目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / "result.json"
            entry = EntryParam(
                TaskId="aa",
                ProjectPath=self.testdata_dir,
                TestSelectors=[
                    "test_mark_layers_case.py",
                ],
                FileReportPath=str(report_file),
            )

            collect_testcases(entry)

            re = read_file_load_result(report_file)
            self.assertEqual(len(re.LoadErrors), 0)
            self.assertEqual(len(re.Tests), 2)

            tests_by_name = {it.Name: it for it in re.Tests}

            class_case_name = "test_mark_layers_case.py?TestMarkLayers/test_layers"
            self.assertIn(class_case_name, tests_by_name)
            class_attrs = tests_by_name[class_case_name].Attributes
            self.assertEqual(class_attrs["owner"], "func_owner")
            self.assertEqual(class_attrs["extra_attributes"], '[{"layer": "module"}]')
            self.assertEqual(
                set(json.loads(class_attrs["tags"])),
                {"mod_tag", "class_tag", "func_tag"},
            )

            coding_case_name = "test_mark_layers_case.py?test_coding_id_layers/[case1]"
            self.assertIn(coding_case_name, tests_by_name)
            coding_attrs = tests_by_name[coding_case_name].Attributes
            self.assertEqual(coding_attrs["owner"], "module_owner")
            self.assertEqual(coding_attrs["extra_attributes"], '[{"layer": "module"}]')
            self.assertEqual(coding_attrs["coding_testcase_id"], "CID-001")
            self.assertEqual(set(json.loads(coding_attrs["tags"])), {"mod_tag"})
