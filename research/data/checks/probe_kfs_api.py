#!/usr/bin/env python
"""Probe the KFS wildfire statistics Open API (registry id kfs_fire_stats_api)
for how far back its record reaches.

    DATA_GO_KR_KEY=<key> /home/user/wildfireguardian/.auto/venv/bin/python \
        research/data/checks/probe_kfs_api.py

Blocked as of this program's start on WJ-001: DATA_GO_KR_KEY is unset in this
sandbox. This script is written so that the probe is a single command the
moment the key lands; it does nothing else until then.

Reads the key from the DATA_GO_KR_KEY environment variable ONLY. It never
accepts the key as a command-line argument (a CLI argument is visible in
process listings and shell history) and it never prints the key, in any log
line, error message or exception. If the key is unset, it prints a clear
message and exits non-zero without attempting any request.

What it does once a key is available
-------------------------------------
Queries https://apis.data.go.kr/1400000/forestStusService/getfirestatsservice
(the endpoint recorded in research/data/REGISTRY.yaml for kfs_fire_stats_api)
for a small sample year at each end of the range the brief asks about, 1991
and 2001, plus the earliest year the committed CSV shows (2022, see
kfs_fire_stats_csv) as a sanity check that the API and the CSV are describing
the same underlying record. It does not download or write a bulk archive; it
is a probe, not an ingest script.

Rate limit: this script issues at most one request per second, matching the
scope rule for Korean government portals.
"""

from __future__ import annotations

import os
import sys
import time

ENDPOINT = "https://apis.data.go.kr/1400000/forestStusService/getfirestatsservice"
KEY_ENV = "DATA_GO_KR_KEY"

#: Years to probe. 1991 and 2001 bracket the range the program brief asks
#: about ("does the record reach back before 1991 or before 2001"); 2022 is
#: the earliest year the committed CSV (kfs_fire_stats_csv) shows, used only
#: as a sanity check that the API and the CSV describe the same record.
PROBE_YEARS = (1991, 2001, 2022)

#: At most one request per second to a Korean government portal.
REQUEST_INTERVAL_S = 1.0


def get_key() -> str:
    key = os.environ.get(KEY_ENV)
    if not key:
        print(
            f"STOP-GATE: {KEY_ENV} is not set in this environment.\n"
            f"This is human gate WJ-001. Nothing was requested; no network "
            f"call was made. Set {KEY_ENV} and re-run this exact command.",
            file=sys.stderr,
        )
        sys.exit(2)
    return key


def probe_year(year: int, key: str) -> dict:
    """One request for one year. Returns a small, loggable summary dict.

    The key is passed only inside the request itself (as the serviceKey query
    parameter, which is how this API is documented to authenticate) and is
    never included in anything this function returns, logs or raises.
    """
    import urllib.parse
    import urllib.request

    params = {
        "serviceKey": key,
        "searchStDt": f"{year}0101",
        "searchEdDt": f"{year}1231",
        "numOfRows": "1",
        "pageNo": "1",
    }
    url = f"{ENDPOINT}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            status = resp.status
            body = resp.read(2000)
    except Exception as exc:  # noqa: BLE001
        # Reraise-safe: strip the key from any URL that might be embedded in
        # the exception's string representation before it is ever printed.
        msg = str(exc).replace(key, "***REDACTED***")
        return {"year": year, "ok": False, "error": msg}

    text = body.decode("utf-8", errors="replace")
    return {"year": year, "ok": status == 200, "http_status": status,
             "body_preview": text[:300]}


def main() -> int:
    key = get_key()

    print(f"Probing {ENDPOINT} for years {PROBE_YEARS}")
    print("(the key itself is never printed)\n")

    results = []
    for i, year in enumerate(PROBE_YEARS):
        if i:
            time.sleep(REQUEST_INTERVAL_S)
        r = probe_year(year, key)
        results.append(r)
        if r["ok"]:
            print(f"  {year}: HTTP {r['http_status']}  body preview: "
                  f"{r['body_preview']!r}")
        else:
            detail = r.get("error") or f"HTTP {r.get('http_status')}"
            print(f"  {year}: FAILED  {detail}")

    n_ok = sum(1 for r in results if r["ok"])
    print(f"\n{n_ok}/{len(results)} probe years returned HTTP 200.")
    print("This script does not interpret the response body as reachable or "
          "not-reachable data; read the body preview above and, if 1991 or "
          "2001 returns real rows, update research/data/REGISTRY.yaml's "
          "kfs_fire_stats_api temporal_coverage from what was actually "
          "returned, not from this script's exit code.")
    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
