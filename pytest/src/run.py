import json
import sys
from pathlib import Path
from typing import Optional, List, BinaryIO

from dacite import from_dict
from testsolar_testtool_sdk.model.param import EntryParam

# 将pytestx加入path
parent = str(Path(__file__).parent.resolve())
if parent not in sys.path:
    sys.path.append(parent)

from testsolar_pytestx.executor import run_testcases  # type: ignore[import] # noqa: E402
from testsolar_pytestx.ini_fixer import fix_pytest_ini  # type: ignore[import] # noqa: E402


def run_testcases_from_args(
    args: List[str], workspace: Optional[str] = None, pipe_io: Optional[BinaryIO] = None
) -> None:
    if len(args) != 2:
        raise SystemExit("Usage: python run.py <entry_file>")

    filename = args[1]

    with open(filename, "r") as f:
        entry = from_dict(data_class=EntryParam, data=json.loads(f.read()))
        if workspace:
            entry.ProjectPath = workspace

        # 检查用户的pytest.ini中是否有冲突配置，如果有冲突配置覆盖
        with fix_pytest_ini(Path(entry.ProjectPath)):
            run_testcases(entry=entry, pipe_io=pipe_io)


if __name__ == "__main__":
    run_testcases_from_args(sys.argv)
