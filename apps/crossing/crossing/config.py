"""Crossing-app configuration: defaults in code, optional overrides from ``crossing.yaml`` (DESIGN.md sections 5, 8, 9).

Every threshold here is a PLACEHOLDER for a fire service (or the research team) to set; none has been validated on
a real fire or on the real sensors. Units are in the key names (``_s`` seconds, ``_m`` metres, ``_c`` deg C,
``_kw_m2`` kW/m2, ``_deg`` degrees, ``_hz`` hertz).

Loading: ``load_config(path=None, overrides=None)`` starts from the dataclass defaults, deep-merges the YAML file
(``apps/crossing/crossing.yaml`` when it exists and no path is given), then ``overrides`` (a nested dict, used by the
CLI). Unknown keys raise ``ValueError`` so a typo in a limit cannot silently fall back to a default.
"""
from __future__ import annotations

import copy
import math
import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from . import _repo
from .decision import DecisionConfig

APP = _repo.APP
DEFAULT_YAML = APP / "crossing.yaml"
DEFAULT_RECORDS = APP / "records"

SENSORS = ("thermal", "radar", "tc_plate", "tc_housing", "tc_air", "imu", "gnss", "pi")


def _freeze_defaults() -> Dict[str, Optional[float]]:
    # VALUE freeze windows (orchestrator decision D2, 2026-11-17; DESIGN 5 as built). Thermal and radar are noisy
    # sensors whose raw values never repeat byte for byte while working: identical thermal pixels or identical radar
    # IQ / range profile for >= 1.0 s = frozen (a P2 Pro (TC001-compatible) shutter/FFC pause > 1 s gives a brief
    # fail-closed CLOSED). Thermocouples (0.25 C steps), the IMU (1/16 deg steps, still vehicle) and a GNSS without
    # a fix can legitimately repeat identical values, so their value windows stay long (imu 2.0, tc_* 5.0,
    # gnss 5.0); for them a frozen Pi stream is caught at once by the wire seq / t_mono check in link.py instead.
    # The Pi health payload is not value-checked (None); its seq / t_mono still are.
    return {"thermal": 1.0, "radar": 1.0, "imu": 2.0, "tc_plate": 5.0, "tc_housing": 5.0, "tc_air": 5.0,
            "gnss": 5.0, "pi": None}


@dataclass
class LinkConfig:
    """Freshness rules of DESIGN 5 (laptop monotonic clock at receipt) and the WebSocket client behaviour."""
    stale_s: float = 2.0                 # a reading must have arrived within this
    heartbeat_stale_s: float = 2.0       # the Pi's latest heartbeat for the sensor must be this recent and "ok"
    freeze_s: Dict[str, Optional[float]] = field(default_factory=_freeze_defaults)
    silence_s: float = 1.5               # no message at all for this long = link down (Pi heartbeats every 0.5 s)
    reconnect_min_s: float = 0.5         # exponential backoff between connection attempts
    reconnect_max_s: float = 5.0
    open_timeout_s: float = 3.0
    ping_interval_s: float = 1.0
    ping_timeout_s: float = 2.0
    max_frame_bytes: int = 8 * 1024 * 1024


def _use_max_age_defaults() -> Dict[str, float]:
    # Stricter than the 2 s link staleness: the pipeline stops USING a sensor's latest value when it is older than
    # this (laptop receipt clock). Thermal/radar/tc/imu follow the Pi driver stale_s (DESIGN 3; imu raised from 0.5
    # to 1.0 for Wi-Fi jitter); gnss 1.5 s assumes a receiver at >= 1 Hz (a 1 Hz receiver with Wi-Fi jitter may
    # need 2.0). This is what makes a sensor that stops close the verdict in under 2 s. pi (1 Hz health) 1.6 s since
    # every sensor is required for every verdict (D1): 3.0 s (or the 2.0 s link staleness) let a stopped pi stream
    # close only after 2.0-2.2 s; 1.6 s gives <= 1.8 s, at the price of a short CLOSED when one 1 Hz pi reading is
    # more than 0.6 s late (fail closed).
    return {"thermal": 1.0, "radar": 1.0, "tc_plate": 1.0, "tc_housing": 1.0, "tc_air": 1.0, "imu": 1.0,
            "gnss": 1.5, "pi": 1.6}


