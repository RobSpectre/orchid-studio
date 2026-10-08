#!/bin/bash
# Build the unmodified official release with OSC enabled; all output is ignored.
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME_DIR="$PROJECT_DIR/local/hydrogen-runtime"
BREW_PREFIX="$(brew --prefix)"
mkdir -p "$RUNTIME_DIR"
SOURCE_ARCHIVE="$RUNTIME_DIR/hydrogen-1.2.7.tar.gz"
if [ ! -f "$SOURCE_ARCHIVE" ]; then
  curl -fL https://github.com/hydrogen-music/hydrogen/archive/refs/tags/1.2.7.tar.gz -o "$SOURCE_ARCHIVE"
fi
printf '%s  %s\n' 4336299b7ebb5897d9faf2d4e705bba34a223d8e8c889b3805312559b0d27ef8 "$SOURCE_ARCHIVE" | shasum -a 256 -c -
if [ ! -d "$RUNTIME_DIR/hydrogen-1.2.7" ]; then
  tar -xzf "$SOURCE_ARCHIVE" -C "$RUNTIME_DIR"
fi
# Avoid discovering Orchid Studio's Git metadata from the nested source archive.
GIT_CEILING_DIRECTORIES="$RUNTIME_DIR" cmake \
  -S "$RUNTIME_DIR/hydrogen-1.2.7" -B "$RUNTIME_DIR/build" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DDISPLAY_VERSION_PIPELINE=1.2.7-osc-local \
  -DCMAKE_PREFIX_PATH="$BREW_PREFIX/opt/qt@5;$BREW_PREFIX/opt/libarchive;$BREW_PREFIX" \
  -DWANT_OSC=ON -DWANT_DEBUG=OFF -DWANT_CPPUNIT=OFF -DWANT_JACK=OFF \
  -DWANT_PULSEAUDIO=OFF -DWANT_LADSPA=OFF -DWANT_COREAUDIO=ON \
  -DWANT_COREMIDI=ON -DWANT_PORTAUDIO=ON -DWANT_BUNDLE=ON
cmake --build "$RUNTIME_DIR/build" --target hydrogen h2cli -j 6
"$RUNTIME_DIR/build/src/gui/hydrogen.app/Contents/MacOS/hydrogen" --help | grep -- --osc-port
