import os

from testsolar_testtool_sdk.model.testresult import TestCaseStep


def check_allure_enabled() -> bool:
    enable_allure = os.environ.get("TESTSOLAR_TTP_ENABLEALLURE", "")
    return enable_allure == "true"


def parse_allure_step_info(steps: dict, index: int | None = None) -> list[TestCaseStep]:
    case_steps = []
    if not index:
        index = 0
    if isinstance(steps, list):
        for step in steps:
            index += 1
            result = step["status"]
            if result == "passed":
                result = True
            else:
                result = False
            log = ""
            if "parameters" in step.keys():
                for param in step["parameters"]:
                    for key in param:
                        log += "%-30s%-20s\n" % (
                            "key: {}".format(key),
                            "value: {}".format(param[key]),
                        )
            if "statusDetails" in step.keys():
                if "message" and "trace" in step["statusDetails"]:
                    log += (
                            step["statusDetails"]["message"]
                            + step["statusDetails"]["trace"]
                    )
            step_info = {
                "title": "{}： {}".format(".".join(list(str(index))), step["name"]),
                "logs": gen_allure_log(log, result, step["start"]),
                "startTime": format_allure_time(step["start"]),
                "endTime": format_allure_time(step["stop"]),
                "resultType": "succeed" if result else "failed",
            }
            case_steps.append(step_info)
            if "steps" in step:
                case_steps.extend(parse_allure_step_info(step["steps"], index * 10))
    return case_steps


def gen_allure_log(content, result, log_time):
    logs = []
    if content:
        logs.append(
            {
                "content": content,
                "level": 2 if result else 4,
                "time": format_allure_time(log_time),
            }
        )
    return logs


def format_allure_time(result_time):
    return result_time / 1000
