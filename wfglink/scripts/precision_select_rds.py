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


def amend_test_from_reserve(selection: dict, listings: Path, n_test: int = 6, n_prefix: int = 2) -> dict:
    """Amendment of 2026-10-17 (recorded in LOG and the protocol): the first sealed-test fires were
    decoded while the camera-motion gate was being developed (global-motion statistics only, no
    labels, no detections), so they can no longer serve as a sealed test. They become calibration
    material, and a fresh sealed test is drawn from the untouched reserve: the next n_test fires in
    the original seeded fire order, with plots, clips and prefixes drawn by numpy default_rng(seed + 1)
    in that order. Content-blind: names and sizes only."""
    rng = np.random.default_rng(int(selection["seed"]) + 1)
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
    reserve = [f for f in selection["fire_order"] if selection["fire_roles"][f] == "reserve"]
    new_test = reserve[:n_test]
    chosen = []
    for item in selection["selected"]:
        it = dict(item)
        if it["role"] in ("test", "test_negative_footage"):
            it["role_original"] = it["role"]
            it["role"] = "calibration" if it["role"] == "test" else "calibration_negative_footage"
            it["demoted_reason"] = "decoded during camera-motion gate development (global-motion statistics only)"
        chosen.append(it)
    for k, fire in enumerate(new_test):
        plots = sorted(clips[fire])
        plot = plots[int(rng.integers(len(plots)))]
        cands = sorted(clips[fire][plot], key=lambda m: m["name"])
        clip = cands[int(rng.integers(len(cands)))]
        item = {"archive": "RDS-2021-0069", "clip_group": "C8", "fire": fire, "plot": plot, "role": "test",
                "member": clip["name"], "member_bytes": clip["size"], "member_crc32": clip["crc32"],
                "archive_url": clip["archive_url"], "fetch": "whole", "amendment": 1}
        chosen.append(item)
        if k < n_prefix and (fire, plot) in full:
            fm = full[(fire, plot)]
            chosen.append({**item, "member": fm["name"], "member_bytes": fm["size"], "member_crc32": fm["crc32"],
                           "archive_url": fm["archive_url"], "fetch": "prefix", "prefix_bytes": 120_000_000,
                           "role": "test_negative_footage"})
    roles = dict(selection["fire_roles"])
    for f in new_test:
        roles[f] = "test"
    for f, r in selection["fire_roles"].items():
        if r == "test":
            roles[f] = "calibration"
    return {**selection, "amendment": {"number": 1, "rule": amend_test_from_reserve.__doc__.strip(),
                                       "rng": f"default_rng({int(selection['seed']) + 1})", "new_test_fires": new_test},
            "fire_roles": roles, "selected": chosen}


def raw_name(item: dict) -> str:
    """The file name in data/raw for a selected member, e.g. C8_ROUG016_C3.avi, C8_ROUG016_prefix.avi, C7_PP31.mov."""
    base = item["member"].split("/")[-1]
    stem, ext = base.rsplit(".", 1)
    if item.get("fetch") == "prefix":
        stem += "_prefix"
    return f"{item['clip_group']}_{stem}.{ext.lower()}"


def fetch(selection: Path, raw_dir: Path, receipts: Path) -> int:
    """Fetch every selected member into raw_dir (skipping files already complete), appending one
    provenance record per file to receipts (JSON lines)."""
    from fetch_rds_members import get_member

    sel = json.loads(selection.read_text())
    done = set()
    if receipts.exists():
        done = {json.loads(line)["member"] for line in receipts.read_text().splitlines() if line.strip()}
    failures = 0
    for item in sel["selected"]:
        out = raw_dir / raw_name(item)
        if item["member"] in done and out.exists():
            continue
        member = {"name": item["member"], "size": item["member_bytes"], "crc32": item["member_crc32"],
                  "method": 8, "local_offset": None}
        try:
            from fetch_rds_members import list_members

            listing = {m["name"]: m for m in list_members(item["archive_url"])["members"]}
            member = listing[item["member"]]
            rec = get_member(item["archive_url"], member, out, item.get("prefix_bytes"))
        except Exception as exc:  # recorded, the run continues with the next member
            failures += 1
            print(f"FAILED {item['member']}: {exc}")
            continue
        rec.update({"role": item["role"], "clip_group": item["clip_group"], "raw_name": out.name})
        with open(receipts, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"ok {out.name} {rec['bytes_written'] / 1e6:.1f} MB sha256 {rec['sha256'][:16]}")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--listings")
    ap.add_argument("--seed", type=int, default=20261017)
    ap.add_argument("--out", required=True, help="selection JSON (written by the selection, read by --fetch)")
    ap.add_argument("--fetch", action="store_true", help="fetch the members of an existing selection")
    ap.add_argument("--amend-from", help="write amendment 1 of this selection (test fires redrawn from the reserve) to --out")
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--receipts", default="results/validation/precision_20261017/fetch_receipts.jsonl")
    a = ap.parse_args(argv)
    if a.fetch:
        return fetch(Path(a.out), Path(a.raw_dir), Path(a.receipts))
    if a.amend_from:
        res = amend_test_from_reserve(json.loads(Path(a.amend_from).read_text()), Path(a.listings))
    else:
        res = select(Path(a.listings), a.seed)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1))
    for s in res["selected"]:
        print(f"{s['role']:22} {s['clip_group']} {s['member']} {s['member_bytes'] / 1e6:.1f} MB {s['fetch']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
