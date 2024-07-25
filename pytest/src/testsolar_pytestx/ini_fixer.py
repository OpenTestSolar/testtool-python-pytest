import configparser
import os
import shutil
from configparser import ConfigParser
from contextlib import contextmanager
from pathlib import Path

from loguru import logger


@contextmanager
def fix_pytest_ini(workdir: Path):
    ini_file = workdir / 'pytest.ini'
    backup_file = workdir / '__pytest.ini.bak'
    has_conflict_options = False

    try:
        # 如果有pytest.ini文件才处理
        if ini_file.exists():
            config = configparser.ConfigParser()
            config.read(ini_file)

            if remove_conflict(config):
                has_conflict_options = True
                shutil.copyfile(ini_file, backup_file)

                with open(ini_file, 'w') as file:
                    config.write(file)

        # 执行原有业务逻辑
        yield

    finally:
        if has_conflict_options:
            os.remove(ini_file)
            shutil.move(backup_file, ini_file)


def remove_conflict(config: ConfigParser) -> bool:
    """
    The --rootdir=path command-line option can be used to force a specific directory. Note that contrary to other command-line options,
    --rootdir cannot be used with addopts inside pytest.ini because the rootdir is used to find pytest.ini already.
    """
    if 'pytest' in config and 'addopts' in config['pytest']:
        logger.info(f"removing {config['pytest']['addopts']}")
        del config['pytest']['addopts']
        return True

    return False
