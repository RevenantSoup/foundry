#!/bin/sh
set -eu
exec "${FOUNDRY_TEST_PYTHON:?test interpreter required}" "$(dirname "$0")/mock-stripe-python.py" "$@"
