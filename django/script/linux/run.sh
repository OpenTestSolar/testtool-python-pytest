TOOL_ROOT=$(dirname $(dirname $(dirname $(readlink -fm $0))))
echo ${TOOL_ROOT}

if [ -f "Pipfile" ]; then
    echo "Run in pipenv..."
    python -m pipenv install
    python -m pipenv run pip install -r ${TOOL_ROOT}/requirements.txt -i https://mirrors.tencent.com/tencent_pypi/simple/
    python -m pipenv run sh -c "cd ${TOOL_ROOT}/src && python main.py"
else
    cd ${TOOL_ROOT}/src
    python main.py
fi