@dataclass
class ThermalConfig:
    t_flame_c: float = 300.0             # flame-temperature pixel threshold (placeholder; flames read cool, 6.2)
    t_hot_c: float = 60.0                # hot-pixel threshold (display only)
    bearing_tol_deg: float = 3.0         # flame_at_bearing tolerance
    min_pixels: int = 2                  # a single hot pixel is not a flame
    # InfiRay P2 Pro (TC001-compatible 256 x 192 temperature frame). 56 x 42 deg is the TC001 vendor figure kept
    # for the P2 Pro: P2 Pro FOV UNVERIFIED (vendor 56 deg); measure it (test C) before trusting near-edge ranges.
    hfov_deg: float = 56.0
    vfov_deg: float = 42.0
    width: int = 256
    height: int = 192
    # FS-1: live (non-simulated) thermal frames show flame ABSENCE only after a lab check on a target hotter than
    # 150 C has confirmed that the camera really is in low gain and that the low-gain raw scale (raw/64 K, documented
    # for high gain only) reads right. Until then this stays false and every live frame counts as flame-unknown
    # (verdicts CLOSED). Frames whose gain field is not "low" are flame-unknown whatever this says. PLACEHOLDER.
    low_gain_verified: bool = False
    saturation_margin_c: float = 5.0     # pixels within this of the gain ceiling count as flame-temperature pixels


@dataclass
class MountConfig:
    """PLACEHOLDERS to be measured on the vehicle (mirrors hardware/vehicle-unit/config/unit.yaml ``mount``).

    ``camera_pitch_deg = None`` (default) takes the pitch from the unit: the ``mount`` of the Pi's ``hello`` (or of
    a replayed session's session.json config) when present, else ``hardware/vehicle-unit/config/unit.yaml``
    ``mount.camera_pitch_deg``, else 0. A number here overrides the unit. ``imu_heading_trusted = None`` likewise
    takes ``mount.imu_heading_trusted`` from the unit (default False: IMU yaw is not used for the REOPENED view)."""
    camera_height_m: float = 2.6
    camera_pitch_deg: Optional[float] = None
    camera_roll_deg: float = 0.0
    camera_yaw_deg: float = 0.0
    imu_mount_pitch_deg: float = 0.0     # IMU pitch reading on level ground (removed before the slope fallback)
    radar_height_m: float = 2.6
    radar_yaw_deg: float = 0.0
    imu_heading_trusted: Optional[bool] = None
    imu_heading_offset_deg: float = 0.0  # added to the IMU (magnetic) heading when trusted: declination + mount yaw
    # Sign of the build manual's sensor x offsets (unit hello.mount.sensor_offsets_mm, from
    # hardware/vehicle-unit/config/unit.yaml). +1 = manual +x is to the RIGHT when looking along the camera's view
    # (from behind the unit); -1 = manual +x is to the right as seen standing in FRONT of the unit (the working
    # reading noted in unit.yaml: "+ to the right seen from the front"); 0 (default) = sign UNCONFIRMED, no lateral
    # parallax correction is applied (insensitive to a sign flip: the bearing error stays atan(44 mm / r), 0.25 deg
    # at 10 m; a wrong sign would double it). Only the radar-bearing parallax correction uses it (camera x -52 mm,
    # radar x -8 mm, against the 2.5 deg baseline-beam tolerance), see pipeline.sensor_parallax_deg. Set +1 or -1
    # only once the build manual's convention is confirmed.
    offset_x_sign: int = 0


@dataclass
class FluxConfig:
    """Flux-disc protection. The copper disc sits on printed PETG tabs (user's build, 2026-11-17), so a plate
    thermocouple (tc_plate) reading >= ``disc_max_c`` is a tc_plate FAULT (PLATE_DISC_OVER_TEMP): every verdict is
    CLOSED while it lasts, the plate flux is marked invalid, no calibration pair is recorded and the REOPENED quiet
    hold restarts. 70 C is the USER-SET limit (not a placeholder); allowed range 40..70 C (never above the user's
    70 C, as on the Pi; the lower bound only catches a typo). The field-test record
    scripts stop a run at the same value (field_tests/recordkit.DiscGuard)."""
    disc_max_c: float = 70.0


