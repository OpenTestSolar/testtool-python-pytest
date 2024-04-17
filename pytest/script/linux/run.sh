#! /bin/bash

set -exu -o pipefail

# 暂时仅支持amd64，后续再支持arm64
curl -Lk https://github.com/OpenTestSolar/testtools-uni-sdk/releases/download/0.0.1/testtools_sdk.amd64 -o /usr/local/bin/testtools_sdk
chmod +x /usr/local/bin/testtools_sdk

TOOL_ROOT=$(realpath "$0" | xargs dirname | xargs dirname | xargs dirname)
echo "${TOOL_ROOT}"
echo "$TESTSOLAR_WORKSPACE"

export PYTHONUNBUFFERED=1
export TESTSOLAR_TTP_LOADINSUBPROC=1 # 隔离环境

/usr/local/bin/testtools_sdk version
/usr/local/bin/testtools_sdk serve --tool pytest