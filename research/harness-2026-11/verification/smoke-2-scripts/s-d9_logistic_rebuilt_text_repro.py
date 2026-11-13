"""Owen: is the STAGE2 §7a S2-2 text (10b0d7b3) sufficient to reproduce logistic_rebuilt?

Two fits on the same synthetic samples:
  TEXT  - written only from the S2-2 items 1-6 (sample order = event list order then interval order; mask
          score_mask & finite environment (every channel) & finite features; one default_rng(0) advanced sample by
          sample, keep = (y==1) | (rng.random(len(y)) < 0.05); weights 1 / 20; StandardScaler fit WITH sample_weight;
          LogisticRegression(max_iter=3000, random_state=0), default C, fit with sample_weight).
  PIPE  - the pinned pipeline.py command_baselines itself (88d376d2), unmodified, with only its data loaders
          (Environment, available, fit_samples, logistic_features, dilation) replaced by stubs that hand it the same
          synthetic samples and features. The stubs do not touch the fit.
The samples include non-finite environment and feature cells, unscored cells and a non-sorted event order, so the
mask and the draw order are exercised. Synthetic only; no part-a, R or sealed data.

    python s-d9_logistic_rebuilt_text_repro.py PIPELINE_PY OUTDIR
"""
import importlib.util
import json
import pickle
import sys
import types
from pathlib import Path

import numpy as np


def make_samples(n_events=7, per_event=(3, 5), shape=(24, 24), seed=7):
    rng = np.random.default_rng(seed)
    events = [f"EV{k:02d}" for k in rng.permutation(n_events)]          # deliberately not sorted
    samples, feats = [], {}
    for e in events:
        for i in range(int(rng.integers(*per_event))):
            env = rng.normal(size=(4,) + shape)
            env[rng.integers(4), rng.random(shape) < 0.03] = np.nan     # non-finite environment cells
            initial = rng.random(shape) < 0.1
            score = ~initial & (rng.random(shape) < 0.9)                 # some unscored cells
            f = rng.normal(size=(shape[0] * shape[1], 21))
            f[rng.random(len(f)) < 0.02, rng.integers(21)] = np.inf      # non-finite features
            logit = f[:, 0] * 1.5 - 3.0 + 0.5 * f[:, 3]
            y = (rng.random(len(f)) < 1 / (1 + np.exp(-np.nan_to_num(logit, posinf=0.0)))).reshape(shape) & ~initial
            s = types.SimpleNamespace(event_id=e, initial=initial, endpoint=y | initial, score_mask=score,
                                      environment=env, hours=12.0)
            feats[id(s)] = f
            samples.append(s)
    return events, samples, feats


def text_fit(samples, feats):
    """From the S2-2 text only."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    rng = np.random.default_rng(0)
    xs, ys = [], []
    for s in samples:                                                    # items 1 and 3: order as given
        f = feats[id(s)]
        m = s.score_mask.ravel() & np.isfinite(s.environment).all(axis=0).ravel() & np.isfinite(f).all(axis=1)
        y = s.endpoint.ravel()[m]
        keep = (y == 1) | (rng.random(len(y)) < 0.05)
        xs.append(f[m][keep]); ys.append(y[keep])
    x, y = np.concatenate(xs), np.concatenate(ys)
    w = np.where(y == 1, 1.0, 20.0)
    sc = StandardScaler().fit(x, sample_weight=w)
    lr = LogisticRegression(max_iter=3000, random_state=0).fit(sc.transform(x), y.astype(int), sample_weight=w)
    return sc, lr, len(y)


def pipe_fit(pipeline_py, events, samples, feats, out):
    spec = importlib.util.spec_from_file_location("pl_stage2", pipeline_py)
    P = importlib.util.module_from_spec(spec)
    sys.modules["pl_stage2"] = P
    spec.loader.exec_module(P)
    P.Environment = lambda *a, **k: types.SimpleNamespace(names=None, terrain_gradient=lambda e: None)
    P.available = lambda args, evs: list(events)
    P.fit_samples = lambda args, evs, env, mixed: [s for e in evs for s in samples if s.event_id == e]
    P.logistic_features = lambda s, names, grad: feats[id(s)]
    P.B.dilation = lambda initial, hours, k: np.zeros(initial.shape)
    args = types.SimpleNamespace(data_root=Path(out), work=Path(out), run=Path(out), seed=0, negative_fraction=0.05)
    P.command_baselines(args)
    sc, lr = pickle.loads((Path(out) / "baselines" / "logistic.pkl").read_bytes())
    return sc, lr, json.loads((Path(out) / "baselines" / "logistic.json").read_text())["rows"]


def main(pipeline_py, out):
    events, samples, feats = make_samples()
    ordered = [s for e in events for s in samples if s.event_id == e]
    a = text_fit(ordered, feats)
    b = pipe_fit(pipeline_py, events, samples, feats, out)
    eq = dict(rows=a[2] == b[2], mean=np.array_equal(a[0].mean_, b[0].mean_), scale=np.array_equal(a[0].scale_, b[0].scale_),
              coef=np.array_equal(a[1].coef_, b[1].coef_), intercept=np.array_equal(a[1].intercept_, b[1].intercept_))
    print(json.dumps(dict(rows_text=a[2], rows_pipeline=b[2], bit_identical=eq,
                          max_abs_coef_diff=float(np.abs(a[1].coef_ - b[1].coef_).max()))))
    # sensitivity: the text says order matters; a sorted order must give a different draw
    srt = sorted(samples, key=lambda s: s.event_id)
    c = text_fit(srt, feats)
    print(json.dumps(dict(sorted_order_rows=c[2], sorted_order_coef_equal=bool(np.array_equal(c[1].coef_, a[1].coef_)))))
    # and the fit_logistic reading (unweighted scaler, max_iter 2000) differs
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    rng = np.random.default_rng(0); xs, ys = [], []
    for s in ordered:
        f = feats[id(s)]
        m = s.score_mask.ravel() & np.isfinite(s.environment).all(axis=0).ravel() & np.isfinite(f).all(axis=1)
        y = s.endpoint.ravel()[m]; k = (y == 1) | (rng.random(len(y)) < 0.05); xs.append(f[m][k]); ys.append(y[k])
    x, y = np.concatenate(xs), np.concatenate(ys)
    sc = StandardScaler().fit(x); lr = LogisticRegression(C=1.0, max_iter=2000, random_state=0).fit(sc.transform(x), y.astype(int))
    print(json.dumps(dict(fit_logistic_reading_coef_equal=bool(np.array_equal(lr.coef_, a[1].coef_)),
                          fit_logistic_reading_max_abs_coef_diff=float(np.abs(lr.coef_ - a[1].coef_).max()))))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
