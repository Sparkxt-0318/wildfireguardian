"""Survey-timing leak bound, arms L and L2 (LEAK_BOUND_PLAN.md rev 1-4 @ claude/s-d9-leakbound (rev 4: interval cap 0)).
Part-a fire folds only. Arm R is NOT RUN (rev 1 item 2). Descriptive; "material" per rev 1.

Stages (checkpointed; re-running the identical command resumes):
  extract  per fire, cached to RUN/cache/<fire>.npz: every masked cell of every cropped part-a interval
           (pipeline.perimeter_samples(crop=False) -> pipeline.cropped), base features (pipeline.logistic_features),
           y, dist_m (cropped grid), interval F1; plus new-burn cells outside the crop.
  fit      ONE keep-draw over all entries (fire-id sort, interval, row-major; default_rng(0), 0.05); per fold k:
           StandardScaler(sample_weight) + LogisticRegression(max_iter=3000, random_state=0) for base / L (+F1) /
           L2 (+F1,+F2) on the 4 other folds; models -> RUN/fold_<k>.pkl.
  score    per held-out fire: per-fire aggregates (band <= 4000 m and full) -> RUN/fold_<k>_agg.json.
  report   whole-fire bootstrap (B=2000, default_rng(20261030)) -> RUN/LEAK_BOUND.json and RUN/LEAK_BOUND.md.

    python run_leakbound_L.py --data-root WS/data/environment --pins PINS.json --perimeters WS/data/perimeters \
        --folds FOLDS.csv --times PARTA_TIMES.csv --work W --run RUN --stop-at 2026-11-13T23:30:00Z [--limit N]

--limit N (smoke): extract only the first N fires (sorted) and stop; no fit, no score.
--stop-at: before each fire and each fold, if now >= stop-at, write RUN/STOPPED.json and exit 3 (NOT COMPLETE).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import importlib.util
import json
import pickle
import platform
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
SCRIPTS = REPO / "research/forecast-v2/scripts"
CELL_M = 375.0
BAND_M = 4000.0
NEG_FRAC = 0.05
KEEP_SEED = 0
BOOT_B = 2000
BOOT_SEED = 20261030
ARMS = ("base", "L", "L2")
BASE_LABEL = "base = logistic_rebuilt recipe refit on the other 4 part-a folds; NOT the A1 logistic_rebuilt object"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def utc(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def f1_value(cutoff_iso, last_utc):
    r = max(0.0, (utc(last_utc) - utc(cutoff_iso)).total_seconds()) / 86400.0
    return float(np.log1p(r))


def f2_value(first_utc, last_utc, surveys):
    span = (utc(last_utc) - utc(first_utc)).total_seconds() / 86400.0
    return float(np.log1p(int(surveys) / max(1.0, span)))


def columns(arm, x, f1, f2):
    if arm == "base":
        return x
    if arm == "L":
        return np.column_stack([x, f1])
    return np.column_stack([x, f1, f2])


def draw_keep(ys, seed=KEEP_SEED, frac=NEG_FRAC):
    """One uniform per entry, drawn once over fires in the given (sorted) order: identical to one global draw."""
    rng = np.random.default_rng(seed)
    return [(y == 1) | (rng.random(len(y)) < frac) for y in ys]


def fit_models(train, frac=NEG_FRAC):
    """train: dict x, y, f1, f2 (kept rows only). Returns {arm: (scaler, model)}; the command_baselines recipe."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    w = np.where(train["y"] == 1, 1.0, 1.0 / frac)
    out = {}
    for arm in ARMS:
        X = columns(arm, train["x"], train["f1"], train["f2"])
        scaler = StandardScaler().fit(X, sample_weight=w)
        model = LogisticRegression(max_iter=3000, random_state=0)
        model.fit(scaler.transform(X), train["y"].astype(int), sample_weight=w)
        out[arm] = (scaler, model)
    return out


def predict(fitted, arm, x, f1, f2):
    scaler, model = fitted[arm]
    return model.predict_proba(scaler.transform(columns(arm, x, f1, f2)))[:, 1]


def aggregate(y, band, preds):
    """Per-fire sufficient statistics for band and full domain."""
    y = y.astype(np.float64)
    out = {}
    for dom, m in (("band", band), ("full", np.ones(len(y), bool))):
        d = dict(n=int(m.sum()), sum_y=float(y[m].sum()))
        for arm, p in preds.items():
            pm, ym = p[m], y[m]
            low = pm < 0.1
            d[arm] = dict(sse=float(((pm - ym) ** 2).sum()), calib_n=int(low.sum()),
                          calib_sum_p=float(pm[low].sum()), calib_sum_y=float(ym[low].sum()))
        out[dom] = d
    return out


