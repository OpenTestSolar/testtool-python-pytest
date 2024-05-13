# testtool-python
Pytest Test Tool for TestSolar

## 版本发布

- 修改 [testtool.yaml](pytest/testtool.yaml) 文件中的`version`
- 修改 [pyproject.toml](pytest/pyproject.toml) 文件中的`version`
- 在`main`分支上打tag，名称跟version保持一致
- push到仓库
- 在Github页面上新建Release，选择新的tag
- 流水线会自动合并元数据并提交PR