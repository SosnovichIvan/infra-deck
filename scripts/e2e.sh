#!/bin/sh
set -eu
mkdir -p .runtime
exec .venv/bin/python scripts/run_e2e.py "$@"
