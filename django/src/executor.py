import sys
from typing import Optional, BinaryIO

from testsolar_testtool_sdk.model.param import EntryParam


def run_testcases(entry: EntryParam, pipe_io: Optional[BinaryIO] = None):
    if entry.ProjectPath not in sys.path:
        sys.path.insert(0, entry.ProjectPath)
    pass


class DjangoTestExecutor:
    def __init__(self):
        pass
