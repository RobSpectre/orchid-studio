#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME_DIR="$PROJECT_DIR/local/hydrogen-runtime"
SOURCE_DIR="$RUNTIME_DIR/hydrogen-1.2.7"
HYDROGEN_BINARY="$RUNTIME_DIR/build/src/gui/hydrogen.app/Contents/MacOS/hydrogen"
SONG_PATH="${1:-$PROJECT_DIR/local/first-drums.h2song}"
if [ ! -x "$HYDROGEN_BINARY" ]; then
  echo 'Build Hydrogen first; see docs/HYDROGEN.md.' >&2
  exit 1
fi
if [ ! -f "$SONG_PATH" ]; then
  echo 'Create the drum song first; see docs/HYDROGEN.md.' >&2
  exit 1
fi
mkdir -p "$RUNTIME_DIR/user-data"
if [ ! -f "$RUNTIME_DIR/hydrogen.conf" ]; then
  python3 - "$SOURCE_DIR/data/hydrogen.default.conf" "$RUNTIME_DIR/hydrogen.conf" <<'PY'
import sys
import xml.etree.ElementTree as ET
tree = ET.parse(sys.argv[1])
values = {'oscEnabled': 'true', 'oscFeedbackEnabled': 'true', 'oscServerPort': '9000',
          'audio_driver': 'PortAudio'}
for node in tree.iter():
    if node.tag in values:
        node.text = values[node.tag]
tree.write(sys.argv[2], encoding='utf-8', xml_declaration=True)
PY
fi
exec "$HYDROGEN_BINARY" -d PortAudio -O 9000 -P "$SOURCE_DIR/data" \
  --config "$RUNTIME_DIR/hydrogen.conf" --user-data "$RUNTIME_DIR/user-data" \
  -L "$RUNTIME_DIR/runtime.log" -V Info -s "$SONG_PATH"
