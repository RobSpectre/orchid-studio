#!/bin/sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec "$project_dir/.venv/bin/orchid-studio" serve --api-port 8765 --api-only --pistil-host "$@"
