"""Small, deterministic models for the verifier (numpy and scipy only), with pinned save/load.

LogReg: L2-regularised logistic regression fitted with scipy's L-BFGS-B on standardised inputs
(missing values imputed with the training median), from zero weights, so a fit is
deterministic. MLP: one hidden ReLU layer trained with Adam in numpy; the seed fixes the
initial weights and the batch order. Optional hard-negative selection: from epoch
hard_neg_epoch on, only the hardest hard_neg_frac of each batch's negatives (largest loss)
contribute, so the many easy negatives (sensor noise) stop dominating the gradient.

Model wraps an estimator with an optional PCA applied to its raw inputs (patch models: the
flattened patch pixels), an optional patch PCA whose per-window statistics are inputs
(temporal models), the input feature names and an out-of-distribution envelope (median and
MAD per window feature on the training data).

save writes the arrays to a .npz (stored, fixed timestamps, so the same model gives the same
bytes) and a .json sidecar next to it with the feature names, standardisation, PCA, training
data hashes, seed, epochs, profile, envelope, command line and the .npz SHA-256. Everything
that changes what the model does at run time (RUNTIME_KEYS: format, kind, estimator and its
settings, feature names and their order, profile, envelope, PCA sizes) is also stored inside
the .npz as canonical JSON (the member meta_json), so the pinned SHA-256 covers it; the sidecar
is a readable copy. load refuses (ModelUnavailable) a missing file, an unpinned or wrong
SHA-256, a sidecar that does not belong to the .npz or differs from the stored copy in any of
those fields, and arrays that cannot be read; `validate` refuses a model whose array sizes do
not fit its inputs (bad_format), so a pinned model can never fail inside a scorer.
"""
from __future__ import annotations

import io
import json
import math
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

FORMAT = "wfglink.verify.model/1"
RUNTIME_KEYS = ("format", "kind", "estimator", "hyper", "feature_names", "profile", "envelope", "pca", "patch_pca")


