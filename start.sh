#!/bin/sh
# ORION one-command launcher - Linux / macOS
# (Windows / Windows Server: start.cmd; any OS with Python 3.10+: python start.py)
#
# Starts the whole platform: doctor -> status -> demo cycle -> web dashboard.
# Also works without the exec bit:  sh start.sh

set -e
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
    exec python3 start.py "$@"
fi

exec python start.py "$@"
