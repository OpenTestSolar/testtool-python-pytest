import configparser
import os
import shutil
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from loguru import logger


@contextmanager
def fix_pytest_ini(workdir: Path) -> Generator[None, None, None]:
    ini_file = workdir / "pytest.ini"
    backup_file = workdir / "__pytest.ini.bak"
    has_conflict_options = False

    try:
        # 如果有pytest.ini文件才处理
        if ini_file.exists():
            has_conflict_options = remove_conflict(ini_file, backup_file)

        # 执行原有业务逻辑
        yield

    finally:
        if has_conflict_options:
            os.remove(ini_file)
            shutil.move(str(backup_file), str(ini_file))


def remove_conflict(ini_file: Path, backup_file: Path) -> bool:
    """
    去除冲突选项，参考pytest文档：

    https://docs.pytest.org/en/latest/reference/customize.html#initialization-determining-rootdir-and-configfile

    The --rootdir=path command-line option can be used to force a specific directory. Note that contrary to other command-line options,
    --rootdir cannot be used with addopts inside pytest.ini because the rootdir is used to find pytest.ini already.
    """
    try:
        config = configparser.ConfigParser()
        config.read(ini_file)

        if "pytest" in config:
            if "addopts" in config["pytest"]:
                logger.info("removing addopts in pytest.ini")
                del config["pytest"]["addopts"]
            # 如果用户重设置了错误的testpaths，也需要去除
            if "testpaths" in config["pytest"]:
                logger.info("removing testpaths in pytest.ini")
                del config["pytest"]["testpaths"]

            shutil.copyfile(str(ini_file), str(backup_file))

            with open(ini_file, "w") as file:
                config.write(file)

            return True
    except Exception as e:
        logger.warning(e)
        logger.warning(traceback.format_exc())

    return False
