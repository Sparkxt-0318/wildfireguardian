"""Thermal frames from the InfiRay P2 Pro (TC001-compatible): validity, hot/flame masks, bearings (DESIGN 6.2).

Camera (user, 2026-11-17): an InfiRay P2 Pro, USB id 0bda:5830. It delivers the same 256 x 384 YUYV frame as the
Topdon TC001 (lower half = 16-bit raw temperature, raw/64 = K), so the Pi driver keeps its name `thermal_tc001.py`
and the sensor name `thermal`, and every TC001 figure below (gain ranges, 56 x 42 deg field of view) is the
TC001 vendor figure carried over: P2 Pro FOV UNVERIFIED (vendor 56 deg); P2 Pro gain ranges UNVERIFIED. The
constant names keep the TC001_ prefix for compatibility.

Frames arrive as temperature in kelvin, float [h, w] = [192, 256]. Decoding of the wire format is
`wfgvu.protocol.decode_thermal` (owned by the sensor-head code); `frame_from_reading` calls it lazily so this module
works on plain numpy arrays and is testable without the vehicle-unit package.

Physics and sensor assumptions (stated, not verified on hardware):
- The camera (P2 Pro; TC001 figures) is an uncooled microbolometer (8-14 um, LWIR). In its low-gain range it reads up to about 550 C;
  anything hotter saturates near that ceiling, so a reading of ~550 C means ">= 550 C", never a gas temperature.
  In its high-gain range (vendor ~-20..150 C) NO pixel can reach the 300 C flame threshold, so a high-gain frame
  (or one whose gain field is missing) can never show that flames are ABSENT: ``flame_evidence_mask`` then returns
  None (flame pixels unknown) and the pipeline fails closed (FS-1). The ``gain`` field is the unit's CONFIGURED
  value (the driver cannot read the camera's gain back), and the raw/64 K scale is documented for high gain only:
  until a lab check on a target hotter than 150 C confirms the camera is in low gain and the low-gain scale reads
  right (crossing.yaml ``thermal.low_gain_verified``, default false), live (non-simulated) frames are treated as
  flame-unknown too.
- Flames are optically thin in LWIR: a vegetation flame of 0.5-2 m path has an effective emissivity well below 1,
  and the flame does not fill a pixel at range. A flame whose gas is at 800-1000 C therefore commonly READS 300-600 C
  (or less for thin or distant flames). The flame threshold (default 300 C) is a configurable placeholder chosen
  to sit well above hot asphalt, sun-heated metal and engine surfaces (< ~120 C) and below typical flame readings.
  It will miss thin or distant flames (they read cooler than the threshold); that is the fail-closed direction
  here because the decision needs a FLAME to evaluate a crossing at all.
- Smoke is mostly transparent at 8-14 um compared with the visible band: smoke alone does not raise pixels to flame
  temperature. Hot exhaust, hot water mist and steam can raise readings locally; they are rejected downstream by the
  radar AND rule, not here.
- The emissivity setting of the camera (default 0.95) is applied by the camera to every pixel; no per-material
  correction is made.
- Pinhole model, principal point at the image centre unless configured, no lens distortion correction.
  Pixel (row i, col j) has its centre at continuous image coordinates (i, j); the image spans -0.5 .. w-0.5.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

C_TO_K = 273.15
TC001_LOW_GAIN_MAX_C = 550.0           # approximate saturation of the low-gain range (vendor figure, unverified)
TC001_HIGH_GAIN_MAX_C = 150.0          # approximate saturation of the high-gain range (vendor figure, unverified)
GAIN_CEILING_C = {"low": TC001_LOW_GAIN_MAX_C, "high": TC001_HIGH_GAIN_MAX_C}
VALID_MIN_K = 200.0                    # anything colder than -73 C is not a plausible camera value (TC001-compatible)
VALID_MAX_K = 1000.0                   # above ~727 C cannot come out of the low-gain range (TC001 vendor figure)


@dataclass(frozen=True)
class CameraModel:
    """Pinhole camera. Defaults: InfiRay P2 Pro / TC001 frame, 256 x 192 px, 56 x 42 deg field of view (the TC001
    vendor figure; P2 Pro FOV UNVERIFIED (vendor 56 deg): measure it, field test C).

    fx = (w/2) / tan(hfov/2), fy = (h/2) / tan(vfov/2) in pixels; principal point (cx, cy) defaults to the image
    centre ((w-1)/2, (h-1)/2) in the pixel-centre convention.
    """
    w: int = 256
    h: int = 192
    hfov_deg: float = 56.0
    vfov_deg: float = 42.0
    cx: Optional[float] = None
    cy: Optional[float] = None

    @property
    def fx(self) -> float:
        return (self.w / 2.0) / math.tan(math.radians(self.hfov_deg) / 2.0)

    @property
    def fy(self) -> float:
        return (self.h / 2.0) / math.tan(math.radians(self.vfov_deg) / 2.0)

    @property
    def ppx(self) -> float:
        return (self.w - 1) / 2.0 if self.cx is None else float(self.cx)

    @property
    def ppy(self) -> float:
        return (self.h - 1) / 2.0 if self.cy is None else float(self.cy)

    def col_bearing_deg(self, col) -> np.ndarray:
        """Horizontal angle of a column in the camera frame, degrees, + right of boresight."""
        return np.degrees(np.arctan((np.asarray(col, dtype=float) - self.ppx) / self.fx))

    def row_elevation_deg(self, row) -> np.ndarray:
        """Vertical angle of a row (on the centre column) in the camera frame, degrees, + above boresight."""
        return np.degrees(np.arctan(-(np.asarray(row, dtype=float) - self.ppy) / self.fy))

    def bearing_to_col(self, bearing_deg: float) -> float:
        return self.ppx + self.fx * math.tan(math.radians(bearing_deg))


DEFAULT_CAMERA = CameraModel()


@dataclass
class ThermalFrame:
    """One thermal frame: t (laptop monotonic s at receipt), temps_k float32 [h, w] in K."""
    t: float
    temps_k: np.ndarray
    sim: bool = False


def validate_frame(temps_k, model: CameraModel = DEFAULT_CAMERA) -> Tuple[bool, str]:
    """Shape, finiteness and range check. Fail closed: any problem -> (False, reason)."""
    a = np.asarray(temps_k)
    if a.ndim != 2 or a.shape != (model.h, model.w):
        return False, f"shape {a.shape} != {(model.h, model.w)}"
    if not np.all(np.isfinite(a)):
        return False, "non-finite pixels"
    lo, hi = float(a.min()), float(a.max())
    if lo < VALID_MIN_K or hi > VALID_MAX_K:
        return False, f"pixel range {lo:.1f}..{hi:.1f} K outside {VALID_MIN_K}..{VALID_MAX_K} K"
    if hi - lo < 1e-3:
        return False, "uniform frame (shutter, blocked lens or frozen sensor)"
    return True, ""


def frame_from_reading(data: dict, t: float, sim: bool = False) -> ThermalFrame:
    """Decode a protocol `thermal` reading's data via wfgvu.protocol.decode_thermal (imported lazily)."""
    from crossing import _repo
    _repo.vu()
    from wfgvu.protocol import decode_thermal  # owned by the sensor-head code
    return ThermalFrame(t=float(t), temps_k=np.asarray(decode_thermal(data), dtype=np.float32), sim=sim)


