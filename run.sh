#!/usr/bin/env bash
# Launches MegaManager. Runs setup.sh automatically first if the virtual
# environment or dependencies aren't there yet.
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

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

exec "$VENV_PY" server.py
