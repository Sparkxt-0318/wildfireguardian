#!/usr/bin/env bash
# Probe 3: read sub1.js / publicMain.js to find the fire-list data call. One request per URL, 2 s apart.
set -u
UA="wfg-live-probe/0.3 (+https://github.com/Sparkxt-0318/wildfireguardian)"
OUT=probe-out; mkdir -p "$OUT"
B=https://fd.forest.go.kr
for s in /ffas/js/publicConnect/sub/sub1.js /ffas/js/publicConnect/main/publicMain.js; do
  n=$(basename "$s"); curl -sS -A "$UA" -m 30 -o "$OUT/$n" "$B$s?v=20230410_01"; sleep 2
  echo "===== $s ($(wc -c < "$OUT/$n") bytes): ajax blocks ====="
  grep -n -A 14 -E '\$\.ajax|url *:' "$OUT/$n" | cut -c1-220 | head -260
  echo "===== $s: field names (item.xxx / data.xxx) ====="
  grep -o -E '(item|data|row|obj|v|value|el|list\[i\]|result)\.[a-zA-Z_]+[A-Za-z0-9_]*' "$OUT/$n" | sort | uniq -c | sort -rn | head -80
done
