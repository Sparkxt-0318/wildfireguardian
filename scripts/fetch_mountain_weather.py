#!/usr/bin/env python
"""Pull 산악기상관측망 (NIFoS mountain weather) observations for a declared window.

The network is the one the national spread system's own post-mortem said it lacked
(NIFoS, 2025-04: 「초속 27m 정도의 순간 최대 풍속이 실제로는 예상이 안 됐습니다」).
It serves 10 m wind at minute resolution and, verified 2026-09-14, HISTORY back through
the March 2025 fire -- 94 stations in 경상북도, of which 8 carry 영덕 in their name.

API: data.go.kr 15084696, https://apis.data.go.kr/1400377/mtweather/mountListSearch
Key: read from ~/.config/wildfireguardian/datago.key. NEVER pass it on the command line,
never print it, never write it into this repository.

One call returns every station in a region for ONE timestamp (no range parameter), so the
call count is the number of timestamps. 개발계정 quota is 10,000 calls/day.

    python scripts/fetch_mountain_weather.py --start 202503220000 --end 202503282300 --step 60
    python scripts/fetch_mountain_weather.py --start 202503251700 --end 202503252359 --step 1

Writes newline-delimited JSON to data/raw/mountain_weather/<region>_<start>_<end>_<step>m.jsonl
(git-ignored) plus a sidecar manifest. Re-running skips timestamps already present.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "data" / "raw" / "mountain_weather"
KEY_PATH = Path.home() / ".config" / "wildfireguardian" / "datago.key"
ENDPOINT = "https://apis.data.go.kr/1400377/mtweather/mountListSearch"
REGIONS = {"16": "경상북도", "10": "강원도", "15": "경상남도"}


def read_key() -> str:
    if not KEY_PATH.exists():
        raise SystemExit(
            f"no key at {KEY_PATH}. Apply at https://www.data.go.kr/data/15084696/openapi.do,\n"
            "then: printf '%s' '<key>' > ~/.config/wildfireguardian/datago.key && chmod 600 that file")
    return KEY_PATH.read_text(encoding="utf-8").strip()


def fetch(key: str, region: str, tm: str, rows: int = 300, tries: int = 3) -> list[dict]:
    """One timestamp, one region. Returns the item list (possibly empty)."""
    url = (f"{ENDPOINT}?serviceKey={key}&pageNo=1&numOfRows={rows}"
           f"&_type=json&localArea={region}&tm={tm}")
    last = None
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                doc = json.loads(r.read().decode("utf-8"))
            body = doc.get("response", {}).get("body", {})
            header = doc.get("response", {}).get("header", {})
            if header.get("resultCode") not in ("00", None):
                raise RuntimeError(f"API said {header.get('resultCode')}: {header.get('resultMsg')}")
            items = (body.get("items") or {}).get("item") or []
            if isinstance(items, dict):
                items = [items]
            return items
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"tm={tm} failed after {tries} tries: {last}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", required=True, help="YYYYMMDDHHMM (KST)")
    ap.add_argument("--end", required=True, help="YYYYMMDDHHMM (KST), inclusive")
    ap.add_argument("--step", type=int, default=60, help="minutes between timestamps")
    ap.add_argument("--region", default="16", choices=sorted(REGIONS))
    ap.add_argument("--sleep", type=float, default=0.3, help="seconds between calls")
    args = ap.parse_args()

    key = read_key()
    t0 = datetime.strptime(args.start, "%Y%m%d%H%M")
    t1 = datetime.strptime(args.end, "%Y%m%d%H%M")
    stamps = []
    t = t0
    while t <= t1:
        stamps.append(t.strftime("%Y%m%d%H%M"))
        t += timedelta(minutes=args.step)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"mtw_{args.region}_{args.start}_{args.end}_{args.step}m.jsonl"
    done = set()
    if out.exists():
        for line in out.open(encoding="utf-8"):
            try:
                done.add(json.loads(line)["_tm_requested"])
            except Exception:  # noqa: BLE001,S110
                pass
    todo = [s for s in stamps if s not in done]
    print(f"{REGIONS[args.region]}: {len(stamps)} timestamps, {len(done)} already held, "
          f"{len(todo)} to fetch, step {args.step} min", flush=True)

    n_rows = n_empty = 0
    with out.open("a", encoding="utf-8") as f:
        for i, tm in enumerate(todo, 1):
            items = fetch(key, args.region, tm)
            if not items:
                n_empty += 1
            for it in items:
                it["_tm_requested"] = tm
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
                n_rows += 1
            if i % 50 == 0 or i == len(todo):
                print(f"  [{i}/{len(todo)}] {tm} rows={n_rows} empty_stamps={n_empty}", flush=True)
            time.sleep(args.sleep)

    man = out.with_suffix(".manifest.json")
    man.write_text(json.dumps({
        "source": "산림청 국립산림과학원_산악기상정보, data.go.kr 15084696",
        "endpoint": ENDPOINT,
        "region_code": args.region, "region": REGIONS[args.region],
        "window_kst": [args.start, args.end], "step_min": args.step,
        "timestamps_requested": len(stamps), "rows_written_this_run": n_rows,
        "empty_timestamps_this_run": n_empty,
        "fetched_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fields": "obsid, obsname, localarea, tm, tm10m/tm2m (기온), hm10m/hm2m (습도), "
                  "wd10m/wd2m + *str (풍향), ws10m/ws2m (풍속), pa (기압), ts (지면온도), "
                  "rn/cprn (강수)",
        "note": "10 m wind is the height fire-spread models want. '-' means the station "
                "reported nothing at that minute; it is kept, not dropped.",
        "licence": "공공데이터포털 제공, 이용허락범위 확인 필요; raw stays git-ignored.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(REPO)} (+ manifest)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
