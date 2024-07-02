#!/usr/bin/env bash

set -exu -o pipefail

pdm run ruff format src
pdm run ruff format tests
pdm run ruff check src
pdm run ruff check tests
pdm run mypy src
pdm run pytest tests --durations=5 --cov=. --cov-fail-under=90 --cov-report term