def flame_mask(temps_k, t_flame_c: float = 300.0) -> np.ndarray:
    """Pixels reading at or above the flame threshold (C). Thin flames read cooler than their gas temperature,
    so this under-detects thin or distant flames (see module docstring)."""
    return np.asarray(temps_k, dtype=float) >= (t_flame_c + C_TO_K)


def hot_mask(temps_k, t_hot_c: float = 60.0) -> np.ndarray:
    """Pixels at or above `t_hot_c` (C): warm surfaces, exhaust, embers, flames. Not a flame indicator."""
    return np.asarray(temps_k, dtype=float) >= (t_hot_c + C_TO_K)


def saturated_mask(temps_k, margin_c: float = 5.0, ceiling_c: float = TC001_LOW_GAIN_MAX_C) -> np.ndarray:
    """Pixels within `margin_c` of the gain ceiling (default low gain): their true reading is unknown (>= ceiling)."""
    return np.asarray(temps_k, dtype=float) >= (ceiling_c - margin_c + C_TO_K)


def gain_ceiling_c(gain) -> Optional[float]:
    """Approximate saturation of the camera range for ``gain`` (TC001 vendor figures, P2 Pro UNVERIFIED) ("low" ~550 C, "high" ~150 C, vendor ranges, NOT
    confirmed on our camera); None for a missing or unknown gain."""
    return GAIN_CEILING_C.get(gain) if isinstance(gain, str) else None


