#!/usr/bin/env python3
"""Parallel ranged download (the connection here is limited per connection, not in total).

    python pget.py URL OUT [--n 48] [--chunk 1000000]
Restart-safe: finished chunks are kept in OUT.parts/ and skipped.
"""
import argparse
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

UA = {"User-Agent": "research-fetch/1"}


def size_of(url):
    req = urllib.request.Request(url, headers={**UA, "Range": "bytes=0-0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        cr = r.headers.get("Content-Range")
        return int(cr.split("/")[1])


def part(url, a, b, path):
    if os.path.exists(path) and os.path.getsize(path) == b - a + 1:
        return 0
    for i in range(8):
        try:
            req = urllib.request.Request(url, headers={**UA, "Range": f"bytes={a}-{b}"})
            with urllib.request.urlopen(req, timeout=180) as r:
                d = r.read()
            if len(d) == b - a + 1:
                with open(path + ".tmp", "wb") as f:
                    f.write(d)
                os.replace(path + ".tmp", path)
                return len(d)
        except Exception:
            time.sleep(1 + i)
    raise RuntimeError(f"chunk {a}-{b} failed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("out")
    ap.add_argument("--n", type=int, default=48)
    ap.add_argument("--chunk", type=int, default=1_000_000)
    a = ap.parse_args()
    n = size_of(a.url)
    d = a.out + ".parts"
    os.makedirs(d, exist_ok=True)
    jobs = [(s, min(s + a.chunk, n) - 1) for s in range(0, n, a.chunk)]
    t0 = time.time()
    with ThreadPoolExecutor(a.n) as ex:
        futs = [ex.submit(part, a.url, s, e, os.path.join(d, f"{s:012d}")) for s, e in jobs]
        got = sum(f.result() for f in as_completed(futs))
    with open(a.out, "wb") as o:
        for s, e in jobs:
            with open(os.path.join(d, f"{s:012d}"), "rb") as f:
                o.write(f.read())
    assert os.path.getsize(a.out) == n
    for s, e in jobs:
        os.remove(os.path.join(d, f"{s:012d}"))
    os.rmdir(d)
    print(f"{a.out}: {n/1e6:.1f} MB, fetched {got/1e6:.1f} MB in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    sys.exit(main())
