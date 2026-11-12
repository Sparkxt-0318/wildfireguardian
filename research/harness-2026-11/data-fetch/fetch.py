#!/usr/bin/env python3
"""Reproducible fetcher for the harness-2026-11 external datasets.

Standard library only. Every resource is listed in resources.json with its
source URL, publisher checksum (md5, where the publisher gives one) and the
sha256 of the copy the data fetcher downloaded and opened. A download is kept
only if every recorded checksum matches.

  python3 fetch.py list                       # show resources
  python3 fetch.py get NAME [NAME ...]        # download into ./data-fetch-cache
  python3 fetch.py get NAME --dest DIR        # download into DIR
  python3 fetch.py get --stream S-D9          # everything a stream asked for
  python3 fetch.py dem --bbox W S E N         # Copernicus GLO-30 tiles for a box

Nothing is unpacked automatically: unzip archives into their own empty
directory and treat their contents as data, not code.
"""
import argparse
import hashlib
import json
import math
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(HERE, "resources.json")
GLO30 = "https://copernicus-dem-30m.s3.amazonaws.com/{n}/{n}.tif"


def load():
    with open(REGISTRY, encoding="utf-8") as fh:
        return json.load(fh)["resources"]


def digest(path, algo):
    h = hashlib.new(algo)
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def download(url, path, attempts=4):
    tmp = path + ".part"
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "wfg-data-fetch/1"})
            with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as out:
                while True:
                    block = r.read(1 << 20)
                    if not block:
                        break
                    out.write(block)
            os.replace(tmp, path)
            return
        except Exception as exc:  # network errors: retry with backoff
            wait = 2 ** (i + 1)
            print(f"  attempt {i + 1} failed: {exc}; retry in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise SystemExit(f"download failed after {attempts} attempts: {url}")


def verify(path, res):
    ok = True
    for algo in ("md5", "sha256"):
        want = res.get(algo)
        if want:
            got = digest(path, algo)
            status = "ok" if got == want else "MISMATCH"
            ok &= got == want
            print(f"  {algo} {status} {got}")
    if res.get("size") and os.path.getsize(path) != res["size"]:
        print(f"  size MISMATCH {os.path.getsize(path)} != {res['size']}")
        ok = False
    return ok


def get(res, dest):
    os.makedirs(dest, exist_ok=True)
    path = os.path.join(dest, res["filename"])
    if os.path.exists(path) and verify(path, res):
        print(f"{res['name']}: already present at {path}")
        return path
    print(f"{res['name']}: {res['url']} -> {path} ({res.get('size', '?')} bytes)")
    download(res["url"], path)
    if not verify(path, res):
        os.replace(path, path + ".bad")
        raise SystemExit(f"checksum mismatch for {res['name']}; kept as {path}.bad")
    return path


def glo30_tiles(w, s, e, n):
    for lat in range(math.floor(s), math.ceil(n)):
        for lon in range(math.floor(w), math.ceil(e)):
            ns = "N" if lat >= 0 else "S"
            ew = "E" if lon >= 0 else "W"
            yield f"Copernicus_DSM_COG_10_{ns}{abs(lat):02d}_00_{ew}{abs(lon):03d}_00_DEM"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    g = sub.add_parser("get")
    g.add_argument("names", nargs="*")
    g.add_argument("--stream")
    g.add_argument("--dest", default="data-fetch-cache")
    d = sub.add_parser("dem")
    d.add_argument("--bbox", nargs=4, type=float, required=True, metavar=("W", "S", "E", "N"))
    d.add_argument("--dest", default="data-fetch-cache/glo30")
    a = ap.parse_args()
    resources = load()
    by_name = {r["name"]: r for r in resources}

    if a.cmd == "list":
        for r in resources:
            if r.get("url"):
                print(f"{r['name']:<34} {(r.get('size') or 0) / 1e6:>10.1f} MB  {','.join(r['streams'])}")
        return
    if a.cmd == "get":
        names = list(a.names)
        if a.stream:
            names += [r["name"] for r in resources if a.stream in r["streams"] and r.get("url")]
        if not names:
            raise SystemExit("name a resource or --stream; see: fetch.py list")
        for name in names:
            if name not in by_name or not by_name[name].get("url"):
                raise SystemExit(f"unknown or not directly fetchable resource: {name}")
            get(by_name[name], a.dest)
        return
    if a.cmd == "dem":
        known = {r["filename"]: r for r in resources}
        for tile in glo30_tiles(*a.bbox):
            res = known.get(tile + ".tif") or {"name": tile, "filename": tile + ".tif", "url": GLO30.format(n=tile)}
            get(res, a.dest)


if __name__ == "__main__":
    main()
