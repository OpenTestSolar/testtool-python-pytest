import sys

from testsolar_testtool_sdk.model.param import EntryParam

from .collector import collect_testcases

if __name__ == '__main__':
    argc = len(sys.argv)
    if argc != 2:
        print("Usage: load.py <filename>")

    filename = sys.argv[1]

    with open(filename, 'r') as f:
        entry = EntryParam.parse_raw(f.read())
        collect_testcases(entry)
