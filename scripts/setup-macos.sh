#!/bin/sh
set -eu
if [ "$(uname -s)" != Darwin ]; then
  echo 'The full Pistil AU host currently requires macOS.' >&2
  exit 1
fi
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir"
python_bin=${ORCHID_PYTHON:-python3}
"$python_bin" -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ required"'
xcrun --find swiftc >/dev/null
"$python_bin" -m venv .venv
.venv/bin/python -m pip install -e '.[midi]'
.venv/bin/orchid-studio build-host
.venv/bin/orchid-studio doctor --midi
printf '\nReady. Run scripts/start-macos.sh; see docs/PORTABILITY.md to transfer a session.\n'
