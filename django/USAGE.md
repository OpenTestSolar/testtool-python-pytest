# 使用文档

本文档描述如何在 TestSolar 中使用 `django` 测试工具。

## TestContainer 配置

```yaml
testTool:
  use: github.com/OpenTestSolar/testtool-python@master:django
```

我们提供`git`和`http`两种使用方式。

| **访问协议** | **访问地址**                                                                                   | **说明** |
|----------|--------------------------------------------------------------------------------------------|--------|
| `git`    | `github.com/OpenTestSolar/testtool-python@master:django`                                     |        |
| `http`   | `https://mirrors.tencent.com/repository/generic/testsolar/testtools/python@master:django` |        |

### 分支/tag切换

当临时使用到特殊版本的测试工具时，可切换到对应的分支或者tag。

格式：`github.com/OpenTestSolar/testtool-python@{BRANCH_OR_TAG}:django`

```yaml
testTool: # 测试工具相关配置
  use: github.com/OpenTestSolar/testtool-python@3.12_promote:django
```

## 基础镜像

默认使用的基础镜像为：`python:3`

如果要修改使用自己的基础镜像，可以在 `.testsolar/testcontainer.yaml` 设置 `baseImage`：

```yaml
schemaVersion: 1.0
baseImage: python:3
testTool:
  use: github.com/OpenTestSolar/testtool-python@master:django
```

## 配置参数

通过在`testTool`下的`with`字段，可以指定测试工具的相关配置参数。

```yaml
testTool:
  use: github.com/OpenTestSolar/testtool-python@master:django
  with:
    workerCount: '0'
```

> 注意：所有配置参数类型全部为**字符串**，请使用引号将值括起来，避免类型解析错误。

| **参数名称** | **默认值** | **参数含义** | **说明** |
|----------|---------|----------|--------|
| `workerCount` | 0 | 并发数 |  |



