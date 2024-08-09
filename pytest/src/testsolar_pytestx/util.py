import os
import shlex
from typing import List


def append_extra_args(args: List[str]) -> None:
    extra_args = os.environ.get("TESTSOLAR_TTP_EXTRAARGS", "")
    if extra_args:
        args.extend(shlex.split(extra_args))
