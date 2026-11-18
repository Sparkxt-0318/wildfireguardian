#!/usr/bin/env bash
# Probe 2: find the data call behind fd.forest.go.kr 실시간산불정보 (sub1.do). One request per URL.
set -u
UA="wfg-live-probe/0.2 (+https://github.com/Sparkxt-0318/wildfireguardian)"
OUT=probe-out; mkdir -p "$OUT/js"
B=https://fd.forest.go.kr
date -u +"probe start %Y-%m-%dT%H:%M:%SZ"
echo "FIRMS_MAP_KEY secret: ${FIRMS_MAP_KEY:+set}${FIRMS_MAP_KEY:-NOT SET}" | sed 's/set.*/set/'
echo "FIRMS_MAP_KEY var: ${FIRMS_VAR:+set}"
curl -sS -A "$UA" -m 30 -c "$OUT/cj" -o "$OUT/sub1.html" -w 'sub1 %{http_code} %{size_download}\n' "$B/ffas/pubConn/movePage/sub1.do"
sleep 2
echo "==== sub1 inline script lines mentioning url/ajax/.do ===="
grep -n -E 'url|ajax|\.do|fetch\(|\$\.post|\$\.get' "$OUT/sub1.html" | cut -c1-400 | head -120
echo "==== sub1 script src ===="
grep -oE '<script[^>]+src="[^"]+"' "$OUT/sub1.html" | sed -E 's/.*src="([^"]+)".*/\1/' | tee "$OUT/srcs"
for s in $(grep -E '^/ffas|^/js|^/pubConn' "$OUT/srcs" | grep -v -i -E 'jquery|swiper|lib/|plugin' | head -15); do
  n=$(echo "$s" | tr '/?' '__'); curl -sS -A "$UA" -m 30 -b "$OUT/cj" -o "$OUT/js/$n" "$B$s"; sleep 1
  echo "--- $s ($(wc -c < "$OUT/js/$n") bytes)"
  grep -n -o -E '.{0,120}(url|\.do)["'"'"' ].{0,160}' "$OUT/js/$n" | grep -i -E 'fire|frfr|occu|prgrs|pubConn|ffas' | head -40
done
echo "==== sub1 table/headers ===="
grep -n -E '<th|<caption|id="[a-zA-Z]*(List|list|Tbody|tbody)' "$OUT/sub1.html" | cut -c1-300 | head -60
date -u +"probe end %Y-%m-%dT%H:%M:%SZ"
