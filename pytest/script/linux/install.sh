#! /bin/bash

set -exu -o pipefail

TOOL_ROOT=$(realpath "$0" | xargs dirname | xargs dirname | xargs dirname)

echo "${TOOL_ROOT}"
cd "${TOOL_ROOT}"

curl -sSL https://pdm-project.org/install-pdm.py | python3 -

# 安装到全局的python中，无需创建虚拟环境(当前已经使用uniSDK，对运行环境的依赖很少)
"$HOME"/.local/bin/pdm install -g

# 将version信息写进文件，来判断走sdk V1还是V2逻辑
solarctl version > /tmp/solarctl_version
