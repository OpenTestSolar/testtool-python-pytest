# Pytest test tool for TestSolar

支持在TestSolar上使用[PyTest](https://docs.pytest.org/en/)测试工具，使用demo可参考仓库: [pytest-demo](https://github.com/OpenTestSolar/testtool-pytest-demo)。 

注意：依赖Python>=3.7

## 如何使用

### 直接在TestSolar中作为测试工具使用

```yaml
schemaVersion: 1.0
testTool:
  use: github.com/OpenTestSolar/testtool-python@main:pytest
```

### 作为python包引用

```shell
pip install testsolar-pytestx 
```
