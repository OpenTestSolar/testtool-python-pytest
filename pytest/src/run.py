import sys

from .executor import run_testcases
from testsolar_testtool_sdk.model.param import EntryParam

if __name__ == '__main__':
    argc = len(sys.argv)
    if argc != 2:
        print("Usage: run.py <filename>")

    filename = sys.argv[1]

    with open(filename, 'r') as f:
        entry = EntryParam.parse_raw(f.read())
        run_testcases(entry)
