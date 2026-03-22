#!/usr/bin/env bash
set -euo pipefail

# Cold Calls station launcher — called by systemd
# Reads station identity from /etc/cold-call-station

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
UV="$HOME/.local/bin/uv"

# Read station number
if [[ ! -f /etc/cold-call-station ]]; then
    echo "ERROR: /etc/cold-call-station not found. Run setup.sh first." >&2
    exit 1
fi
STATION="$(cat /etc/cold-call-station)"

CONFIG="station${STATION}.yaml"
if [[ ! -f "$REPO_DIR/config/$CONFIG" ]]; then
    echo "ERROR: Config file config/$CONFIG not found." >&2
    exit 1
fi

if [[ ! -x "$UV" ]]; then
    echo "ERROR: uv not found at $UV" >&2
    exit 1
fi

cd "$REPO_DIR"

# Unbuffered stdout so logs show up in journalctl immediately
export PYTHONUNBUFFERED=1

echo "Starting Cold Calls station $STATION (config: $CONFIG)"
exec "$UV" run python -m cold_call.main --config "$CONFIG"
