#!/usr/bin/env bash

set -exu -o pipefail

pdm run ruff check src
pdm run mypy src
pdm run pytest tests --durations=5 --cov=. --cov-fail-under=90 --cov-report term