@dataclass
class GeometryConfig:
    pitch_sigma_deg: float = 0.5
    s_max_m: float = 80.0
    ds_m: float = 2.0
    column_step: int = 2                 # evaluate every n-th flame column for the near edge (speed; 2 = 0.22 deg)
    path_half_width_deg: float = 6.0     # near edge = nearest flame base within this of the vehicle's path
                                         # (straight ahead along the course); ~ (half vehicle width + margin) at 10 m
    # REOPENED view of the recorded crossing (D3). PLACEHOLDERS.
    reopen_max_view_m: float = 40.0      # the far end of the crossing must be within this distance of the camera
    reopen_fov_margin_deg: float = 4.0   # the crossing must lie this far inside the image edges (heading error)
    reopen_half_width_m: float = 4.0     # lateral half-width of the crossed road patch around the track
    # FS-3: the facing used for the REOPENED view. GNSS course is the direction of TRAVEL, so it is taken as the
    # facing only at >= reliable_course_speed_m_s, within course_imu_max_diff_deg of a trusted IMU heading, and not
    # jumping more than course_jump_deg from the last forward course (reversing). PLACEHOLDERS.
    reliable_course_speed_m_s: float = 2.0
    course_imu_max_diff_deg: float = 60.0
    course_jump_deg: float = 120.0
    low_speed_course_tol_deg: float = 15.0   # below the reliable speed the held facing survives only within this
    # FS-8: line of sight to the crossing (DEM terrain only) and the image check at the patch's ground points.
    reopen_los_ds_m: float = 1.0         # DEM profile step towards each patch point
    reopen_ground_min_c: float = -30.0   # patch ground pixels must read within this range (colder = sky) PLACEHOLDER
    reopen_ground_max_c: float = 150.0
    # FS-9: BNO055 accel / gyro calibration status (0-3) below this = IMU fault (pitch/roll feed the near edge and
    # the flame height). PLACEHOLDER.
    imu_min_calib: int = 1


@dataclass
class RadarConfig:
    """Baseline management and detector overrides (crossing.radar_flame.RadarFlameConfig field names)."""
    detector: Dict[str, Any] = field(default_factory=dict)
    baseline_frames: int = 30            # newest usable frames used by a capture (>= 20, RadarBaseline.MIN_FRAMES)
    buffer_frames: int = 100
    moving_speed_m_s: float = 0.3        # GNSS speed above this = moving: radar UNKNOWN, baseline invalidated
    baseline_move_m: float = 3.0         # GNSS displacement from the capture point that invalidates it (GNSS wander ~1-2 m)
    auto_baseline: bool = False          # capture automatically once stationary with no flame pixels (opt-in)
    auto_baseline_still_s: float = 4.0
    baseline_file: Optional[str] = None  # load at start (JSON from RadarBaseline.save)
    ui_max_bins: int = 128               # per-bin arrays in State are max-pooled to at most this many bins


@dataclass
class DepthConfig:
    enabled: Optional[List[str]] = None  # None = depth.DEFAULT_ENABLED (spread_burn, byram, radar_loss_depth)
    spread_track_s: float = 30.0         # near-edge world track kept for estimator a
    flicker_k: float = 4.0
    # DEPTH-HI rule (depth.py): the dose uses an upper end >= the largest valid non-experimental estimator upper
    # end. narrow_decision_hi = true lets it fall to the combined upper end, but only for a fuel calibrated with
    # >= narrow_decision_hi_min_pairs pairs (>= 9, the conformal minimum). PLACEHOLDERS; default off.
    narrow_decision_hi: bool = False
    narrow_decision_hi_min_pairs: int = 30
    disagree_factor: float = 3.0         # ESTIMATORS_DISAGREE when max/min estimator central value exceeds this


