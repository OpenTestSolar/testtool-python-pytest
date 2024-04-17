import json
import sys
from pathlib import Path
from typing import Optional, List, BinaryIO

from dacite import from_dict
from testsolar_testtool_sdk.model.param import EntryParam

# 将src的上一级目录加入path，方便entry调用
parent = Path(__file__).parent.resolve().parent
if parent not in sys.path:
    sys.path.append(str(parent))

from .pytestx.collector import collect_testcases


def collect_testcases_from_args(
        args: List[str], workspace: Optional[str] = None, pipe_io: Optional[BinaryIO] = None
) -> None:
    if len(args) != 2:
        raise SystemExit("Usage: python load.py <entry_file>")

    filename = args[1]

    with open(filename, "r") as f:
        entry = from_dict(data_class=EntryParam, data=json.loads(f.read()))
        if workspace:
            entry.ProjectPath = workspace
        collect_testcases(entry_param=entry, pipe_io=pipe_io)


if __name__ == "__main__":
    collect_testcases_from_args(sys.argv)
