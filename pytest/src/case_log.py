import time


def gen_logs(report):
    logs = []
    if report.capstdout:
        logs.append(report.capstdout)
    if report.capstderr:
        logs.append(report.capstderr)
    if report.caplog:
        logs.append(report.caplog)

    log = "\n".join(logs)
    error_log = ""
    if report.outcome == "failed":
        error_log = report.longreprtext
        if error_log:
            if log:
                log += "\n\n"
            log += error_log
    logs = []
    if log:
        logs.append(
            {
                "content": log,
                "level": 4 if error_log else 2,
                "time": time.time() - report.duration,
            }
        )
    return logs




