"""Scorers: one number per track window, and whether it may be used.

Every scorer has score(window_vec, patch_stats) -> (score, valid, reason), a threshold (accept
when valid and score >= threshold), min_hits (feature hits a window needs before scoring) and
gated (whether camera motion and the timebase block it). patch_stats is the window's patches
of hits with features, (k, 2, P, P), or None.

- AcceptAll (the control): score 1.0, always valid, needs no hits and is not gated, so it
  accepts every confirmed track at confirmation and reproduces the legacy counts exactly.
- RuleScorer (family A): lower bounds on snr_med, speed_med, net_disp, straightness and upper
  bounds on hotspot_max, pre_presence_med, bg_grad_med, large_near_max, codec_med,
  ctx_change_med (only those given for the profile), plus n_hits >= min_hits and
  (n_streak < 2 or align_frac >= 0.5). The score is the smallest signed standardised margin,
  (value - threshold) / iqr for a lower bound and (threshold - value) / iqr for an upper one
  (raw margins for the two fixed rules), so the window passes when the score is >= 0. A rule
  whose feature is missing (NaN) makes the window invalid (missing_feature).
- PatchScorer (family B): the mean logit of the window's hit patches (PCA, then the model).
- TemporalScorer (family C): window features and patch PCA statistics, then the model.
  Both report sigmoid(logit) as the score and use the pinned threshold of their profile.
- Unavailable(reason): never valid.

build_scorer picks the method of the config for a profile; missing thresholds or weights, an
unpinned or wrong SHA-256, a profile mismatch and a model whose arrays do not fit its inputs
give Unavailable("method_unavailable:<why>").
"""
from __future__ import annotations

import math
from typing import Any, Protocol

import numpy as np

from wfglink.verify.config import VerifyConfig
from wfglink.verify.features import WI

RULE_LOWER = ("snr_med", "speed_med", "net_disp", "straightness")
RULE_UPPER = ("hotspot_max", "pre_presence_med", "bg_grad_med", "large_near_max", "codec_med", "ctx_change_med")
ALIGN_MIN = 0.5


class Scorer(Protocol):
    method: str
    threshold: float
    min_hits: int
    gated: bool

    def score(self, window_vec: np.ndarray, patch_stats: np.ndarray | None) -> tuple[float, bool, str]: ...

    def identity(self) -> dict[str, Any]: ...


def ood(window_vec: np.ndarray, envelope: dict | None, z_max: float, max_out: int) -> bool:
    """True when at least max_out of the envelope's features have |robust z| > z_max
    (robust z = (value - median) / (1.4826 MAD); a feature with zero MAD counts when it differs)."""
    if not envelope:
        return False
    out = 0
    for name, med, mad in zip(envelope["names"], envelope["median"], envelope["mad"]):
        if name not in WI:
            continue
        v = float(window_vec[WI[name]])
        if not math.isfinite(v):
            continue
        s = 1.4826 * float(mad)
        z = abs(v - float(med)) / s if s > 0 else (math.inf if v != float(med) else 0.0)
        out += z > z_max
    return out >= max_out


class AcceptAll:
    method = "accept_all"
    threshold = 0.0
    min_hits = 0
    gated = False

    def score(self, window_vec, patch_stats):
        return 1.0, True, ""

    def identity(self) -> dict[str, Any]:
        return {"method": self.method}


class Unavailable:
    threshold = math.inf
    min_hits = 0
    gated = True
    available = False

    def __init__(self, reason: str, method: str = ""):
        self.reason = reason if reason.startswith("method_unavailable") else f"method_unavailable:{reason}"
        self.method = method

    def score(self, window_vec, patch_stats):
        return math.nan, False, self.reason

    def identity(self) -> dict[str, Any]:
        return {"method": self.method, "unavailable": self.reason}


class RuleScorer:
    method = "rules"
    threshold = 0.0
    gated = True

    def __init__(self, thresholds: dict[str, Any], min_hits: int):
        lower = dict(thresholds.get("lower") or {})
        upper = dict(thresholds.get("upper") or {})
        iqr = dict(thresholds.get("iqr") or {})
        bad = (set(lower) - set(RULE_LOWER)) | (set(upper) - set(RULE_UPPER))
        if bad:
            raise ValueError(f"rules thresholds name unknown features: {sorted(bad)}")
        if not lower and not upper:
            raise ValueError("rules thresholds are empty")
        missing = [k for k in (*lower, *upper) if not (k in iqr and float(iqr[k]) > 0)]
        if missing:
            raise ValueError(f"rules thresholds lack a positive iqr for {missing}")
        self.lower = {k: float(v) for k, v in lower.items()}
        self.upper = {k: float(v) for k, v in upper.items()}
        self.iqr = {k: float(iqr[k]) for k in (*lower, *upper)}
        self.min_hits = int(min_hits)
        self.thresholds = {"lower": self.lower, "upper": self.upper, "iqr": self.iqr}

    def margins(self, w: np.ndarray) -> dict[str, float]:
        out = {"n_hits": float(w[WI["n_hits"]]) - self.min_hits}
        if float(w[WI["n_streak"]]) >= 2:
            out["align_frac"] = float(w[WI["align_frac"]]) - ALIGN_MIN
        for k, thr in self.lower.items():
            out[k] = (float(w[WI[k]]) - thr) / self.iqr[k]
        for k, thr in self.upper.items():
            out[k] = (thr - float(w[WI[k]])) / self.iqr[k]
        return out

    def score(self, window_vec, patch_stats):
        m = self.margins(np.asarray(window_vec, np.float64))
        nan = [k for k, v in m.items() if not math.isfinite(v)]
        if nan:
            return math.nan, False, f"missing_feature:{nan[0]}"
        return float(min(m.values())), True, ""

    def identity(self) -> dict[str, Any]:
        from wfglink.provenance import sha256_json

        return {"method": self.method, "thresholds_sha256": sha256_json(self.thresholds)}


