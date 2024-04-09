import os
import sys
from typing import BinaryIO

import pytest
from loguru import logger
from testsolar_testtool_sdk.model.param import EntryParam

from .converter import selector_to_pytest
from .pytestx import PytestTestSolarPlugin
from .allure import check_allure_enabled


def run_testcases(entry: EntryParam, pipe_io: BinaryIO = None):
    if entry.project_path not in sys.path:
        sys.path.insert(0, entry.project_path)
    args = [
        f"--rootdir={entry.project_path}",
        "--continue-on-collection-errors",
    ]
    args.extend([os.path.join(entry.project_path, selector_to_pytest(it)) for it in entry.test_selectors])

    allure_dir = ""
    if check_allure_enabled():
        allure_dir = os.path.join(entry.project_path, "allure_results")
        args.append("--alluredir={}".format(allure_dir))

        if not os.path.isdir(allure_dir):
            os.mkdir(allure_dir)
        else:
            for f_name in os.listdir(allure_dir):
                os.remove(os.path.join(allure_dir, f_name))
    extra_args = os.environ.get("TESTSOLAR_TTP_EXTRAARGS", "")
    if extra_args:
        args.extend(extra_args.split())
    timeout = int(os.environ.get("TESTSOLAR_TTP_TIMEOUT", "0"))
    if timeout > 0:
        args.append("--timeout=%d" % timeout)
    logger.info(args)

    my_plugin = PytestTestSolarPlugin(
        allure_path=allure_dir,
    )
    pytest.main(args, plugins=[my_plugin])
    logger.info("pytest process exit")
