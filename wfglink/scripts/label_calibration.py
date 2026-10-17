#!/usr/bin/env python3
"""Score the blind labellers against hidden truth, and the two C5 labellers against each other.

Before labelling real tiles, every labeller labelled the same twelve synthetic tiles
(results/labels/calibration: six faint tiles from the core suite's base case and six bright
ones from its snr-30 case, drawn by `label-tiles` with cal_cfg.yaml, truth from the generator
in truth_labels.csv). This script matches each labeller's sure labels to the truth exactly as
`label-score` matches labels to detections (Hungarian within labels.match_px; unsure labels
are don't care) and reports recall, precision and the position error, per labeller and pooled,
and recall by ember SNR. It also gives the inter-labeller F1 on C5's check tiles.

Usage: .venv/bin/python scripts/label_calibration.py [--record]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wfglink.config import load_config  # noqa: E402
from wfglink.provenance import record_number  # noqa: E402
from wfglink.validate.labels import inter_labeler_f1  # noqa: E402
from wfglink.validate.match import match_points  # noqa: E402

CAL = ROOT / "results" / "labels" / "calibration"
C5 = ROOT / "results" / "labels" / "C5"
SCRIPT = "scripts/label_calibration.py"
SNR_BINS = ((0.0, 10.0, "snr_lt10"), (10.0, 20.0, "snr_10_20"), (20.0, np.inf, "snr_ge20"))


def score(truth: pd.DataFrame, labels: pd.DataFrame, match_px: float, min_conf: float) -> dict:
    """Matches per tile; truth matched only by an unsure label is left out (don't care)."""
    lab = labels[labels["x"].notna()]
    sure, unsure = lab[lab["confidence"] >= min_conf], lab[lab["confidence"] < min_conf]
    tp = fp = 0
    err: list[float] = []
    hit_snr: list[tuple[float, bool]] = []
    for tid in sorted(set(truth["tile_id"]) | set(lab["tile_id"])):
        t = truth[(truth["tile_id"] == tid) & truth["x"].notna()]
        txy = t[["x", "y"]].to_numpy(float)
        sxy = sure.loc[sure["tile_id"] == tid, ["x", "y"]].to_numpy(float)
        uxy = unsure.loc[unsure["tile_id"] == tid, ["x", "y"]].to_numpy(float)
        ti, si, _ = match_points(txy, sxy, match_px)
        tp += len(ti)
        fp += len(sxy) - len(ti)
        err += [float(np.hypot(*(txy[a] - sxy[b]))) for a, b in zip(ti, si)]
        rest = np.setdiff1d(np.arange(len(txy)), ti)
        dont_care: set[int] = set()
        if len(rest) and len(uxy):
            ri, _, _ = match_points(txy[rest], uxy, match_px)
            dont_care = set(rest[ri].tolist())
        for k, snr in enumerate(t["snr"].to_numpy(float)):
            if k not in dont_care:
                hit_snr.append((snr, k in set(ti.tolist())))
    n_truth = len(hit_snr)
    out = {"tp": tp, "fp": fp, "fn": n_truth - tp, "recall": tp / n_truth if n_truth else np.nan,
           "precision": tp / (tp + fp) if tp + fp else np.nan,
           "err_med_px": float(np.median(err)) if err else np.nan, "err_p90_px": float(np.percentile(err, 90)) if err else np.nan}
    hs = np.array(hit_snr, dtype=float).reshape(-1, 2)
    for lo, hi, name in SNR_BINS:
        sel = (hs[:, 0] >= lo) & (hs[:, 0] < hi)
        out[f"recall_{name}"] = float(hs[sel, 1].mean()) if sel.any() else np.nan
        out[f"n_{name}"] = int(sel.sum())
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--record", action="store_true", help="write the pooled numbers to results/NUMBERS.json")
    args = ap.parse_args()
    cfg = load_config()
    lc = cfg.get("labels", {})
    match_px, min_conf = float(lc.get("match_px", 3.0)), float(lc.get("min_confidence", 0.75))
    truth = pd.read_csv(CAL / "truth_labels.csv")
    labellers = sorted({p.name.split("_cal_")[0] for p in CAL.glob("L*_cal_*.csv")})
    rows = []
    for cs in ("base", "snr-30"):
        t = truth[truth["set"] == cs]
        pooled = []
        for lab in labellers:
            labels = pd.read_csv(CAL / f"{lab}_cal_{cs}.csv")
            rows.append({"labeller": lab, "set": cs, **score(t, labels, match_px, min_conf)})
            pooled.append(labels.assign(tile_id=lab + ":" + labels["tile_id"].astype(str)))
        tp_all = pd.concat([t.assign(tile_id=lab + ":" + t["tile_id"].astype(str)) for lab in labellers])
        rows.append({"labeller": "pooled", "set": cs, **score(tp_all, pd.concat(pooled), match_px, min_conf)})
    df = pd.DataFrame(rows)
    df.to_csv(CAL / "scores.csv", index=False)
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(df.round(3).to_string(index=False))
    il = inter_labeler_f1(C5 / "labels_agent.csv", C5 / "labels_agent_check.csv", cfg=cfg, manifest=C5 / "manifest.csv",
                          tags=("agent-labeled", "agent-labeled (second labeller)"))
    print(f"C5 inter-labeller F1 {il['f1']['value']:.3f} on {il['tiles']} tiles ({il['matches']} matches)")
    if args.record:
        inputs = {"truth": CAL / "truth_labels.csv", **{p.name: p for p in sorted(CAL.glob("L*_cal_*.csv"))}}
        names = {"base": "faint", "snr-30": "bright"}
        for cs, nm in names.items():
            r = df[(df["labeller"] == "pooled") & (df["set"] == cs)].iloc[0]
            what = f"{nm} synthetic calibration tiles (core suite {cs}), all labellers pooled"
            record_number(f"labels.calibration.{nm}.recall", round(float(r["recall"]), 4), "fraction",
                          f"Labeller recall of true embers on the {what}", script=SCRIPT, config=cfg, inputs=inputs)
            record_number(f"labels.calibration.{nm}.precision", round(float(r["precision"]), 4), "fraction",
                          f"Labeller precision on the {what}", script=SCRIPT, config=cfg, inputs=inputs)
            record_number(f"labels.calibration.{nm}.err_med_px", round(float(r["err_med_px"]), 2), "px",
                          f"Median position error of matched labels on the {what}", script=SCRIPT, config=cfg, inputs=inputs)
        both = pd.concat([df[(df["labeller"] == "pooled")]])
        for _, _, name in SNR_BINS:
            n = both[f"n_{name}"].sum()
            rec = float((both[f"recall_{name}"].fillna(0) * both[f"n_{name}"]).sum() / n) if n else float("nan")
            if n:
                record_number(f"labels.calibration.recall_{name}", round(rec, 4), "fraction",
                              f"Labeller recall of true embers with SNR in bin {name}, calibration tiles pooled",
                              script=SCRIPT, config=cfg, inputs=inputs)
        record_number("labels.C5.inter_labeler_f1", round(float(il["f1"]["value"]), 4), "fraction",
                      "F1 between two agent labellers on C5's check tiles (first five frames of the draw)",
                      script=SCRIPT, config=cfg, inputs={"a": C5 / "labels_agent.csv", "b": C5 / "labels_agent_check.csv"})
        print("recorded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
