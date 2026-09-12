#!/usr/bin/env python
"""Register the real-hazard rescue run (NH-057, 2026-09-12) in docs/NUMBERS.json.

ADDITIVE ON PURPOSE (WFG-040): loads the registry, replaces only `rrh_` keys.

    python scripts/register_rescue_routing_real_hazard.py          # upsert
    python scripts/register_rescue_routing_real_hazard.py --check  # exit 1 if stale
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
ARTIFACT = "data/processed/rescue_routing_real_hazard.json"
MANIFEST = "outputs/dispatch_real_hazard/20260912T153043Z/MANIFEST.json"
PREFIX = "rrh_"

BAND = (
    "A SAMPLE OF THE ROAD NETWORK ON A SIMULATED FIRE, NOT A HOUSEHOLD COUNT AND NOT "
    "COMPARABLE TO THE SYNTHETIC-HAZARD SHEETS. Four facts travel together or none may "
    "be quoted. (1) THE HAZARD IS REAL IN THE SENSE EVERY ROUTING SURFACE USES: the "
    "leave-one-fire-out forward simulation of the 2025 영덕 fire in "
    "data/processed/routing_demo_canonical.npz, on its 500 m grid, 0-720 min. It is a "
    "simulation of the observed fire, not the FIRMS observation itself. (2) THE ORIGINS "
    "ARE SAMPLED walk-graph nodes at stride 18, not households, and THE WALK TIMING IS "
    "FLAT (the OSM loader carries no slope); the vehicle side is the config's assumptions "
    "(cutoff 0.7, 40 km/h, dispatch delay, safety margin, 75-min budget). (3) NOTHING "
    "SYNTHETIC DRIVES A NUMBER: the script refuses to run if any real loader falls back, "
    "and no synthetic terrain, envelope or coastline is built. (4) THIS IS A SEPARATE RUN "
    "from outputs/dispatch/ and outputs/dispatch_full/: different hazard, different "
    "extent, different origin set. Do not reconcile, subtract, average or compare; the "
    "2026-08-01 sheets stay byte-unchanged as the record. Of the origins needing rescue, "
    "all but one are the immobile draw (immobile_fraction 0.3), so the walk-out question "
    "on this hazard is decided by mobility, not by the fire. "
    "docs/rescue_routing_real_hazard.md states the method, the result and what it does "
    "NOT show."
)

FORBIDDEN = [
    "households", "가구", "실제 가구",
    "compared with the synthetic run", "합성 실행과 비교",
    "the real fire strands", "실제 화재에서 고립",
    "slope-aware", "경사를 반영",
]

_SAMPLE = ("영덕 2025 · real LOFO hazard on the canonical 500 m grid · 2026-07-24 OSM "
           "snapshots · 444 sampled origins (stride 18) · budget 600 min · vehicle "
           "cutoff 0.7 · responder budget 75 min")

FIGURES = [
    ("n_origins", ARTIFACT, "n_origins", "origins",
     "origins scanned: walk-graph nodes at stride 18, not burning at t0, inside the reach band"),
    ("already_safe", ARTIFACT, "four_way_counts.already_safe", "origins",
     "origins whose fire-blind shortest walk reaches a refuge without entering the hazard"),
    ("saved_by_rescue_reachable_refuge", ARTIFACT,
     "four_way_counts.saved_by_rescue_reachable_refuge", "origins",
     "origins that reach a rescue-reachable refuge only on the time-aware walk"),
    ("no_safe_pedestrian_route", ARTIFACT, "four_way_counts.no_safe_pedestrian_route", "origins",
     "origins needing rescue for which a survival-aware vehicle route from some depot exists"),
    ("no_surviving_vehicle_ingress", ARTIFACT,
     "four_way_counts.no_surviving_vehicle_ingress", "origins",
     "origins needing rescue for which no depot has a survival-aware vehicle route (rescuer_reachable False)"),
    ("n_need_rescue", ARTIFACT, "responder_exposure.n_need_rescue", "origins",
     "the two rescue classes together"),
    ("n_need_rescue_immobile", ARTIFACT, "responder_exposure.n_need_rescue_immobile", "origins",
     "of those, the immobile draw (config immobile_fraction 0.3)"),
    ("n_refuges", ARTIFACT, "n_refuges", "refuges", "OSM refuges in the extent"),
    ("n_refuges_rescue_reachable", ARTIFACT, "n_refuges_rescue_reachable", "refuges",
     "refuges a responder can reach and leave under the vehicle cutoff"),
    ("n_clusters", MANIFEST, "villages", "clusters",
     "dispatch clusters at eps 500 m in the generated sheet set (len(villages) in MANIFEST.json)"),
]


def _get(doc, path):
    cur = doc
    for part in path.split("."):
        cur = cur[int(part)] if part.isdigit() else cur[part]
    return cur


def build_entries(head: str, doc_hash: str) -> dict:
    arts = {f: json.loads((REPO / f).read_text(encoding="utf-8")) for f in {ARTIFACT, MANIFEST}}
    out = {}
    for suffix, file, path, unit, derivation in FIGURES:
        raw = _get(arts[file], path)
        value = len(raw) if isinstance(raw, list) else raw
        check = ({"kind": "expression", "expr": "len(a)", "tolerance": 0.0,
                  "operands": {"a": {"file": file, "json_path": path}}}
                 if isinstance(raw, list) else
                 {"kind": "json_path", "tolerance": 0.0,
                  "operands": {"a": {"file": file, "json_path": path}}})
        out[PREFIX + suffix] = {
            "value": value,
            "unit": unit,
            "source_file": file,
            "json_path": path,
            "derivation": derivation + ". Regenerate: python scripts/run_rescue_routing_real_hazard.py",
            "config_hash": doc_hash,
            "git_commit": head,
            "sample": _SAMPLE,
            "caveat": BAND,
            "forbidden_phrasings": FORBIDDEN,
            "reproducible": True,
            "reproducibility": {
                "status": "reproducible",
                "evidence": ("python scripts/run_rescue_routing_real_hazard.py reads the committed "
                             "canonical npz and the committed data/snapshots/ only (no network, no "
                             "data/cache/), refuses any synthetic fallback, and re-derives the "
                             "per-origin classes against run_pipeline's own counts before writing."),
                "blocked_by": None,
            },
            "provenance": "internal",
            "arm": "rescue_routing_real_hazard",
            "notes": "docs/rescue_routing_real_hazard.md. Sheets: outputs/dispatch_real_hazard/20260912T153043Z/.",
            "check": check,
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    doc = json.loads(NUMBERS.read_text(encoding="utf-8"))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()
    new = build_entries(head, doc["config_hash"])
    cur = doc["numbers"]
    stale = [k for k, e in new.items()
             if k not in cur or cur[k]["value"] != e["value"] or cur[k].get("caveat") != e.get("caveat")]
    if args.check:
        if stale:
            print("STALE real-hazard rescue registry entries: " + ", ".join(stale))
            return 1
        print(f"OK — {len(new)} real-hazard rescue entries match the artifacts")
        return 0
    for k, e in new.items():
        if k in cur:
            e["git_commit"] = cur[k].get("git_commit", head)
        cur[k] = e
    NUMBERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"upserted {len(new)} real-hazard rescue entries ({len(stale)} new or changed); registry now {len(cur)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
