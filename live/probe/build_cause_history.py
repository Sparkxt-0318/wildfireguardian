#!/usr/bin/env python3
"""Build live/config/cause_history.json: number of fires by reported cause, per province and calendar month, 2016-2025.

Source: Korea Forest Service 국가산불정보시스템 산불통계 page (fd.forest.go.kr/ffas/pubConn/movePage/sub3.do), the call
POST /ffas/pubConn/stat/selectStatallList.do (startDate, endDate, sidoLgdngCd). Each row is one fire with the cause class
the Forest Service recorded after the fact (frfr_occrr_caus_clssc_cd / _nm). Run by hand; the live run never calls it.

    python3 live/probe/build_cause_history.py            # writes live/config/cause_history.json
"""
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

URL = "https://fd.forest.go.kr/ffas/pubConn/stat/selectStatallList.do"
PAGE = "https://fd.forest.go.kr/ffas/pubConn/movePage/sub3.do"
UA = "wfg-live-probe/0.5 (+https://github.com/Sparkxt-0318/wildfireguardian/tree/Main/live)"
YEARS = list(range(2016, 2026))
# Gyeongbuk 47; Gangwon was 42 until June 2023 and 51 after (the live service scope, live.toml [kfs] province_codes)
PROVINCES = {"gyeongbuk": ["47"], "gangwon": ["42", "51"]}
OUT = Path(__file__).resolve().parents[1] / "config/cause_history.json"


def call(start, end, code):
    last = None
    for k in range(4):
        try:
            return _call(start, end, code)
        except Exception as e:  # noqa: BLE001  (IncompleteRead and resets seen on long responses)
            last = e
            time.sleep(3 * (k + 1))
    raise last


def _call(start, end, code):
    data = urllib.parse.urlencode({"startDate": start, "endDate": end, "sidoLgdngCd": code}).encode()
    req = urllib.request.Request(URL, data=data, headers={"User-Agent": UA, "Referer": PAGE})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    return body, json.loads(body)["statAllList"]


def main():
    counts = {}      # province -> month -> cause name -> n
    codes = {}
    digest = hashlib.sha256()
    n_rows = 0
    for prov, pcodes in PROVINCES.items():
        counts[prov] = {"%02d" % m: Counter() for m in range(1, 13)}
        for y in YEARS:
            for pc in pcodes:
                body, rows = call("%d-01-01" % y, "%d-12-31" % y, pc)
                digest.update(body)
                for r in rows:
                    m = r["frfr_frng_dtm"][5:7]
                    nm = r["frfr_occrr_caus_clssc_cd_nm"] or "미분류"
                    counts[prov][m][nm] += 1
                    codes[nm] = r["frfr_occrr_caus_clssc_cd"]
                    n_rows += 1
                print(prov, y, pc, len(rows), file=sys.stderr)
                time.sleep(2)
    doc = {"schema": "wfg.live.cause_history/1",
           "what": "fires by recorded cause, per province and calendar month, 2016-2025 (history, not the current fire)",
           "source": "산림청 국가산불정보시스템 산불통계 (selectStatallList.do)", "source_page": PAGE,
           "retrieved": date.today().isoformat(), "years": [YEARS[0], YEARS[-1]], "n_fires": n_rows,
           "responses_sha256": digest.hexdigest(), "cause_codes": codes,
           "provinces": {p: {m: dict(c.most_common()) for m, c in mm.items()} for p, mm in counts.items()}}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print("wrote", OUT, n_rows, "fires")


if __name__ == "__main__":
    main()