@dataclass
class CrossingDetectConfig:
    """Automatic crossing detection for calibration pairs (DESIGN 7)."""
    thickness_q_kw_m2: float = 5.0       # pulse detection, far-edge record, and the measured-thickness floor
    # Measured thickness threshold = max(thickness_q_kw_m2, thickness_frac_of_peak * pulse peak) (D7, see
    # calibrate.measure_thickness). 0 restores the fixed 5 kW/m2 threshold of DESIGN 7.
    thickness_frac_of_peak: float = 0.5
    min_speed_m_s: float = 0.5           # GNSS movement needed for a pulse to count as a crossing
    end_hold_s: float = 2.0              # flux below threshold this long ends the pulse
    buffer_s: float = 180.0
    prediction_max_age_s: float = 60.0   # newest valid depth prediction before the pulse must be this recent
    flux_window_s: float = 1.0           # centred derivative window (flux.derivative) for the measured thickness


@dataclass
class PathsConfig:
    records_dir: str = str(DEFAULT_RECORDS)
    pairs_path: Optional[str] = None     # None = calibrate.DEFAULT_PAIRS_PATH (real sessions only)
    sim_pairs_path: Optional[str] = None  # None = records/calibration/pairs_sim.jsonl (simulated sessions)
    replay_pairs_path: Optional[str] = None  # None = records/calibration/pairs_replay.jsonl (replays of real data)
    plate_loss_file: Optional[str] = None


@dataclass
class LogConfig:
    enabled: bool = True
    chunk_frames: int = 100              # frames per thermal/radar npz chunk
    keep_wire: bool = True               # wire.jsonl.gz: every received message + receipt time (replayable)
    health_every_s: float = 1.0


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8781
    ws_hz: float = 5.0


