"""The `verify` config section (configs/high_precision.yaml) as typed, read-only values.

Every key is read without a numeric default in code: a missing key raises KeyError naming it,
so a run can never silently use a value that is not in the overlay it records.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from wfglink import PROJECT_ROOT

OVERLAY = PROJECT_ROOT / "configs" / "high_precision.yaml"
METHODS = ("accept_all", "rules", "patch", "temporal")
PROFILES = ("file_native", "live_downscaled")
UNPROFILED = "unprofiled"        # neither file mode at native size nor the booth's downscaled analysis


def _req(d: Mapping[str, Any], key: str, where: str) -> Any:
    if not isinstance(d, Mapping) or key not in d:
        raise KeyError(f"verify config: missing key {where}.{key} (see {OVERLAY.name})")
    return d[key]


def profile_of(record: bool, downscale: bool) -> str:
    """file_native (file mode: record, native size) or live_downscaled (the booth)."""
    if record and not downscale:
        return "file_native"
    if downscale and not record:
        return "live_downscaled"
    return UNPROFILED


@dataclass(frozen=True)
class MotionCfg:
    thumb_width: int
    max_shift_px: float
    consecutive: int
    max_residual_frac: float
    hold_s: float


@dataclass(frozen=True)
class HotspotCfg:
    cell_px: int
    half_life_s: float


@dataclass(frozen=True)
class PatchCfg:
    target_px: int
    context_px: int

    @property
    def factor(self) -> int:
        """Context pixels averaged into one patch pixel."""
        return self.context_px // self.target_px


@dataclass(frozen=True)
class OodCfg:
    z_max: float
    max_out: int


@dataclass(frozen=True)
class ModelSpec:
    path: str
    sha256: str | None
    threshold: float | None

    def resolved(self) -> Path:
        p = Path(self.path)
        return p if p.is_absolute() else PROJECT_ROOT / p


@dataclass(frozen=True)
class VerifyConfig:
    mode: str
    method: str
    ring_frames: int
    window_hits: int
    min_hits: int
    deadline_s: float
    max_dets_per_frame: dict[str, int]
    motion: MotionCfg
    hotspot: HotspotCfg
    patch: PatchCfg
    ood: OodCfg
    rules_q: float
    rules_thresholds: dict[str, Any]
    models: dict[str, dict[str, ModelSpec]]
    dump: bool

    @classmethod
    def from_cfg(cls, cfg: Mapping[str, Any]) -> "VerifyConfig | None":
        """The verify section of a resolved config, or None when the config has none."""
        if "verify" not in cfg:
            return None
        v = cfg["verify"]
        w = "verify"
        method = str(_req(v, "method", w))
        if method not in METHODS:
            raise ValueError(f"verify.method {method!r}: use one of {', '.join(METHODS)}")
        m = _req(v, "motion", w)
        h = _req(v, "hotspot", w)
        p = _req(v, "patch", w)
        o = _req(v, "ood", w)
        r = _req(v, "rules", w)
        patch = PatchCfg(int(_req(p, "target_px", w + ".patch")), int(_req(p, "context_px", w + ".patch")))
        if (patch.target_px % 2 == 0 or patch.context_px % patch.target_px or patch.context_px < patch.target_px
                or (patch.context_px // patch.target_px) % 2 == 0):
            raise ValueError("verify.patch: target_px must be odd and context_px an odd multiple of it")
        models: dict[str, dict[str, ModelSpec]] = {}
        for name, per_profile in (_req(v, "models", w) or {}).items():
            models[str(name)] = {}
            for prof, spec in (per_profile or {}).items():
                ww = f"{w}.models.{name}.{prof}"
                thr = _req(spec, "threshold", ww)
                models[str(name)][str(prof)] = ModelSpec(str(_req(spec, "path", ww)), _req(spec, "sha256", ww),
                                                         None if thr is None else float(thr))
        budget = _req(v, "max_dets_per_frame", w)
        return cls(
            mode=str(_req(v, "mode", w)), method=method,
            ring_frames=int(_req(v, "ring_frames", w)), window_hits=int(_req(v, "window_hits", w)),
            min_hits=int(_req(v, "min_hits", w)), deadline_s=float(_req(v, "deadline_s", w)),
            max_dets_per_frame={str(k): int(val) for k, val in budget.items()},
            motion=MotionCfg(int(_req(m, "thumb_width", w + ".motion")), float(_req(m, "max_shift_px", w + ".motion")),
                             int(_req(m, "consecutive", w + ".motion")),
                             float(_req(m, "max_residual_frac", w + ".motion")), float(_req(m, "hold_s", w + ".motion"))),
            hotspot=HotspotCfg(int(_req(h, "cell_px", w + ".hotspot")), float(_req(h, "half_life_s", w + ".hotspot"))),
            patch=patch,
            ood=OodCfg(float(_req(o, "z_max", w + ".ood")), int(_req(o, "max_out", w + ".ood"))),
            rules_q=float(_req(r, "q", w + ".rules")),
            rules_thresholds=dict(_req(r, "thresholds", w + ".rules") or {}),
            models=models, dump=bool(_req(v, "dump", w)))

    def budget(self, profile: str) -> int:
        """Detections per frame that get features (the largest configured budget when unprofiled)."""
        if profile in self.max_dets_per_frame:
            return self.max_dets_per_frame[profile]
        return max(self.max_dets_per_frame.values())


def hp_config(method: str, extra_configs=(), overrides: Mapping[str, Any] | None = None,
              local: bool = False) -> dict[str, Any]:
    """default.yaml, the high-precision overlay, any extra configs, then verify.method = method
    and the given overrides."""
    from wfglink.config import deep_merge, load_config

    if method not in METHODS:
        raise ValueError(f"high-precision method {method!r}: use one of {', '.join(METHODS)}")
    ov = deep_merge({"verify": {"method": method}}, overrides or {})
    return load_config(OVERLAY, *(extra_configs or ()), overrides=ov, local=local)