class _ModelScorer:
    gated = True

    def __init__(self, model, threshold: float, min_hits: int, ood_cfg=None, spec=None):
        self.model = model
        self.threshold = float(threshold)
        self.min_hits = int(min_hits)
        self.ood_cfg = ood_cfg
        self.spec = spec

    def _ood(self, w: np.ndarray) -> bool:
        if self.ood_cfg is None:
            return False
        return ood(w, self.model.envelope, self.ood_cfg.z_max, self.ood_cfg.max_out)

    def identity(self) -> dict[str, Any]:
        meta = self.model.meta
        return {"method": self.method, "model_path": meta.get("path"), "model_sha256": meta.get("npz_sha256"),
                "sidecar_sha256": meta.get("sidecar_sha256"), "threshold": self.threshold}


class PatchScorer(_ModelScorer):
    method = "patch"

    def score(self, window_vec, patch_stats):
        w = np.asarray(window_vec, np.float64)
        if patch_stats is None or len(patch_stats) == 0:
            return math.nan, False, "too_few_hits"
        if self._ood(w):
            return math.nan, False, "out_of_distribution"
        X = np.asarray(patch_stats, np.float32).reshape(len(patch_stats), -1)
        z = float(np.mean(self.model.logits(X)))
        return float(1.0 / (1.0 + math.exp(-z))) if z > -700 else 0.0, True, ""


def patch_pc_stats(patches: np.ndarray | None, pca) -> tuple[np.ndarray, np.ndarray]:
    """Mean and standard deviation over a window's patches of their PCA projections (NaN without patches)."""
    k = pca.k
    if patches is None or len(patches) == 0:
        return np.full(k, np.nan), np.full(k, np.nan)
    proj = pca.transform(np.asarray(patches, np.float32).reshape(len(patches), -1))
    return proj.mean(axis=0), proj.std(axis=0)


def temporal_vector(names, window_vec: np.ndarray, patches: np.ndarray | None, patch_pca) -> np.ndarray:
    """The inputs of a temporal model by name: window features, and patch_pc<i>_mean / _sd."""
    w = np.asarray(window_vec, np.float64)
    mean = sd = None
    out = np.full(len(names), np.nan)
    for j, n in enumerate(names):
        if n in WI:
            out[j] = w[WI[n]]
        elif n.startswith("patch_pc") and patch_pca is not None:
            if mean is None:
                mean, sd = patch_pc_stats(patches, patch_pca)
            i, stat = n[len("patch_pc"):].split("_")
            out[j] = (mean if stat == "mean" else sd)[int(i)]
        else:
            raise KeyError(n)
    return out


class TemporalScorer(_ModelScorer):
    method = "temporal"

    def score(self, window_vec, patch_stats):
        w = np.asarray(window_vec, np.float64)
        if self._ood(w):
            return math.nan, False, "out_of_distribution"
        x = temporal_vector(self.model.feature_names, w, patch_stats, self.model.patch_pca)
        z = float(self.model.logits(x[None, :])[0])
        return float(1.0 / (1.0 + math.exp(-z))) if z > -700 else 0.0, True, ""


def _known_names(names, patch_pca) -> bool:
    for n in names:
        if n in WI:
            continue
        if n.startswith("patch_pc") and patch_pca is not None:
            try:
                i, stat = n[len("patch_pc"):].split("_")
                if stat in ("mean", "sd") and 0 <= int(i) < patch_pca.k:
                    continue
            except ValueError:
                pass
        return False
    return True


def build_scorer(vcfg: VerifyConfig, profile: str):
    """The scorer of vcfg.method for this profile, or Unavailable with the reason."""
    method = vcfg.method
    if method == "accept_all":
        return AcceptAll()
    if method == "rules":
        every = vcfg.rules_thresholds
        th = every.get(profile)
        if not th:
            # profile_mismatch only when other profiles have thresholds and this one has no entry.
            other = any(v for k, v in every.items() if k != profile)
            return Unavailable("profile_mismatch" if other and profile not in every else "no_thresholds", method)
        try:
            return RuleScorer(th, vcfg.min_hits)
        except (ValueError, TypeError, AttributeError):
            return Unavailable("bad_thresholds", method)
    if method in ("patch", "temporal"):
        from wfglink.verify.models import ModelUnavailable, load, validate

        specs = vcfg.models.get(method) or {}
        spec = specs.get(profile)
        if spec is None:
            return Unavailable("profile_mismatch" if specs else "no_model", method)
        if spec.threshold is None:
            return Unavailable("no_threshold", method)
        try:
            model = load(spec.resolved(), spec.sha256)
        except ModelUnavailable as exc:
            return Unavailable(exc.reason, method)
        if model.meta.get("profile") != profile:
            return Unavailable("profile_mismatch", method)
        if model.kind != method:
            return Unavailable("wrong_model_kind", method)
        if method == "temporal" and not _known_names(model.feature_names, model.patch_pca):
            return Unavailable("unknown_features", method)
        try:
            validate(model, vcfg.patch.target_px)
        except ModelUnavailable as exc:
            return Unavailable(exc.reason, method)
        cls = PatchScorer if method == "patch" else TemporalScorer
        return cls(model, spec.threshold, vcfg.min_hits, vcfg.ood, spec)
    return Unavailable("unknown_method", method)


__all__ = ["AcceptAll", "PatchScorer", "RuleScorer", "Scorer", "TemporalScorer", "Unavailable", "build_scorer", "ood",
           "patch_pc_stats", "temporal_vector"]
