"""Generate (if needed) and evaluate a synthetic suite; optionally record numbers.

Usage:
  .venv/bin/python scripts/run_suite.py core [--workers 3] [--set detect.prefilter_sigma_px=1.0 ...]
                                        [--tag name] [--record]

Writes results/runs/suite_<suite>[_<tag>]/eval.json (every clip) and summary.json (per case).
--record writes the per-case medians to results/NUMBERS.json under <suite>.<case>.<metric>;
it refuses unless the run uses the committed default config (no --set), so recorded numbers
always describe the committed method.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import yaml

from wfglink import PROJECT_ROOT
from wfglink.config import load_config
from wfglink.provenance import git_state, record_number
from wfglink.synth.generate import run_suite
from wfglink.validate.suite import SUMMARY_KEYS, evaluate_suite

SCRIPT = "scripts/run_suite.py"
UNITS = {"f1": "fraction", "precision": "fraction", "recall": "fraction", "mota": "fraction",
         "id_switches": "count", "track_speed_med_rel_err": "fraction", "track_speed_bias": "fraction",
         "direction_med_err_deg": "deg", "streak_speed_med_rel_err": "fraction", "exposure_rel_err": "fraction",
         "cpc_gross_rel_err": "fraction", "cpc_gross_in_ci": "fraction", "pnf_rel_err": "fraction", "snr50": "SNR",
         "fp_per_mpx_frame": "per megapixel per frame", "recall_bright": "fraction",
         "track_fp_per_frame": "per frame", "gate_between_bounds": "fraction"}
DESCRIPTIONS = {
    "f1": "Detection F1 (Hungarian match within max(3 px, L/2)), median over seeds",
    "precision": "Detection precision, median over seeds",
    "recall": "Detection recall over visible embers (SNR >= 3 before compression), median over seeds",
    "mota": "CLEAR MOT accuracy of tracks, median over seeds",
    "id_switches": "Track identity switches per clip, median over seeds",
    "track_speed_med_rel_err": "Median absolute relative error of per-point track speed, median over seeds",
    "track_speed_bias": "Median signed relative error of per-point track speed, median over seeds",
    "direction_med_err_deg": "Median direction error of per-point track velocity, median over seeds",
    "streak_speed_med_rel_err": "Median absolute relative error of per-point streak speed, median over seeds",
    "exposure_rel_err": "Relative error of the exposure time estimate, median over seeds",
    "cpc_gross_rel_err": "Relative error of the gross Cumulative Particle Count (gate), median over seeds",
    "cpc_gross_in_ci": "Fraction of clips whose true gross count lies in the reported interval",
    "pnf_rel_err": "Relative error of the Particle Number Flux (projected), median over seeds",
    "snr50": "Ember SNR (matched, before compression) at 50 percent detection completeness, pooled seeds",
    "fp_per_mpx_frame": "False detections (on no ember at all) per megapixel per frame, median over seeds",
    "recall_bright": "Detection recall of embers at or above validate.bright_snr, median over seeds",
    "track_fp_per_frame": "Track points on no ember (CLEAR MOT false positives) per frame, median over seeds",
    "gate_between_bounds": "Fraction of clips whose gross count lies between the bright-ember and all-visible truths",
}


def parse_set(items: list[str]) -> dict:
    over: dict = {}
    for it in items:
        key, val = it.split("=", 1)
        d = over
        parts = key.split(".")
        for p in parts[:-1]:
            d = d.setdefault(p, {})
        d[parts[-1]] = yaml.safe_load(val)
    return over


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("suite")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--set", nargs="*", default=[])
    ap.add_argument("--tag", default="")
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--no-generate", action="store_true")
    a = ap.parse_args()
    suite_yaml = PROJECT_ROOT / "configs" / "suites" / f"{a.suite}.yaml"
    root = PROJECT_ROOT / "data" / "synthetic" / a.suite
    if a.record and (a.set or git_state()["git_dirty"]):
        print("--record needs the committed default config: no --set and a clean source tree", file=sys.stderr)
        return 2
    t0 = time.time()
    if not a.no_generate:
        run_suite(suite_yaml, root, workers=a.workers)
    t_gen = time.time() - t0
    over = parse_set(a.set)
    cfg = load_config(overrides=over) if over else load_config()
    res = evaluate_suite(root, cfg, workers=a.workers)
    out = PROJECT_ROOT / "results" / "runs" / (f"suite_{a.suite}" + (f"_{a.tag}" if a.tag else ""))
    out.mkdir(parents=True, exist_ok=True)
    res["overrides"] = over
    res["seconds"] = {"generate": round(t_gen, 1), "evaluate": round(time.time() - t0 - t_gen, 1)}
    (out / "eval.json").write_text(json.dumps(res, indent=1, default=str))
    (out / "summary.json").write_text(json.dumps(res["cases"], indent=1, default=str))
    keys = ["f1", "precision", "recall", "snr50", "recall_bright", "fp_per_mpx_frame", "mota", "track_fp_per_frame",
            "track_speed_med_rel_err", "direction_med_err_deg", "streak_speed_med_rel_err", "exposure_rel_err",
            "cpc_gross_rel_err", "gate_between_bounds"]
    print("case".ljust(30) + " ".join(k[:9].rjust(9) for k in keys))
    for case, row in res["cases"].items():
        vals = [row.get(k) for k in keys]
        print(case.ljust(30) + " ".join(("" if v is None else f"{v:9.3f}").rjust(9) for v in vals))
    if a.record:
        cfg_path = str(PROJECT_ROOT / "configs" / "default.yaml")
        for case, row in res["cases"].items():
            for name in list(SUMMARY_KEYS) + ["snr50"]:
                v = row.get(name)
                if v is None:
                    continue
                record_number(f"{a.suite}.{case}.{name}", round(float(v), 4), UNITS[name], DESCRIPTIONS[name],
                              script=SCRIPT, config=cfg, config_path=cfg_path,
                              inputs={"suite": str(suite_yaml), "manifest": str(root / "manifest.json")})
        print(f"recorded {a.suite} numbers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
