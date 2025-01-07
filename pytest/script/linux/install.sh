#! /bin/bash

set -exu -o pipefail

TOOL_ROOT=$(realpath "$0" | xargs dirname | xargs dirname | xargs dirname)

echo "${TOOL_ROOT}"
cd "${TOOL_ROOT}"

# 安装到全局的python中，无需创建虚拟环境(当前已经使用uniSDK，对运行环境的依赖很少)
pip3 install -r requirements.txt

# 使用COS上的安装脚本安装uniSDK，后续修改为testsolar的独立域名
curl -Lk https://testsolar-1321258242.cos.ap-guangzhou.myqcloud.com/cli/testtools_sdk-install/stable/install.sh | bash
