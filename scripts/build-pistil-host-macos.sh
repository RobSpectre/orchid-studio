#!/bin/sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python_bin=${ORCHID_PYTHON:-"$project_dir/.venv/bin/python"}
PYTHONPATH="$project_dir/src${PYTHONPATH:+:$PYTHONPATH}" exec "$python_bin" -m orchid_studio build-host
