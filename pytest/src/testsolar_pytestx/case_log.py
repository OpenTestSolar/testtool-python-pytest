from datetime import datetime, timedelta
from typing import List

try:
    from pytest import TestReport
except ImportError:
    from _pytest.reports import TestReport  # 兼容pytest低版本
from testsolar_testtool_sdk.model.testresult import TestCaseLog, LogLevel


def _report_failed(report: TestReport) -> bool:
    return report.failed or report.outcome == "rerun"  # type: ignore


def gen_logs(report: TestReport) -> TestCaseLog:
    logs: List[str] = []
    if report.capstdout:
        logs.append(report.capstdout)
    if report.capstderr:
        logs.append(report.capstderr)
    if report.caplog:
        logs.append(report.caplog)

    log = "\n".join(logs)

    if _report_failed(report=report):
        error_log = report.longreprtext
        if error_log:
            log += "\n\n"
            log += error_log

    return TestCaseLog(
        Time=datetime.utcnow() - timedelta(seconds=report.duration),
        Level=LogLevel.ERROR if _report_failed(report=report) else LogLevel.INFO,
        Content=log,
    )
