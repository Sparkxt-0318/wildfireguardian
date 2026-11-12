"""Write a displacement file restricted to a fire subset (Iris: the main numbers without the GOFER-matched fires).

The GOFER-matched part-a fires among the 25 are Bobcat, CZU Lightning, KNP Complex and Slater
(RESULTS.md §3d, A1 item 25). LNU-Meyers is GOFER-matched too but is not among the 25. In this analysis these fires
use NIROPS brackets like the others; they are excluded only because of their H-dev assignment.

    python subset_displacement.py --input results/displacement_mcem.json --drop-gofer \
        --out results/displacement_mcem_nogofer.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

GOFER = ["CA-ANF-003687_Bobcat", "CA-CZU-005205_CZULightning", "CA-KNP-000122_KNPComplex", "CA-KNF-007035_Slater"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--drop-gofer", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    d = json.loads(a.input.read_text())
    drop = GOFER if a.drop_gofer else []
    missing = [f for f in drop if f not in d["per_fire"]]
    assert not missing, missing
    d["per_fire"] = {f: v for f, v in d["per_fire"].items() if f not in drop}
    d["summary"] = None  # the stored summary is for all fires; recompute with displacement_checks.py
    d["subset"] = dict(source=str(a.input), dropped=drop, command="python subset_displacement.py " + " ".join(argv or sys.argv[1:]))
    a.out.write_text(json.dumps(d))
    print(len(d["per_fire"]), "fires kept")


if __name__ == "__main__":
    main()
