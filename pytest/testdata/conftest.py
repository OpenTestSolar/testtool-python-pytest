"""
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

        # 在模块导入时就初始化，确保在 httpx 被导入之前完成 patch
        initialize_header_injection()

    except ImportError:
        # testsolar_pytestx 未安装，跳过
        pass