def flame_evidence_mask(temps_k, gain, t_flame_c: float = 300.0, margin_c: float = 5.0,
                        scale_verified: bool = False) -> Tuple[Optional[np.ndarray], str]:
    """(mask, reason): the flame mask ONLY when the frame can show flame pixels AND their absence (FS-1).

    Returns (None, reason) - flame pixels UNKNOWN, never "zero" - when:
    - ``gain`` is not "low" (missing or unknown counts as not low): in the high-gain range (vendor ~-20..150 C)
      no pixel can read the 300 C flame threshold, so an empty mask would be taken as "no flame";
    - the flame threshold is at or above the gain ceiling minus ``margin_c`` (same reason);
    - ``scale_verified`` is False: the raw/64 K scale is documented for the high-gain range only and the camera's
      gain is the CONFIGURED value (the driver cannot read it back), so live low-gain temperatures stay unverified
      until a lab check on a target hotter than 150 C (placeholder config ``thermal.low_gain_verified``).
    Pixels at or near the ceiling (``saturated_mask``) are counted as flame-temperature pixels: their true value
    is >= the ceiling, so they can never be read as "no flame"."""
    if gain != "low":
        return None, "thermal gain %r is not 'low': flame absence cannot be shown" % (gain,)
    ceil = gain_ceiling_c(gain)
    if ceil is None or t_flame_c >= ceil - margin_c:
        return None, "flame threshold %.0f C at or above the gain ceiling: flame absence cannot be shown" % t_flame_c
    if not scale_verified:
        return None, ("low-gain temperature scale and camera gain not verified (thermal.low_gain_verified false): "
                      "flame absence cannot be shown")
    a = np.asarray(temps_k, dtype=float)
    return flame_mask(a, t_flame_c) | saturated_mask(a, margin_c, ceil), ""


def column_bearing_deg(col, w: int = 256, hfov_deg: float = 56.0, cx: Optional[float] = None) -> np.ndarray:
    """Bearing of a column centre relative to the camera boresight, degrees, + right. Pinhole model."""
    return CameraModel(w=w, hfov_deg=hfov_deg, cx=cx).col_bearing_deg(col)


def flame_columns(mask) -> np.ndarray:
    """Indices of columns containing at least one flame pixel."""
    return np.flatnonzero(np.asarray(mask, dtype=bool).any(axis=0))


def lowest_flame_row(mask) -> np.ndarray:
    """Per column, the largest row index (lowest in the image) holding a flame pixel; -1 where none."""
    m = np.asarray(mask, dtype=bool)
    h = m.shape[0]
    has = m.any(axis=0)
    low = h - 1 - np.argmax(m[::-1, :], axis=0)
    return np.where(has, low, -1)


def top_flame_row(mask) -> np.ndarray:
    """Per column, the smallest row index (highest in the image) holding a flame pixel; -1 where none."""
    m = np.asarray(mask, dtype=bool)
    has = m.any(axis=0)
    return np.where(has, np.argmax(m, axis=0), -1)


def flame_at_bearing(mask, bearing_deg: float, tol_deg: float = 3.0, model: CameraModel = DEFAULT_CAMERA,
                     min_pixels: int = 2) -> Tuple[bool, int]:
    """Is there flame within +-tol_deg of `bearing_deg` (camera frame, + right)? Returns (flag, n_pixels).

    `min_pixels` (default 2) rejects a single hot pixel (a dead or noisy bolometer element).
    """
    m = np.asarray(mask, dtype=bool)
    if m.shape != (model.h, model.w):
        raise ValueError(f"mask shape {m.shape} != {(model.h, model.w)}")
    b = model.col_bearing_deg(np.arange(model.w))
    cols = np.abs(b - bearing_deg) <= tol_deg
    n = int(m[:, cols].sum())
    return n >= min_pixels, n


def flame_bearing_deg(mask, model: CameraModel = DEFAULT_CAMERA) -> Optional[float]:
    """Pixel-count weighted mean bearing of flame pixels, or None when there are none."""
    m = np.asarray(mask, dtype=bool)
    counts = m.sum(axis=0)
    if counts.sum() == 0:
        return None
    b = model.col_bearing_deg(np.arange(m.shape[1]))
    return float(np.sum(b * counts) / counts.sum())
