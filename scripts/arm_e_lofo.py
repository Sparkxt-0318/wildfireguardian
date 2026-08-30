#!/usr/bin/env python
"""Leave-one-fire-out for Arm E, under Arm A's protocol (Session 12 Phase 2c).

Same transcription of ``spread_v2.model.leave_one_fire_out`` that Session 10's
Arm D runner used, with the feature list as a parameter. Arm A's function is
left alone. Run with ``--features A`` on the SAME dataset to get a like-for-like
Arm A baseline computed by identical code on this platform — that, and not the
committed Arm A artifact, is what an Arm E delta must be measured against,
because the committed values were produced on the reference environment and the
platform floor is 0.0064 pooled / 0.0307 far-band.

Adds the pre-registered STRATIFIED evaluation: the same metrics computed
separately for gentle and steep terrain, split at Session 11's split point under
the Phase 1 native slope definition. Session 11 measured that observed spread
bearing tracks upslope bearing on steep ground (50.8 deg) and not on gentle
ground (89.4 deg, i.e. chance), so a gentle-stratum null is a CONFIRMATION.

    python scripts/arm_e_lofo.py --features A
    python scripts/arm_e_lofo.py --features E
    python scripts/arm_e_lofo.py --features E --aggregate

Writes ONLY under data/processed/arms/E/ and A_replication_e/.
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

ARM_ROOT = REPO / "data" / "processed" / "arms"
DATASET = ARM_ROOT / "E" / "arm_e_dataset.pkl"

#: Session 11's slope-conditioning split point, recomputed under the Phase 1
#: native effective slope (docs/slope_resolution.json). NOT re-tuned here: it is
#: the pre-registered boundary, adopted as measured.
STEEP_SPLIT_DEG = 18.66

#: The measurement floor from Session 10 (docs/platform_drift.json). A pooled
#: difference below the first, or a far-band difference below the second, is not
#: measurable on this platform.
FLOOR_POOLED = 0.0064
FLOOR_FAR_BAND = 0.0307


#: Arm N — the NULL CONTROL, and the reason this script has three arms.
#:
#: Arm E adds two columns and the pooled AUC moves. But BOTH added features come
#: back indistinguishable from zero in permutation importance, so the movement
#: may be nothing to do with slope: adding any two columns changes the
#: early-stopping validation split and the tree structure, and that alone
#: perturbs the fit. Arm N adds two columns of deterministic noise instead, so
#: the same perturbation happens with no signal in it. If Arm N moves the AUC as
#: much as Arm E does, Arm E's movement is not evidence of a directional slope
#: signal, and the honest reading of the whole arm changes.
NOISE_COLUMNS: tuple[str, ...] = ("noise_a", "noise_b")


def feature_columns(tag: str) -> tuple[str, ...]:
    from wildfireguardian.spread_v2.features import FEATURE_COLUMNS
    from wildfireguardian.spread_v2_arme.features import ARM_E_FEATURE_COLUMNS

    return {"A": FEATURE_COLUMNS,
            "E": FEATURE_COLUMNS + ARM_E_FEATURE_COLUMNS,
            "N": FEATURE_COLUMNS + NOISE_COLUMNS}[tag]


def out_dir(tag: str) -> Path:
    name = {"E": "E", "N": "N_noise_control"}.get(tag, "A_replication_e")
    d = ARM_ROOT / name / "lofo"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_dataset(tag: str = "A"):
    with DATASET.open("rb") as fh:
        ds = pickle.load(fh)
    if tag == "N":
        # Deterministic, row-indexed, drawn once for the whole table so every
        # fold sees the same values — exactly how a real feature behaves.
        rng = np.random.default_rng(20250603)
        for c in NOISE_COLUMNS:
            ds = ds.copy() if c == NOISE_COLUMNS[0] else ds
            ds[c] = rng.standard_normal(len(ds))
    return ds


def _safe_auc(y, p):
    from sklearn.metrics import roc_auc_score

    y = np.asarray(y)
    if len(y) == 0 or y.min() == y.max():
        return None
    return float(roc_auc_score(y, p))


def run_fold(ds, held: str, cols: tuple[str, ...], seed: int) -> dict:
    from wildfireguardian.spread_v2.model import IgnitionModelV2

    train = ds[ds["fire_id"] != held]
    test = ds[ds["fire_id"] == held]
    if train["label"].nunique() < 2 or len(test) == 0:
        return {"fire": held, "auc": None, "skipped": True}

    model = IgnitionModelV2(seed=seed, feature_columns=tuple(cols)).fit(train)
    p = model.predict_proba(test)
    y = test["label"].to_numpy()
    auc = _safe_auc(y, p)

    rng = np.random.default_rng(seed)
    X = test[list(cols)].to_numpy(dtype="float64")
    drops: dict[str, float] = {}
    if auc is not None:
        for j, name in enumerate(cols):
            Xp = X.copy()
            Xp[:, j] = rng.permutation(Xp[:, j])
            ap = _safe_auc(y, model.predict_proba_matrix(Xp))
            drops[name] = (auc - ap) if ap is not None else 0.0

    slope = test["native_slope_deg"].to_numpy()
    band = test["dist_band"].to_numpy()
    steep = slope > STEEP_SPLIT_DEG

    # Stratified permutation importance — the pre-registered test.
    strat_imp: dict[str, dict] = {}
    for label, mask in (("gentle", ~steep), ("steep", steep)):
        sub_auc = _safe_auc(y[mask], p[mask])
        entry = {"n": int(mask.sum()), "positives": int(y[mask].sum()),
                 "auc": sub_auc, "importance": {}}
        if sub_auc is not None and mask.sum() > 0:
            r2 = np.random.default_rng(seed)
            Xs, ys = X[mask], y[mask]
            for j, name in enumerate(cols):
                Xp = Xs.copy()
                Xp[:, j] = r2.permutation(Xp[:, j])
                ap = _safe_auc(ys, model.predict_proba_matrix(Xp))
                entry["importance"][name] = (sub_auc - ap) if ap is not None else 0.0
        strat_imp[label] = entry

    return {
        "fire": held,
        "n_test_rows": int(len(test)), "n_test_positives": int(y.sum()),
        "auc": auc,
        "auc_far": _safe_auc(y[band == "far"], p[band == "far"]),
        "auc_mid": _safe_auc(y[band == "mid"], p[band == "mid"]),
        "permutation_importance": drops,
        "stratified": strat_imp,
        "oof": {"label": y.astype(int).tolist(), "prob": [float(v) for v in p],
                "dist_band": band.tolist(),
                "steep": steep.astype(int).tolist()},
    }


def _imp_table(folds, cols, key=None) -> list[dict]:
    """Row-weighted importance + fold spread, as Arm A aggregates it."""
    rows = []
    for c in cols:
        pairs = []
        for f in folds:
            if f.get("auc") is None:
                continue
            if key is None:
                d, n = f["permutation_importance"].get(c), f["n_test_rows"]
            else:
                s = f["stratified"][key]
                if s["auc"] is None or c not in s["importance"]:
                    continue
                d, n = s["importance"][c], s["n"]
            if d is not None and n:
                pairs.append((d, n))
        if not pairs:
            continue
        d = np.array([a for a, _ in pairs], float)
        w = np.array([b for _, b in pairs], float)
        rows.append({
            "feature": c,
            "weighted_mean_auc_drop": float(np.average(d, weights=w)),
            "fold_mean": float(d.mean()),
            "fold_sd": float(d.std(ddof=1)) if len(d) > 1 else None,
            "fold_min": float(d.min()), "fold_max": float(d.max()),
            "n_folds": len(d),
        })
    rows.sort(key=lambda r: -r["weighted_mean_auc_drop"])
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows


def aggregate(tag: str) -> dict:
    cols = feature_columns(tag)
    folds = [json.loads(p.read_text(encoding="utf-8"))
             for p in sorted(out_dir(tag).glob("fold_*.json"))]
    if not folds:
        raise SystemExit(f"no folds computed for arm {tag}")
    good = [f for f in folds if f.get("auc") is not None]

    y = np.concatenate([np.array(f["oof"]["label"]) for f in good])
    p = np.concatenate([np.array(f["oof"]["prob"]) for f in good])
    band = np.concatenate([np.array(f["oof"]["dist_band"]) for f in good])
    steep = np.concatenate([np.array(f["oof"]["steep"]) for f in good]).astype(bool)

    aucs = {f["fire"]: f["auc"] for f in folds}
    vals = [v for v in aucs.values() if v is not None]

    strat = {}
    for label, mask in (("gentle", ~steep), ("steep", steep)):
        strat[label] = {
            "n": int(mask.sum()), "positives": int(y[mask].sum()),
            "pooled_auc": _safe_auc(y[mask], p[mask]),
            "per_fire_auc": {f["fire"]: f["stratified"][label]["auc"] for f in good},
            "importance_ranking": _imp_table(good, cols, key=label),
        }

    payload = {
        "arm": {"E": "E", "N": "N_noise_control"}.get(tag, "A_replication_e"),
        "provenance": "derived",
        "seed": 20250603,
        "protocol": "leave-one-fire-out over 6 fires, HistGradientBoostingClassifier, "
                    "spread_v2 hyperparameters unchanged",
        "steep_split_deg": STEEP_SPLIT_DEG,
        "slope_source": "native ~30 m SRTM -> 500 m effective slope",
        "n_features": len(cols), "feature_columns": list(cols),
        "n_oof_rows": int(len(y)), "n_oof_positives": int(y.sum()),
        "pooled_auc": _safe_auc(y, p),
        "far_band_auc": _safe_auc(y[band == "far"], p[band == "far"]),
        "mid_band_auc": _safe_auc(y[band == "mid"], p[band == "mid"]),
        "per_fire_auc": aucs,
        "mean_of_folds_auc": float(np.mean(vals)) if vals else None,
        "fold_auc_sd": float(np.std(vals, ddof=1)) if len(vals) > 1 else None,
        "fold_auc_min": float(np.min(vals)) if vals else None,
        "fold_auc_max": float(np.max(vals)) if vals else None,
        "importance_ranking": _imp_table(good, cols),
        "stratified": strat,
    }
    path = out_dir(tag).parent / f"lofo_arm_{tag}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in
                      ("arm", "n_oof_rows", "pooled_auc", "mean_of_folds_auc",
                       "fold_auc_sd", "far_band_auc", "mid_band_auc")}, indent=2))
    print(f"wrote {path}")
    return payload


def compare() -> dict:
    """Arm E against the same-platform Arm A, with the measurement floor applied."""
    a = json.loads((ARM_ROOT / "A_replication_e" / "lofo_arm_A.json")
                   .read_text(encoding="utf-8"))
    e = json.loads((ARM_ROOT / "E" / "lofo_arm_E.json").read_text(encoding="utf-8"))

    def row(name, va, ve, floor):
        d = None if (va is None or ve is None) else ve - va
        return {"arm_A_replication": va, "arm_E": ve, "delta": d,
                "floor": floor,
                "clears_floor": None if d is None else bool(abs(d) > floor),
                "verdict": ("not measurable on this platform" if d is not None
                            and abs(d) <= floor else "exceeds the floor")}

    out = {
        "note": ("Deltas are Arm E minus an Arm A replication computed by the SAME "
                 "code on the SAME platform. The floor is the cross-platform "
                 "reproduction drift measured in Session 10 "
                 "(docs/platform_drift.json); a delta inside it is not a "
                 "measurement, whichever way it points."),
        "pooled_auc": row("pooled", a["pooled_auc"], e["pooled_auc"], FLOOR_POOLED),
        "far_band_auc": row("far", a["far_band_auc"], e["far_band_auc"], FLOOR_FAR_BAND),
        "mid_band_auc": row("mid", a["mid_band_auc"], e["mid_band_auc"], FLOOR_POOLED),
        "mean_of_folds_auc": row("mof", a["mean_of_folds_auc"], e["mean_of_folds_auc"],
                                 FLOOR_POOLED),
        "per_fire": {f: row(f, a["per_fire_auc"].get(f), e["per_fire_auc"].get(f),
                            FLOOR_POOLED) for f in sorted(a["per_fire_auc"])},
        "stratified": {
            s: row(s, a["stratified"][s]["pooled_auc"], e["stratified"][s]["pooled_auc"],
                   FLOOR_POOLED) for s in ("gentle", "steep")},
    }
    path = ARM_ROOT / "E" / "arm_e_vs_a.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in
                      ("pooled_auc", "far_band_auc", "stratified")}, indent=2))
    print(f"wrote {path}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", choices=["A", "E", "N"])
    ap.add_argument("--fold", action="append", default=None)
    ap.add_argument("--aggregate", action="store_true")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--seed", type=int, default=20250603)
    args = ap.parse_args()

    if args.compare:
        compare()
        return 0
    if not args.features:
        ap.error("--features is required unless --compare")
    if args.aggregate:
        aggregate(args.features)
        return 0

    ds = load_dataset(args.features)
    cols = feature_columns(args.features)
    for held in (args.fold or sorted(ds["fire_id"].unique())):
        dest = out_dir(args.features) / f"fold_{held}.json"
        if dest.exists():
            print(f"cached {held}")
            continue
        print(f"fold {held} ({args.features}) ...", flush=True)
        res = run_fold(ds, held, cols, args.seed)
        dest.write_text(json.dumps(res) + "\n", encoding="utf-8")
        print(f"  auc={res.get('auc')} rows={res.get('n_test_rows')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
