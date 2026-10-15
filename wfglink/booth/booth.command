#!/usr/bin/env bash
# Double-click in Finder to start the booth in Terminal (the same as ./booth/booth.sh).
# Esc, then Esc again, in the booth screen ends it; so does closing this Terminal window.
exec bash "$(cd "$(dirname "$0")" && pwd)/booth.sh" "$@"
