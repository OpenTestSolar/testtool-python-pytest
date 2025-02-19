import os
import subprocess
from loguru import logger

JUNIT_XML_PATH = "testsolar_junit.xml"
COVERAGE_REPORT_PATH = "testsolar_pytest.lcov"


class RawCmdExecutor:
    def __init__(self, cmdline: str) -> None:
        self._cmdline = cmdline
        self._exec_cmdline = cmdline

    def _append_junit_xml(self) -> None:
        self._exec_cmdline += f" --junitxml={JUNIT_XML_PATH} "

    def _append_coverage_args(self) -> None:
        try:
            cache_dir = os.path.expanduser("~/.cache")
        except Exception as e:
            logger.error(f"[PLUGIN] Failed to get user cache dir: {e}")
            return

        coverage_dir = os.path.join(cache_dir, ".testsolar", "coverage")

        try:
            os.makedirs(coverage_dir, mode=0o755, exist_ok=True)
        except OSError as e:
            logger.error(f"[PLUGIN] Failed to create coverage dir: {e}")
            return

        coverage_file = os.path.join(coverage_dir, COVERAGE_REPORT_PATH)
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
