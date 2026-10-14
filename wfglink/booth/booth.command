#!/usr/bin/env bash
# Double-click in Finder to start the booth in Terminal (same as booth/booth.sh).
exec bash "$(cd "$(dirname "$0")" && pwd)/booth.sh" "$@"
