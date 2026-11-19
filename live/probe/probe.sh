#!/usr/bin/env bash
# Probe 4: one call to each public KFS fire-list endpoint; print request shape and response fields.
set -u
UA="wfg-live-probe/0.4 (+https://github.com/Sparkxt-0318/wildfireguardian)"
OUT=probe-out; mkdir -p "$OUT"
B=https://fd.forest.go.kr/ffas
curl -sS -A "$UA" -m 30 -o "$OUT/sub1.js" "$B/js/publicConnect/sub/sub1.js?v=20230410_01"; sleep 2
echo "===== sub1.js 380-470 and 600-700 (params) ====="; sed -n '386,470p;600,700p' "$OUT/sub1.js" | cut -c1-200
curl -sS -A "$UA" -m 30 -o "$OUT/sub1.html" "$B/pubConn/movePage/sub1.do"; sleep 2
echo "===== sub1.html vue bindings ====="; grep -o -E '\{\{[^}]{1,80}\}\}|v-(for|if|bind)?:?[a-z]*="[^"]{1,100}"' "$OUT/sub1.html" | sort -u | head -80
echo "===== GET selectPublicFireShowList.do ====="
curl -sS -A "$UA" -m 30 -H 'Accept: application/json' -H 'X-Requested-With: XMLHttpRequest' -D "$OUT/h1" -o "$OUT/showlist.json" "$B/pubConn/selectPublicFireShowList.do"; sleep 2
head -5 "$OUT/h1"; head -c 3000 "$OUT/showlist.json"; echo
echo "===== GET selectPublicFireShowCnt.do ====="
curl -sS -A "$UA" -m 30 -H 'Accept: application/json' -H 'X-Requested-With: XMLHttpRequest' -o "$OUT/cnt.json" "$B/pubConn/selectPublicFireShowCnt.do"; sleep 2
head -c 1500 "$OUT/cnt.json"; echo
TODAY=$(TZ=Asia/Seoul date +%Y%m%d); WEEK=$(TZ=Asia/Seoul date -d '-7 day' +%Y%m%d)
echo "===== POST occur/getPublicShowFireInfoList.do (last 7 days, page 1) ====="
curl -sS -A "$UA" -m 30 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'X-Requested-With: XMLHttpRequest' \
  -d "{\"param\":{\"startDtm\":\"$WEEK\",\"endDtm\":\"$TODAY\",\"issuCode\":\"\",\"prgrsCode\":\"\",\"sido\":\"\",\"sigungu\":\"\"},\"pager\":{\"page\":1,\"size\":10}}" \
  -D "$OUT/h2" -o "$OUT/infolist.json" "$B/pubConn/occur/getPublicShowFireInfoList.do"
head -5 "$OUT/h2"; head -c 4000 "$OUT/infolist.json"; echo
