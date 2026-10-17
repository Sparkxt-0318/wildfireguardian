"""Development comparison on C5 (precision evaluation of 2026-10-17): baseline and families A, B, C.

Every candidate of the predeclared grids (rules at each q, patch and temporal at each seed and
threshold, the accept_all control) is replayed on the C5 accept_all dump (verify/replay.py:
the same detections, tracks and features for all). Each candidate's accepted observations (the
points drawn as accepted, as the high-precision frame-level pseudo-run holds them) are scored
with the unchanged label-score settings on the 40 scored C5 tiles; the legacy baseline is the
dump's raw detections scored the same way. Tracks near those tiles were excluded from training
(verify dataset --exclude-tiles), but C5 is the development recording of every family, so this
is development evidence with agent labels (PROVISIONAL), never a test.

    python scripts/precision_dev_compare.py --out results/runs/precision_20261017/dev_compare
        [--validation results/validation/precision_20261017/dev/c5_dev_comparison.json]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
RUN = ROOT / "results/runs/precision_20261017/runs/C5_dump"
DATASET = ROOT / "results/runs/precision_20261017/dataset_c5"
TRAIN_REPORT = ROOT / "results/runs/precision_20261017/train/train_report.json"
MODELS = ROOT / "data/models/verify"
TILES = ROOT / "results/labels/C5"
LABELS = TILES / "labels_agent.csv"


def pseudo_run(dst: Path, shown: list[tuple[int, int]], name: str) -> None:
    """The frame-level pseudo-run of process.py for a replayed candidate."""
    dst.mkdir(parents=True, exist_ok=True)
    det = pd.read_parquet(RUN / "detections.parquet")
    if len(det) and shown:
        j = det.groupby("frame").cumcount().to_numpy()
        key = pd.MultiIndex.from_arrays([det["frame"].to_numpy(np.int64), j])
        det = det[key.isin(pd.MultiIndex.from_tuples(shown))]
    else:
        det = det.iloc[0:0]
    det.to_parquet(dst / "detections.parquet", index=False)
    fr = pd.read_parquet(RUN / "high_precision" / "frame_level" / "frames.parquet")
    n_by = det.groupby("frame").size() if len(det) else pd.Series(dtype=np.int64)
    fr["detections"] = fr["frame"].map(n_by).fillna(0).astype(np.int64)
    fr.to_parquet(dst / "frames.parquet", index=False)
    s = json.loads((RUN / "high_precision" / "frame_level" / "summary.json").read_text())
    s["pseudo_run"] = {**s.get("pseudo_run", {}), "method": name, "replayed": True}
    (dst / "summary.json").write_text(json.dumps(s, indent=1, default=str))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--validation", default=None)
    a = ap.parse_args(argv)
    import yaml

    from wfglink.provenance import git_state, now_shanghai, sha256_file
    from wfglink.validate.labels import score_labels
    from wfglink.verify.calibrate import build_candidates, rule_candidates
    from wfglink.verify.config import hp_config
    from wfglink.verify.dataset import load_dataset
    from wfglink.verify.replay import confirmation_delays, load_dump, replay_many

    draft = yaml.safe_load((ROOT / "results/validation/precision_20261017/protocol_draft.yaml").read_text())
    grids = draft["selection"]["grids"]
    cfg = hp_config("accept_all")
    ds = load_dataset(DATASET)
    pos = ds["tracks"][ds["tracks"]["label"] == 1]
    rules = rule_candidates(pos, grids["rules_q"])
    rep = json.loads(TRAIN_REPORT.read_text())
    dups: list = []
    cands = build_candidates(rules, MODELS, cfg, "file_native", grids["model_threshold"],
                             {"patch": (0, 1), "temporal": (0, 1)}, ("accept_all", "rules", "patch", "temporal"),
                             sha256_file(DATASET / "dataset.json"), rep, dups)
    dump = load_dump(RUN)
    res = replay_many(dump, {n: c["scorer"] for n, c in cands.items()}, cfg, "file_native", strict_config=False)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    minutes = float(json.loads((RUN / "high_precision" / "hp_summary.json").read_text())["totals"]["supported_s"]) / 60
    base = score_labels(TILES, LABELS, RUN)
    rows = [{"name": "legacy_raw_detections", "family": "baseline", "tp": base["tp"], "fp": base["fp"], "fn": base["fn"],
             "precision": base["precision"]["value"], "recall": base["recall"]["value"], "accepted_tracks": None}]
    for name, c in cands.items():
        r = res[name]
        d = out / "pseudo" / name
        pseudo_run(d, r.observer.shown_detections(), name)
        sc = score_labels(TILES, LABELS, d)
        acc = len(r.accepted_ids())
        dl = confirmation_delays(r)
        rows.append({"name": name, "family": c["family"], "seed": c.get("seed"), "param": c.get("param"),
                     "available": bool(getattr(c["scorer"], "available", True)),
                     "unavailable": getattr(c["scorer"], "reason", None),
                     "tp": sc["tp"], "fp": sc["fp"], "fn": sc["fn"], "precision": sc["precision"]["value"],
                     "precision_ci": sc["precision"]["ci"], "recall": sc["recall"]["value"],
                     "recall_ci": sc["recall"]["ci"], "accepted_tracks": acc,
                     "accepted_tracks_per_min": acc / minutes if minutes else None, "crossings": int(len(r.events)),
                     "median_confirm_to_accept_s": float(np.median(dl)) if dl.size else None})
        shutil.rmtree(d)
    rec = {"schema_version": 1, "created": now_shanghai(), "tag": "development, agent labels, PROVISIONAL",
           "recording": "C5_nist_emberometer (development)", "run": str(RUN.relative_to(ROOT)),
           "labels": str(LABELS.relative_to(ROOT)), "labels_sha256": sha256_file(LABELS),
           "score": "validate.labels.score_labels, unchanged settings (3 px, unsure labels don't care)",
           "baseline_note": ("legacy_raw_detections is the dump's raw detections, the same detector output as the "
                             "Linux reproduction of the f9e72c2 baseline; the Mac record (FP 168) is kept separately "
                             "(c5_baseline_discrepancy.json)"),
           "training_exclusion": "tracks within 16 px and 1 s of the 40 scored tiles were excluded from training",
           "dataset_json_sha256": sha256_file(DATASET / "dataset.json"), "train_report_sha256": sha256_file(TRAIN_REPORT),
           "duplicate_models": dups, "replay_notes": list(dump.notes), "supported_minutes": minutes,
           "rows": rows, **git_state()}
    (out / "c5_dev_comparison.json").write_text(json.dumps(rec, indent=1, default=str) + "\n")
    if a.validation:
        Path(a.validation).write_text(json.dumps(rec, indent=1, default=str) + "\n")
    for r in rows:
        print(f"{r['name']:28} tp {r['tp']:3} fp {r['fp']:4} fn {r['fn']:3} "
              f"precision {r['precision'] if r['precision'] is None else round(r['precision'], 3)} "
              f"recall {r['recall'] if r['recall'] is None else round(r['recall'], 3)} accepted {r['accepted_tracks']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