@dataclass
class Config:
    tick_hz: float = 5.0
    link: LinkConfig = field(default_factory=LinkConfig)
    use_max_age_s: Dict[str, float] = field(default_factory=_use_max_age_defaults)
    thermal: ThermalConfig = field(default_factory=ThermalConfig)
    mount: MountConfig = field(default_factory=MountConfig)
    geometry: GeometryConfig = field(default_factory=GeometryConfig)
    radar: RadarConfig = field(default_factory=RadarConfig)
    depth: DepthConfig = field(default_factory=DepthConfig)
    crossing: CrossingDetectConfig = field(default_factory=CrossingDetectConfig)
    decision: DecisionConfig = field(default_factory=DecisionConfig)
    plate: Dict[str, float] = field(default_factory=dict)     # flux.PlateSpec overrides
    flux: FluxConfig = field(default_factory=FluxConfig)       # disc_max_c (70 C, user-set: PETG tabs)
    # Derivative window of flux.FluxEstimator. 2.2 s, not the 1.0 s default of DESIGN 6.1. First chosen because
    # FluxEstimator rejected about half of jittered 10 Hz samples at 1.0 s; that pruning bug is fixed in flux.py
    # (integration, 2026-11-17), but 2.2 s is KEPT for noise: at 1.0 s the flux noise of a quiet plate (0.1 C
    # thermocouple noise, 0.25 C steps, SIMULATED) crosses the 1.0 kW/m2 REOPENED threshold often enough to reset the
    # 30 s quiet hold again and again (REOPENED never reached on a synthetic 80 s crossing). Cost: more smoothing and
    # a 1.1 s lag of the flux estimate. Placeholder: to be set from real plate noise.
    flux_window_s: float = 2.2
    paths: PathsConfig = field(default_factory=PathsConfig)
    log: LogConfig = field(default_factory=LogConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    vehicle: str = "fire_engine"
    fuel: str = "DEFAULT"

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def _merge(obj: Any, data: Any, where: str) -> Any:
    """Return ``obj`` updated from ``data`` (dataclasses recursively, dicts merged key by key)."""
    if data is None:
        return obj
    if dataclasses.is_dataclass(obj):
        if not isinstance(data, dict):
            raise ValueError("%s: expected a mapping" % where)
        names = {f.name for f in dataclasses.fields(obj)}
        for k, v in data.items():
            if k not in names:
                raise ValueError("%s: unknown key %r" % (where, k))
            setattr(obj, k, _merge(getattr(obj, k), v, "%s.%s" % (where, k)))
        return obj
    if isinstance(obj, dict) and isinstance(data, dict):
        out = dict(obj)
        for k, v in data.items():
            out[k] = _merge(out.get(k), v, "%s.%s" % (where, k)) if isinstance(out.get(k), dict) else v
        return out
    return data


def load_config(path: Optional[Any] = None, overrides: Optional[dict] = None) -> Config:
    """Defaults <- YAML file <- overrides. ``path=None`` uses ``crossing.yaml`` next to this app if present."""
    cfg = Config()
    p = Path(path) if path is not None else DEFAULT_YAML
    if path is not None and not p.exists():
        raise FileNotFoundError("config file not found: %s" % p)
    if p.exists():
        with open(p, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        _merge(cfg, data, "config")
    if overrides:
        _merge(cfg, copy.deepcopy(overrides), "overrides")
    validate(cfg)
    return cfg


def _real(v) -> bool:
    """Finite real number, bool excluded."""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def _check(where: str, v, lo: Optional[float] = None, hi: Optional[float] = None, *, lo_open: bool = False,
           integer: bool = False) -> None:
    if not _real(v) or (integer and float(v) != int(v)):
        raise ValueError("%s must be a finite %s, got %r" % (where, "integer" if integer else "number", v))
    if lo is not None and (v <= lo if lo_open else v < lo):
        raise ValueError("%s must be %s %s (placeholder bound), got %r" % (where, ">" if lo_open else ">=", lo, v))
    if hi is not None and v > hi:
        raise ValueError("%s must be <= %s (placeholder bound), got %r" % (where, hi, v))


# FS-4: bounds a crossing.yaml / override value must stay inside, so a typo cannot switch the fail-safe off (a huge
# q0 or tiny chi zeroing the dose, a verdict that never expires, stale values kept for ever). The bounds are
# PLACEHOLDERS like the limits themselves; they bracket the shipped defaults.
FREEZE_MAX_S = {"thermal": 2.0, "radar": 2.0}      # noisy sensors: value freeze must be caught fast
FREEZE_OTHER_MAX_S = 5.0                            # tc_* / imu / gnss repeat legitimately (shipped 5.0 / 2.0)
DISC_MAX_C_USER = 70.0                             # user's flux-disc limit (PETG tabs): hard upper bound
WINDOW_MAX_S = 2.0                                  # link staleness and use_max_age_s (shipped max: pi 1.6)


def _validate_decision(d) -> None:
    w = "decision."
    _check(w + "verdict_ttl_s", d.verdict_ttl_s, 0.0, 5.0, lo_open=True)
    _check(w + "stale_s", d.stale_s, 0.0, 2.0, lo_open=True)
    _check(w + "q0_kw_m2", d.q0_kw_m2, 0.0, 5.0)
    _check(w + "chi", d.chi, 0.1, 1.0)
    _check(w + "spray_margin", d.spray_margin, 0.0, 0.5)
    _check(w + "min_flame_evidence_s", d.min_flame_evidence_s, 3.0)
    _check(w + "reopen_hold_s", d.reopen_hold_s, 30.0)
    _check(w + "approach_m", d.approach_m, 0.0, lo_open=True)
    _check(w + "reopen_flux_kw_m2", d.reopen_flux_kw_m2, 0.0, 1.0)
    _check(w + "reopen_hot_pixels", d.reopen_hot_pixels, 0.0, integer=True)
    _check(w + "reopen_max_speed_m_s", d.reopen_max_speed_m_s, 0.0, 1.0)
    _check(w + "speed_resolution_m_s", d.speed_resolution_m_s, 0.0, lo_open=True)
    _check(w + "leg_points", d.leg_points, 50.0, integer=True)
    if d.half_width_m is not None:
        _check(w + "half_width_m", d.half_width_m, 0.0, lo_open=True)


def validate(cfg: Config) -> None:
    """Sanity of rates, windows and every decision setting (FS-4; bounds are placeholders). Raises ValueError, so a
    bad crossing.yaml or override refuses to start instead of starting with the fail-safe off."""
    if not (_real(cfg.tick_hz) and cfg.tick_hz > 0):
        raise ValueError("tick_hz must be > 0")
    _check("link.stale_s", cfg.link.stale_s, 0.0, WINDOW_MAX_S, lo_open=True)
    _check("link.heartbeat_stale_s", cfg.link.heartbeat_stale_s, 0.0, WINDOW_MAX_S, lo_open=True)
    _check("link.silence_s", cfg.link.silence_s, 0.0, lo_open=True)
    for s, v in cfg.link.freeze_s.items():
        if v is None and s == "pi":
            continue                                 # the Pi health payload is not value-checked (seq/t_mono are)
        _check("link.freeze_s.%s" % s, v, 0.0, FREEZE_MAX_S.get(s, FREEZE_OTHER_MAX_S), lo_open=True)
    for s in SENSORS:
        if s != "pi" and s not in cfg.link.freeze_s:
            raise ValueError("link.freeze_s.%s missing" % s)
        if s not in cfg.use_max_age_s:
            raise ValueError("use_max_age_s.%s missing" % s)
    for s, v in cfg.use_max_age_s.items():
        _check("use_max_age_s.%s" % s, v, 0.0, WINDOW_MAX_S, lo_open=True)
    _validate_decision(cfg.decision)
    # 70 C is the user's limit for the PETG tabs under the copper disc: never above it (the Pi caps it at 70 too);
    # the lower bound only stops a typo
    _check("flux.disc_max_c", cfg.flux.disc_max_c, 40.0, DISC_MAX_C_USER)
    if cfg.mount.offset_x_sign not in (1, 0, -1) or isinstance(cfg.mount.offset_x_sign, bool):
        raise ValueError("mount.offset_x_sign must be +1, 0 (unconfirmed: no correction) or -1, got %r"
                         % (cfg.mount.offset_x_sign,))
    if not isinstance(cfg.thermal.low_gain_verified, bool):
        raise ValueError("thermal.low_gain_verified must be true or false")
    _check("thermal.t_flame_c", cfg.thermal.t_flame_c, 0.0)
    _check("geometry.reliable_course_speed_m_s", cfg.geometry.reliable_course_speed_m_s,
           cfg.radar.moving_speed_m_s if _real(cfg.radar.moving_speed_m_s) else 0.0, lo_open=True)
    _check("geometry.course_imu_max_diff_deg", cfg.geometry.course_imu_max_diff_deg, 0.0, 180.0, lo_open=True)
    _check("geometry.course_jump_deg", cfg.geometry.course_jump_deg, 0.0, 180.0, lo_open=True)
    _check("geometry.low_speed_course_tol_deg", cfg.geometry.low_speed_course_tol_deg, 0.0, 45.0)
    _check("geometry.reopen_los_ds_m", cfg.geometry.reopen_los_ds_m, 0.0, 5.0, lo_open=True)
    _check("geometry.imu_min_calib", cfg.geometry.imu_min_calib, 0.0, 3.0, integer=True)
    if cfg.radar.baseline_frames < 20:
        raise ValueError("radar.baseline_frames must be >= 20 (RadarBaseline.MIN_FRAMES)")
    if cfg.geometry.column_step < 1:
        raise ValueError("geometry.column_step must be >= 1")
    if not 0.0 <= cfg.crossing.thickness_frac_of_peak < 1.0:
        raise ValueError("crossing.thickness_frac_of_peak must be in [0, 1)")
    if not cfg.geometry.reopen_max_view_m > 0:
        raise ValueError("geometry.reopen_max_view_m must be > 0")
    if not isinstance(cfg.depth.narrow_decision_hi, bool):
        raise ValueError("depth.narrow_decision_hi must be true or false")
    _check("depth.narrow_decision_hi_min_pairs", cfg.depth.narrow_decision_hi_min_pairs, 9.0, integer=True)
    _check("depth.disagree_factor", cfg.depth.disagree_factor, 1.0, 100.0, lo_open=True)
