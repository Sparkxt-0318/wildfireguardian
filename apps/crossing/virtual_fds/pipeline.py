"""Laptop pipeline pieces run on virtual readings: thermal mask -> near edge / flame height -> depth estimators.

Uses the crossing modules unchanged (thermal, geometry, terrain, depth, fuels, heat). Geometry: FDS C064 is flat
ground, so the road profile is the IMU-plane fallback with zero grade (`terrain.imu_plane_profile(0.0)`, source
"imu") and a level virtual IMU (roll = pitch = 0). Camera on the roof head at 2.5 m, boresight level, facing the
fire (-x); the vehicle's "course" axis points at the fire, so along-course distances are distances towards -x.

Thermal frames are passed through the wire format (wfgvu.protocol.encode_thermal -> crossing.thermal
.frame_from_reading, u16 raw = 64 * K) when the vehicle-unit package imports, so the 1/64 K quantisation of the
TC001 lower-half frame is included; otherwise the float frame is used and that is recorded.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from crossing import depth as dp
from crossing import thermal as th
from crossing.fuels import C064_GRASS, Fuel
from crossing.geometry import Attitude, CameraPose, flame_height, near_edge
from crossing.terrain import imu_plane_profile

from . import lwir
from .fields import Field

CAMERA_HEIGHT_M = 2.5
POSE = CameraPose(height_m=CAMERA_HEIGHT_M)
IMU = Attitude(0.0, 0.0)
MODEL = th.DEFAULT_CAMERA


def profile(s_max_m: float = 80.0):
    return imu_plane_profile(0.0, s_max_m=s_max_m)


def wire_round_trip(temps_k: np.ndarray) -> Tuple[np.ndarray, str]:
    """encode_thermal -> decode via crossing.thermal.frame_from_reading. Returns (frame K, path label)."""
    try:
        from crossing import _repo
        _repo.vu()
        from wfgvu.protocol import encode_thermal
        data = encode_thermal(np.asarray(temps_k, dtype=np.float32), gain="low")
        fr = th.frame_from_reading(data, t=0.0, sim=True)
        return fr.temps_k, "wfgvu.protocol u16 raw/64 round trip"
    except Exception as exc:  # noqa: BLE001 - reported, never silent
        return np.asarray(temps_k, dtype=np.float32), "float frame (protocol import failed: %s)" % exc


@dataclass
class Observation:
    t: float
    x_vehicle: float
    temps_k: np.ndarray
    valid_frame: bool
    valid_reason: str
    flame_pixels: int
    flame_at_boresight: bool
    saturated_pixels: int
    near_edge: Optional[Any]
    flame_height: Optional[tuple]
    max_optical_depth: float
    wire: str
    alt_threshold: dict = field(default_factory=dict)

    def summary(self) -> dict:
        ne = self.near_edge
        return {"t_s": self.t, "x_vehicle_m": self.x_vehicle, "valid_frame": self.valid_frame,
                "valid_reason": self.valid_reason, "flame_pixels": self.flame_pixels,
                "flame_at_boresight": self.flame_at_boresight, "saturated_pixels": self.saturated_pixels,
                "near_edge_m": None if ne is None else ne.d_m,
                "near_edge_lo_m": None if ne is None else ne.d_lo_m,
                "near_edge_hi_m": None if ne is None else (ne.d_hi_m if math.isfinite(ne.d_hi_m) else None),
                "near_edge_x_world_m": None if ne is None else self.x_vehicle - ne.d_m,
                "near_edge_occluded": None if ne is None else ne.occluded,
                "flame_height_m": None if self.flame_height is None else self.flame_height[0],
                "flame_height_lo_m": None if self.flame_height is None else self.flame_height[1],
                "flame_height_hi_m": None if self.flame_height is None else (
                    self.flame_height[2] if math.isfinite(self.flame_height[2]) else None),
                "max_optical_depth_10_12um": self.max_optical_depth, "wire": self.wire,
                "alt_threshold": self.alt_threshold,
                "temp_max_c": float(self.temps_k.max() - 273.15), "temp_median_c": float(np.median(self.temps_k) - 273.15)}


def observe(f: Field, x_vehicle: float, params: lwir.OpticsParams = lwir.OpticsParams(),
            t_flame_c: float = 300.0, model: th.CameraModel = MODEL, tol_deg: float = 5.0,
            alt_thresholds_c: Sequence[float] = (200.0, 400.0)) -> Observation:
    """Render the virtual TC001 at (x_vehicle, 0, 2.5) and run crossing.thermal + crossing.geometry on it.
    The near edge and flame height are also computed for `alt_thresholds_c` (sensitivity to the 300 C placeholder)."""
    r = lwir.render(f, (x_vehicle, 0.0, CAMERA_HEIGHT_M), model=model, pose=POSE, imu=IMU, params=params)
    temps, wire = wire_round_trip(r.temps_k)
    ok, why = th.validate_frame(temps, model)
    mask = th.flame_mask(temps, t_flame_c)
    flag, _ = th.flame_at_bearing(mask, 0.0, tol_deg=3.0, model=model)
    prof = profile()
    ne = near_edge(mask, model=model, pose=POSE, imu=IMU, profile=prof, bearing_deg=0.0, tol_deg=tol_deg)
    fh = flame_height(mask, ne, model=model, pose=POSE, imu=IMU, profile=prof) if ne is not None else None
    alt = {}
    for tc in alt_thresholds_c:
        m2 = th.flame_mask(temps, tc)
        ne2 = near_edge(m2, model=model, pose=POSE, imu=IMU, profile=prof, bearing_deg=0.0, tol_deg=tol_deg)
        fh2 = flame_height(m2, ne2, model=model, pose=POSE, imu=IMU, profile=prof) if ne2 is not None else None
        alt["%g" % tc] = {"near_edge_m": None if ne2 is None else ne2.d_m,
                          "flame_height_m": None if fh2 is None else fh2[0], "flame_pixels": int(m2.sum())}
    return Observation(t=f.t, x_vehicle=x_vehicle, temps_k=temps, valid_frame=ok, valid_reason=why,
                       flame_pixels=int(mask.sum()), flame_at_boresight=bool(flag),
                       saturated_pixels=int(th.saturated_mask(temps).sum()), near_edge=ne, flame_height=fh,
                       max_optical_depth=r.max_optical_depth, wire=wire, alt_threshold=alt)


def slant_to_horizontal(slant_m: Optional[float], height_m: float = CAMERA_HEIGHT_M) -> Optional[float]:
    """Horizontal distance of an echo at slant range `slant_m`, assuming the echo is at GROUND level `height_m`
    below the radar: the conversion crossing/pipeline.py applies to the far echo (flat ground, dz = 0 here).
    None when the slant range does not reach the ground (or is missing)."""
    if slant_m is None or not math.isfinite(float(slant_m)) or float(slant_m) <= abs(height_m):
        return None
    return math.sqrt(float(slant_m) ** 2 - float(height_m) ** 2)


def ceiling_like_app(near_edge_slant_m: Optional[float], far_echo_slant_m: Optional[float],
                     range_res_m: float = 0.0488) -> dp.Estimate:
    """Estimator c exactly as the crossing app forms it (crossing/pipeline.py): both ends as HORIZONTAL distances,
    the far echo converted from its slant range with the ground-level assumption. For a reflector above the ground
    (virtual_fds: z = 1.0 m) the true horizontal distance is sqrt(r^2 - (2.5 - 1.0)^2), slightly larger than this
    (the app's ceiling is then a little low); the difference of slant ranges is a different number again."""
    return dp.radar_ceiling(slant_to_horizontal(near_edge_slant_m), slant_to_horizontal(far_echo_slant_m),
                            range_res_m)


def estimates(track: Sequence[Sequence[float]], obs_last: Observation, fuel: Fuel = C064_GRASS,
              far_echo_slant_m: Optional[float] = None, near_edge_slant_m: Optional[float] = None,
              flicker_z: Optional[Sequence[float]] = None, range_res_m: float = 0.0488) -> Dict[str, dp.Estimate]:
    """Depth estimators a-e on the virtual readings. track: rows (t, x_world of the near edge, + towards the vehicle).
    Radar quantities are slant ranges from the radar (same head, 2.5 m). c is formed as the crossing app forms it
    (`ceiling_like_app`: horizontal distances, far echo assumed at ground level); d is a range extent along the
    slant range, as the radar sees it. range_res_m: the radar config's bin spacing (run.py passes the main config's,
    0.468 m for config/iwr6843aop_vu.cfg); the 0.0488 m default is the old short config, kept for compatibility."""
    a = dp.spread_burn(np.asarray(track, dtype=float).reshape(-1, 2), fuel)
    h = obs_last.flame_height[0] if obs_last.flame_height is not None else None
    b = dp.byram(h, fuel)
    c = ceiling_like_app(near_edge_slant_m, far_echo_slant_m, range_res_m)
    d = dp.flicker_extent(flicker_z, near_edge_slant_m, range_res_m)
    e = dp.radar_loss_depth(0.0, None)
    return {"a_spread_burn": a, "b_byram": b, "c_radar_ceiling": c, "d_flicker_extent": d, "e_radar_loss_depth": e}


def combine_variants(ests: Dict[str, dp.Estimate]) -> Dict[str, dp.DepthResult]:
    """depth.combine with the default enabled set (a, b, e; uncalibrated: scale 1.5), and reported variants.
    Keys of `ests` starting with "d_flicker_extent" are alternative versions of estimator d; each variant uses one."""
    base = [v for k, v in ests.items() if not k.startswith("d_flicker_extent")]
    out = {"default(a+b)": dp.combine(base),
           "a_only": dp.combine(base, enabled=("spread_burn",)),
           "b_only": dp.combine(base, enabled=("byram",))}
    for k, label in (("d_flicker_extent", "with_flicker(a+b+d)"), ("d_flicker_extent_oracle", "with_oracle_flicker(a+b+d')")):
        if k in ests:
            out[label] = dp.combine(base + [ests[k]], enabled=("spread_burn", "byram", "flicker_extent"))
    return out


def depth_row(res: dp.DepthResult, truth_m: float, band=(7.9, 14.7)) -> dict:
    if not res.valid:
        return {"valid": False, "reason": res.reason}
    return {"valid": True, "depth_m": res.depth_m, "lo_m": res.lo_m, "hi_m": res.hi_m, "used": list(res.used),
            "scale": res.scale, "calibrated": res.calibrated, "truth_m": truth_m,
            "error_m": res.depth_m - truth_m, "ratio": res.depth_m / truth_m,
            "covers_truth": bool(res.lo_m <= truth_m <= res.hi_m),
            "covers_threshold_band": bool(res.lo_m <= band[0] and res.hi_m >= band[1]),
            "inside_threshold_band": bool(band[0] <= res.depth_m <= band[1]), "flags": list(res.flags),
            # DEPTH-HI rule: the upper end the dose uses (>= largest valid estimator upper end)
            "hi_decision_m": res.hi_decision_m, "hi_decision_from": res.hi_decision_from,
            "covers_truth_decision": bool(res.hi_decision_m is not None and res.lo_m <= truth_m <= res.hi_decision_m)}
