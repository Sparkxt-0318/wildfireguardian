#!/usr/bin/env python
"""Register the DENSE buffer-width grid in docs/NUMBERS.json (WFG-127).

The committed fair-opponent artifact sweeps five buffer widths — 250 / 500 /
1000 / 2000 / 3000 m — so the two neighbours of the best width are each a factor
of two away. Three surfaces read a **spike** off that grid anyway. This registers
the three widths that were missing from the gap the claim was about: 750, 1250
and 1500 m, produced by the same runner into a SEPARATE artifact.

ADDITIVE ON PURPOSE, TWICE OVER. `scripts/build_numbers.py` rebuilds the registry
from its own list and would drop the keys other registrars added (WFG-040), so
this script loads the current file and touches only its own prefix. And its
prefix is NEW: it does not rewrite one `pp_uiseong_` key, because those describe
the committed artifact, which this lap did not modify (CHARTER §3 rule 2) and
whose own five-width sweep is still exactly five widths wide.

    python scripts/register_buffer_shape.py          # upsert + report
    python scripts/register_buffer_shape.py --check  # exit 1 if stale
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs" / "NUMBERS.json"
ARTIFACT = ("data/processed/present_perimeter_buffer_shape_uiseong_andong_2025.json")
PREFIX = "ppshape_uiseong_"

#: The widths this registrar owns. The other five belong to `pp_uiseong_`, are
#: reproduced cell for cell by the same run, and are NOT re-registered here: two
#: registry keys for one quantity is the collision the repository has a gate for.
NEW_WIDTHS = (750.0, 1250.0, 1500.0)

#: The caveat every one of these keys carries. It is long for the same reason
#: `pp_uiseong_`'s is: this result both weakens and defends the headline, and
#: either half quoted alone is a false statement about the experiment.
BAND = (
    "DENSE BUFFER GRID, FAIR-OPPONENT ARM, ONE FIRE, CANONICAL (slope 60 m / "
    "DiGraph) TIMING. These three widths were run to settle a question the "
    "five-width grid could not answer and that three surfaces answered anyway: "
    "whether the best buffer width is a spike or a plateau. Four facts travel "
    "together or none of them may be quoted: (1) it is NOT a spike — measured "
    "safe totals run 275, 284, 349, 345, 318, 305, 275, 283 across 250 m to 3 km, "
    "so the top is a shoulder about 750 m to 1 km wide and the previous "
    "「spike, not a plateau」 reading is WITHDRAWN (WC-011); (2) the shoulder is "
    "not symmetric ACROSS ONE GRID STEP — one 250 m step off the thin end takes "
    "the safe total from 349 to 284, one 250 m step off the thick end takes it "
    "from 345 to 318 — so 「if you must be wrong by about a step, be wrong "
    "THICK」 is supported, while 「thicker is always safer」 is NOT: 2 km is back "
    "to 275, where 250 m already was; (3) 750 m scores HIGHER than the 1 km the committed "
    "headline uses, so the fair opponent is stronger than the committed artifact "
    "reports and the forecast's margin on this fire is SMALLER than the "
    "committed margin, not larger — this result runs AGAINST this project; "
    "(4) it is still ONE fire, ONE region and ONE hazard realisation, the grid "
    "is still 250 m coarse at its finest, and nothing here says an operator "
    "could pick the shoulder in advance on a DIFFERENT fire. "
    "⚠ The forecast-aware arm is scored on the SAME hazard field it plans on, so "
    "it carries NO forecast error here; every margin in this band is what a "
    "PERFECT forecast buys over a present-perimeter policy, and the real-model "
    "margin is smaller by an amount this run does not measure."
)

FORBIDDEN = [
    "750 m is the optimal buffer",
    "750 m가 최적",
    "the optimal buffer width is 750",
    "the data chooses the buffer width",
    "데이터가 완충거리를 골라",
    "the buffer width can be known in advance",
    "the forecast is unnecessary",
    "예보는 필요 없다",
]

#: One key per cell, exactly as `register_present_perimeter.py` does it: the
#: table IS the argument, so every cell of it is registered rather than left to
#: a doc-vs-artifact test (CHARTER §3.3).
SWEEP_FIELDS = [
    ("recovered", "recovered_of_forecast_only", "origins",
     "forecast-only origins the present-aware arm also gets to safety"),
    ("broken", "already_safe_broken", "origins",
     "origins the fire-blind control already had safe that this buffer breaks"),
    ("safe", "safe_total", "origins",
     "origins the present-aware arm gets to a refuge safely and inside budget"),
    ("burns", "failed_enters_hazard", "origins",
     "origins whose present-aware route still stands on a cell at p >= 0.5 while "
     "it is at p >= 0.5 — the fire grows past the buffer"),
    ("unreachable", "failed_unreachable", "origins",
     "origins with no route to any refuge — safety bought by telling people "
     "there is no way out"),
    ("late", "failed_over_budget", "origins",
     "origins that reach a refuge safely but outside the 600-minute budget"),
]


def sweep_figures(art: dict) -> list[tuple[str, str, str, str]]:
    """One registry key per cell of the three NEW widths, named by width."""
    out = []
    seen = set()
    for i, row in enumerate(art["buffer_sensitivity"]):
        w = float(row["buffer_m"])
        if w not in NEW_WIDTHS:
            continue
        seen.add(w)
        tag = f"w{int(w)}m"
        for suffix, field, unit, derivation in SWEEP_FIELDS:
            out.append((f"{tag}_{suffix}", f"buffer_sensitivity.{i}.{field}",
                        unit, f"{derivation} (buffer {w:.0f} m)"))
    missing = set(NEW_WIDTHS) - seen
    if missing:
        raise SystemExit(
            f"artifact is missing the widths this registrar owns: {sorted(missing)}. "
            f"Regenerate with --sweep-extra-m "
            f"{','.join(str(int(w)) for w in sorted(NEW_WIDTHS))}")
    return out


def _dig(doc: dict, path: str):
    cur = doc
    for part in path.split("."):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


def build_entries(art: dict, head: str, doc_hash: str) -> dict:
    out = {}
    for suffix, path, unit, derivation in sweep_figures(art):
        out[PREFIX + suffix] = {
            "value": _dig(art, path),
            "unit": unit,
            "source_file": ARTIFACT,
            "json_path": path,
            # The trailing `Regenerate:` clause OVERRIDES the basename inference
            # in scripts/build_artifact_manifest.py, for the reason its sibling
            # registrar records: this script READS the artifact, the runner
            # PRODUCES it, and a wrong regeneration command looks like provenance.
            "derivation": derivation + ". Regenerate: python scripts/"
                          "run_present_perimeter_arm.py --sweep-extra-m 750,1250,1500 "
                          "--out " + ARTIFACT,
            "config_hash": doc_hash,
            "config_hash_at_production": art.get("config_hash"),
            "git_commit": head,
            "sample": "의성·안동 2025 · 368곳 주사 · slope 60 m / DiGraph (canonical)",
            "caveat": BAND,
            "forbidden_phrasings": FORBIDDEN,
            "reproducible": True,
            "reproducibility": {
                "status": "reproducible",
                "evidence": (
                    "python scripts/run_present_perimeter_arm.py "
                    "--sweep-extra-m 750,1250,1500 --out " + ARTIFACT + " "
                    "rebuilds the artifact from the hash-verified snapshot walk "
                    "graph, the committed hazard npz and the committed refuge "
                    "snapshot, with no network access. It refuses to write unless "
                    "it first reproduces the committed canonical arm exactly, and "
                    "the five widths it shares with the committed artifact come "
                    "out cell for cell identical — which is what makes the three "
                    "new widths comparable with the five old ones at all."),
                "blocked_by": None,
            },
            "provenance": "internal",
            "arm": "present_perimeter",
            "notes": "docs/present_perimeter_buffer_shape.md states the method, "
                     "the measured shape, the withdrawal it forces (WC-011) and "
                     "what the denser grid still does not show. WFG-127.",
            "check": {"kind": "json_path", "tolerance": 0.0,
                      "operands": {"a": {"file": ARTIFACT, "json_path": path}}},
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    doc = json.loads(NUMBERS.read_text(encoding="utf-8"))
    art = json.loads((REPO / ARTIFACT).read_text(encoding="utf-8"))
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()
    new = build_entries(art, head, doc["config_hash"])
    cur = doc["numbers"]
    stale = [k for k, e in new.items()
             if k not in cur or cur[k]["value"] != e["value"]
             or cur[k].get("caveat") != e.get("caveat")]
    if args.check:
        if stale:
            print("STALE buffer-shape registry entries: " + ", ".join(stale))
            return 1
        print(f"OK — {len(new)} buffer-shape entries match the artifact")
        return 0
    for k, e in new.items():
        if k in cur:  # the first registration's commit is the provenance
            e["git_commit"] = cur[k].get("git_commit", head)
        cur[k] = e
    NUMBERS.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"upserted {len(new)} buffer-shape entries "
          f"({len(stale)} new or changed); registry now {len(cur)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
