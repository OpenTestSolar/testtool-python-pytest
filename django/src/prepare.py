import os
from pathlib import Path
from typing import List

from loguru import logger


def _found_django_setting_file(directory: str, files: List[str]) -> (bool, str):
    if "wsgi.py" not in files:
        return False, ""

    dir_name = Path(directory).stem

    if "settings.py" in files:
        return True, f"{dir_name}.settings"

    if dir_name == "settings":
        # 检查settings目录下的各个py文件中是否存在 SECRET_KEY，如果有 SECRET_KEY 则认为是Django配置文件
        for py in files:
            if py.endswith(".py"):
                with open(os.path.join(directory, py), 'r') as f:
                    if "SECRET_KEY" in f.read():
                        return True, f"{dir_name}.settings.{Path(py).stem}"

    return False, ""


def init_django_settings_env(proj_root: str):
    """
    初始化django环境

    主要是找到django项目的配置文件路径

    1. 目录下必须存在wsgi.py
    2. 存在配置文件
      - 目录下必须有settings.py
      - 目录名称必须是settings，而且下面有py文件，文件中存在 SECRET_KEY 配置
    """
    for root, _, files in os.walk(top=proj_root):
        found, setting = _found_django_setting_file(root, files)
        if found:
            os.environ["DJANGO_SETTINGS_MODULE"] = setting
            break
    else:
        raise RuntimeError("Can not find django settings!")

    logger.info(f"Django settings module: {os.environ["DJANGO_SETTINGS_MODULE"]}")


def init_django_env(proj_root: str):
    init_django_settings_env(proj_root)

    from django.apps import apps
    from django.conf import settings

    apps.populate(settings.INSTALLED_APPS)  # 初始化操作，避免加载时报错
