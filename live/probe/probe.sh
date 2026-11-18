#!/usr/bin/env bash
# One-off reachability probe for the live service's sources, run on a GitHub-hosted runner.
# Polite: one request per URL, identified User-Agent, no login.
set -u
UA="wfg-live-probe/0.1 (+https://github.com/Sparkxt-0318/wildfireguardian)"
OUT=probe-out; mkdir -p "$OUT"
hit() { # name url
  local n=$1 u=$2
  local code
  code=$(curl -sS -L -A "$UA" -m 30 -o "$OUT/$n" -w '%{http_code} %{size_download} %{url_effective}' "$u" 2>"$OUT/$n.err") || true
  echo "PROBE $n :: $code :: $(head -c 200 "$OUT/$n.err" | tr '\n' ' ')"
}
date -u +"probe start %Y-%m-%dT%H:%M:%SZ"
curl -sS -m 10 https://ifconfig.io/country_code 2>/dev/null | sed 's/^/runner country: /'
hit fd_root https://fd.forest.go.kr/
hit fd_robots https://fd.forest.go.kr/robots.txt
hit fd_ffas https://fd.forest.go.kr/ffas/
hit kfs_robots https://www.forest.go.kr/robots.txt
hit kfs_index "https://www.forest.go.kr/kfsweb/kfs/idx/Index.do"
hit kfs_root https://forest.go.kr/
hit datagokr https://www.data.go.kr/
hit firms_root https://firms.modaps.eosdis.nasa.gov/
if [ -n "${FIRMS_MAP_KEY:-}" ]; then
  echo "FIRMS_MAP_KEY: set (length ${#FIRMS_MAP_KEY})"
  curl -sS -m 30 "https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/?MAP_KEY=${FIRMS_MAP_KEY}" -o "$OUT/firms_status"; echo "PROBE firms_status :: $(head -c 300 $OUT/firms_status)"
  curl -sS -m 60 "https://firms.modaps.eosdis.nasa.gov/api/area/csv/${FIRMS_MAP_KEY}/VIIRS_NOAA20_NRT/124,33,132,39/1" -o "$OUT/firms_n20.csv"; echo "PROBE firms_n20 :: lines $(wc -l < $OUT/firms_n20.csv) :: $(head -c 300 $OUT/firms_n20.csv | tr '\n' '|')"
else
  echo "FIRMS_MAP_KEY: NOT SET"
fi
hit himawari_bucket "https://noaa-himawari9.s3.amazonaws.com/?list-type=2&prefix=AHI-L1b-FLDK/$(date -u +%Y/%m/%d)/&max-keys=5"
hit gfs_bucket "https://noaa-gfs-bdp-pds.s3.amazonaws.com/?list-type=2&prefix=gfs.$(date -u +%Y%m%d)/&delimiter=/&max-keys=5"
hit telegram https://api.telegram.org/
for v in TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID SMTP_HOST SMTP_USER SMTP_PASSWORD ALERT_EMAIL_TO; do
  if [ -n "${!v:-}" ]; then echo "SECRET $v: set"; else echo "SECRET $v: not set"; fi
done
echo "==== robots ===="; for f in fd_robots kfs_robots; do echo "--- $f"; head -c 1500 "$OUT/$f"; echo; done
echo "==== fd_root (title, scripts, .do endpoints) ===="
for f in fd_root fd_ffas kfs_index kfs_root; do
  echo "--- $f size $(wc -c < $OUT/$f)"
  grep -o '<title>[^<]*' "$OUT/$f" | head -3
  grep -oE '[A-Za-z0-9_./-]+\.do[^"'"'"' )]*' "$OUT/$f" | sort -u | head -80
  grep -n -i -E '산불|frfr|fire' "$OUT/$f" | head -40 | cut -c1-300
done
date -u +"probe end %Y-%m-%dT%H:%M:%SZ"
