#! /bin/bash

set -exu -o pipefail

TOOL_ROOT=$(realpath "$0" | xargs dirname | xargs dirname | xargs dirname)

echo "${TOOL_ROOT}"
cd "${TOOL_ROOT}"

python3 -m pip install virtualenv
python3 -m virtualenv .env3

.env3/bin/python3 -m pip install testsolar_testool_sdk

which python
python3 -m pip install -r "${TOOL_ROOT}"/requirements.txt

# 将version信息写进文件，来判断走sdk V1还是V2逻辑
solarctl version > /tmp/solarctl_version
