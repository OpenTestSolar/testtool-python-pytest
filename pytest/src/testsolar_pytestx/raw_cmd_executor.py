import os
import subprocess
from .util import get_cache_directory


JUNIT_XML_PATH = "testsolar_junit.xml"
COVERAGE_REPORT_PATH = "testsolar_pytest.lcov"


def get_result_save_path() -> str:
    cache_dir = get_cache_directory()
    coverage_dir = os.path.join(cache_dir, ".testsolar", "coverage")
    if not os.path.exists(coverage_dir):
        os.makedirs(coverage_dir, mode=0o755, exist_ok=True)
    return coverage_dir


class RawCmdExecutor:
    def __init__(self, cmdline: str) -> None:
        self._cmdline = cmdline
        self._exec_cmdline = cmdline
        self._save_path = get_result_save_path()

    def _append_junit_xml(self) -> None:
        xml_file = os.path.join(self._save_path, JUNIT_XML_PATH)
        self._exec_cmdline += f" --junitxml={xml_file} "

    def _append_coverage_args(self) -> None:
        coverage_file = os.path.join(self._save_path, COVERAGE_REPORT_PATH)
        self._exec_cmdline += f" --cov=. --cov-report=lcov:{coverage_file} "

    def _append_extra_args(self) -> None:
        self._append_junit_xml()
        self._append_coverage_args()

    def exec(self) -> int:
        self._append_extra_args()
        return self._exec_cmd()

    def _exec_cmd(self) -> int:
        result: subprocess.CompletedProcess = subprocess.run(  # type: ignore
            self._exec_cmdline, shell=True, stdout=None, stderr=None
        )
        return result.returncode

    def get_exec_cmdline(self) -> str:
        return self._exec_cmdline