class ModelUnavailable(Exception):
    """A model that cannot be used; `reason` is a short machine-readable word."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = str(reason)


def sigmoid(z):
    z = np.asarray(z, np.float64)
    return np.where(z >= 0, 1.0 / (1.0 + np.exp(-np.abs(z))), np.exp(-np.abs(z)) / (1.0 + np.exp(-np.abs(z))))


def _softplus(z: np.ndarray) -> np.ndarray:
    return np.logaddexp(0.0, z)


class Standardizer:
    """Impute missing values with the training median, then subtract the mean and divide by the
    standard deviation (1 for constant columns)."""

    def __init__(self, impute=None, mean=None, scale=None):
        self.impute = None if impute is None else np.asarray(impute, np.float64)
        self.mean = None if mean is None else np.asarray(mean, np.float64)
        self.scale = None if scale is None else np.asarray(scale, np.float64)

    def fit(self, X: np.ndarray) -> "Standardizer":
        X = np.asarray(X, np.float64)
        med = np.zeros(X.shape[1])
        for j in range(X.shape[1]):
            v = X[:, j][np.isfinite(X[:, j])]
            med[j] = float(np.median(v)) if v.size else 0.0
        Xi = np.where(np.isfinite(X), X, med)
        sd = Xi.std(axis=0)
        self.impute, self.mean, self.scale = med, Xi.mean(axis=0), np.where(sd > 1e-12, sd, 1.0)
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, np.float64)
        return (np.where(np.isfinite(X), X, self.impute) - self.mean) / self.scale


class PCA:
    """Principal components by SVD of the centred data, signs fixed so that each component's
    largest absolute loading is positive (deterministic)."""

    def __init__(self, mean=None, components=None):
        self.mean = None if mean is None else np.asarray(mean, np.float64)
        self.components = None if components is None else np.asarray(components, np.float64)

    @property
    def k(self) -> int:
        return 0 if self.components is None else int(self.components.shape[0])

    def fit(self, X: np.ndarray, k: int) -> "PCA":
        X = np.asarray(X, np.float64)
        self.mean = X.mean(axis=0)
        _, _, vt = np.linalg.svd(X - self.mean, full_matrices=False)
        comp = vt[: max(1, min(int(k), vt.shape[0]))]
        sign = np.sign(comp[np.arange(comp.shape[0]), np.argmax(np.abs(comp), axis=1)])
        self.components = comp * np.where(sign == 0, 1.0, sign)[:, None]
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        return (np.asarray(X, np.float64) - self.mean) @ self.components.T


class LogReg:
    name = "logreg"

    def __init__(self, l2: float = 1.0, max_iter: int = 1000):
        self.l2 = float(l2)
        self.max_iter = int(max_iter)
        self.std = Standardizer()
        self.w: np.ndarray | None = None
        self.b = 0.0

    def hyper(self) -> dict[str, Any]:
        return {"l2": self.l2, "max_iter": self.max_iter}

    def fit(self, X: np.ndarray, y: np.ndarray, sample_weight: np.ndarray | None = None) -> "LogReg":
        from scipy.optimize import minimize

        Z = self.std.fit(X).transform(X)
        y = np.asarray(y, np.float64)
        s = np.ones(len(y)) if sample_weight is None else np.asarray(sample_weight, np.float64)
        s = s / s.sum()
        d = Z.shape[1]

        def f(p):
            w, b = p[:d], p[d]
            z = Z @ w + b
            loss = float(np.sum(s * (_softplus(z) - y * z))) + 0.5 * self.l2 * float(w @ w) / len(y)
            r = s * (sigmoid(z) - y)
            g = np.concatenate([Z.T @ r + self.l2 * w / len(y), [r.sum()]])
            return loss, g

        res = minimize(f, np.zeros(d + 1), jac=True, method="L-BFGS-B", options={"maxiter": self.max_iter})
        self.w, self.b = res.x[:d], float(res.x[d])
        return self

    def decision_function(self, X: np.ndarray) -> np.ndarray:
        return self.std.transform(X) @ self.w + self.b

    def arrays(self) -> dict[str, np.ndarray]:
        return {"w": self.w, "b": np.array([self.b])}

    @classmethod
    def from_arrays(cls, a: dict[str, np.ndarray], hyper: dict[str, Any]) -> "LogReg":
        m = cls(**hyper)
        m.w, m.b = np.asarray(a["w"], np.float64), float(np.asarray(a["b"]).ravel()[0])
        return m


class MLP:
    name = "mlp"

    def __init__(self, hidden: int = 32, lr: float = 1e-3, epochs: int = 30, batch_size: int = 256,
                 l2: float = 1e-4, seed: int = 0, hard_neg_frac: float | None = None,
                 hard_neg_epoch: int | None = None, pos_weight: float = 1.0):
        self.hidden, self.lr, self.epochs, self.batch_size = int(hidden), float(lr), int(epochs), int(batch_size)
        self.l2, self.seed, self.pos_weight = float(l2), int(seed), float(pos_weight)
        self.hard_neg_frac = None if hard_neg_frac is None else float(hard_neg_frac)
        self.hard_neg_epoch = None if hard_neg_epoch is None else int(hard_neg_epoch)
        self.std = Standardizer()
        self.W1 = self.b1 = self.W2 = None
        self.b2 = 0.0
        self.history: list[float] = []

    def hyper(self) -> dict[str, Any]:
        return {"hidden": self.hidden, "lr": self.lr, "epochs": self.epochs, "batch_size": self.batch_size,
                "l2": self.l2, "seed": self.seed, "hard_neg_frac": self.hard_neg_frac,
                "hard_neg_epoch": self.hard_neg_epoch, "pos_weight": self.pos_weight}

    def _forward(self, Z: np.ndarray):
        h_pre = Z @ self.W1 + self.b1
        h = np.maximum(h_pre, 0.0)
        return h_pre, h, h @ self.W2 + self.b2

    def fit(self, X: np.ndarray, y: np.ndarray, val: tuple[np.ndarray, np.ndarray] | None = None,
            patience: int | None = None, max_seconds: float | None = None) -> "MLP":
        """Train for at most `epochs` epochs. With val = (X_val, y_val) the pos_weight-weighted
        mean log loss on it is measured after every epoch and the best epoch's weights are kept;
        patience stops after that many epochs without improvement, max_seconds after that wall
        time. epochs_run, best_epoch, stopped and val_history record what happened. Without
        them the fit is the plain fixed-epoch fit (same weights, bit for bit)."""
        import time as _time

        t_start = _time.perf_counter()
        Z = self.std.fit(X).transform(X)
        y = np.asarray(y, np.float64)
        n, d = Z.shape
        rng = np.random.default_rng(self.seed)
        self.W1 = rng.normal(0.0, math.sqrt(2.0 / d), (d, self.hidden))
        self.b1 = np.zeros(self.hidden)
        self.W2 = rng.normal(0.0, math.sqrt(1.0 / self.hidden), self.hidden)
        p = float(np.clip(y.mean(), 1e-3, 1 - 1e-3)) if n else 0.5
        self.b2 = math.log(p / (1 - p))
        params = [self.W1, self.b1, self.W2, np.array([self.b2])]
        m = [np.zeros_like(q) for q in params]
        v = [np.zeros_like(q) for q in params]
        b1_, b2_, eps, step = 0.9, 0.999, 1e-8, 0
        self.history = []
        self.val_history: list[float] = []
        self.epochs_run, self.best_epoch, self.stopped = 0, None, "epochs"
        Zv = yv = wv = None
        if val is not None:
            Zv, yv = self.std.transform(val[0]), np.asarray(val[1], np.float64)
            wv = np.where(yv > 0.5, self.pos_weight, 1.0)
        best, wait = None, 0
        for ep in range(self.epochs):
            order = rng.permutation(n)
            tot = 0.0
            for a in range(0, n, self.batch_size):
                idx = order[a:a + self.batch_size]
                Zb, yb = Z[idx], y[idx]
                h_pre, h, z = self._forward(Zb)
                loss_i = _softplus(z) - yb * z
                w = np.where(yb > 0.5, self.pos_weight, 1.0)
                if self.hard_neg_frac is not None and self.hard_neg_epoch is not None and ep >= self.hard_neg_epoch:
                    neg = np.flatnonzero(yb < 0.5)
                    if neg.size:
                        keep = max(1, int(math.ceil(self.hard_neg_frac * neg.size)))
                        hard = neg[np.argsort(-loss_i[neg], kind="stable")[:keep]]
                        mask = yb > 0.5
                        mask[hard] = True
                        w = w * mask
                if w.sum() <= 0:
                    continue
                w = w / w.sum()
                tot += float(np.sum(w * loss_i))
                dz = w * (sigmoid(z) - yb)
                gW2 = h.T @ dz + self.l2 * self.W2
                gb2 = np.array([dz.sum()])
                dh = np.outer(dz, self.W2) * (h_pre > 0)
                gW1 = Zb.T @ dh + self.l2 * self.W1
                gb1 = dh.sum(axis=0)
                step += 1
                for q, g, mq, vq in zip(params, (gW1, gb1, gW2, gb2), m, v):
                    mq *= b1_
                    mq += (1 - b1_) * g
                    vq *= b2_
                    vq += (1 - b2_) * g * g
                    q -= self.lr * (mq / (1 - b1_ ** step)) / (np.sqrt(vq / (1 - b2_ ** step)) + eps)
                self.b2 = float(params[3][0])
            self.history.append(tot)
            self.epochs_run = ep + 1
            if Zv is not None and len(yv):
                zv = self._forward(Zv)[2]
                lv = float(np.sum(wv * (_softplus(zv) - yv * zv)) / max(float(wv.sum()), 1e-12))
                self.val_history.append(lv)
                if best is None or lv < best[0] - 1e-12:
                    best, wait = (lv, ep + 1, [q.copy() for q in params]), 0
                else:
                    wait += 1
                if patience is not None and wait >= int(patience):
                    self.stopped = "early_stopping"
                    break
            if max_seconds is not None and _time.perf_counter() - t_start > float(max_seconds):
                self.stopped = "time_cap"
                break
        if best is not None:
            params = best[2]
            self.best_epoch = best[1]
        self.W1, self.b1, self.W2 = params[0], params[1], params[2]
        self.b2 = float(params[3][0])
        return self

    def decision_function(self, X: np.ndarray) -> np.ndarray:
        return self._forward(self.std.transform(X))[2]

    def arrays(self) -> dict[str, np.ndarray]:
        return {"W1": self.W1, "b1": self.b1, "W2": self.W2, "b2": np.array([self.b2])}

    @classmethod
    def from_arrays(cls, a: dict[str, np.ndarray], hyper: dict[str, Any]) -> "MLP":
        m = cls(**hyper)
        m.W1, m.b1, m.W2 = (np.asarray(a[k], np.float64) for k in ("W1", "b1", "W2"))
        m.b2 = float(np.asarray(a["b2"]).ravel()[0])
        return m


ESTIMATORS = {"logreg": LogReg, "mlp": MLP}


@dataclass
class Model:
    """A trained verifier model: kind is "patch" (inputs: flattened patches) or "temporal"
    (inputs: window features and patch statistics, by feature_names)."""

    kind: str
    estimator: Any
    feature_names: tuple[str, ...]
    pca: PCA | None = None            # applied to the raw inputs first (patch models)
    patch_pca: PCA | None = None      # temporal models: patch statistics come from this PCA
    envelope: dict | None = None      # {"names": [...], "median": [...], "mad": [...]} of window features
    meta: dict = field(default_factory=dict)

    def logits(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, np.float64)
        if self.pca is not None:
            X = self.pca.transform(X)
        return np.asarray(self.estimator.decision_function(X), np.float64)


def make_envelope(names, X: np.ndarray) -> dict[str, Any]:
    """Median and MAD of each column of X (training windows), for the OOD test."""
    X = np.asarray(X, np.float64)
    med, mad = [], []
    for j in range(X.shape[1]):
        v = X[:, j][np.isfinite(X[:, j])]
        m = float(np.median(v)) if v.size else 0.0
        med.append(m)
        mad.append(float(np.median(np.abs(v - m))) if v.size else 0.0)
    return {"names": list(names), "median": med, "mad": mad}


def _write_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    """np.load-compatible .npz with stored members and fixed timestamps (same model, same bytes)."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as zf:
        for name in sorted(arrays):
            buf = io.BytesIO()
            np.lib.format.write_array(buf, np.ascontiguousarray(arrays[name]), allow_pickle=False)
            zi = zipfile.ZipInfo(name + ".npy", date_time=(1980, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_STORED
            zi.external_attr = 0o644 << 16
            zf.writestr(zi, buf.getvalue())


def _sha(path: Path) -> str:
    from wfglink.provenance import sha256_file

    return sha256_file(path)


def sidecar_path(path: str | Path) -> Path:
    return Path(path).with_suffix(".json")


def _canonical(obj: Any) -> str:
    """JSON with sorted keys and no spaces (the stored copy of the run-time fields)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _runtime(side: dict[str, Any]) -> dict[str, Any]:
    """The run-time fields of a sidecar, normalised as JSON would read them back."""
    return json.loads(_canonical({k: side.get(k) for k in RUNTIME_KEYS}))


def save(path: str | Path, model: Model, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Write model to path (.npz) and its .json sidecar; returns the sidecar dict (with npz_sha256)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    est = model.estimator
    arrays = {f"est_{k}": np.asarray(v, np.float64) for k, v in est.arrays().items()}
    arrays.update(std_impute=est.std.impute, std_mean=est.std.mean, std_scale=est.std.scale)
    for tag, p in (("pca", model.pca), ("patch_pca", model.patch_pca)):
        if p is not None:
            arrays[f"{tag}_mean"], arrays[f"{tag}_components"] = p.mean, p.components
    meta = dict(meta or {})
    hyper = est.hyper()
    side = {
        "format": FORMAT, "kind": model.kind, "estimator": est.name, "hyper": hyper,
        "feature_names": list(model.feature_names),
        "standardization": {"impute": est.std.impute.tolist(), "mean": est.std.mean.tolist(),
                            "scale": est.std.scale.tolist()},
        "pca": None if model.pca is None else {"k": model.pca.k, "dim": int(model.pca.mean.size)},
        "patch_pca": None if model.patch_pca is None else {"k": model.patch_pca.k,
                                                           "dim": int(model.patch_pca.mean.size)},
        "envelope": model.envelope,
        "profile": meta.pop("profile", model.meta.get("profile")),
        "seed": meta.pop("seed", hyper.get("seed")),
        "epochs": meta.pop("epochs", hyper.get("epochs")),
        "training_data_sha256": meta.pop("training_data_sha256", None),
        "command_line": meta.pop("command_line", None),
        **meta,
    }
    arrays["meta_json"] = np.frombuffer(_canonical(_runtime(side)).encode("utf-8"), np.uint8)
    _write_npz(path, arrays)
    side["npz_sha256"] = _sha(path)
    sidecar_path(path).write_text(json.dumps(side, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return side


def load(path: str | Path, expect_sha256: str | None) -> Model:
    """The model at path, after checking its SHA-256 against the pinned value and its sidecar."""
    path = Path(path)
    if not path.is_file():
        raise ModelUnavailable("missing_file")
    if not expect_sha256:
        raise ModelUnavailable("sha_unpinned")
    sha = _sha(path)
    if sha != str(expect_sha256).lower():
        raise ModelUnavailable("sha_mismatch")
    sp = sidecar_path(path)
    if not sp.is_file():
        raise ModelUnavailable("missing_sidecar")
    try:
        side = json.loads(sp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ModelUnavailable("bad_sidecar") from None
    if not isinstance(side, dict) or side.get("npz_sha256") != sha or side.get("format") != FORMAT:
        raise ModelUnavailable("sidecar_mismatch")
    try:
        with np.load(path, allow_pickle=False) as z:
            a = {k: z[k] for k in z.files}
        stored = json.loads(bytes(np.asarray(a["meta_json"], np.uint8)).decode("utf-8"))
    except (KeyError, ValueError, OSError, TypeError, EOFError, zipfile.BadZipFile):
        raise ModelUnavailable("bad_format") from None
    if _canonical(stored) != _canonical(_runtime(side)):
        raise ModelUnavailable("sidecar_mismatch")
    try:
        cls = ESTIMATORS[stored["estimator"]]
        est = cls.from_arrays({k[4:]: v for k, v in a.items() if k.startswith("est_")}, stored.get("hyper") or {})
        est.std = Standardizer(a["std_impute"], a["std_mean"], a["std_scale"])
        pca = PCA(a["pca_mean"], a["pca_components"]) if "pca_mean" in a else None
        ppca = PCA(a["patch_pca_mean"], a["patch_pca_components"]) if "patch_pca_mean" in a else None
    except (KeyError, ValueError, TypeError, AttributeError):
        raise ModelUnavailable("bad_format") from None
    return Model(kind=str(stored.get("kind")), estimator=est, feature_names=tuple(stored.get("feature_names") or ()),
                 pca=pca, patch_pca=ppca, envelope=stored.get("envelope"),
                 meta={**side, **stored, "path": str(path), "sidecar_sha256": _sha(sp)})


def validate(model: Model, patch_px: int) -> None:
    """Raise ModelUnavailable("bad_format") unless the model's array sizes fit its inputs: patch
    models take flattened (2, patch_px, patch_px) patches (through model.pca when present),
    temporal models one value per feature name; the estimator's standardisation and weights
    match its input size, and the envelope's lists are of one length."""
    def need(ok: bool) -> None:
        if not ok:
            raise ModelUnavailable("bad_format")

    try:
        est = model.estimator
        std = est.std
        d = int(np.asarray(std.mean).size)
        need(d > 0 and np.asarray(std.impute).size == d and np.asarray(std.scale).size == d)
        if isinstance(est, LogReg):
            need(np.asarray(est.w).shape == (d,))
        elif isinstance(est, MLP):
            hdim = int(est.hidden)
            need(np.asarray(est.W1).shape == (d, hdim) and np.asarray(est.b1).shape == (hdim,)
                 and np.asarray(est.W2).shape == (hdim,))
        else:
            need(False)
        n_patch = 2 * int(patch_px) ** 2
        for p in (model.pca, model.patch_pca):
            if p is not None:
                need(np.asarray(p.mean).shape == (n_patch,) and np.asarray(p.components).ndim == 2
                     and np.asarray(p.components).shape[1] == n_patch and p.k > 0)
        if model.kind == "patch":
            # Inputs: the patch PCA components (or the pixels), then any per-hit scalars named
            # in feature_names (scorers.patch_inputs).
            from wfglink.verify.features import FEATURE_NAMES

            n_hit = sum(1 for n in model.feature_names if n in FEATURE_NAMES)
            need(d == (model.pca.k if model.pca is not None else n_patch) + n_hit)
        elif model.kind == "temporal":
            need(model.pca is None and d == len(model.feature_names))
        env = model.envelope
        if env is not None:
            need(isinstance(env, dict) and len(env["names"]) == len(env["median"]) == len(env["mad"]))
    except (AttributeError, KeyError, TypeError, ValueError):
        raise ModelUnavailable("bad_format") from None
