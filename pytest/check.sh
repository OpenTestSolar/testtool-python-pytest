#!/usr/bin/env bash

set -exu -o pipefail

if [[ -z "${GITHUB_ACTIONS+x}" ]]; then
  echo "GITHUB_ACTIONS environment variable is not set.Use local mode."
  uv sync --all-extras --dev
  uv run ruff format src
  uv run ruff format tests
  uv run ruff check src
  uv run ruff check tests
  uv run mypy src/testsolar_pytestx --strict
  uv run mypy src/load.py src/run.py --strict
  uv run pytest tests --durations=5 --cov=. --cov-fail-under=90 --cov-report term
  uv export --no-hashes --no-dev --locked >requirements.txt
else
  echo "GITHUB_ACTIONS environment variable is set.Use CI mode."
  uv sync --all-extras --dev

  uv export --no-hashes --no-dev --locked >requirements.txt
  # 检查是否有未提交的变化
  if ! git diff-index HEAD --; then
    echo "Check uncommit changes.Please run bash check.sh and commit again.Changed files:"
    git diff --name-only
    exit 1
  fi

  uv run ruff check src
  uv run ruff check tests
  uv run mypy src/testsolar_pytestx --strict
  uv run mypy src/load.py src/run.py --strict
  uv run pytest tests --durations=5 --cov=. --cov-fail-under=90 --cov-report term
fi
