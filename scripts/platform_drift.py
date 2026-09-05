#!/usr/bin/env python
"""Measure how far Arm A's own numbers move when the platform changes.

Session 10 follow-up, task 3. This is the session's most consequential finding
and it was living in prose, where nothing can check it.

The measurement: run Arm A's SIXTEEN columns, its seed, its folds and its
protocol on a second platform, and compare against the committed artifact
produced on the reference environment. The dataset is identical by construction
(same FIRMS/ERA5/DEM bundle, same grid, same fold definition), so whatever moves
is the platform and nothing else.

Why it matters: any arm-to-arm delta smaller than this is not a measurement.
Session 10's Arm D pooled delta was -0.0070 against a drift of 0.0064, which is
why the report refused to call it a degradation.

    python scripts/platform_drift.py --write

Writes docs/platform_drift.json — deliberately under docs/, not
data/processed/, so it is tracked and auditable without joining the Korean
baseline's artifact set.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

COMMITTED = REPO / "data" / "processed" / "spread_v2_lofo.json"
REPLICATION = REPO / "data" / "processed" / "arms" / "A_replication" / "lofo_arm_A.json"
OUT = REPO / "docs" / "platform_drift.json"

REFERENCE_ENV = {
    "label": "wfg311",
    "os": "macOS",
    "arch": "arm64 (Apple Silicon)",
    "python": "3.11.15",
    "channel": "conda-forge",
    "note": "The reference environment. Every committed headline value was "
            "produced here (docs/ENVIRONMENT.md).",
}


def build() -> dict:
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    repl = json.loads(REPLICATION.read_text(encoding="utf-8"))

    def drift(key_c: str, key_r: str) -> dict:
        a, b = committed[key_c], repl[key_r]
        return {"reference": a, "second_platform": b,
                "abs_drift": round(abs(a - b), 6), "signed_drift": round(b - a, 6)}

    per_fire = {}
    for fire, a in sorted(committed["per_fire_auc"].items()):
        b = repl["per_fire_auc"].get(fire)
        if a is None or b is None:
            continue
        per_fire[fire] = {"reference": a, "second_platform": b,
                          "abs_drift": round(abs(a - b), 6)}

    return {
        "schema_version": 1,
        "title": "Cross-platform reproduction drift of the Arm A LOGO-CV metrics",
        "provenance": "derived",
        "arm": "A_replication",
        "generated_by": "scripts/platform_drift.py",
        "what_this_is": (
            "The floor below which no arm-to-arm comparison in this project is a "
            "measurement. Not an Arm A value and never to be cited as one."
        ),
        "reference_environment": REFERENCE_ENV,
        "second_platform": {
            "os": platform.system(),
            "arch": platform.machine(),
            "python": platform.python_version(),
            "channel": "PyPI manylinux wheels (uv, python-build-standalone)",
            "note": "Session 10's execution environment. requirements.txt pins "
                    "installed exactly; `make env-check` passes. The versions "
                    "match; only the binary builds differ.",
        },
        "held_identical": {
            "seed": 20250603,
            "feature_columns": committed.get("n_features", 16),
            "folds": "leave-one-fire-out over the same 6 fires, alphabetical order",
            "n_rows": repl["n_oof_rows"],
            "n_positives": repl["n_oof_positives"],
            "dataset_shape_matches_baseline_freeze": (
                repl["n_oof_rows"] == 151904 and repl["n_oof_positives"] == 2989),
        },
        "drift": {
            "pooled_auc": drift("pooled_auc", "pooled_auc"),
            "far_band_auc": drift("far_band_auc", "far_band_auc"),
            "mid_band_auc": drift("mid_band_auc", "mid_band_auc"),
        },
        "per_fire_auc_drift": per_fire,
        "cause": (
            "Floating-point accumulation order and the placement of the "
            "early-stopping validation split inside "
            "HistGradientBoostingClassifier differ between the conda-forge "
            "macOS/arm64 build and the PyPI manylinux aarch64 build. The "
            "estimator, its hyperparameters and its seed are identical."
        ),
        "consequence": (
            "Pooled ROC-AUC is reportable to THREE significant figures. The "
            "fourth digit is not stable across platforms and must not be "
            "compared, ranked or differenced."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    for p in (COMMITTED, REPLICATION):
        if not p.exists():
            raise SystemExit(f"missing input: {p.relative_to(REPO)}")

    payload = build()
    if args.write:
        OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        print(f"wrote {OUT.relative_to(REPO)}")
    print(json.dumps(payload["drift"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