def bootstrap(per_fire, arm, dom, B=BOOT_B, seed=BOOT_SEED):
    fires = sorted(per_fire)
    n = np.array([per_fire[f][dom]["n"] for f in fires], float)
    sb = np.array([per_fire[f][dom]["base"]["sse"] for f in fires])
    sa = np.array([per_fire[f][dom][arm]["sse"] for f in fires])
    point = (sa.sum() - sb.sum()) / n.sum()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(fires), size=(B, len(fires)))
    boot = (sa[idx].sum(1) - sb[idx].sum(1)) / n[idx].sum(1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    base_brier = sb.sum() / n.sum()
    pf = [(per_fire[f][dom][arm]["sse"] - per_fire[f][dom]["base"]["sse"]) / per_fire[f][dom]["n"]
          for f in fires if per_fire[f][dom]["n"] > 0]
    return dict(delta_brier=float(point), ci95=[float(lo), float(hi)], material=bool(hi < 0),
                brier_base=float(base_brier), brier_aug=float(sa.sum() / n.sum()),
                relative_change=float(point / base_brier) if base_brier else None,
                per_fire_delta_quantiles={q: float(np.quantile(pf, q)) for q in (0.05, 0.25, 0.5, 0.75, 0.95)},
                fires=len(fires), cells=int(n.sum()))


def calib(per_fire, arm, dom):
    c = sum(per_fire[f][dom][arm]["calib_n"] for f in per_fire)
    sp = sum(per_fire[f][dom][arm]["calib_sum_p"] for f in per_fire)
    sy = sum(per_fire[f][dom][arm]["calib_sum_y"] for f in per_fire)
    return dict(n=c, mean_p=sp / c if c else None, mean_y=sy / c if c else None, gap=(sp - sy) / c if c else None)


def stop_check(a):
    if a.stop_at and dt.datetime.now(dt.timezone.utc) >= utc(a.stop_at):
        (a.run / "STOPPED.json").write_text(json.dumps(dict(stopped_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                                                             status="NOT COMPLETE (no result)")) + "\n")
        print("STOPPED: NOT COMPLETE", flush=True)
        sys.exit(3)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for k in ("--data-root", "--pins", "--perimeters", "--folds", "--times", "--work", "--run"):
        ap.add_argument(k, type=Path, required=True)
    ap.add_argument("--stop-at", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--threads", type=int, default=2)
    a = ap.parse_args()
    a.run.mkdir(parents=True, exist_ok=True)
    (a.run / "cache").mkdir(exist_ok=True)
    sys.path.insert(0, str(SCRIPTS))
    sys.path.insert(0, str(REPO / "forecast"))
    import torch
    torch.set_num_threads(a.threads)
    from scipy.ndimage import distance_transform_edt
    spec = importlib.util.spec_from_file_location("full_cohort_pipeline", SCRIPTS / "pipeline.py")
    P = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = P
    spec.loader.exec_module(P)

    folds = {r["Incident_C"]: int(r["fold"]) for r in csv.DictReader(a.folds.open())}
    times = {r["Incident_C"]: r for r in csv.DictReader(a.times.open())}
    fires = sorted(folds)
    if set(fires) != set(times):
        raise SystemExit("FOLDS and PARTA_TIMES fire sets differ")
    receipt = dict(plan="LEAK_BOUND_PLAN.md rev 1-4 (claude/s-d9-leakbound)", interval_cap="all eligible intervals <= 48 h per fire (cap 0; rev 4)", arms_run=list(ARMS[1:]),
                   arm_R="NOT RUN (no fold-held-out d4_wind_rebuilt predictions; rev 1 item 2)",
                   script_sha256=sha(__file__), pipeline_sha256=sha(SCRIPTS / "pipeline.py"),
                   pins_sha256=sha(a.pins), folds_sha256=sha(a.folds), times_sha256=sha(a.times),
                   perimeter_manifest_sha256=sha(a.perimeters / "PERIMETER_MANIFEST.json"),
                   fires=len(fires), host=dict(python=platform.python_version(), numpy=np.__version__))
    first = a.run / "RECEIPT_START.json"
    pinned = ("script_sha256", "pipeline_sha256", "pins_sha256", "folds_sha256", "times_sha256", "perimeter_manifest_sha256")
    if first.exists():  # resume: refuse unless every input and code sha equals the first start's
        prev = json.loads(first.read_text())
        diff = [k for k in pinned if prev.get(k) != receipt[k]]
        if diff:
            raise SystemExit(f"RESUME REFUSED: inputs or code differ from RECEIPT_START.json: {diff}")
        n = len(list(a.run.glob("RECEIPT_RESUME_*.json"))) + 1
        (a.run / f"RECEIPT_RESUME_{n}.json").write_text(json.dumps(dict(resumed_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                                                                         same_as_start=list(pinned))) + "\n")
    else:
        first.write_text(json.dumps(dict(receipt, started_utc=dt.datetime.now(dt.timezone.utc).isoformat()), indent=1) + "\n")

    # ---- extract (cached per fire)
    todo = fires[:a.limit] if a.limit else fires
    missing = [ev for ev in todo if not (a.run / "cache" / f"{ev}.npz").exists()]
    env = P.Environment(a.data_root, a.work / "env", input_sha256=json.loads(a.pins.read_text())) if missing else None
    for ev in missing:
        cpath = a.run / "cache" / f"{ev}.npz"
        stop_check(a)
        t0 = time.perf_counter()
        xs, ys, ds, f1s, ivs = [], [], [], [], []
        outside = newburn = band_unc = band_unc_in = 0
        grad = env.terrain_gradient(ev)
        for k, s in enumerate(P.perimeter_samples(ev, a.perimeters, env, crop=False)):
            nb = s.endpoint & ~s.initial
            cs = P.cropped(s)
            r0, r1, c0, c1 = cs.meta["crop"]
            du = (distance_transform_edt(~s.initial) * CELL_M if s.initial.any() else np.full(s.initial.shape, np.inf))
            bu = s.score_mask & (du <= BAND_M)
            band_unc += int(bu.sum())
            band_unc_in += int(bu[r0:r1, c0:c1].sum())
            nb_in = int((cs.endpoint & ~cs.initial).sum())
            newburn += int(nb.sum())
            outside += int(nb.sum()) - nb_in
            feats = P.logistic_features(cs, env.names, grad)
            mask = cs.score_mask.ravel() & np.isfinite(cs.environment).all(axis=0).ravel() & np.isfinite(feats).all(axis=1)
            dist = (distance_transform_edt(~cs.initial) * CELL_M if cs.initial.any()
                    else np.full(cs.initial.shape, np.inf))
            xs.append(feats[mask])
            ys.append(cs.endpoint.ravel()[mask].astype(np.int8))
            ds.append(dist.ravel()[mask].astype(np.float32))
            f1s.append(np.full(int(mask.sum()), f1_value(s.t1, times[ev]["last_utc"])))
            ivs.append(np.full(int(mask.sum()), k, np.int32))
        cat = (lambda v, dt_: np.concatenate(v) if v else np.zeros(0, dt_))
        np.savez_compressed(cpath, x=np.concatenate(xs) if xs else np.zeros((0, 21)), y=cat(ys, np.int8), dist_m=cat(ds, np.float32),
                 f1=cat(f1s, np.float64), interval=cat(ivs, np.int32),
                 f2=np.float64(f2_value(times[ev]["first_utc"], times[ev]["last_utc"], times[ev]["surveys"])),
                 intervals=np.int32(len(xs)), newburn=np.int64(newburn), newburn_outside_crop=np.int64(outside),
                 band_uncropped=np.int64(band_unc), band_uncropped_inside_crop=np.int64(band_unc_in))
        print(json.dumps(dict(fire=ev, intervals=len(xs), cells=int(sum(len(y) for y in ys)),
                              seconds=round(time.perf_counter() - t0, 1))), flush=True)
    if a.limit:
        print(json.dumps(dict(smoke="extract only", fires=len(todo))), flush=True)
        return

    # ---- fit: one keep-draw over all entries in fire-id order
    stop_check(a)
    ys_all = [np.load(a.run / "cache" / f"{ev}.npz")["y"] for ev in fires]
    keep = draw_keep(ys_all)
    keep_sha = hashlib.sha256(np.concatenate(keep).astype(np.uint8).tobytes()).hexdigest()
    for k in range(5):
        fpath, apath = a.run / f"fold_{k}.pkl", a.run / f"fold_{k}_agg.json"
        if apath.exists():
            continue
        stop_check(a)
        if not fpath.exists():
            tr = dict(x=[], y=[], f1=[], f2=[])
            for ev, kp in zip(fires, keep):
                if folds[ev] == k or not kp.any():
                    continue
                z = np.load(a.run / "cache" / f"{ev}.npz")
                tr["x"].append(z["x"][kp]); tr["y"].append(z["y"][kp]); tr["f1"].append(z["f1"][kp])
                tr["f2"].append(np.full(int(kp.sum()), float(z["f2"])))
            tr = {key: np.concatenate(v) for key, v in tr.items()}
            fitted = fit_models(tr)
            fpath.write_bytes(pickle.dumps(dict(fitted=fitted, train_rows=int(len(tr["y"])),
                                                train_positives=int(tr["y"].sum()))))
        fitted = pickle.loads(fpath.read_bytes())["fitted"]
        agg = {}
        for ev in fires:
            if folds[ev] != k:
                continue
            z = np.load(a.run / "cache" / f"{ev}.npz")
            if len(z["y"]) == 0:
                continue
            f2 = np.full(len(z["y"]), float(z["f2"]))
            preds = {arm: predict(fitted, arm, z["x"], z["f1"], f2) for arm in ARMS}
            agg[ev] = dict(aggregate(z["y"], z["dist_m"] <= BAND_M, preds), base_label=BASE_LABEL)
        coef = {arm: dict(standardised=fitted[arm][1].coef_[0].tolist(),
                          f1_raw=(float(fitted[arm][1].coef_[0][21] / fitted[arm][0].scale_[21]) if arm != "base" else None))
                for arm in ARMS}
        apath.write_text(json.dumps(dict(fold=k, per_fire=agg, coefficients=coef), indent=1) + "\n")
        print(json.dumps(dict(fold=k, held_out_fires=len(agg))), flush=True)

    # ---- report
    per_fire, coefs = {}, {}
    for k in range(5):
        d = json.loads((a.run / f"fold_{k}_agg.json").read_text())
        per_fire.update(d["per_fire"])
        coefs[k] = d["coefficients"]
    meta = {ev: np.load(a.run / "cache" / f"{ev}.npz") for ev in fires}
    bu = {ev: (int(m["band_uncropped"]), int(m["band_uncropped_inside_crop"])) for ev, m in meta.items()}
    bu_tot = sum(v[0] for v in bu.values())
    res = dict(receipt, finished_utc=dt.datetime.now(dt.timezone.utc).isoformat(), base_label=BASE_LABEL,
               keep_vector_sha256=keep_sha, keep_rows=int(sum(int(k.sum()) for k in keep)),
               band_truncation=dict(
                   note="share of UNCROPPED 4 km band cells (score_mask, distance on the uncropped grid) outside the crop",
                   overall=(bu_tot - sum(v[1] for v in bu.values())) / bu_tot if bu_tot else None,
                   per_fire={ev: ((v[0] - v[1]) / v[0] if v[0] else None) for ev, v in sorted(bu.items())}),
               fold_assignment_sha256=sha(a.folds),
               newburn_cells=int(sum(int(m["newburn"]) for m in meta.values())),
               newburn_outside_crop=int(sum(int(m["newburn_outside_crop"]) for m in meta.values())),
               fires_scored=len(per_fire), fires_with_no_cells=sorted(set(fires) - set(per_fire)),
               arms={arm: {dom: dict(bootstrap(per_fire, arm, dom), calibration_lt_0_1=dict(
                   base=calib(per_fire, "base", dom), augmented=calib(per_fire, arm, dom)))
                   for dom in ("band", "full")} for arm in ("L", "L2")},
               f1_coefficient_by_fold={k: {arm: coefs[k][arm]["f1_raw"] for arm in ("L", "L2")} for k in coefs},
               material_rule="95% interval of paired dBrier entirely below 0 in the 4 km band, arm L (primary)",
               per_fire=per_fire)
    (a.run / "LEAK_BOUND.json").write_text(json.dumps(res, indent=1) + "\n")
    L = res["arms"]["L"]["band"]
    (a.run / "LEAK_BOUND.md").write_text(
        f"# Survey-timing leak bound, arms L/L2 (part a, 5 fire folds)\n\n"
        f"{BASE_LABEL}.\n\nArm R: NOT RUN. Arm L (primary), 4 km band: dBrier {L['delta_brier']:.3e}, 95% CI "
        f"[{L['ci95'][0]:.3e}, {L['ci95'][1]:.3e}], material = {L['material']}; relative change "
        f"{L['relative_change']:.3%}. L2 band: dBrier {res['arms']['L2']['band']['delta_brier']:.3e}, CI "
        f"{res['arms']['L2']['band']['ci95']}. New-burn cells outside the crop: {res['newburn_outside_crop']} of "
        f"{res['newburn_cells']}. Uncropped 4 km band cells outside the crop: {res['band_truncation']['overall']}.\n")
    if (a.run / "STOPPED.json").exists():  # a resumed run that completes supersedes an earlier clean stop
        (a.run / "STOPPED.json").rename(a.run / "STOPPED_superseded.json")
    print(json.dumps(dict(L_band=L, material=L["material"])), flush=True)


if __name__ == "__main__":
    main()
