import json
import sys

from dacite import from_dict
from testsolar_testtool_sdk.model.param import EntryParam

from .collector import collect_testcases

if __name__ == '__main__':
    argc = len(sys.argv)
    if argc != 2:
        print("Usage: load.py <filename>")

    filename = sys.argv[1]

    with open(filename, 'r') as f:
        entry = from_dict(data_class=EntryParam, data=json.loads(f.read()))
        collect_testcases(entry)
