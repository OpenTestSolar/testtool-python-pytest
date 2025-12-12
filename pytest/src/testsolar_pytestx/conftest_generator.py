"""
conftest.py 生成器模块

用于在测试目录中生成 conftest.py 文件，确保 xdist worker 进程也能正确初始化 header injection。

当使用 pytest.main(plugins=[PytestExecutor]) 方式运行测试时，
xdist worker 进程不会继承主进程的 plugins 参数，
因此需要通过 conftest.py 来确保每个 worker 进程都能执行初始化。
"""

from pathlib import Path
from typing import Optional

from loguru import logger

# conftest.py 的内容模板
# 注意：这个模板会被写入到测试项目目录中
CONFTEST_TEMPLATE = '''"""
Auto-generated conftest.py for testsolar header injection support.
This file ensures that HTTP request header injection works correctly
even when using pytest-xdist for parallel test execution.

DO NOT MODIFY THIS FILE - it will be regenerated on each test run.
"""
import os

# 仅在启用 API 收集时才初始化
if os.environ.get("ENABLE_API_COLLECTING") == "1":
    try:
        from testsolar_pytestx.header_injection import (
            initialize_header_injection,
            set_current_test_nodeid,
        )
        from testsolar_pytestx.converter import normalize_testcase_name

        # 在模块导入时就初始化，确保在 httpx 被导入之前完成 patch
        initialize_header_injection()

        def pytest_runtest_setup(item):
            """在每个测试开始前设置 nodeid"""
            testcase_name = normalize_testcase_name(item.nodeid)
            testcase_class_name = testcase_name.split("?", 1)[-1]
            set_current_test_nodeid(testcase_class_name)

        def pytest_runtest_teardown(item):
            """在每个测试结束后清除 nodeid"""
            set_current_test_nodeid(None)

    except ImportError:
        # testsolar_pytestx 未安装，跳过
        pass
'''

# 用于标识自动生成的 conftest.py 的标记
CONFTEST_MARKER = "Auto-generated conftest.py for testsolar header injection support."


def _is_testsolar_conftest(conftest_path: Path) -> bool:
    """检查 conftest.py 是否是由 testsolar 生成的"""
    if not conftest_path.exists():
        return False

    try:
        content = conftest_path.read_text(encoding="utf-8")
        return CONFTEST_MARKER in content
    except Exception:
        return False


def _backup_existing_conftest(conftest_path: Path) -> Optional[Path]:
    """备份已存在的 conftest.py（如果不是 testsolar 生成的）"""
    if not conftest_path.exists():
        return None

    if _is_testsolar_conftest(conftest_path):
        # 是 testsolar 生成的，不需要备份
        return None

    # 创建备份
    backup_path = conftest_path.with_suffix(".py.testsolar_backup")
    try:
        import shutil

        shutil.copy2(conftest_path, backup_path)
        logger.info(f"Backed up existing conftest.py to {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to backup conftest.py: {e}")
        return None


def _merge_conftest_content(existing_content: str, template_content: str) -> str:
    """合并已有的 conftest.py 内容和模板内容"""
    # 如果已有内容中已经包含了我们的标记，说明已经合并过了
    if CONFTEST_MARKER in existing_content:
        return existing_content

    # 将模板内容添加到已有内容的开头
    merged = (
        template_content + "\n\n# === Original conftest.py content below ===\n\n" + existing_content
    )
    return merged


def generate_conftest_for_header_injection(project_path: str) -> Optional[str]:
    """
    在项目目录中生成支持 header injection 的 conftest.py

    Args:
        project_path: 项目根目录路径

    Returns:
        生成的 conftest.py 路径，如果生成失败则返回 None
    """
    conftest_path = Path(project_path) / "conftest.py"

    try:
        if conftest_path.exists():
            if _is_testsolar_conftest(conftest_path):
                # 已经是 testsolar 生成的，直接覆盖更新
                logger.debug(f"Updating existing testsolar conftest.py at {conftest_path}")
                conftest_path.write_text(CONFTEST_TEMPLATE, encoding="utf-8")
            else:
                # 已有用户的 conftest.py，需要合并
                logger.info(f"Found existing conftest.py at {conftest_path}, merging content")
                existing_content = conftest_path.read_text(encoding="utf-8")
                merged_content = _merge_conftest_content(existing_content, CONFTEST_TEMPLATE)

                # 备份原文件
                _backup_existing_conftest(conftest_path)

                # 写入合并后的内容
                conftest_path.write_text(merged_content, encoding="utf-8")
                logger.info("Merged testsolar header injection into existing conftest.py")
        else:
            # 不存在 conftest.py，直接创建
            logger.info(f"Creating conftest.py at {conftest_path}")
            conftest_path.write_text(CONFTEST_TEMPLATE, encoding="utf-8")

        return str(conftest_path)

    except Exception as e:
        logger.error(f"Failed to generate conftest.py: {e}")
        return None


def cleanup_generated_conftest(project_path: str) -> None:
    """
    清理生成的 conftest.py

    如果 conftest.py 是纯粹由 testsolar 生成的，则删除它。
    如果是合并的，则恢复原始内容。

    Args:
        project_path: 项目根目录路径
    """
    conftest_path = Path(project_path) / "conftest.py"
    backup_path = conftest_path.with_suffix(".py.testsolar_backup")

    try:
        if backup_path.exists():
            # 存在备份，恢复原始文件
            import shutil

            shutil.move(str(backup_path), str(conftest_path))
            logger.info("Restored original conftest.py from backup")
        elif conftest_path.exists() and _is_testsolar_conftest(conftest_path):
            # 是纯粹由 testsolar 生成的，检查是否只有模板内容
            content = conftest_path.read_text(encoding="utf-8")
            if "Original conftest.py content below" not in content:
                # 没有合并用户内容，可以安全删除
                conftest_path.unlink()
                logger.info("Removed generated conftest.py")
    except Exception as e:
        logger.warning(f"Failed to cleanup conftest.py: {e}")
