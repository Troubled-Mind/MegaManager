#!/usr/bin/env bash
# Launches MegaManager. Runs setup.sh automatically first if the virtual
# environment or dependencies aren't there yet, then opens your browser to it.
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

URL="http://localhost:6342"

VENV_PY=".venv/bin/python3"
[ -x "$VENV_PY" ] || VENV_PY=".venv/bin/python"

needs_setup() {
    [ -x "$VENV_PY" ] || return 0
    "$VENV_PY" -c "import sqlalchemy" >/dev/null 2>&1 || return 0
    command -v mega-cmd >/dev/null 2>&1 || command -v mega-login >/dev/null 2>&1 || return 0
    command -v rclone >/dev/null 2>&1 || return 0
    return 1
}

if needs_setup; then
    echo "==> First run (or missing dependencies) detected, running setup.sh first..."
    ./setup.sh || echo "WARNING setup.sh reported problems - trying to start anyway."
    VENV_PY=".venv/bin/python3"
    [ -x "$VENV_PY" ] || VENV_PY=".venv/bin/python"
fi

if [ ! -x "$VENV_PY" ]; then
    echo "ERROR Could not find a working Python virtual environment. Run ./setup.sh manually to see what failed."
    exit 1
fi

"$VENV_PY" server.py &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null' EXIT INT TERM

# Account quota syncing and other startup work happens in the background once
# the server is up - it doesn't block the server from accepting connections,
# so we don't need to wait for it, just for the HTTP port itself to respond.
echo "==> Waiting for MegaManager to come up..."
READY=false
for _ in $(seq 1 30); do
    if command -v curl >/dev/null 2>&1; then
        curl -sf "$URL/api/version" >/dev/null 2>&1 && { READY=true; break; }
    else
        (exec 3<>/dev/tcp/127.0.0.1/6342) 2>/dev/null && { exec 3<&- 3>&-; READY=true; break; }
    fi
    sleep 1
done

if [ "$READY" = true ]; then
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$URL" >/dev/null 2>&1 &
    elif command -v open >/dev/null 2>&1; then
        open "$URL" >/dev/null 2>&1 &
    else
        echo "==> Open $URL in your browser to get started."
    fi
else
    echo "WARNING MegaManager didn't respond within 30s - open $URL manually once it's ready."
fi

wait "$SERVER_PID"
