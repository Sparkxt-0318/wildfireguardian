#!/usr/bin/env python3
"""S1 of the independent part-a rerun (Owen): rebuild every part-a label state from the raw NIROPS shapefile.

For each Incident_C on PART_A_ALLOWLIST_FINAL (and nothing else) it runs Daniel's committed v2 builder, which reads
NIROPS only through nirops_access.py (ID column, then by fid). It then compares the sha256 of the rebuilt states.npz,
perimeters.geojson and labels with the committed part-a pool (PERIMETER_MANIFEST.json and the committed
states.npz). It exits 1 on any mismatch, failure, or pin mismatch. Keys are Incident_C; no names are used.
The builder's --exposed-reference option is never passed, so only allowlisted incidents can be built.

    python s1_labels.py --repo REPO --shp NIROPS_2020_2024_R1_R6.shp --pool-rev REV --work DIR --out S1.json
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PINS = dict(
    shapefile="a14f391ae0e2f75a1d218aed91ad03eb35bfc311a4909021f9fe1f6310fdf09b",
    allowlist="7db3cc0ef084",  # prefix of PART_A_ALLOWLIST_FINAL.csv sha256 (2d40d170)
)
ALLOWLIST = "research/harness-2026-11/S-D9/cohort/PART_A_ALLOWLIST_FINAL.csv"
BUILDER = "research/harness-2026-11/data-fetch-3/nirops_access/build_nirops_event_v2.py"
POOL = "research/harness-2026-11/data-fetch-3/parta_pool"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def git_bytes(repo: Path, rev: str, path: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), "show", f"{rev}:{path}"], check=True, capture_output=True).stdout


def build_one(inc, repo, src, shp, allow, work, manifest, pool_rev):
    ws = Path(tempfile.mkdtemp(prefix="s1_", dir=work))
    try:
        r = subprocess.run([sys.executable, str(src / BUILDER), inc, "--shp", str(shp), "--allowlist", str(allow),
                            "--workspace", str(ws)], capture_output=True, text=True)
        if r.returncode:
            return inc, dict(ok=False, error=(r.stderr or r.stdout)[-400:])
        per = ws / "data/perimeters" / inc
        got = dict(states=sha256(per / "states.npz"), geojson=sha256(per / "perimeters.geojson"))
        exp = manifest["events"].get(inc, {})
        committed = hashlib.sha256(git_bytes(repo, pool_rev, f"{POOL}/perimeters/{inc}/states.npz")).hexdigest()
        res = dict(states_sha256=got["states"], geojson_sha256=got["geojson"],
                   states_vs_manifest=got["states"] == exp.get("states_sha256"),
                   states_vs_committed_file=got["states"] == committed,
                   geojson_vs_manifest=got["geojson"] == exp.get("geojson_sha256"))
        res["ok"] = all(res[k] for k in ("states_vs_manifest", "states_vs_committed_file", "geojson_vs_manifest"))
        return inc, res
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", type=Path, required=True, help="git checkout holding the pinned revisions")
    ap.add_argument("--src", type=Path, required=True, help="worktree at --pool-rev (builder + forecast/wildfire)")
    ap.add_argument("--pool-rev", required=True, help="commit of the part-a pool (daniel/data-fetch-3)")
    ap.add_argument("--shp", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help="test only: first N incidents in sha256(Incident_C) order")
    a = ap.parse_args(argv)
    fails = []
    shp_sha = sha256(a.shp)
    if shp_sha != PINS["shapefile"]:
        fails.append(f"shapefile sha {shp_sha}")
    allow = a.src / ALLOWLIST
    allow_sha = sha256(allow)
    if not allow_sha.startswith(PINS["allowlist"]):
        fails.append(f"allowlist sha {allow_sha}")
    if fails:
        print("PIN MISMATCH:", fails); sys.exit(1)
    ids = sorted({r["Incident_C"] for r in csv.DictReader(open(allow))})
    if a.limit:
        ids = sorted(ids, key=lambda i: hashlib.sha256(i.encode()).hexdigest())[:a.limit]
    manifest = json.loads(git_bytes(a.repo, a.pool_rev, f"{POOL}/PERIMETER_MANIFEST.json"))
    a.work.mkdir(parents=True, exist_ok=True)
    results = {}
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        futs = [ex.submit(build_one, i, a.repo, a.src, a.shp, allow, a.work, manifest, a.pool_rev) for i in ids]
        for n, f in enumerate(cf.as_completed(futs), 1):
            inc, res = f.result()
            results[inc] = res
            if not res["ok"]:
                print("MISMATCH", inc, res, flush=True)
            if n % 25 == 0:
                print(f"{n}/{len(ids)}", flush=True)
    bad = sorted(i for i, r in results.items() if not r["ok"])
    out = dict(stage="S1 labels", pool_rev=a.pool_rev, shapefile_sha256=shp_sha, allowlist_sha256=allow_sha,
               manifest_script_sha256=manifest.get("script_sha256"), incidents=len(ids),
               limited=bool(a.limit), ok=len(ids) - len(bad), mismatches=bad, results=dict(sorted(results.items())))
    a.out.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: out[k] for k in ("incidents", "ok", "mismatches", "limited")}))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
