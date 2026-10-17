"""Training of the verifier's model families from a dataset folder (python -m wfglink verify train).

Everything is declared here before any data is seen; nothing is searched.

Family C (temporal): models.LogReg(l2=1.0, max_iter=500) on the window features
(features.WINDOW_NAMES) plus 8 patch statistics, the mean and standard deviation over the
window's patches of their projections on TEMPORAL_PCA_K = 4 principal components (a PCA fit
on the training hit samples only); scorers.temporal_vector builds these inputs, as the
TemporalScorer does at run time.

Family B (patch): models.MLP(hidden=32, lr=1e-3, epochs at most 80, batch 256, l2=1e-4,
seed s, hard_neg_frac=0.5, hard_neg_epoch=5, pos_weight = negatives / positives) on the
PATCH_PCA_K = 48 principal components of the flattened patches (fit on the training hit
samples) plus the 14 hit scalars PATCH_HIT_FEATURES (the estimator standardises all inputs;
scorers.patch_inputs, as the PatchScorer does at run time). Early stopping: patience 10 on
the hit samples of a held-out part of the training block groups (those whose rank among the
sorted training groups is 0 mod 5; no hold-out, and the full 80 epochs, with fewer than two
training groups or held-out hits of one class only), keeping the best epoch; a wall-time cap of max_seconds (600) per fit.
Augmentation of the training hits only (never the held-out ones, each copy in its hit's
group): the 8 dihedral transforms of the patch (the identity at brightness 1, the other 7
each at a brightness factor drawn log-uniformly in [0.8, 1.25] from the seed); brightness
scales the patch's z values (z = 2 sinh(patch), clipped to [-5, 30] again) and snr, and
adds log(factor) to log_flux. A track's score is the mean logit of its window's hits.

Seeds {0, 1}: for both families the seed draws the per-cell cap of negative tracks
(dataset.cap_negatives); for the patch family it also seeds the MLP and the augmentation.

Development estimate: grouped cross-validation over the block groups, N_FOLDS = 5 folds,
fold = rank of the group among the sorted group ids mod 5; out-of-fold track scores give
the ROC AUC (auc, the raw scores of every track) and, per threshold of the protocol grid,
precision and recall at the track level against the reviewed labels. The out-of-fold scores
mirror the run time: a track whose window is outside the fold model's envelope
(scorers.ood, the verify.ood settings of the dataset or the overlay) is not accepted at any
threshold (by_threshold; auc_runtime ranks it lowest; ood_tracks counts them).
train_report.json labels this a development estimate on agent labels (PROVISIONAL), never
an accuracy claim, and lists its caveats (caveats; test_negatives_sharing_a_training_cell
counts the test negatives in a cell that also has training negatives). Then the final
model is fit on all the (capped) training data and saved to
<models_dir>/<profile>/<family>_seed<s>.npz with its sidecar (models.save): training data
hashes, the command line, epochs run, wall time.

The OOD envelope saved with a model (scorers.ood at run time) is the class-balanced median
and MAD of the training windows' ENVELOPE_NAMES (each class weighs one half; _envelope).

Reported with the models: sampling (whether the per-cell cap binds, and whether the seeds
give identical training sets; when they do, the temporal seeds are one model, and
same_as / distinct_models say so), and deterministic (false, with a warning, when any
cross-validation or final fit stopped on the wall-time cap: the epoch it stops at depends
on the machine's load, so its SHA-256 cannot be reproduced).

A dataset whose dataset.json floor says inadequate trains nothing: train_report.json gets
status NOT_RUN and the reason.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np

from wfglink.verify.features import FEATURE_NAMES, WINDOW_NAMES

FAMILIES = ("temporal", "patch")
SEEDS = (0, 1)
N_FOLDS = 5
TEMPORAL_PCA_K = 4
PATCH_PCA_K = 48
PATCH_HIT_FEATURES = ("snr", "log_flux", "area", "width", "length", "sat_frac", "color", "color_nan", "scale",
                      "bg_luma", "bg_grad", "large_near", "codec", "density")
THRESHOLDS = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98, 0.99)
ENVELOPE_NAMES = ("snr_med", "speed_med", "bg_luma_med", "bg_grad_med", "codec_med", "density_med", "ctx_change_med",
                  "pre_presence_med", "large_near_max")
TEMPORAL = {"l2": 1.0, "max_iter": 500}
PATCH = {"hidden": 32, "lr": 1e-3, "epochs": 80, "batch_size": 256, "l2": 1e-4, "hard_neg_frac": 0.5,
         "hard_neg_epoch": 5}
PATIENCE = 10
MAX_SECONDS = 600.0
BRIGHTNESS = (0.8, 1.25)
LABEL = "development estimate on agent labels (cross-validated on the development recording): PROVISIONAL"
CAVEATS = (
    "The folds are 4 s time blocks only: a negative at a fixed place (one cell, for example a fixture light or a foil "
    "reflection) can be in the training and the test folds, so the cross-validated precision is optimistic for "
    "location-bound false positives (test_negatives_sharing_a_training_cell counts them).",
    "One development recording with agent labels: not an estimate for other cameras, scenes or annotators.",
    "Each track is scored at its first scored window only; at run time a window outside the envelope is retried at "
    "the next checkpoint, here it is not accepted (by_threshold, auc_runtime). auc uses the raw scores of every track.",
)


def temporal_names() -> tuple[str, ...]:
    return (*WINDOW_NAMES, *(f"patch_pc{i}_{s}" for i in range(TEMPORAL_PCA_K) for s in ("mean", "sd")))


def patch_names() -> tuple[str, ...]:
    return (*(f"patch_pc{i}" for i in range(PATCH_PCA_K)), *PATCH_HIT_FEATURES)


def folds_of(groups) -> dict[int, int]:
    """Fold of each block group: its rank among the sorted group ids, mod N_FOLDS."""
    return {int(g): i % N_FOLDS for i, g in enumerate(sorted(set(int(v) for v in groups)))}


def roc_auc(y: np.ndarray, s: np.ndarray) -> float | None:
    """Mann-Whitney ROC AUC (ties count one half); None without both classes."""
    from scipy.stats import rankdata

    y, s = np.asarray(y, int), np.asarray(s, float)
    ok = np.isfinite(s)
    y, s = y[ok], s[ok]
    n1, n0 = int((y == 1).sum()), int((y == 0).sum())
    if n1 == 0 or n0 == 0:
        return None
    r = rankdata(s)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def threshold_table(y: np.ndarray, p: np.ndarray, thresholds=THRESHOLDS) -> list[dict[str, Any]]:
    y, p = np.asarray(y, int), np.asarray(p, float)
    ok = np.isfinite(p)
    out = []
    for thr in thresholds:
        acc = ok & (p >= thr)
        tp, fp = int((acc & (y == 1)).sum()), int((acc & (y == 0)).sum())
        fn = int((y == 1).sum()) - tp
        out.append({"threshold": float(thr), "accepted": tp + fp, "tp": tp, "fp": fp, "fn": fn,
                    "precision": tp / (tp + fp) if tp + fp else None,
                    "recall": tp / (tp + fn) if tp + fn else None})
    return out


def _sigmoid(z: np.ndarray) -> np.ndarray:
    from wfglink.verify.models import sigmoid

    return sigmoid(z)


# Data access -----------------------------------------------------------------------------

def _window_rows(tracks) -> list[np.ndarray]:
    return [np.arange(int(a), int(a) + int(n)) for a, n in zip(tracks["win_hit_start"], tracks["win_hit_count"])]


def _hit_values(hits, rows: np.ndarray) -> np.ndarray:
    return hits[list(FEATURE_NAMES)].to_numpy(np.float64)[rows]


def _sample_rows(hits, keys: set[int]) -> np.ndarray:
    m = hits["sample"].to_numpy(bool) & hits["key"].isin(keys).to_numpy()
    return np.flatnonzero(m)


def _wmedian(v: np.ndarray, w: np.ndarray) -> float:
    """Weighted (lower) median: the smallest value whose cumulative weight reaches half."""
    o = np.argsort(v, kind="stable")
    c = np.cumsum(w[o])
    return float(v[o][min(int(np.searchsorted(c, 0.5 * c[-1])), len(v) - 1)])


def _envelope(tracks) -> dict[str, Any] | None:
    """Class-balanced median and MAD of the training windows' ENVELOPE_NAMES (each class weighs
    one half, so the minority class is not out of its own training envelope: with the plain
    median of a set of mostly negatives, fast and bright embers lie many MADs from it), leaving
    out features with zero MAD (a constant feature cannot be judged by a robust z)."""
    X = tracks[list(ENVELOPE_NAMES)].to_numpy(np.float64)
    y = tracks["label"].to_numpy(np.int64)
    n1, n0 = int((y == 1).sum()), int((y == 0).sum())
    w = np.where(y == 1, 0.5 / n1 if n1 else 0.0, 0.5 / n0 if n0 else 0.0)
    names, med, mad = [], [], []
    for j, n in enumerate(ENVELOPE_NAMES):
        ok = np.isfinite(X[:, j]) & (w > 0)
        if not ok.any():
            continue
        m = _wmedian(X[ok, j], w[ok])
        d = _wmedian(np.abs(X[ok, j] - m), w[ok])
        if d > 0:
            names.append(n)
            med.append(m)
            mad.append(d)
    return {"names": names, "median": med, "mad": mad} if names else None


def fit_pca(X: np.ndarray, k: int):
    """models.PCA of X from the top k eigenvectors of its scatter matrix (the components of the
    SVD, with models.PCA's sign rule; only k eigenpairs are computed, which is much faster for
    many rows of a few hundred pixels)."""
    from scipy.linalg import eigh

    from wfglink.verify.models import PCA

    X = np.asarray(X, np.float64)
    mean = X.mean(axis=0)
    Xc = X - mean
    d = X.shape[1]
    k = max(1, min(int(k), d))
    vals, vecs = eigh(Xc.T @ Xc, subset_by_index=[d - k, d - 1], driver="evr")
    order = np.argsort(-vals, kind="stable")
    comp = vecs[:, order].T
    sign = np.sign(comp[np.arange(comp.shape[0]), np.argmax(np.abs(comp), axis=1)])
    return PCA(mean, comp * np.where(sign == 0, 1.0, sign)[:, None])


# Family C ---------------------------------------------------------------------------------

def fit_temporal(ds: dict[str, Any], tracks, profile: str):
    from wfglink.verify.models import LogReg, Model

    hits, patches = ds["hits"], ds["patches"]
    srows = _sample_rows(hits, set(int(k) for k in tracks["key"]))
    flat = patches[srows].astype(np.float32).reshape(len(srows), -1)
    pca = fit_pca(flat, TEMPORAL_PCA_K)
    names = temporal_names()
    X = _temporal_X(ds, tracks, names, pca)
    est = LogReg(**TEMPORAL).fit(X, tracks["label"].to_numpy(np.float64))
    return Model("temporal", est, names, patch_pca=pca, envelope=_envelope(tracks), meta={"profile": profile}), {}


def _temporal_X(ds, tracks, names, pca) -> np.ndarray:
    from wfglink.verify.scorers import temporal_vector

    patches = ds["patches"]
    W = tracks[list(WINDOW_NAMES)].to_numpy(np.float64)
    rows = _window_rows(tracks)
    return np.vstack([temporal_vector(names, W[i], patches[r] if len(r) else None, pca) for i, r in enumerate(rows)]) \
        if len(rows) else np.zeros((0, len(names)))


def score_temporal(model, ds, tracks) -> np.ndarray:
    X = _temporal_X(ds, tracks, model.feature_names, model.patch_pca)
    return _sigmoid(model.logits(X)) if len(X) else np.zeros(0)


# Family B ---------------------------------------------------------------------------------

def _dihedral(p: np.ndarray, k: int) -> np.ndarray:
    """Transform k (0..7) of the dihedral group on the last two axes: rotations by k mod 4
    quarter turns, mirrored for k >= 4."""
    q = np.rot90(p, k % 4, axes=(-2, -1))
    return q[..., ::-1] if k >= 4 else q


def _brighten(p: np.ndarray, f: np.ndarray) -> np.ndarray:
    """Patches (n, 2, P, P) with their z values times f (n,), clipped and stored as asinh(z / 2) again."""
    z = 2.0 * np.sinh(p.astype(np.float64))
    return np.arcsinh(np.clip(f[:, None, None, None] * z, -5.0, 30.0) / 2.0)


def augment(patches: np.ndarray, values: np.ndarray, rng) -> tuple[np.ndarray, np.ndarray]:
    """8 copies of every hit (see the module notes): patches (n, 2, P, P), values (n, F)."""
    lo, hi = math.log(BRIGHTNESS[0]), math.log(BRIGHTNESS[1])
    base = patches.astype(np.float64)
    ps, vs = [], []
    for k in range(8):
        f = np.ones(len(patches)) if k == 0 else np.exp(rng.uniform(lo, hi, len(patches)))
        q = _dihedral(base, k)
        q = _brighten(q, f) if k else q
        v = values.copy()
        v[:, FEATURE_NAMES.index("snr")] *= f
        v[:, FEATURE_NAMES.index("log_flux")] += np.log(f)
        ps.append(q)
        vs.append(v)
    return np.concatenate(ps).astype(np.float32), np.concatenate(vs)


class _PatchSpec:
    """Model-like holder for scorers.patch_inputs while a model is being built."""

    def __init__(self, pca, names):
        self.pca, self.feature_names = pca, names


def fit_patch(ds: dict[str, Any], tracks, profile: str, seed: int, max_seconds: float = MAX_SECONDS):
    from wfglink.verify.models import MLP, Model
    from wfglink.verify.scorers import patch_inputs

    hits, patches = ds["hits"], ds["patches"]
    groups = sorted(set(int(g) for g in tracks["group"]))
    val_groups = {g for i, g in enumerate(groups) if i % N_FOLDS == 0} if len(groups) >= 2 else set()
    fit_keys = set(int(k) for k, g in zip(tracks["key"], tracks["group"]) if int(g) not in val_groups)
    val_keys = set(int(k) for k, g in zip(tracks["key"], tracks["group"]) if int(g) in val_groups)
    fr, vr = _sample_rows(hits, fit_keys), _sample_rows(hits, val_keys)
    y_fit, y_val = hits["label"].to_numpy(np.float64)[fr], hits["label"].to_numpy(np.float64)[vr]
    flat = patches[fr].astype(np.float32).reshape(len(fr), -1)
    pca = fit_pca(flat, PATCH_PCA_K)
    names = patch_names()
    spec = _PatchSpec(pca, names)
    rng = np.random.default_rng(int(seed))
    pa, va = augment(patches[fr], _hit_values(hits, fr), rng)
    X = patch_inputs(spec, pa, va)
    y = np.tile(y_fit, 8)
    val = None
    if len(vr) and len(set(y_val.tolist())) > 1:
        val = (patch_inputs(spec, patches[vr], _hit_values(hits, vr)), y_val)
    n_pos, n_neg = float((y == 1).sum()), float((y == 0).sum())
    est = MLP(**PATCH, seed=int(seed), pos_weight=n_neg / n_pos if n_pos > 0 else 1.0)
    t0 = time.perf_counter()
    est.fit(X, y, val=val, patience=PATIENCE if val is not None else None, max_seconds=max_seconds)
    info = {"epochs_run": est.epochs_run, "best_epoch": est.best_epoch, "stopped": est.stopped,
            "wall_s": round(time.perf_counter() - t0, 2), "fit_hits": int(len(fr)), "augmented_rows": int(len(X)),
            "holdout_groups": sorted(val_groups), "holdout_hits": int(len(vr)),
            "early_stopping": val is not None}
    return Model("patch", est, names, pca=pca, envelope=_envelope(tracks), meta={"profile": profile}), info


def score_patch(model, ds, tracks) -> np.ndarray:
    from wfglink.verify.scorers import patch_logits

    hits, patches = ds["hits"], ds["patches"]
    out = np.full(len(tracks), np.nan)
    for i, r in enumerate(_window_rows(tracks)):
        if len(r):
            out[i] = float(np.mean(patch_logits(model, patches[r], _hit_values(hits, r))))
    return _sigmoid(out)


FIT = {"temporal": lambda ds, tr, prof, seed, ms: fit_temporal(ds, tr, prof),
       "patch": lambda ds, tr, prof, seed, ms: fit_patch(ds, tr, prof, seed, ms)}
SCORE = {"temporal": score_temporal, "patch": score_patch}


# Driver -----------------------------------------------------------------------------------

def model_path(models_dir: str | Path, profile: str, family: str, seed: int) -> Path:
    return Path(models_dir) / profile / f"{family}_seed{int(seed)}.npz"


def ood_settings(rec: dict[str, Any]) -> dict[str, Any]:
    """The dataset's verify.ood settings (dataset.json), else the overlay's."""
    o = (rec.get("settings") or {}).get("ood")
    if o:
        return {"z_max": float(o["z_max"]), "max_out": int(o["max_out"]), "source": "dataset"}
    from wfglink.verify.config import VerifyConfig, hp_config

    v = VerifyConfig.from_cfg(hp_config("accept_all")).ood
    return {"z_max": float(v.z_max), "max_out": int(v.max_out), "source": "overlay"}


def ood_mask(model, tracks, ood_cfg: dict[str, Any] | None) -> np.ndarray:
    """Tracks whose window is outside the model's envelope (scorers.ood), as the run time tests it."""
    from wfglink.verify.scorers import ood

    if not ood_cfg or not model.envelope or not len(tracks):
        return np.zeros(len(tracks), bool)
    W = tracks[list(WINDOW_NAMES)].to_numpy(np.float64)
    return np.array([ood(w, model.envelope, float(ood_cfg["z_max"]), int(ood_cfg["max_out"])) for w in W], bool)


