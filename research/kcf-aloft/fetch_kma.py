#!/usr/bin/env python3
"""KMA ASOS hourly gusts for G-obs (PROTOCOL.md amendment 2). No value is interpreted here.

    KMA_KEY_FILE=/path/to/key python3 fetch_kma.py --out WORK/kma_hours.jsonl --fire derived/fire_hours.csv.gz
    KMA_KEY_FILE=/path/to/key python3 fetch_kma.py --out WORK/kma_hours.jsonl --seasons 2025 2024 2023 2022

apihub.kma.go.kr `kma_sfctm2.php?tm=YYYYMMDDHH00&stn=0`, one call per KST hour, all ASOS stations (EUC-KR).
Appends one JSON line per hour: {"tm": stamp, "stn": [ids with a row], "gust": [[id, GST_WS, GST_TM], ...]} with a gust
entry only where GST_WS is a number >= 0. Hours already in the file are skipped. The key is read from the file named
by KMA_KEY_FILE (or the variable KMA_API_KEY); it is never written, printed or logged, and no URL is logged.
"""
import argparse
import json
import os
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

URL = "https://apihub.kma.go.kr/api/typ01/url/kma_sfctm2.php?tm={tm}&stn=0&help=0&authKey="


def key():
    f = os.environ.get("KMA_KEY_FILE")
    k = open(f).read().strip() if f else os.environ.get("KMA_API_KEY", "")
    if not k:
        sys.exit("no KMA key: set KMA_KEY_FILE or KMA_API_KEY")
    return k


def one(tm, k, tries=8):
    for i in range(tries):
        try:
            txt = urllib.request.urlopen(URL.format(tm=tm) + k, timeout=45).read().decode("euc-kr", "replace")
            rows = [l.split() for l in txt.splitlines() if l[:1].isdigit()]
            rows = [r for r in rows if len(r) > 6 and r[0] == tm]
            if rows:
                gust = [[int(r[1]), float(r[5]), r[6]] for r in rows if float(r[5]) >= 0]
                return dict(tm=tm, stn=[int(r[1]) for r in rows], gust=gust, tries=i + 1,
                            fetched_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        except Exception:
            pass
        time.sleep(1 + i)
    return dict(tm=tm, failed=True, tries=tries, fetched_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--fire")
    ap.add_argument("--seasons", nargs="*", type=int, default=[])
    ap.add_argument("--threads", type=int, default=6)
    a = ap.parse_args()
    want = []
    if a.fire:
        f = pd.read_csv(a.fire, usecols=["timeline", "t_utc"])
        t = pd.to_datetime(f[f.timeline == "primary"].t_utc) + pd.Timedelta(hours=9)
        want += sorted(set(t.dt.strftime("%Y%m%d%H00")))
    for y in a.seasons:                      # stamps 00:00 .. 23:00 KST of every season day
        want += [x.strftime("%Y%m%d%H00") for x in pd.date_range(f"{y}-02-01 00:00", f"{y}-05-15 23:00", freq="1h")]
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out):
            r = json.loads(l)
            if not r.get("failed"):
                done.add(r["tm"])
    todo = [t for t in dict.fromkeys(want) if t not in done]
    print(f"{len(want)} hours wanted, {len(todo)} to fetch", flush=True)
    k, lock, n = key(), threading.Lock(), [0, 0]
    with open(a.out, "a") as fh, ThreadPoolExecutor(a.threads) as ex:
        for r in ex.map(lambda t: one(t, k), todo):
            with lock:
                fh.write(json.dumps(r) + "\n")
                fh.flush()
                n[0] += 1
                n[1] += bool(r.get("failed"))
                if n[0] % 50 == 0:
                    print(n[0], "done,", n[1], "failed", r["tm"], flush=True)
    print("finished:", n[0], "fetched,", n[1], "failed", flush=True)


if __name__ == "__main__":
    main()
