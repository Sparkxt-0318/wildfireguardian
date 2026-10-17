"""Predeclared, content-blind selection of USFS archive videos for the precision evaluation.

Reads the archive listings written by `scripts/fetch_rds_members.py list --json` and picks
members by a fixed rule and seed, before any video is fetched or viewed:

- C8 (RDS-2021-0069, FBAT in-fire videos): the fire folders (one per wildfire incident) are
  sorted by name and shuffled with numpy's default_rng(seed). The first 3 fires are the
  calibration/selection population, the next 6 the sealed final test, the rest a reserve that is
  never fetched (kept for a later fresh test). In each chosen fire one plot (camera deployment)
  is drawn among the plots with highlight clips (*_C#.avi), then one of that plot's clips.
  For the first 2 test fires the drawn plot's full video is also listed, to be fetched as a
  leading prefix (representative footage before and around the fire's arrival).
- C7 (RDS-2022-0071, tree-burn firebrand videos): the smallest video of each tree species
  (DF, GF, PP, WJ), for calibration only (one burn site, so one deployment group per test).

Only names and sizes are used; nothing about the content. The output is a JSON file that is
committed before fetching.

    python scripts/precision_select_rds.py --listings results/runs/precision_20261017/rds \
        --seed 20261017 --out results/validation/precision_20261017/data_selection.json
"""
from __future__ import annotations

import argparse
import glob
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

CLIP_RE = re.compile(r"^([A-Z]{4})(\d{3})_C(\d+)\.avi$", re.I)
FULL_RE = re.compile(r"^([A-Z]{4})(\d{3})\.avi$", re.I)
SPECIES_RE = re.compile(r"^(DF|GF|PP|WJ)(\d+)(-\d+)?\.MOV$", re.I)


def _members(listings: Path, archive_id: str) -> list[dict]:
    out = []
    for f in sorted(glob.glob(str(listings / f"{archive_id}_*.json"))):
        d = json.loads(Path(f).read_text())
        for m in d["members"]:
            if not m["name"].endswith("/"):
                out.append({**m, "archive_url": d["url"], "archive_bytes": d["archive_bytes"]})
    return out


def select(listings: Path, seed: int, n_cal: int = 3, n_test: int = 6, n_prefix: int = 2) -> dict:
    rng = np.random.default_rng(seed)
    c8 = _members(listings, "RDS-2021-0069")
    clips: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    full: dict[tuple[str, str], dict] = {}
    for m in c8:
        parts = m["name"].split("/")
        fire, base = parts[1], parts[-1]
        if (mc := CLIP_RE.match(base)):
            clips[fire][mc.group(1).upper() + mc.group(2)].append(m)
        elif (mf := FULL_RE.match(base)):
            full[(fire, mf.group(1).upper() + mf.group(2))] = m
    fires = sorted(f for f in clips if clips[f])
    order = [fires[i] for i in rng.permutation(len(fires))]
    roles = {f: ("calibration" if k < n_cal else "test" if k < n_cal + n_test else "reserve")
             for k, f in enumerate(order)}
    chosen = []
    for k, fire in enumerate(order):
        if roles[fire] == "reserve":
            continue
        plots = sorted(clips[fire])
        plot = plots[int(rng.integers(len(plots)))]
        cands = sorted(clips[fire][plot], key=lambda m: m["name"])
        clip = cands[int(rng.integers(len(cands)))]
        item = {"archive": "RDS-2021-0069", "clip_group": "C8", "fire": fire, "plot": plot,
                "role": roles[fire], "member": clip["name"], "member_bytes": clip["size"],
                "member_crc32": clip["crc32"], "archive_url": clip["archive_url"], "fetch": "whole"}
        chosen.append(item)
        test_rank = k - n_cal
        if roles[fire] == "test" and test_rank < n_prefix and (fire, plot) in full:
            fm = full[(fire, plot)]
            chosen.append({**item, "member": fm["name"], "member_bytes": fm["size"], "member_crc32": fm["crc32"],
                           "archive_url": fm["archive_url"], "fetch": "prefix", "prefix_bytes": 120_000_000,
                           "role": "test_negative_footage"})
    c7 = _members(listings, "RDS-2022-0071")
    by_species: dict[str, list[dict]] = defaultdict(list)
    for m in c7:
        base = m["name"].split("/")[-1]
        if (ms := SPECIES_RE.match(base)) and "/Videos/" in m["name"]:
            by_species[ms.group(1).upper()].append(m)
    for sp in sorted(by_species):
        m = min(by_species[sp], key=lambda m: (m["size"], m["name"]))
        chosen.append({"archive": "RDS-2022-0071", "clip_group": "C7", "species": sp, "role": "calibration",
                       "member": m["name"], "member_bytes": m["size"], "member_crc32": m["crc32"],
                       "archive_url": m["archive_url"], "fetch": "whole"})
    return {"seed": seed, "rule": __doc__.strip().split("\n\n")[1], "fire_order": order, "fire_roles": roles,
            "n_fires_with_clips": len(fires), "selected": chosen}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--listings", required=True)
    ap.add_argument("--seed", type=int, default=20261017)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    res = select(Path(a.listings), a.seed)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1))
    for s in res["selected"]:
        print(f"{s['role']:22} {s['clip_group']} {s['member']} {s['member_bytes'] / 1e6:.1f} MB {s['fetch']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
