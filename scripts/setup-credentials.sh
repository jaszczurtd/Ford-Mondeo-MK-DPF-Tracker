#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

if [[ $# -gt 0 && "${1}" != --* ]]; then
    destination=$1
    shift
    exec python3 "${SCRIPT_DIR}/setup_credentials.py" \
        --destination "${destination}" "$@"
fi

exec python3 "${SCRIPT_DIR}/setup_credentials.py" "$@"
