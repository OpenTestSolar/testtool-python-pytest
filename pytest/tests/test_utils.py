

import os
import shlex
from typing import List
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from testsolar_pytestx.util import (
    get_unique_string
)

def test_get_unique_string():
    report_path = "/root/testsolar/task/155267770-a13cd9b/run"
    unique_string = get_unique_string(report_path)
    assert unique_string == "155267770-a13cd9b"

def test_get_unique_string_empty():
    report_path = ""
    unique_string = get_unique_string(report_path)
    assert unique_string == str(os.getpid())