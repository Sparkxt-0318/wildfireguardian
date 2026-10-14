"""Self-check of the LED turntable analysis on rendered stand-ins with known truth.

This checks the analysis code, not the cameras: the real LED clips come from sitting 1.
Two fixed cases (seeds fixed): a straight camera at 33 1/3 rpm with a long exposure, and a
slightly tilted camera at 45 rpm with a half-frame exposure. Results go to NUMBERS.json
under led_standin.*.

Usage: .venv/bin/python scripts/led_standin_check.py [--out results/runs/led_standin]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from wfglink import PROJECT_ROOT
from wfglink.config import load_config
from wfglink.provenance import record_number
from wfglink.sitting.standins import led_turntable_clip
from wfglink.validate.led import analyse_led_clip

CASES = {
    "straight_33rpm_duty0.9": dict(rpm=33.333, duty=0.9, tilt_ratio=1.0),
    "tilt0.97_45rpm_duty0.5": dict(rpm=45.0, duty=0.5, tilt_ratio=0.97),
}
SCRIPT = "scripts/led_standin_check.py"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(PROJECT_ROOT / "results" / "runs" / "led_standin"))
    ap.add_argument("--no-record", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    cfg_path = str(PROJECT_ROOT / "configs" / "default.yaml")
    report = {}
    for name, case in CASES.items():
        clip = out / f"{name}.mp4"
        truth = led_turntable_clip(clip, seconds=10, size=(1280, 720), fps=30, radii_px=(60, 160, 280), seed=0, **case)
        r = analyse_led_clip([clip], truth["omega_rad_s"], cfg)
        exp_err = (100 * (r["exposure"]["t_exp_ms"] / (1000 * truth["exposure_s"]) - 1)
                   if "t_exp_ms" in r.get("exposure", {}) else None)
        report[name] = {"truth": truth, "result": r, "exposure_error_pct": exp_err}
        print(name, json.dumps({k: r.get(k) for k in ("median_speed_error_pct", "median_speed_error_uncorrected_pct",
                                                      "detection_recall", "detection_precision", "passes")}),
              "exposure error %:", None if exp_err is None else round(exp_err, 2))
        if a.no_record:
            continue
        pre = f"led_standin.{name}."
        common = dict(script=SCRIPT, config=cfg, config_path=cfg_path)
        record_number(pre + "median_speed_error_pct", r["median_speed_error_pct"], "%",
                      "Median over tracks of the relative track-speed error against omega times ring radius, stand-in clip", **common)
        record_number(pre + "median_speed_error_uncorrected_pct", r["median_speed_error_uncorrected_pct"], "%",
                      "Same, before dividing out the derivative filter's circular-motion gain", **common)
        record_number(pre + "detection_recall", r["detection_recall"], "fraction",
                      "Mean per-frame fraction of LED rings with a detection, stand-in clip", **common)
        record_number(pre + "detection_precision", r["detection_precision"], "fraction",
                      "Detections on an LED ring (one per ring per frame) over all detections, stand-in clip", **common)
        if exp_err is not None:
            record_number(pre + "exposure_error_pct", round(exp_err, 2), "%",
                          "Relative error of the exposure estimate (Deming fit of streak length on speed), stand-in clip", **common)
    (out / "report.json").write_text(json.dumps(report, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