def cross_validate(ds, tracks, family: str, profile: str, seed: int, max_seconds: float,
                   ood_cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    folds = folds_of(tracks["group"])
    fold = tracks["group"].map(lambda g: folds[int(g)]).to_numpy()
    y = tracks["label"].to_numpy(int)
    cells = tracks["cell"].astype(str).to_numpy() if "cell" in tracks else np.full(len(tracks), "")
    oof = np.full(len(tracks), np.nan)
    out_env = np.zeros(len(tracks), bool)
    per_fold = []
    shared = test_neg = 0
    for k in range(N_FOLDS):
        tr, te = fold != k, fold == k
        ok = te.any() and len(set(y[tr].tolist())) == 2
        info: dict[str, Any] = {}
        if ok:
            model, info = FIT[family](ds, tracks[tr], profile, seed, max_seconds)
            oof[te] = SCORE[family](model, ds, tracks[te])
            out_env[te] = ood_mask(model, tracks[te], ood_cfg)
        train_cells = set(cells[tr & (y == 0)].tolist())
        n_sh = int(sum(c in train_cells for c in cells[te & (y == 0)]))
        shared += n_sh
        test_neg += int((te & (y == 0)).sum())
        per_fold.append({"fold": k, "groups": sorted(g for g, f in folds.items() if f == k), "test_tracks": int(te.sum()),
                         "fitted": bool(ok), "stopped": info.get("stopped"), "ood_tracks": int(out_env[te].sum()),
                         "test_negatives_sharing_a_training_cell": n_sh})
    runtime = np.where(out_env, np.nan, oof)
    return {"auc": roc_auc(y, oof), "auc_runtime": roc_auc(y, np.where(out_env & np.isfinite(oof), 0.0, oof)),
            "tracks": int(len(tracks)), "positives": int((y == 1).sum()),
            "negatives": int((y == 0).sum()), "scored": int(np.isfinite(oof).sum()), "ood_tracks": int(out_env.sum()),
            "test_negatives": test_neg, "test_negatives_sharing_a_training_cell": shared, "folds": per_fold,
            "by_threshold": threshold_table(y, runtime), "by_threshold_without_ood": threshold_table(y, oof),
            "ood": ood_cfg}


def train_all(ds_dir: str | Path, models_dir: str | Path, report_path: str | Path, families=FAMILIES, seeds=SEEDS,
              max_seconds: float = MAX_SECONDS, command_line: str | None = None, cv: bool = True) -> dict[str, Any]:
    """Cross-validate and fit every family and seed (see the module notes); write the models and
    train_report.json. Returns the report."""
    from wfglink.provenance import git_state, now_shanghai, sha256_file, sha256_json
    from wfglink.verify.dataset import cap_negatives, load_dataset
    from wfglink.verify.models import save

    ds = load_dataset(ds_dir)
    rec = ds["record"]
    profile = rec.get("profile", "file_native")
    data_sha = {"dataset_json": sha256_file(Path(ds_dir) / "dataset.json"), **(rec.get("files_sha256") or {})}
    report: dict[str, Any] = {"schema_version": 1, "created": now_shanghai(), "label": LABEL, "dataset": str(ds_dir),
                              "training_data_sha256": data_sha, "profile": profile, "command_line": command_line,
                              **git_state()}
    floor = rec.get("floor") or {}
    if not floor.get("adequate"):
        report.update(status="NOT_RUN", reason=f"dataset below the data floor: {floor.get('reason') or 'no verdict'}",
                      floor=floor)
        _write(report_path, report)
        return report
    cap = int(rec["settings"]["max_neg_per_cell"])
    ood_cfg = ood_settings(rec)
    report.update(status="OK", floor=floor, settings={
        "temporal": {**TEMPORAL, "pca_k": TEMPORAL_PCA_K, "inputs": list(temporal_names())},
        "patch": {**PATCH, "pca_k": PATCH_PCA_K, "hit_features": list(PATCH_HIT_FEATURES), "patience": PATIENCE,
                  "max_seconds": max_seconds, "brightness": list(BRIGHTNESS), "augmentation": "8 dihedral transforms"},
        "folds": N_FOLDS, "fold_rule": "rank of the block group among the sorted group ids mod 5",
        "thresholds": list(THRESHOLDS), "envelope_names": list(ENVELOPE_NAMES), "ood": ood_cfg},
        caveats=list(CAVEATS), models={})
    tracks_all = ds["tracks"]
    masks = {int(s): cap_negatives(tracks_all, cap, int(s)) for s in seeds}
    neg = tracks_all[tracks_all["label"] == 0]
    max_cell = int(neg.groupby("cell").size().max()) if len(neg) else 0
    first = masks[int(seeds[0])] if masks else None
    identical = bool(masks) and all(np.array_equal(m, first) for m in masks.values())
    report["sampling"] = {
        "max_neg_per_cell": cap, "max_negatives_in_a_cell": max_cell, "cap_binding": max_cell > cap,
        "identical_training_sets": identical, "seeds": [int(s) for s in seeds],
        "note": ("the per-cell cap does not bind: every seed draws the same training tracks, so the temporal seeds "
                 "are one model (the patch seeds still differ in the MLP's start and the augmentation)")
        if identical and len(masks) > 1 else ""}
    stopped_on_cap: list[str] = []
    for family in families:
        for seed in seeds:
            tracks = tracks_all[masks[int(seed)]].reset_index(drop=True)
            entry: dict[str, Any] = {"family": family, "seed": int(seed), "tracks": int(len(tracks))}
            if cv:
                entry["cv"] = cross_validate(ds, tracks, family, profile, int(seed), max_seconds, ood_cfg)
                stopped_on_cap += [f"{family}_seed{int(seed)} fold {f['fold']}" for f in entry["cv"]["folds"]
                                   if f.get("stopped") == "time_cap"]
            t0 = time.perf_counter()
            model, info = FIT[family](ds, tracks, profile, int(seed), max_seconds)
            wall = round(time.perf_counter() - t0, 2)
            path = model_path(models_dir, profile, family, int(seed))
            est = model.estimator
            side = save(path, model, {"profile": profile, "seed": int(seed),
                                      "epochs": getattr(est, "epochs_run", None) if family == "patch" else None,
                                      "training_data_sha256": data_sha, "command_line": command_line,
                                      "wall_s": wall, "fit": info, "training_tracks": int(len(tracks)),
                                      "training_positives": int((tracks["label"] == 1).sum()),
                                      "dataset": str(ds_dir), "labels": LABEL,
                                      "cv_auc": (entry.get("cv") or {}).get("auc")})
            entry["final"] = {"path": str(path), "sha256": side["npz_sha256"],
                              "sidecar_sha256": sha256_file(path.with_suffix(".json")), "wall_s": wall, **info}
            if info.get("stopped") == "time_cap":
                stopped_on_cap.append(f"{family}_seed{int(seed)} final")
            same = [n for n, e in report["models"].items()
                    if e["family"] == family and e["final"]["sha256"] == side["npz_sha256"]]
            if same:
                entry["same_as"] = same[0]
            report["models"][f"{family}_seed{int(seed)}"] = entry
    distinct: dict[str, list[list[str]]] = {}
    for n, e in report["models"].items():
        groups = distinct.setdefault(e["family"], [])
        g = next((g for g in groups if report["models"][g[0]]["final"]["sha256"] == e["final"]["sha256"]), None)
        if g is None:
            groups.append([n])
        else:
            g.append(n)
    report["distinct_models"] = distinct
    report["deterministic"] = not stopped_on_cap
    if stopped_on_cap:
        report["warnings"] = [f"{len(stopped_on_cap)} fits stopped on the wall-time cap ({', '.join(stopped_on_cap)}): "
                              "the epoch they stop at depends on the machine's load, so these models cannot be "
                              "reproduced byte for byte"]
    report["report_sha256_of_models"] = sha256_json({k: v["final"]["sha256"] for k, v in report["models"].items()})
    _write(report_path, report)
    return report


def _write(path: str | Path, rec: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
