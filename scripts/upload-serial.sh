#!/usr/bin/env bash
# =============================================================================
# Serial upload helper: starts the persistent monitor if needed, then builds and
# uploads through the CMake firmware target.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CMAKE_BUILD_DIR="$PROJECT_DIR/.build/cmake"
MONITOR="$PROJECT_DIR/scripts/serial-persistent.py"

if ! pgrep -f "serial-persistent.py -m pico" >/dev/null 2>&1; then
    nohup python3 "$MONITOR" -m pico >/tmp/mondeo-dpf-persistent-monitor.log 2>&1 &
fi

"$SCRIPT_DIR/configure-cmake.sh"
cmake --build "$CMAKE_BUILD_DIR" --target firmware_upload
