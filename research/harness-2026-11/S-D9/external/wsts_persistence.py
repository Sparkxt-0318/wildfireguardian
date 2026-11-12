"""WildfireSpreadTS 2019: label-only check of our adapter against WSTS's published persistence AP.

DEVELOPMENT-ONLY (external/WSTS_DESIGN.md; the orchestrator approved 2019 only, streamed one fire at a
time and deleted after use, labels only). It reads band 23 ("active fire") only. Nothing is committed but
hashes and counts.

WSTS protocol (Gerard et al. 2023; Sofia's reading): label = next day's active-fire band binarised
(finite = detected); test targets start at each fire's 6th day; full scenes centre-cropped to a multiple
of 32 pixels; AP pooled over all pixels of the test year. Persistence predicts today's binarised map.
Published 2019 persistence AP: 0.105 (Table 2). Because persistence is binary, the pooled AP is exactly
r * p + (1 - r) * base, where r and p are recall and precision at the single positive threshold.

Score B counts (our native question, new burn) are also accumulated: the label is active on day t + 1 and
not in S_t, the cumulative union of detections up to day t, over cells not in S_t. Persistence is
always 0 there, so only the base rate is reported.

  python wsts_persistence.py --listing wsts_list.tsv --url-env WSTS_URL --tools DIR --work DIR --out WSTS_2019_PERSISTENCE.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import tifffile

AF_BAND = 22          # 0-based index of band 23, "active fire"
FIRST_TARGET = 5      # 0-based index of the 6th day
YEAR = "2019"


def crop32(a):
    h, w = a.shape
    hh, ww = (h // 32) * 32, (w // 32) * 32
    r0, c0 = (h - hh) // 2, (w - ww) // 2
    return a[r0:r0 + hh, c0:c0 + ww]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--listing", required=True, type=Path)
    ap.add_argument("--url-env", required=True)
    ap.add_argument("--tools", required=True, type=Path)
    ap.add_argument("--work", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    fires = sorted({ln.split("\t")[0].split("/")[1] for ln in args.listing.read_text().splitlines()[1:]
                    if ln.startswith(f"{YEAR}/fire_") and ln.split("\t")[0].endswith(".tif")})
    per_fire, tot = {}, dict(tp=0, fp=0, fn=0, tn=0, newburn_pos=0, newburn_cells=0)
    for i, fire in enumerate(fires):
        dest = args.work / "wsts_stream"
        shutil.rmtree(dest, ignore_errors=True)
        subprocess.run([shutil.which("python3"), "-I", str(args.tools / "remote_zip.py"), "extract", "--url",
                        os.environ[args.url_env], "--dest", str(dest), "--jobs", "4", f"{YEAR}/{fire}/*"],
                       check=True, capture_output=True)
        files = sorted((dest / YEAR / fire).glob("*.tif"))
        h = hashlib.sha256()
        maps = []
        for f in files:
            h.update(f.name.encode() + hashlib.sha256(f.read_bytes()).digest())
            maps.append(np.isfinite(crop32(tifffile.imread(f)[..., AF_BAND])))
        c = dict(days=len(files), tp=0, fp=0, fn=0, tn=0, newburn_pos=0, newburn_cells=0, shape=None)
        if maps:
            c["shape"] = list(maps[0].shape)
            union = np.zeros_like(maps[0])
            for k in range(len(maps)):
                if k >= 1:
                    union |= maps[k - 1]
                if k >= FIRST_TARGET:
                    pred, y = maps[k - 1], maps[k]
                    c["tp"] += int((pred & y).sum()); c["fp"] += int((pred & ~y).sum())
                    c["fn"] += int((~pred & y).sum()); c["tn"] += int((~pred & ~y).sum())
                    out_s = ~union
                    c["newburn_pos"] += int((y & out_s).sum()); c["newburn_cells"] += int(out_s.sum())
        c["tif_digest_sha256"] = h.hexdigest()
        per_fire[fire] = c
        for k in tot:
            tot[k] += c[k]
        shutil.rmtree(dest, ignore_errors=True)
        print(f"{i + 1}/{len(fires)} {fire} days {c['days']} tp {c['tp']} fn {c['fn']}", flush=True)
    n = tot["tp"] + tot["fp"] + tot["fn"] + tot["tn"]
    pos = tot["tp"] + tot["fn"]
    base = pos / n
    r = tot["tp"] / pos if pos else None
    p = tot["tp"] / (tot["tp"] + tot["fp"]) if tot["tp"] + tot["fp"] else 0.0
    ap_ = r * p + (1 - r) * base if r is not None else None
    out = dict(label="DEVELOPMENT-ONLY label check on WSTS 2019 (Zenodo 8006177); no model scored", year=YEAR,
               fires=len(fires), fires_with_targets=sum(1 for c in per_fire.values() if c["days"] > FIRST_TARGET),
               pixels=n, positives=pos, base_rate=base, persistence=dict(recall=r, precision=p, average_precision=ap_),
               published_persistence_ap_2019=0.105,
               score_b_newburn=dict(cells=tot["newburn_cells"], positives=tot["newburn_pos"],
                                    base_rate=tot["newburn_pos"] / tot["newburn_cells"] if tot["newburn_cells"] else None),
               per_fire=per_fire)
    args.out.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("fires", "fires_with_targets", "pixels", "positives", "base_rate",
                                          "persistence", "score_b_newburn")}, indent=1))


if __name__ == "__main__":
    main()
