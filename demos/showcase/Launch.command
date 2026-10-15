#!/bin/zsh
set -eu
cd "${0:A:h}"
if command -v node >/dev/null 2>&1; then
  exec node server.mjs --open
fi
for runtime in /usr/local/bin/node /opt/homebrew/bin/node; do
  if [[ -x "$runtime" ]]; then exec "$runtime" server.mjs --open; fi
done
if command -v python3 >/dev/null 2>&1; then
  exec python3 launch.py
fi
print 'This local showcase needs Node.js 20+ or Python 3. No account or internet is needed after setup.'
read '?Press Return to close.'
