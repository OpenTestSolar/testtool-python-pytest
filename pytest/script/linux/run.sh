#! /bin/bash

set -exu -o pipefail

curl -L https://TODO/install.sh | FC_VERSION=stable sh

TOOL_ROOT=$(realpath "$0" | xargs dirname | xargs dirname | xargs dirname)
echo "${TOOL_ROOT}"

cd "${TOOL_ROOT}"/src
echo "$TESTSOLAR_WORKSPACE"

export PYTHONUNBUFFERED=1
export TESTSOLAR_TTP_LOADINSUBPROC=1 # 隔离环境

/usr/local/bin/testtools_sdk version
/usr/local/bin/testtools_sdk serve --tool pytest --file-report-mode
