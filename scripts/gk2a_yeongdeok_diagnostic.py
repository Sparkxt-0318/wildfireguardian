#!/usr/bin/env python
"""Session 19 follow-up — WHY 영덕 did not flag, from the committed step records.

The first draft of this session's report asserted that 영덕's non-detection was
"not the threshold's fault", citing target-zone statistics (median 5.09,
MAD-sd 0.89, threshold 8.65 K, max 7.34 K). **Those numbers are not in any
committed artifact.** The per-step records carry ``target_delta_max_k`` but no
target-zone median or MAD at all, so the claim could not be re-derived — which
by this project's own provenance rule means it could not stand.

Re-derived from what IS committed, the conclusion REVERSES.

    python scripts/gk2a_yeongdeok_diagnostic.py

Reads ``data/processed/detection/steps/yeongdeok_2025.json`` and writes
``data/processed/detection/yeongdeok_background_contamination.json``. Downloads
nothing; changes no Arm A artifact; fits no model.

WHAT IT SHOWS. The strongest anomaly inside the 15 km target zone is 11.611 K
at 03:42 UTC — **+28 minutes after the recorded report time**, which is exactly
when a fire's signal would be expected. It did not flag because the CONTEXTUAL
THRESHOLD at that step was 21.964 K, and it was that high because the background
annulus was itself anomalous: ring median 8.328 K against 1.13 K for a clean
Korean night scene. 의성·안동 was burning 66 km away, inside 영덕's own 30–80 km
ring.

So the non-detection at 영덕 measures the BACKGROUND RING, not the fire, and not
the sensor's sensitivity floor.

⚠ WHAT THIS DOES NOT ESTABLISH. It does not identify the 11.611 K anomaly AS the
fire. Against the clean-night threshold (3.09 K) 217 of 283 steps would clear —
including steps hours before the report — which shows that threshold is far too
permissive for daytime scenes and that clearing it is not evidence of fire. The
honest claim is narrower and is the one the artifact states: the detector AS
SPECIFIED is confounded here, so 영덕's "not detected" is uninformative about
GK2A's floor rather than evidence against it.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
STEPS = REPO / "data" / "processed" / "detection" / "steps" / "yeongdeok_2025.json"
OUT = REPO / "data" / "processed" / "detection" / "yeongdeok_background_contamination.json"

K_SIGMA = 4.0
DELTA_FLOOR_K = 3.0

#: Measured clean Korean night scene, reported in docs/detection_floor.md §3.
CLEAN_BG_MEDIAN_K = 1.13
CLEAN_BG_MAD_SD_K = 0.49


def threshold(median_k: float, mad_sd_k: float) -> float:
    return max(median_k + K_SIGMA * mad_sd_k, DELTA_FLOOR_K)


def main() -> int:
    d = json.loads(STEPS.read_text(encoding="utf-8"))
    ref = d["reference_time_utc"]
    steps = [s for s in d["steps"]
             if "bg_delta_median_k" in s and s.get("target_delta_max_k") is not None]

    thr = np.array([threshold(s["bg_delta_median_k"], s["bg_delta_mad_sd_k"])
                    for s in steps], dtype="float64")
    tmax = np.array([s["target_delta_max_k"] for s in steps], dtype="float64")

    best = int(np.argmax(tmax))
    b = steps[best]
    clean_thr = threshold(CLEAN_BG_MEDIAN_K, CLEAN_BG_MAD_SD_K)

    out = {
        "what": (
            "Why 영덕 produced no flag, re-derived from the committed per-step "
            "records. Supersedes an earlier draft claim that cited target-zone "
            "statistics which no artifact contains."),
        "reference_time_utc": ref,
        "n_steps_total": len(d["steps"]),
        "n_steps_with_background_stats": len(steps),
        "strongest_anomaly": {
            "time_utc": b["time"],
            "minutes_after_reference": 28,
            "target_delta_max_k": round(float(b["target_delta_max_k"]), 3),
            "contextual_threshold_k": round(float(thr[best]), 3),
            "shortfall_k": round(float(thr[best] - tmax[best]), 3),
            "bg_delta_median_k": round(float(b["bg_delta_median_k"]), 3),
            "bg_delta_mad_sd_k": round(float(b["bg_delta_mad_sd_k"]), 3),
            "target_frac_below_cloud_bt": b.get("target_frac_below_cloud_bt"),
        },
        "background_ring_was_itself_anomalous": {
            "ring_median_at_best_step_k": round(float(b["bg_delta_median_k"]), 3),
            "clean_night_scene_median_k": CLEAN_BG_MEDIAN_K,
            "clean_night_scene_mad_sd_k": CLEAN_BG_MAD_SD_K,
            "ratio_ring_median_to_clean": round(
                float(b["bg_delta_median_k"]) / CLEAN_BG_MEDIAN_K, 2),
            "cause": (
                "의성·안동 2025 ignited the same day 66 km away — inside 영덕's "
                "own 30-80 km background annulus — and burned at ΔT ≈ 67 K."),
        },
        "threshold_range_over_run": {
            "min_k": round(float(thr.min()), 3),
            "median_k": round(float(thr.median() if hasattr(thr, "median")
                                    else np.median(thr)), 3),
            "max_k": round(float(thr.max()), 3),
            "n_steps_at_absolute_floor": int((thr <= DELTA_FLOOR_K + 1e-9).sum()),
        },
        "counterfactual_clean_background": {
            "clean_threshold_k": round(clean_thr, 3),
            "strongest_anomaly_exceeds_clean_threshold_by_k": round(
                float(tmax[best] - clean_thr), 3),
            "would_have_flagged": bool(tmax[best] > clean_thr),
            "n_steps_clearing_clean_threshold": int((tmax > clean_thr).sum()),
            "⚠_why_that_count_is_not_evidence_of_fire": (
                "217 of 283 steps clear it, including steps hours BEFORE the "
                "report time. A 3.09 K threshold is far too permissive for a "
                "daytime scene, where solar reflection alone puts background "
                "contrast at +6 to +8 K. Clearing it is not evidence of fire."),
        },
        "conclusion": (
            "영덕's non-detection measures the BACKGROUND ANNULUS, not the fire "
            "and not GK2A's sensitivity floor. The strongest target anomaly "
            "(11.611 K) arrives +28 min after the recorded report time and is "
            "suppressed by a threshold (21.964 K) inflated by a second fire "
            "66 km away. ⚠ This does NOT identify that anomaly as the fire, and "
            "it does NOT convert 영덕 into a detection: no detection is claimed "
            "for 영덕 anywhere. It removes 영덕 from the evidence base as "
            "CONFOUNDED rather than leaving it as a null."),
        "supersedes": (
            "The draft claim '문턱 탓이 아닙니다' with target-zone statistics "
            "5.09 / 0.89 / 8.65 / 7.34 K. Those four numbers appear in NO "
            "committed artifact and are withdrawn."),
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")
    print(json.dumps({k: out[k] for k in
                      ("strongest_anomaly", "counterfactual_clean_background")},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
