"""Fusion pipeline: link messages -> physics modules -> verdict -> State, at 5 Hz (DESIGN.md sections 5-9).

``Pipeline(cfg, vehicle, fuel)`` consumes parsed protocol messages (live link or replay) with the laptop receipt
time, and ``tick(now)`` (every 0.2 s) runs:

  thermal frame -> flame mask (thermal.py) -> near edge + flame height (geometry.py over a terrain Profile)
  radar frames -> RadarFlameDetector vs the captured baseline (radar_flame.py) -> fuse_flame (AND rule)
  plate thermocouple -> FluxEstimator + RunningDose (flux.py)
  depth estimators a-e + combine + intensity (depth.py), calibration per fuel (calibrate.py)
  decision.decide -> Verdict; effective() expiry; ReopenTracker; has_passed
  -> State dict (JSON schema in apps/crossing/README.md, STATE_SCHEMA), research log rows, optional sim-link.

Fail-closed rules applied here (on top of decision.py's own):
- A sensor's latest value is USED only while it is younger than ``use_max_age_s[sensor]`` on the laptop receipt
  clock (thermal/radar/tc/imu 1.0 s, gnss 1.5 s). Older values become None, the sensor gets no input time, and the
  decision closes. Together with the 5 Hz tick this closes the verdict within 2 s of a sensor stopping.
- Thermal frames failing ``thermal.validate_frame`` (shape, range, uniform/frozen) count as a thermal fault.
- FS-1: flame pixels come only from a frame that can show their ABSENCE: gain field "low" (missing / "high" = not
  low: no high-gain pixel can read 300 C), threshold below the gain ceiling, and the low-gain scale verified on the
  camera (crossing.yaml ``thermal.low_gain_verified``, default false; simulated data counts as verified). Otherwise
  flame pixels are None (fused flame UNKNOWN, REOPENED hold never builds) and the thermal sensor carries a fault.
  Pixels at the gain ceiling count as flame pixels.
- FS-9: IMU accel/gyro calibration status below ``geometry.imu_min_calib`` (placeholder) is an IMU fault.
- A radar frame with ``frame_ok`` false is a radar fault for that tick; the detector also reports UNKNOWN.
- Vehicle moving (GNSS speed > ``moving_speed_m_s``) or speed unknown -> radar UNKNOWN (echo phases change with
  any motion); moving or GNSS displacement > ``baseline_move_m`` invalidates the radar baseline.
- Any exception inside the per-tick computation gives a CLOSED verdict with reason INTERNAL_ERROR.
- Every sensor's health (reading, heartbeat, freeze) must be fresh for every go verdict (decision.ALL_SENSORS, D1).
- Minimum flame evidence (D4): the fused FLAME must have held continuously for ``decision.min_flame_evidence_s``
  (3.0 s) on consecutive ticks before CROSS FAST / SPRAY (``flame_held_s``; a gap > stale_s restarts it).
- Flame base cut off by the image bottom or side (geometry ``base_cut_off``) or hidden behind terrain
  (``occluded``) -> NEAR_EDGE_NOT_OBSERVED (D5, FS-2).
- REOPENED view (D3): the recorded crossing (near/far edge GNSS positions at the plate-flux pulse, or the recorded
  flame location + depth_hi) must be inside the camera's current view: every corner of the crossed road patch
  (+-``reopen_half_width_m`` across the track) at a camera bearing within the horizontal FOV minus
  ``reopen_fov_margin_deg``, its far end within ``reopen_max_view_m`` (40 m), LINE OF SIGHT to every patch point
  over the DEM (FS-8; terrain only: buildings, walls, vegetation are not in a bare-earth DEM; no DEM = not
  verifiable = not in view), every point projected (DEM heights, camera height, mount and IMU pitch/roll) inside
  the image margins, and the thermal pixel at each point a plausible ground temperature (``reopen_ground_min_c``
  .. ``reopen_ground_max_c``). Facing (FS-3): a trusted IMU heading (+ offset) first; else the GNSS course of the
  last forward travel at >= ``reliable_course_speed_m_s`` (2 m/s), held while stopped; manoeuvring between 0.3 and
  2 m/s or a course jump > ``course_jump_deg`` (reversing) from the last forward course makes the facing unknown
  until reliable forward travel in the old direction (or a trusted IMU heading) shows it again. The quiet hold also
  needs zero flame-temperature pixels in the image columns covering the crossing. Otherwise CLOSED with
  REOPEN_CROSSING_NOT_IN_VIEW and ``reopen.view.hint`` asks the crew to face the crossed road. All placeholders.

Physics and geometry assumptions made here (the physics modules state theirs):
- The flux estimator and the crossing pulse use the Pi's ``t_mono`` (sample timing on the Pi, no Wi-Fi jitter in
  dT/dt); everything about freshness uses the laptop clock.
- Radar ranges are slant ranges from the radar; the near edge from geometry is an along-course horizontal distance
  to the flame base on the ground. Conversion: slant = hypot(d, radar_height - ground_dz(d)); the first solid echo
  is converted back to a horizontal distance with the same height difference (echo assumed at ground level).
- Camera mount pitch: crossing.yaml ``mount.camera_pitch_deg`` when set, else the unit's own value (``hello.mount``
  / replayed session.json, else hardware/vehicle-unit/config/unit.yaml ``mount``), else 0 (state geometry.camera).
- Local east/north metres from GNSS use an equirectangular projection about the first fix (error < 1 cm per km at
  the distances used here). The recorded flame location (REOPENED reference) is the vehicle position + d along
  the camera's facing (FS-3; lateral offsets ignored). The course (radar / near-edge track frame) is the last GNSS
  course while moving (speed > moving_speed_m_s); stopped GNSS course is meaningless and is not used. The near-edge track for the spread rate (estimator a) is kept in the vehicle frame
  while stationary (no GNSS noise) and in that course-aligned world frame while moving.
- Without a DEM, the road profile is the IMU-grade plane (slope_source "imu"); with ``--dem`` the DEM profile along
  the facing (FS-3; slope_source "dem"), falling back to the IMU plane when the facing is unknown or the DEM gives
  no valid profile.
- Crossing detection (for calibration pairs, DESIGN 7): a pulse starts when a valid plate flux exceeds
  ``thickness_q_kw_m2`` (5 kW/m2) while GNSS speed >= ``min_speed_m_s``; it ends after ``end_hold_s`` below the
  threshold. calibrate.measure_thickness (threshold max(5 kW/m2, half the pulse peak), D7) then gives the measured
  thickness; it is paired with the depth predicted
  by the last CROSS FAST / SPRAY verdict (else the last valid depth) within ``prediction_max_age_s``. Pairs from
  simulated sessions go to a SEPARATE store (pairs_sim.jsonl) and never calibrate real sessions; replays of
  recorded real sessions go to pairs_replay.jsonl (FS-5). A pair repeating a stored crossing (same pulse, same
  prediction, same key) is refused, so --loop passes and repeated "mark crossing" presses add nothing.

Nothing here has run against the real roof unit; all tests use synthetic sessions.
"""
from __future__ import annotations

import asyncio
import base64
import collections
import heapq
import json
import logging
import math
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterable, Iterator, List, Optional, Tuple

import numpy as np

from . import __version__, _repo
from . import calibrate as cal
from . import decision as dc
from . import depth as dp
from . import flux as fx
from . import fuels as fu
from . import heat
from . import radar_flame as rf
from . import thermal as th
from .config import Config, load_config
from .geometry import Attitude, CameraPose, flame_height, flame_top_cut_off, level_from_camera, near_edge
from .link import LinkState
from .terrain import Dem, Profile, imu_plane_profile, line_of_sight, road_profile
from .vehicles import PLACEHOLDER_NOTE, Vehicle, get_vehicle

_repo.vu()
from wfgvu import protocol  # noqa: E402

log = logging.getLogger("crossing.pipeline")

STATE_SCHEMA = "crossing.state/1"
EARTH_R = 6371008.8
ADVISORY = "Advisory only: verdicts are for trained crews. Every limit is a PLACEHOLDER for the fire service to set."
HEAT_D_M = (0.0, 1.0, 2.0, 5.0, 10.0, 15.0, 20.0, 30.0, 40.0, 50.0)
REOPEN_VIEW_HINT = "Face the crossed road: stop with the crossing in front of the camera, within %.0f m."


def _unit_yaml_mount() -> dict:
    """``mount`` of hardware/vehicle-unit/config/unit.yaml ({} when missing or unreadable)."""
    try:
        import yaml
        with open(_repo.VU_ROOT / "config" / "unit.yaml", "r", encoding="utf-8") as fh:
            d = yaml.safe_load(fh) or {}
        m = d.get("mount") if isinstance(d, dict) else None
        return dict(m) if isinstance(m, dict) else {}
    except Exception:  # noqa: BLE001 - no unit config: defaults
        return {}


def _wrap180(a: float) -> float:
    return (a + 180.0) % 360.0 - 180.0


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _num(v) -> bool:
    return isinstance(v, (int, float, np.floating, np.integer)) and not isinstance(v, (bool, np.bool_)) \
        and math.isfinite(float(v))


def _f(v) -> Optional[float]:
    return float(v) if _num(v) else None


def _pool(a, factor: int, how: str = "max") -> list:
    """Downsample a per-bin array by ``factor`` (max / any / first). NaNs are ignored where possible."""
    x = np.asarray(a)
    if factor <= 1 or x.size == 0:
        return x.tolist()
    n = int(math.ceil(x.size / factor))
    if x.dtype == bool or how == "any":
        pad = np.zeros(n * factor, dtype=bool)
        pad[:x.size] = x.astype(bool)
        return pad.reshape(n, factor).any(axis=1).tolist()
    if how == "first":
        return x[::factor].tolist()
    pad = np.full(n * factor, np.nan)
    pad[:x.size] = x.astype(float)
    r = pad.reshape(n, factor)
    with np.errstate(all="ignore"):
        allnan = np.all(np.isnan(r), axis=1)
        out = np.where(allnan, np.nan, np.nanmax(np.where(np.isnan(r), -np.inf, r), axis=1))
    return out.tolist()


@dataclass
class ThermalLatest:
    rx: float
    temps_k: Optional[np.ndarray]
    valid: bool
    reason: str
    mask: Optional[np.ndarray]
    flame_pixels: Optional[int]
    hot_pixels: Optional[int]
    shutter: bool = False
    flame_unknown: str = ""          # FS-1: why flame pixels are unknown (mask None) on an otherwise valid frame


@dataclass
class Geo:
    """Geometry result for one thermal frame."""
    rx: float
    profile: Optional[Profile]
    ne: Any                       # geometry.NearEdge or None
    fh: Optional[Tuple[float, float, float]]
    reason: str


class Pipeline:
    """See module docstring. Single-threaded: call ``feed``/``on_text``/``tick`` from one thread or event loop."""

    def __init__(self, cfg: Optional[Config] = None, vehicle: Any = None, fuel: Any = None, *,
                 dem: Optional[Dem] = None, research_log: Any = None, simlink: Any = None, mode: str = "live",
                 source: str = "", baseline: Optional[rf.RadarBaseline] = None):
        self.cfg = cfg if cfg is not None else load_config()
        self.vehicle: Vehicle = vehicle if isinstance(vehicle, Vehicle) else get_vehicle(vehicle or self.cfg.vehicle)
        self.fuel: fu.Fuel = fu.get_fuel(fuel or self.cfg.fuel)
        self.dem = dem
        self.rlog = research_log
        self.simlink = simlink
        self.mode = mode
        self.source = source
        self.link = LinkState(self.cfg.link)
        c = self.cfg
        self.camera = th.CameraModel(w=c.thermal.width, h=c.thermal.height, hfov_deg=c.thermal.hfov_deg,
                                     vfov_deg=c.thermal.vfov_deg)
        self.mount_info: Dict[str, Any] = {}
        self.imu_heading_trusted = False
        self._apply_unit_mount(_unit_yaml_mount(), "vehicle-unit config/unit.yaml")
        self.plate = fx.PlateSpec(**c.plate)
        loss = None
        if c.paths.plate_loss_file:
            loss = fx.LossModel.load(c.paths.plate_loss_file)
        self.flux_est = fx.FluxEstimator(self.plate, loss, window_s=c.flux_window_s)
        self.dose = fx.RunningDose(q0=c.decision.q0_kw_m2)
        if baseline is None and c.radar.baseline_file:
            baseline = rf.RadarBaseline.load(c.radar.baseline_file)
        self.detector = rf.RadarFlameDetector(baseline, cfg=rf.RadarFlameConfig(**c.radar.detector))
        self.baseline_info: Dict[str, Any] = {"present": baseline is not None, "reason": "loaded from file"
                                              if baseline is not None else "no baseline captured"}
        self._baseline_pos: Optional[Tuple[float, float]] = None
        self.radar_buf: Deque[rf.RadarFrame] = collections.deque(maxlen=max(c.radar.buffer_frames,
                                                                           c.radar.baseline_frames))
        self._radar_meta: Optional[dict] = None
        self.reopen = dc.ReopenTracker(c.decision)
        self.flame_hold = dc.HoldTracker(c.decision.stale_s)
        self.crossing_ref: Optional[dict] = None      # near/far edge positions of the last recorded crossing
        self._th: Optional[ThermalLatest] = None
        self._geo: Optional[Geo] = None
        self._flux: Optional[fx.FluxSample] = None
        self._flux_rx: Optional[float] = None
        self._plate_row: Dict[str, Any] = {}
        self.flux_hist: Deque[fx.FluxSample] = collections.deque()
        self.plate_hist: Deque[Tuple[float, float, Optional[float]]] = collections.deque()  # (t_pi, plate_c, air_c)
        self.gnss_hist: Deque[Tuple[float, float, int]] = collections.deque()   # (t_pi, speed, fix)
        self.pos_hist: Deque[Tuple[float, float, float]] = collections.deque()  # (t_pi, east m, north m), fixes
        self.edge_track: Deque[Tuple[float, float]] = collections.deque()   # (t_rx, x towards the vehicle, m)
        self._track_frame: Optional[str] = None
        self.origin: Optional[Tuple[float, float]] = None
        self.course_deg: Optional[float] = None
        self._still_since: Optional[float] = None
        self._moving_fixes = 0
        self.flame_ref: Optional[dict] = None
        self.far_edge_ref: Optional[dict] = None
        self.verdict: Optional[dc.Verdict] = None
        self._last_valid_depth: Optional[dict] = None
        self._last_go_depth: Optional[dict] = None
        self.crossing: Dict[str, Any] = {"active": False, "t_start_pi": None, "below_since_pi": None,
                                         "prediction": None, "last": None, "n_auto": 0, "n_manual": 0}
        self.state: Dict[str, Any] = {}
        self.state_version = 0
        self.errors = 0
        self.last_error = ""
        self._sim_known = False
        self.store_real = cal.PairStore(c.paths.pairs_path)
        self.store_sim = cal.PairStore(c.paths.sim_pairs_path or (Path(c.paths.records_dir) / "calibration"
                                                                   / "pairs_sim.jsonl"))
        # FS-5: replays of recorded REAL sessions (and every --loop pass) never touch pairs.jsonl
        self.store_replay = cal.PairStore(getattr(c.paths, "replay_pairs_path", None)
                                          or (Path(c.paths.records_dir) / "calibration" / "pairs_replay.jsonl"))
        # FS-3: facing for the REOPENED view (GNSS course only from reliable forward travel; see _update_facing)
        self.facing_deg: Optional[float] = None
        self.facing_valid = False
        self.facing_ref: Optional[float] = None       # last accepted forward course (continuity reference)
        self.facing_reason = "no forward travel at a reliable GNSS course speed yet"
        self.calib = cal.FuelCalibration(fuel=self.fuel.code, status="not loaded")
        self._recalibrate()

    # ------------------------------------------------------------------------------------------- properties
    @property
    def sim(self) -> bool:
        return bool(self.link.sim)

    def store(self) -> cal.PairStore:
        """Where calibration pairs go and are read from: simulated data -> pairs_sim.jsonl; a replay of recorded
        real data -> pairs_replay.jsonl (FS-5: never the real store, never calibrates live decisions); live real
        data -> pairs.jsonl."""
        if self.sim:
            return self.store_sim
        if self.mode != "live":
            return self.store_replay
        return self.store_real

    def _apply_unit_mount(self, mount: Optional[dict], source: str) -> None:
        """Camera pitch / IMU-heading trust from the unit (hello or config); crossing.yaml values win when set."""
        c = self.cfg.mount
        mount = mount if isinstance(mount, dict) else {}
        old = getattr(self, "mount_info", {}) or {}
        pitch, psrc = old.get("camera_pitch_deg"), old.get("pitch_source")
        if c.camera_pitch_deg is not None:
            pitch, psrc = float(c.camera_pitch_deg), "crossing.yaml"
        elif _num(mount.get("camera_pitch_deg")):
            pitch, psrc = float(mount["camera_pitch_deg"]), source
        elif pitch is None:
            pitch, psrc = 0.0, "default 0 (no unit mount pitch)"
        trusted, tsrc = old.get("imu_heading_trusted"), old.get("imu_heading_source")
        if c.imu_heading_trusted is not None:
            trusted, tsrc = bool(c.imu_heading_trusted), "crossing.yaml"
        elif isinstance(mount.get("imu_heading_trusted"), bool):
            trusted, tsrc = mount["imu_heading_trusted"], source
        elif trusted is None:
            trusted, tsrc = False, "default false"
        self.mount_info = {"camera_pitch_deg": pitch, "pitch_source": psrc, "imu_heading_trusted": bool(trusted),
                           "imu_heading_source": tsrc}
        self.imu_heading_trusted = bool(trusted)
        self.pose = CameraPose(height_m=c.camera_height_m, mount_pitch_deg=pitch, mount_roll_deg=c.camera_roll_deg,
                               mount_yaw_deg=c.camera_yaw_deg)
        self._geo = None

    def _recalibrate(self) -> None:
        try:
            self.calib = cal.recalibrate(self.store().load(), self.fuel.code)
        except Exception as exc:  # noqa: BLE001 - unreadable store: uncalibrated (wider intervals)
            self.calib = cal.FuelCalibration(fuel=self.fuel.code, status="calibration store unreadable: %s" % exc)

    # ------------------------------------------------------------------------------------------- input
    def set_connected(self, flag: bool, now: float, reason: str = "") -> None:
        self.link.set_connected(flag, now, reason)
        if self.rlog is not None:
            self.rlog.wire_link(now, flag, reason)

    def on_text(self, text: Any, now: float) -> Optional[dict]:
        """Live path: one raw WebSocket frame received at laptop time ``now``."""
        msg = self.link.on_text(text, now)
        if msg is not None:
            self._process(msg, now)
        elif self.rlog is not None:
            self.rlog.event(now, "link", "parse_error", self.link.last_parse_error)
        return msg

    def feed(self, msg: dict, now: float) -> None:
        """Replay/test path: one already parsed (and validated) message received at laptop time ``now``."""
        try:
            protocol.validate(msg)
        except protocol.ProtocolError as exc:
            self.link.parse_errors += 1
            self.link.last_parse_error = str(exc)[:200]
            return
        self.link.on_message(msg, now)
        self._process(msg, now)

    def _process(self, msg: dict, now: float) -> None:
        extras: Dict[str, Any] = {}
        try:
            if self.sim and not self._sim_known:
                self._sim_known = True
                self._recalibrate()
            if msg["type"] == "hello":
                if isinstance(msg.get("mount"), dict):
                    self._apply_unit_mount(msg["mount"], "unit hello")
                if self.simlink is not None:
                    self.simlink.set_ids(msg.get("unit_id"), msg.get("session_id"))
            if msg["type"] == "reading":
                handler = getattr(self, "_on_" + msg["sensor"], None)
                if handler is not None:
                    extras = handler(msg, now) or {}
        except Exception as exc:  # noqa: BLE001 - a bad message must not stop the pipeline; it fails closed
            self.errors += 1
            self.last_error = "%s: %s" % (type(exc).__name__, exc)
            log.debug("message handler error", exc_info=True)
        if self.rlog is not None:
            self.rlog.message(msg, now, extras)

    # -- per-sensor handlers (return extras for the research log)
    def _on_thermal(self, msg: dict, now: float) -> dict:
        data = msg["data"]
        try:
            temps = protocol.decode_thermal(data)
        except protocol.ProtocolError as exc:
            self._th = ThermalLatest(now, None, False, "decode: %s" % exc, None, None, None)
            return {"valid": False, "reason": self._th.reason}
        ok, why = th.validate_frame(temps, self.camera)
        mask, unknown = None, ""
        if ok:
            # FS-1: flame pixels only from a frame that can show their ABSENCE (gain "low", threshold below the gain
            # ceiling, low-gain scale verified on the camera or simulated data); saturated pixels count as flame.
            tc = self.cfg.thermal
            mask, unknown = th.flame_evidence_mask(
                temps, data.get("gain"), tc.t_flame_c, tc.saturation_margin_c,
                scale_verified=bool(tc.low_gain_verified) or msg.get("sim") is True)
        hot = int(th.hot_mask(temps, self.cfg.thermal.t_hot_c).sum()) if ok else None
        n = int(mask.sum()) if mask is not None else None
        self._th = ThermalLatest(now, temps, ok, why, mask, n, hot, bool(data.get("shutter", False)),
                                 flame_unknown=unknown)
        return {"temps_k": temps, "valid": ok, "reason": why or unknown, "flame_pixels": n}

    def _on_radar(self, msg: dict, now: float) -> dict:
        data = msg["data"]
        try:
            frame = rf.frame_from_reading(data, now, sim=bool(msg.get("sim")))
            if not (_num(frame.range_res_m) and frame.range_res_m > 0):
                raise ValueError("range_res_m missing")
            if frame.iq is not None and frame.range_profile_db is not None \
                    and frame.iq.shape[0] != len(frame.range_profile_db):
                raise ValueError("heatmap and range profile disagree on bins")
        except (protocol.ProtocolError, ValueError, TypeError, KeyError) as exc:
            frame = rf.RadarFrame(t=now, range_res_m=float("nan"), frame_ok=False, sim=bool(msg.get("sim")))
            self._radar_meta = {"rx": now, "frame_ok": False, "reason": "decode: %s" % exc}
            self.detector.push(frame, now)
            return {}
        self.detector.push(frame, now)
        if frame.usable:
            self.radar_buf.append(frame)
        self._radar_meta = {"rx": now, "frame_ok": bool(frame.frame_ok), "reason": "" if frame.frame_ok
                            else "frame_ok false (inconsistent frame on the Pi)", "n_bins": frame.n_bins,
                            "range_res_m": frame.range_res_m, "frame": data.get("frame"),
                            "n_points": None if data.get("points") is None else len(data["points"])}
        return {"iq": frame.iq}

    def _on_tc_plate(self, msg: dict, now: float) -> dict:
        d = msg["data"]
        air = self._value("tc_air", now)
        air_c = None
        if air is not None and not air["data"].get("fault"):
            air_c = air["data"].get("temp_c")
        sample = self.flux_est.update(float(msg["t_mono"]), d.get("temp_c"), air_c, fault=d.get("fault"))
        if not d.get("fault") and _num(d.get("temp_c")):
            self.plate_hist.append((float(msg["t_mono"]), float(d["temp_c"]), air_c))
        else:
            self.plate_hist.append((float(msg["t_mono"]), float("nan"), air_c))
        while self.plate_hist and self.plate_hist[0][0] < float(msg["t_mono"]) - self.cfg.crossing.buffer_s:
            self.plate_hist.popleft()
        self._flux, self._flux_rx = sample, now
        if math.isfinite(sample.t):
            self.dose.add(sample.t, sample.q_kw_m2, sample.valid)
            self.flux_hist.append(sample)
            while self.flux_hist and self.flux_hist[0].t < sample.t - self.cfg.crossing.buffer_s:
                self.flux_hist.popleft()
        self._plate_row = {"plate_c": d.get("temp_c"), "air_c": air_c}
        if self.rlog is not None:
            self.rlog.flux({"rx_mono": now, "t_pi": sample.t, "plate_c": d.get("temp_c"), "air_c": air_c,
                            "q_kw_m2": sample.q_kw_m2, "q_abs_kw_m2": sample.q_abs_kw_m2, "dTdt_k_s": sample.dTdt,
                            "valid": sample.valid, "reason": sample.reason, "dose_tdu": self.dose.dose_tdu,
                            "dose_complete": self.dose.complete, "uncounted_s": self.dose.uncounted_s})
        self._crossing_update(sample, now)
        return {}

    def _on_gnss(self, msg: dict, now: float) -> dict:
        d = msg["data"]
        speed = d.get("speed_m_s")
        fix = d.get("fix") or 0
        t_pi = float(msg["t_mono"])
        if _num(speed):
            self.gnss_hist.append((t_pi, float(speed), int(fix)))
            while self.gnss_hist and self.gnss_hist[0][0] < t_pi - self.cfg.crossing.buffer_s:
                self.gnss_hist.popleft()
        if fix >= 1 and _num(d.get("lat")) and _num(d.get("lon")):
            e, n = self.en(d["lat"], d["lon"])
            self.pos_hist.append((t_pi, e, n))
            while self.pos_hist and self.pos_hist[0][0] < t_pi - self.cfg.crossing.buffer_s:
                self.pos_hist.popleft()
        thr = self.cfg.radar.moving_speed_m_s
        moving = not (_num(speed) and speed <= thr)
        if fix >= 1 and _num(speed) and speed > thr and _num(d.get("course_deg")):
            self.course_deg = float(d["course_deg"]) % 360.0
        if fix >= 1 and _num(speed):
            self._update_facing(float(speed), d.get("course_deg"), now)
        self._still_since = None if moving else (self._still_since if self._still_since is not None else now)
        self._moving_fixes = self._moving_fixes + 1 if moving else 0
        if self.detector.baseline is not None:
            why = ""
            if self._moving_fixes >= 2:
                why = "vehicle moving (GNSS speed)"
            elif self._baseline_pos is not None and fix >= 1 and _num(d.get("lat")) and _num(d.get("lon")):
                e, n = self.en(d["lat"], d["lon"])
                dist = math.hypot(e - self._baseline_pos[0], n - self._baseline_pos[1])
                if dist > self.cfg.radar.baseline_move_m:
                    why = "vehicle moved %.1f m from the capture point" % dist
            if why:
                self.clear_baseline(now, "invalidated: " + why)
        return {}

    # ------------------------------------------------------------------------------------------- helpers
    def en(self, lat: float, lon: float) -> Tuple[float, float]:
        """Local east/north metres about the first fix (equirectangular)."""
        if self.origin is None:
            self.origin = (float(lat), float(lon))
        lat0, lon0 = self.origin
        k = math.pi / 180.0 * EARTH_R
        return (float(lon) - lon0) * k * math.cos(math.radians(lat0)), (float(lat) - lat0) * k

    def _value(self, sensor: str, now: float) -> Optional[dict]:
        """Latest reading message of ``sensor`` if received within use_max_age_s (laptop clock), else None."""
        tr = self.link.tracks.get(sensor)
        if tr is None or tr.last_msg is None or tr.last_rx_mono is None:
            return None
        age = now - tr.last_rx_mono
        if age < -dc.AGE_ROUNDING_TOL_S or age > self.cfg.use_max_age_s.get(sensor, self.cfg.link.stale_s):
            return None
        return tr.last_msg

    def _rx(self, sensor: str) -> Optional[float]:
        return self.link.tracks[sensor].last_rx_mono

    # ------------------------------------------------------------------------------------------- baseline
    def capture_baseline(self, now: float, force: bool = False) -> dict:
        """Operator action: capture the radar baseline from the newest frames (no flame present, vehicle still)."""
        c = self.cfg.radar
        g = self._value("gnss", now)
        speed = g["data"].get("speed_m_s") if g else None
        if not (_num(speed) and speed <= c.moving_speed_m_s):
            return {"ok": False, "reason": "vehicle not known to be stationary (GNSS speed %s)" % speed}
        thl = self._th
        if not force and (thl is None or not thl.valid or now - thl.rx > self.cfg.use_max_age_s["thermal"]):
            return {"ok": False, "reason": "no valid thermal frame to confirm there is no flame (force to override)"}
        if not force and thl.flame_pixels is None:
            return {"ok": False, "reason": "flame pixels unknown (%s); force to override" % thl.flame_unknown}
        if not force and thl.flame_pixels:
            return {"ok": False, "reason": "%d flame-temperature pixels in view (force to override)"
                    % thl.flame_pixels}
        frames = [f for f in self.radar_buf if f.usable]
        if self._still_since is not None:
            frames = [f for f in frames if f.t >= self._still_since]
        frames = frames[-c.baseline_frames:]
        if not frames or now - frames[-1].t > self.cfg.use_max_age_s["radar"]:
            return {"ok": False, "reason": "no fresh radar frames"}
        if len(frames) < c.baseline_frames:
            return {"ok": False, "reason": "only %d stationary radar frames (need %d)" % (len(frames),
                                                                                         c.baseline_frames)}
        try:
            g_d = g["data"]
            meta = {"utc": utc_now(), "rx_mono": now, "lat": g_d.get("lat"), "lon": g_d.get("lon"),
                    "sim": self.sim, "forced": bool(force)}
            bl = rf.RadarBaseline.capture(frames, meta=meta)
        except ValueError as exc:
            return {"ok": False, "reason": str(exc)}
        self.detector.baseline = bl
        self._baseline_pos = None
        if g and g["data"].get("fix") and _num(g["data"].get("lat")) and _num(g["data"].get("lon")):
            self._baseline_pos = self.en(g["data"]["lat"], g["data"]["lon"])
        self.baseline_info = {"present": True, "reason": "captured", "n_frames": bl.n_frames, "rx_mono": now,
                              "utc": meta["utc"], "forced": bool(force), "n_bins": bl.n_bins,
                              "range_res_m": bl.range_res_m}
        if self.rlog is not None:
            self.rlog.baseline(now, bl.to_dict())
            self.rlog.change(now, "baseline", {"captured": True, "n_frames": bl.n_frames, "forced": bool(force)})
        return {"ok": True, "reason": "captured", "n_frames": bl.n_frames}

    def clear_baseline(self, now: float, reason: str = "cleared by operator") -> None:
        if self.detector.baseline is None:
            return
        self.detector.baseline = None
        self._baseline_pos = None
        self.baseline_info = {"present": False, "reason": reason, "rx_mono": now}
        if self.rlog is not None:
            self.rlog.change(now, "baseline", {"captured": False, "reason": reason})

    def _auto_baseline(self, now: float) -> None:
        c = self.cfg.radar
        if not c.auto_baseline or self.detector.baseline is not None or self._still_since is None:
            return
        if now - self._still_since < c.auto_baseline_still_s:
            return
        res = self.capture_baseline(now)
        if res.get("ok"):
            self.baseline_info["reason"] = "captured automatically (auto_baseline: stationary, no flame pixels)"

    # ------------------------------------------------------------------------------------------- vehicle/fuel
    def set_vehicle(self, vehicle: Any, now: Optional[float] = None) -> Vehicle:
        v = vehicle if isinstance(vehicle, Vehicle) else get_vehicle(str(vehicle))
        self.vehicle = v
        if self.rlog is not None:
            self.rlog.change(now if now is not None else time.monotonic(), "vehicle", v.to_dict())
        return v

    def set_fuel(self, fuel: Any, now: Optional[float] = None) -> fu.Fuel:
        f = fu.get_fuel(fuel)
        self.fuel = f
        self._recalibrate()
        self.edge_track.clear()
        if self.rlog is not None:
            self.rlog.change(now if now is not None else time.monotonic(), "fuel", f.to_dict())
        return f

    # ------------------------------------------------------------------------------------------- crossings
    def _crossing_update(self, s: fx.FluxSample, now: float) -> None:
        cc, cr = self.cfg.crossing, self.crossing
        if not math.isfinite(s.t):
            return
        g = self._value("gnss", now)
        speed = g["data"].get("speed_m_s") if g else None
        above = s.valid and s.q_kw_m2 > cc.thickness_q_kw_m2
        if not cr["active"]:
            if above and _num(speed) and speed >= cc.min_speed_m_s:
                pred = self._last_go_depth or self._last_valid_depth
                if pred is not None and now - pred["rx"] > cc.prediction_max_age_s:
                    pred = None
                cr.update(active=True, t_start_pi=s.t, below_since_pi=None, prediction=pred, start_rx=now)
            return
        if above:
            cr["below_since_pi"] = None
            return
        if cr["below_since_pi"] is None:
            cr["below_since_pi"] = s.t
        if s.t - cr["below_since_pi"] >= cc.end_hold_s:
            cr["active"] = False
            res = self._finish_crossing(now, cr["t_start_pi"], s.t, cr.get("prediction"), "auto",
                                        t_edge_pi=cr["below_since_pi"])
            cr["last"] = res

    def position_at(self, t_pi: float, max_gap_s: float = 1.5) -> Optional[Tuple[float, float]]:
        """Vehicle position (local east/north m) at Pi time ``t_pi``, linearly interpolated between GNSS fixes;
        None when no fix lies within ``max_gap_s`` on both sides."""
        h = self.pos_hist
        for (ta, ea, na), (tb, eb, nb) in zip(h, list(h)[1:]):
            if ta <= t_pi <= tb and tb - ta <= max_gap_s:
                w = 0.0 if tb == ta else (t_pi - ta) / (tb - ta)
                return ea + w * (eb - ea), na + w * (nb - na)
        return None

    def _finish_crossing(self, now: float, t0_pi: float, t1_pi: float, prediction: Optional[dict],
                         source: str, measured_m: Optional[float] = None,
                         t_edge_pi: Optional[float] = None) -> dict:
        """Close a crossing: measure the thickness (unless given), record the far edge for REOPENED and store the
        predicted-vs-measured pair. The far edge is the GNSS position when the plate flux fell below the
        thickness threshold (``t_edge_pi``; the radiant zone beyond the flame makes this conservative, i.e. later),
        not the position when the pulse was declared over ``end_hold_s`` later."""
        thick = None
        pulse = None                     # FS-5: the measured flux pulse identifies the physical crossing
        if measured_m is None or self.flux_hist:
            fl = self.batch_flux(t0_pi - 10.0, t1_pi + 1.0)
            gn = [(t, v) for (t, v, f) in self.gnss_hist if f >= 1 and t0_pi - 10.0 <= t <= t1_pi + 3.0]
            thick = cal.measure_thickness(fl, gn, self.cfg.crossing.thickness_q_kw_m2,
                                          frac_of_peak=self.cfg.crossing.thickness_frac_of_peak)
            pulse = thick if thick.valid else None
            if measured_m is not None:
                thick = None             # tape-measured: the pulse only identifies the crossing
        if measured_m is None:
            if not thick.valid:
                out = {"ok": False, "source": source, "reason": "thickness: " + thick.reason, "rx_mono": now}
                if self.rlog is not None:
                    self.rlog.event(now, "app", "crossing_no_pair", out["reason"])
                return out
            measured_m = thick.thickness_m
        g = self._value("gnss", now)
        edge = self.position_at(t_edge_pi) if t_edge_pi is not None else None
        if edge is None and g and g["data"].get("fix") and _num(g["data"].get("lat")) and _num(g["data"].get("lon")):
            edge = self.en(g["data"]["lat"], g["data"]["lon"])     # manual mark: where the vehicle is now
        if edge is not None and self.course_deg is not None:
            ux, uy = self._course_unit()
            self.far_edge_ref = {"pos": edge, "dir": (ux, uy), "beyond_m": self.vehicle.length_m,
                                 "rx": now, "kind": "far edge at crossing", "t_pi": t_edge_pi}
            near = self.position_at(t0_pi) if source == "auto" else None
            if near is None:
                near = (edge[0] - measured_m * ux, edge[1] - measured_m * uy)
            self.crossing_ref = {"near": near, "far": edge, "dir": (ux, uy), "rx": now,
                                 "kind": "crossing recorded by the plate-flux pulse (GNSS near/far edge)"}
        if prediction is None:
            out = {"ok": False, "source": source, "reason": "no depth prediction before the crossing",
                   "measured_m": measured_m, "rx_mono": now}
            if self.rlog is not None:
                self.rlog.event(now, "app", "crossing_no_pair", out["reason"])
            return out
        d: dp.DepthResult = prediction["depth"]
        sess = self.link.session_id
        if pulse is not None:
            key = cal.make_key(sess, self.fuel.code, "pulse", pulse.t_end)
        else:
            key = cal.make_key(sess, self.fuel.code, "prediction", prediction.get("rx"))
        pair = cal.make_pair(self.fuel.code, d, measured_m, loss_db=prediction.get("loss_db"), time=utc_now(),
                             lat=prediction.get("lat"), lon=prediction.get("lon"),
                             session=sess, sim=self.sim, key=key,
                             t_start_pi=pulse.t_start if pulse is not None else None,
                             t_end_pi=pulse.t_end if pulse is not None else None,
                             prediction_rx=prediction.get("rx"), source=source)
        store = self.store()
        try:
            stored = store.load()
        except Exception as exc:  # noqa: BLE001 - an unreadable store cannot show the pair is new: refuse
            stored, dup = [], "calibration store unreadable: %s" % exc
        else:
            dup = cal.is_duplicate(pair, stored)
        if dup:
            out = {"ok": False, "source": source, "reason": "not stored: " + dup, "measured_m": measured_m,
                   "rx_mono": now, "duplicate": True, "store": str(store.path)}
            if self.rlog is not None:
                self.rlog.event(now, "app", "crossing_no_pair", out["reason"])
            return out
        store.append(pair)
        self._recalibrate()
        self.crossing["n_auto" if source == "auto" else "n_manual"] += 1
        out = {"ok": True, "source": source, "measured_m": measured_m, "predicted_m": d.depth_m, "lo_m": d.lo_m,
               "hi_m": d.hi_m, "store": str(store.path), "sim": self.sim, "rx_mono": now,
               "prediction_age_s": now - prediction["rx"]}
        if self.rlog is not None:
            row = {"rx_mono": now, "utc": pair.time, "source": source, "fuel": pair.fuel,
                   "predicted_m": pair.predicted_m, "lo_m": pair.lo_m, "hi_m": pair.hi_m,
                   "sigma_log": pair.sigma_log, "measured_m": pair.measured_m, "loss_db": pair.loss_db,
                   "lat": pair.lat, "lon": pair.lon, "session": pair.session, "sim": pair.sim,
                   "thickness_duration_s": thick.duration_s if thick else None,
                   "thickness_mean_speed_m_s": thick.mean_speed_m_s if thick else None,
                   "prediction_age_s": out["prediction_age_s"], "store": str(store.path)}
            row.update({"est_%s_m" % k: v for k, v in pair.estimates.items()})
            row.update({k: getattr(pair, k) for k in ("key", "t_start_pi", "t_end_pi", "est_flicker_extent_lo_m",
                                                      "est_flicker_extent_hi_m", "est_flicker_extent_valid",
                                                      "est_flicker_extent_reason", "flicker_extent_agrees")})
            self.rlog.pair(row)
        return out

    def batch_flux(self, t_a: float, t_b: float) -> List[Tuple[float, float, bool]]:
        """Plate flux over [t_a, t_b] (Pi clock) recomputed from the buffered plate samples with a CENTRED
        derivative window (``crossing.flux_window_s``, default 1.0 s, flux.derivative) for the measured thickness.

        Same energy balance as flux.FluxEstimator: q = (rho*cp*d*dT/dt + loss(T)) / absorptivity / 1000 [kW/m2],
        loss from the plate's LossModel. Rows (t_pi, q_kw_m2, valid); a sample is invalid when its temperature is
        missing/faulted, the air temperature is missing, or the derivative window is incomplete (gaps, ends)."""
        rows = [r for r in self.plate_hist if t_a <= r[0] <= t_b]
        if len(rows) < 4:
            return []
        t = np.array([r[0] for r in rows])
        y = np.array([r[1] for r in rows]) + th.C_TO_K
        dTdt = fx.derivative(t, y, window_s=self.cfg.crossing.flux_window_s)
        out = []
        for (ti, tc, ta), yi, g in zip(rows, y, dTdt):
            ok = math.isfinite(g) and math.isfinite(yi) and ta is not None and math.isfinite(ta)
            q = float("nan")
            if ok:
                loss = float(self.flux_est.loss.loss_w_m2(yi, ta + th.C_TO_K))
                q = (self.plate.heat_capacity_j_m2_k * g + loss) / self.plate.absorptivity / 1000.0
                ok = math.isfinite(q)
            out.append((ti, q, ok))
        return out

    def mark_crossing(self, now: float, measured_m: Optional[float] = None, lookback_s: float = 60.0) -> dict:
        """Operator action. With ``measured_m`` (tape-measured thickness, m) the pair uses it; otherwise the
        thickness is measured from the flux pulse in the last ``lookback_s`` of plate data. FS-5: a second press for
        the same flux pulse or the same depth prediction is refused (``cal.is_duplicate``); in a replay the pair
        goes to pairs_replay.jsonl, never to the real store."""
        if measured_m is not None and not (_num(measured_m) and 0 < measured_m < 1000):
            return {"ok": False, "reason": "measured_m must be a positive number of metres"}
        pred = self._last_go_depth or self._last_valid_depth
        if pred is not None and now - pred["rx"] > max(self.cfg.crossing.prediction_max_age_s, lookback_s):
            pred = None
        t1 = self.flux_hist[-1].t if self.flux_hist else 0.0
        res = self._finish_crossing(now, t1 - lookback_s + 10.0, t1, pred, "manual", measured_m)
        self.crossing["last"] = res
        return res

    # ------------------------------------------------------------------------------------------- tick
    def path_bearing_cam(self) -> float:
        """Bearing of the vehicle's path (straight ahead) in the camera frame, deg + right."""
        return -float(self.cfg.mount.camera_yaw_deg)

    def _imu_calib_fault(self, imu_d: Optional[dict]) -> Optional[str]:
        """FS-9: BNO055 accel/gyro calibration status below ``geometry.imu_min_calib`` (placeholder, 0-3 scale) or
        missing = IMU fault: roll/pitch feed the near edge and the flame height. sys/mag are not required (pitch and
        roll do not depend on the magnetometer; sys is 0 for seconds after start)."""
        if imu_d is None:
            return None                                   # missing data closes through freshness / values
        cal = imu_d.get("calib")
        if not isinstance(cal, dict):
            return "calibration status missing"
        need = self.cfg.geometry.imu_min_calib
        bad = [k for k in ("accel", "gyro") if not (_num(cal.get(k)) and cal.get(k) >= need)]
        if bad:
            return "calibration %s below %d" % ("/".join("%s=%s" % (k, cal.get(k)) for k in bad), need)
        return None

    def _course_unit(self) -> Tuple[float, float]:
        a = math.radians(self.course_deg or 0.0)
        return math.sin(a), math.cos(a)

    def _trusted_imu_heading(self, imu_d: Optional[dict]) -> Optional[float]:
        if self.imu_heading_trusted and imu_d and _num(imu_d.get("heading_deg")):
            return (float(imu_d["heading_deg"]) + self.cfg.mount.imu_heading_offset_deg) % 360.0
        return None

    def _update_facing(self, speed: float, course: Any, now: float) -> None:
        """FS-3: GNSS course is the direction of TRAVEL, not where the camera faces (180 deg off while reversing,
        noisy at low speed). The facing for the REOPENED view is taken from it only on a fix with speed >=
        ``geometry.reliable_course_speed_m_s`` whose course is within ``course_imu_max_diff_deg`` of a trusted IMU
        heading (when there is one) and within ``course_jump_deg`` of the last accepted forward course. A fix between
        moving_speed_m_s and the reliable speed keeps the held facing only while its course stays within
        ``low_speed_course_tol_deg`` of it (braking or creeping straight on; it never updates the facing); any other
        such fix (manoeuvring, reversing) or a course jump clears it. The continuity reference stays, so reversing at
        any speed never sets it again (only a trusted IMU heading or reliable travel in the old direction does). The
        first reliable travel of a session is assumed forward (stated)."""
        gc = self.cfg.geometry
        if speed <= self.cfg.radar.moving_speed_m_s:
            return                                                # stopped: the facing is held
        if speed < gc.reliable_course_speed_m_s or not _num(course):
            if self.facing_valid and self.facing_deg is not None and _num(course) \
                    and abs(_wrap180(float(course) - self.facing_deg)) <= gc.low_speed_course_tol_deg:
                return                                            # braking / creeping straight on: held
            self.facing_valid = False
            self.facing_reason = ("manoeuvring at %.1f m/s (< %.1f m/s): GNSS course not a reliable facing"
                                  % (speed, gc.reliable_course_speed_m_s))
            return
        crs = float(course) % 360.0
        im = self._value("imu", now)
        imu = self._trusted_imu_heading(im["data"] if im else None)
        if imu is not None:
            diff = abs(_wrap180(crs - imu))
            if diff > gc.course_imu_max_diff_deg:
                self.facing_valid = False
                self.facing_reason = "GNSS course %.0f deg from the trusted IMU heading (reversing?)" % diff
                return
        elif self.facing_ref is not None:
            jump = abs(_wrap180(crs - self.facing_ref))
            if jump > gc.course_jump_deg:
                self.facing_valid = False
                self.facing_reason = ("GNSS course %.0f deg from the last forward course (reversing?): facing unknown"
                                      % jump)
                return
        self.facing_deg, self.facing_ref, self.facing_valid = crs, crs, True
        self.facing_reason = "gnss course at %.1f m/s" % speed

    def heading(self, speed: Any, imu_d: Optional[dict]) -> Tuple[Optional[float], str]:
        """Vehicle facing (deg from north, clockwise) for the REOPENED view (FS-3): a trusted IMU heading
        (+ imu_heading_offset_deg) first, stopped or moving; else the GNSS course of the last reliable forward travel
        (``_update_facing``), held while stopped; else None ("facing uncertain": the view check then fails)."""
        imu = self._trusted_imu_heading(imu_d)
        if imu is not None:
            return imu, "imu (trusted)"
        if self.facing_valid and self.facing_deg is not None:
            moving = _num(speed) and speed > self.cfg.radar.moving_speed_m_s
            return self.facing_deg, ("gnss course (forward travel)" if moving else
                                     "gnss course held (stopped, last forward travel)")
        return None, "facing uncertain: " + self.facing_reason

    def _crossing_patch(self) -> Optional[dict]:
        if self.crossing_ref is not None:
            return self.crossing_ref
        fr = self.flame_ref
        if fr is not None and _num(fr.get("depth_hi_m")):
            ux, uy = fr["dir"]
            d = float(fr["depth_hi_m"])
            return {"near": fr["pos"], "far": (fr["pos"][0] + d * ux, fr["pos"][1] + d * uy), "dir": fr["dir"],
                    "kind": "recorded flame location + depth_hi", "rx": fr.get("rx")}
        return None

    def crossing_view(self, pos, heading: Optional[float], imu_d: Optional[dict], gnss_d: Optional[dict] = None,
                      temps_k: Optional[np.ndarray] = None) -> dict:
        """Is the recorded crossing inside the camera's current view? (D3, FS-8; see module docstring). Returns a
        dict with in_view, reason, the image column range covering the crossing and the numbers behind the answer.

        Geometry (bearing inside the FOV, distance), then LINE OF SIGHT over the DEM to each of the six patch points
        (near/far end x left/centre/right; terrain only: buildings, walls, vegetation and vehicles are not in a
        bare-earth DEM; without a DEM line of sight cannot be shown and the answer is False), then the projected image
        position of each point (DEM heights, camera height, mount and IMU pitch/roll) must lie inside the image
        margins, and the thermal pixel there must be valid, unsaturated and read a plausible ground temperature
        (``reopen_ground_min_c`` .. ``reopen_ground_max_c``; colder = sky). The image check cannot tell a wall or a
        crest face from the road: only the DEM covers terrain. All limits are placeholders."""
        gc, cam = self.cfg.geometry, self.camera
        out: Dict[str, Any] = {"in_view": False, "reason": "", "cols": None, "max_view_m": gc.reopen_max_view_m}
        ref = self._crossing_patch()
        if ref is None:
            out["reason"] = "no recorded crossing or flame location"
            return out
        out["ref_kind"] = ref.get("kind")
        if pos is None:
            out["reason"] = "no GNSS position"
            return out
        if heading is None or not _num(heading):
            out["reason"] = "heading unknown"
            return out
        ux, uy = ref["dir"]
        px, py = -uy, ux                                  # left of the travel direction at the crossing
        hw = gc.reopen_half_width_m
        rel, dist, world = [], [], []
        for e, n in (ref["near"], ref["far"]):
            for lat in (-hw, 0.0, hw):
                de, dn = e + lat * px - pos[0], n + lat * py - pos[1]
                dist.append(math.hypot(de, dn))
                world.append(math.degrees(math.atan2(de, dn)) % 360.0)
                rel.append(_wrap180(world[-1] - heading - self.pose.mount_yaw_deg))
        d_near = math.hypot(ref["near"][0] - pos[0], ref["near"][1] - pos[1])
        d_far = math.hypot(ref["far"][0] - pos[0], ref["far"][1] - pos[1])
        half = cam.hfov_deg / 2.0 - gc.reopen_fov_margin_deg
        out.update(bearing_min_deg=min(rel), bearing_max_deg=max(rel), d_near_m=d_near, d_far_m=d_far,
                   d_max_m=max(dist), d_min_m=min(dist), half_fov_used_deg=half)
        if max(abs(r) for r in rel) > half:
            worst = max(rel, key=abs)
            where = "behind the camera" if abs(worst) > 90.0 else ("to the right" if worst > 0 else "to the left")
            out["reason"] = ("crossing %s (camera bearing up to %.0f deg), outside the view (+-%.0f deg)"
                             % (where, worst, half))
            return out
        if max(dist) > gc.reopen_max_view_m:
            out["reason"] = "crossing %.0f m away (> %.0f m)" % (max(dist), gc.reopen_max_view_m)
            return out
        pitch = imu_d.get("pitch_deg") if imu_d else None
        roll = imu_d.get("roll_deg") if imu_d else None
        if not (_num(pitch) and _num(roll)):
            out["reason"] = "no IMU pitch/roll for the view angle"
            return out
        # ---- FS-8: line of sight over the DEM (terrain only)
        if self.dem is None:
            out["reason"] = ("line of sight to the crossing not verifiable (no DEM; a crest, cutting or bend "
                             "could hide it)")
            return out
        if not (gnss_d and _num(gnss_d.get("lat")) and _num(gnss_d.get("lon"))):
            out["reason"] = "no GNSS lat/lon for the DEM line of sight"
            return out
        dzs = []
        for k, (dd, wb) in enumerate(zip(dist, world)):
            try:
                prof = road_profile(self.dem, float(gnss_d["lat"]), float(gnss_d["lon"]), wb,
                                    dd + gc.reopen_los_ds_m, gc.reopen_los_ds_m)
                ok, why, dz = line_of_sight(prof, self.pose.height_m, dd)
            except Exception as exc:  # noqa: BLE001 - any DEM problem: not shown in view (fail closed)
                ok, why, dz = False, "DEM error %s" % type(exc).__name__, float("nan")
            if not ok:
                out["reason"] = ("crossing hidden or not checkable from the camera (point %d at %.0f m: %s; DEM line "
                                 "of sight covers terrain only)" % (k, dd, why))
                out["los"] = "blocked"
                return out
            dzs.append(dz)
        out["los"] = "clear over the DEM (terrain only: buildings, walls and vegetation are not in it)"
        # ---- projected image positions of the patch points (DEM heights) and the image check
        R = level_from_camera(CameraPose(self.pose.height_m, self.pose.mount_pitch_deg, self.pose.mount_roll_deg,
                                         self.pose.mount_yaw_deg), Attitude(float(roll), float(pitch)))
        lim = math.tan(math.radians(cam.vfov_deg / 2.0 - gc.reopen_fov_margin_deg)) * cam.fy
        rows, cols = [], []
        for dd, wb, dz in zip(dist, world, dzs):
            a = math.radians(wb - heading)
            v = R.T @ np.array([dd * math.cos(a), -dd * math.sin(a), dz - self.pose.height_m])
            if not v[0] > 1e-6:
                out["reason"] = "crossing point behind the camera plane"
                return out
            rows.append(cam.ppy - cam.fy * v[2] / v[0])
            cols.append(cam.ppx - cam.fx * v[1] / v[0])
        out["rows"] = [round(r, 1) for r in rows]
        if max(rows) > cam.ppy + lim:
            out["reason"] = ("crossing too close: its near end (%.1f m) is below the image (row %.0f > %.0f)"
                             % (min(dist), max(rows), cam.ppy + lim))
            return out
        if min(rows) < cam.ppy - lim:
            out["reason"] = "crossing above the image (row %.0f)" % min(rows)
            return out
        if temps_k is None or np.shape(temps_k) != (cam.h, cam.w):
            out["reason"] = "no valid thermal frame for the view check"
            return out
        lo_k, hi_k = gc.reopen_ground_min_c + th.C_TO_K, gc.reopen_ground_max_c + th.C_TO_K
        for r, cc in zip(rows, cols):
            ri, ci = int(round(min(max(r, 0), cam.h - 1))), int(round(min(max(cc, 0), cam.w - 1)))
            t = float(temps_k[ri, ci])
            if not (math.isfinite(t) and lo_k <= t <= hi_k):
                out["reason"] = ("the image at the crossing (row %d, col %d) reads %.0f C, not a plausible ground "
                                 "temperature (%.0f..%.0f C): not shown to be the road" %
                                 (ri, ci, t - th.C_TO_K, gc.reopen_ground_min_c, gc.reopen_ground_max_c))
                return out
        m = gc.reopen_fov_margin_deg
        c_lo = int(math.floor(cam.bearing_to_col(max(-89.0, min(rel) - m))))
        c_hi = int(math.ceil(cam.bearing_to_col(min(89.0, max(rel) + m))))
        out.update(in_view=True, reason="ok", cols=[max(0, c_lo), min(cam.w - 1, c_hi)])
        return out

    def _profile(self, now: float, imu_d: Optional[dict], gnss_d: Optional[dict]) -> Profile:
        gc = self.cfg.geometry
        look, _ = self.heading(None, imu_d)        # FS-3: along where the camera faces, not the last travel course
        if self.dem is not None and gnss_d and gnss_d.get("fix") and look is not None \
                and _num(gnss_d.get("lat")) and _num(gnss_d.get("lon")):
            try:
                p = road_profile(self.dem, gnss_d["lat"], gnss_d["lon"], look, gc.s_max_m, gc.ds_m)
                if p.valid:
                    return p
            except Exception:  # noqa: BLE001 - DEM problems fall back to the IMU plane
                pass
        pitch = imu_d.get("pitch_deg") if imu_d else None
        return imu_plane_profile(pitch if _num(pitch) else float("nan"), self.cfg.mount.imu_mount_pitch_deg,
                                 gc.s_max_m, gc.ds_m)

    def _geometry(self, now: float, thl: ThermalLatest, imu_d: Optional[dict], gnss_d: Optional[dict]) -> Geo:
        profile = self._profile(now, imu_d, gnss_d)
        if thl.mask is None:
            return Geo(thl.rx, profile, None, None, thl.flame_unknown or "no valid thermal frame")
        if not profile.valid:
            return Geo(thl.rx, profile, None, None, "no valid road profile: " + profile.reason)
        if not imu_d or not (_num(imu_d.get("roll_deg")) and _num(imu_d.get("pitch_deg"))):
            return Geo(thl.rx, profile, None, None, "no IMU attitude")
        att = Attitude(float(imu_d["roll_deg"]), float(imu_d["pitch_deg"]))
        mask = thl.mask
        step = self.cfg.geometry.column_step
        if step > 1:
            m2 = np.zeros_like(mask)
            m2[:, ::step] = mask[:, ::step]
            mask = m2
        ps = self.cfg.geometry.pitch_sigma_deg
        ne = near_edge(mask, self.camera, self.pose, att, profile, self.path_bearing_cam(),
                       tol_deg=self.cfg.geometry.path_half_width_deg, pitch_sigma_deg=ps)
        if ne is None:
            return Geo(thl.rx, profile, None, None, "no flame base on the vehicle's path (+-%.0f deg) on the road "
                       "profile" % self.cfg.geometry.path_half_width_deg)
        fh = flame_height(thl.mask, ne, self.camera, self.pose, att, profile, pitch_sigma_deg=ps)
        if ne.base_cut_off:
            return Geo(thl.rx, profile, ne, fh, "flame base not observed: " + ne.cut_off_reason)
        if ne.occluded:
            return Geo(thl.rx, profile, ne, fh, "flame base not observed: occluded by terrain (hidden behind a crest; "
                       "distance only a near bound)")
        if fh is None and flame_top_cut_off(thl.mask, ne):
            return Geo(thl.rx, profile, ne, None, "flame top above the image: flame height unknown")
        return Geo(thl.rx, profile, ne, fh, "ok")

    def tick(self, now: float) -> dict:
        """Re-decide from fresh data only and publish the State (call at tick_hz, default 5 Hz)."""
        try:
            st = self._tick(now)
        except Exception as exc:  # noqa: BLE001 - never a go state from a crash
            self.errors += 1
            self.last_error = "%s: %s" % (type(exc).__name__, exc)
            log.error("tick failed: %s", traceback.format_exc())
            self.verdict = dc.Verdict(dc.CLOSED, ["INTERNAL_ERROR:%s" % type(exc).__name__], now,
                                      now + self.cfg.decision.verdict_ttl_s)
            st = self._minimal_state(now)
        self.state = st
        self.state_version += 1
        if self.rlog is not None:
            try:
                self.rlog.tick(st)
            except Exception:  # noqa: BLE001 - logging must not stop decisions
                log.exception("research log tick failed")
        return st

    def _tick(self, now: float) -> dict:
        c = self.cfg
        health = self.link.health(now)
        hmap = health.as_dict()
        self._auto_baseline(now)
        msgs = {s: self._value(s, now) for s in protocol.SENSORS}
        data = {s: (m["data"] if m else None) for s, m in msgs.items()}
        imu_d, gnss_d = data["imu"], data["gnss"]

        # ---- thermal + geometry
        thl = self._th if (self._th is not None and msgs["thermal"] is not None
                           and abs(self._th.rx - self._rx("thermal")) < 1e-9) else None
        thermal_fault = None
        if thl is not None and not thl.valid:
            thermal_fault = "invalid frame: %s" % thl.reason
        elif thl is not None and thl.mask is None:
            thermal_fault = "flame pixels unknown: %s" % (thl.flame_unknown or "no flame mask")     # FS-1
        geo = None
        if thl is not None and thl.valid:
            if self._geo is None or self._geo.rx != thl.rx:
                self._geo = self._geometry(now, thl, imu_d, gnss_d)
            geo = self._geo
        ne = geo.ne if geo is not None else None
        fh = geo.fh if geo is not None else None
        profile = geo.profile if geo is not None else self._profile(now, imu_d, gnss_d)
        # The crossing is evaluated along the vehicle's path: thermal flag and radar beam at the path bearing.
        cam_bearing = self.path_bearing_cam()
        thermal_flag = None
        n_bear = None
        if thl is not None and thl.valid and thl.mask is not None:
            thermal_flag, n_bear = th.flame_at_bearing(thl.mask, cam_bearing, c.thermal.bearing_tol_deg, self.camera,
                                                       c.thermal.min_pixels)

        # ---- radar
        speed = gnss_d.get("speed_m_s") if gnss_d else None
        moving = not (_num(speed) and speed <= c.radar.moving_speed_m_s)
        radar_bearing = cam_bearing + c.mount.camera_yaw_deg - c.mount.radar_yaw_deg
        dz_ne = 0.0
        near_slant = None
        if ne is not None and math.isfinite(ne.d_m):
            dz_ne = ne.ground_dz_m if math.isfinite(ne.ground_dz_m) else 0.0
            near_slant = math.hypot(ne.d_m, c.mount.radar_height_m - dz_ne)
        rs = self.detector.evaluate(now, near_edge_m=near_slant, bearing_deg=radar_bearing, moving=moving)
        far_h = None                     # horizontal distance of the first solid echo BEYOND the flame base
        if ne is not None and rs.far_echo_m is not None and math.isfinite(rs.far_echo_m):
            hd = c.mount.radar_height_m - dz_ne
            if rs.far_echo_m > abs(hd):
                far_h = math.sqrt(rs.far_echo_m ** 2 - hd ** 2)
        flame = rf.fuse_flame(rs, thermal_flag)
        flame_held = self.flame_hold.update(now, flame.status == "FLAME")
        radar_fault = None
        if self._radar_meta is not None and msgs["radar"] is not None and not self._radar_meta.get("frame_ok", True):
            radar_fault = self._radar_meta.get("reason") or "frame not ok"

        # ---- near-edge track for estimator a: position along the road axis, pointing TOWARDS the vehicle, with the
        # vehicle's own motion removed. Stationary: vehicle frame, x = -d (no GNSS noise enters). Moving with a
        # known course: world frame, x = -(position + d * course unit) . course unit. The track restarts when the
        # frame changes or after a 3 s gap (lateral offsets are ignored: 1-D along the road).
        pos = None
        if gnss_d and gnss_d.get("fix") and _num(gnss_d.get("lat")) and _num(gnss_d.get("lon")):
            pos = self.en(gnss_d["lat"], gnss_d["lon"])
        stationary = _num(speed) and speed <= c.radar.moving_speed_m_s
        frame = "vehicle" if stationary else ("world" if (pos is not None and self.course_deg is not None) else None)
        if self.edge_track and (now - self.edge_track[-1][0] > 3.0 or frame != self._track_frame):
            self.edge_track.clear()
        self._track_frame = frame
        if frame is not None and ne is not None and not ne.occluded and math.isfinite(ne.d_m) and geo is not None \
                and (not self.edge_track or geo.rx > self.edge_track[-1][0]):
            if frame == "vehicle":
                x = -ne.d_m
            else:
                ux, uy = self._course_unit()
                x = -(pos[0] * ux + pos[1] * uy + ne.d_m)
            self.edge_track.append((geo.rx, x))
        while self.edge_track and self.edge_track[0][0] < now - c.depth.spread_track_s:
            self.edge_track.popleft()

        # ---- depth
        ests = []
        if len(self.edge_track) >= 2:
            a = dp.spread_burn(np.array(self.edge_track), self.fuel)
            a.details["frame"] = self._track_frame
        else:
            a = dp._invalid("spread_burn", "no near-edge track (needs a flame base on the path and GNSS speed: "
                            "stationary, or moving with a known course)")
        ests.append(a)
        ests.append(dp.byram(fh[0] if fh else None, self.fuel))
        if self.detector.baseline is not None:
            rr = float(self.detector.baseline.range_res_m)
        elif self._radar_meta and _num(self._radar_meta.get("range_res_m")):
            rr = float(self._radar_meta["range_res_m"])
        else:
            rr = 0.1
        ests.append(dp.radar_ceiling(ne.d_m if ne is not None else None, far_h, rr))
        z = None
        if rs.per_bin:
            zp = np.asarray(rs.per_bin.get("flicker_phase_z", []), dtype=float)
            za = np.asarray(rs.per_bin.get("flicker_amp_z", []), dtype=float)
            if zp.size and zp.size == za.size:
                z = np.fmax(zp, za)
        ests.append(dp.flicker_extent(z if z is not None else [], near_slant, rr, c.depth.flicker_k))
        ests.append(dp.radar_loss_depth(_f(rs.loss_db), self.calib.db_per_m))
        depth = dp.combine(ests, self.calib, enabled=c.depth.enabled, disagree_factor=c.depth.disagree_factor,
                           narrow_decision_hi=c.depth.narrow_decision_hi,
                           narrow_min_pairs=c.depth.narrow_decision_hi_min_pairs)
        inten = dp.intensity(fh, a, self.fuel)
        loss_db = _f(rs.loss_db)
        if depth.valid:
            self._last_valid_depth = {"rx": now, "depth": depth, "loss_db": loss_db,
                                      "lat": gnss_d.get("lat") if gnss_d else None,
                                      "lon": gnss_d.get("lon") if gnss_d else None}

        # ---- flux
        fs = self._flux if (self._flux is not None and msgs["tc_plate"] is not None
                            and self._flux_rx is not None and abs(self._flux_rx - self._rx("tc_plate")) < 1e-9) \
            else None
        plate_q = fs.q_kw_m2 if (fs is not None and fs.valid) else None

        # ---- passed / reopen
        passed = False
        if pos is not None:
            for ref in (self.far_edge_ref, self.flame_ref):
                if ref and dc.has_passed(pos, ref["pos"], ref["dir"], ref["beyond_m"]):
                    passed = True
        flame_px = thl.flame_pixels if thl is not None and thl.valid else None
        reopen_ok = all(hmap.get(s, {}).get("fresh") is True for s in dc.ALL_SENSORS)
        hdg, hdg_src = self.heading(speed, imu_d)
        view = self.crossing_view(pos, hdg, imu_d, gnss_d,
                                  thl.temps_k if (thl is not None and thl.valid) else None)
        view.update(heading_deg=hdg, heading_source=hdg_src)
        cross_hot = None
        if view["in_view"] and thl is not None and thl.valid and thl.mask is not None:
            a, b = view["cols"]
            cross_hot = int(thl.mask[:, a:b + 1].sum())
        view["hot_pixels"] = cross_hot
        if not view["in_view"]:
            view["hint"] = REOPEN_VIEW_HINT % self.cfg.geometry.reopen_max_view_m
        quiet = self.reopen.update(now, plate_q, flame_px, reopen_ok, in_view=view["in_view"],
                                   crossing_hot_pixels=cross_hot,
                                   speed_m_s=speed if _num(speed) else None)

        # ---- decision
        faults: Dict[str, Optional[str]] = {s: None for s in protocol.SENSORS}
        for s in protocol.TC_SENSORS:
            if data[s] is not None and data[s].get("fault"):
                faults[s] = str(data[s]["fault"])
        faults["thermal"] = thermal_fault
        faults["radar"] = radar_fault
        if data["pi"] is not None and data["pi"].get("under_voltage_now") is True:
            faults["pi"] = "under-voltage"
        faults["imu"] = self._imu_calib_fault(imu_d)
        input_times = {s: self._rx(s) for s in protocol.SENSORS if msgs[s] is not None}
        if thl is None and "thermal" in input_times:
            input_times.pop("thermal")

        def tc(s):
            return data[s].get("temp_c") if data[s] is not None and not data[s].get("fault") else None

        inp = dc.DecisionInputs(
            link_up=health.link_up, health=hmap, faults=faults, input_times=input_times,
            flame_status=flame.status, radar_status=rs.status,
            near_edge_m=_f(ne.d_m) if ne is not None else None, far_echo_m=far_h, depth=depth, intensity=inten,
            tc_air_c=tc("tc_air"), tc_plate_c=tc("tc_plate"), tc_housing_c=tc("tc_housing"),
            plate_flux_kw_m2=plate_q, flame_pixels=flame_px,
            imu_roll_deg=imu_d.get("roll_deg") if imu_d else None,
            imu_pitch_deg=imu_d.get("pitch_deg") if imu_d else None,
            gnss_fix=gnss_d.get("fix") if gnss_d else None, lat=gnss_d.get("lat") if gnss_d else None,
            lon=gnss_d.get("lon") if gnss_d else None, utc=gnss_d.get("utc") if gnss_d else None,
            speed_m_s=speed if _num(speed) else None, passed=passed, reopen_quiet_s=quiet, sim=self.sim,
            flame_held_s=flame_held,
            # FS-2 / PHYS-2 / PHYS-3: a base cut off by the image OR hidden behind terrain is not observed
            near_edge_observed=(None if ne is None else not (ne.base_cut_off or ne.occluded)),
            crossing_in_view=bool(view["in_view"]), crossing_view_reason=view.get("reason", ""),
            crossing_hot_pixels=cross_hot)
        verdict = dc.decide(inp, self.vehicle, c.decision, now)
        self.verdict = verdict
        if verdict.state in (dc.CROSS_FAST, dc.SPRAY) and depth.valid:
            self._last_go_depth = {"rx": now, "depth": depth, "loss_db": loss_db, "lat": inp.lat, "lon": inp.lon}
        if flame.status == "FLAME" and depth.valid and ne is not None and pos is not None \
                and hdg is not None and math.isfinite(ne.d_m) and not ne.occluded:
            # FS-3: placed along where the camera faces (the flame is straight ahead), not the last travel course
            ux, uy = math.sin(math.radians(hdg)), math.cos(math.radians(hdg))
            d_hi = dc.depth_hi_for_decision(depth)          # DEPTH-HI rule: the decision upper end, not hi_m
            self.flame_ref = {"pos": (pos[0] + ne.d_m * ux, pos[1] + ne.d_m * uy), "dir": (ux, uy),
                              "beyond_m": d_hi + self.vehicle.length_m, "rx": now,
                              "kind": "recorded flame location", "depth_hi_m": d_hi}
        if self.simlink is not None:          # step 9: flame-backed CLOSED / confirmed REOPENED per location only
            from .simlink import tick_evidence
            self.simlink.offer_tick(tick_evidence(self, verdict, now, inp, flame.status, rs.status, flame_held))

        st = self._state(now, health, verdict, thl, geo, profile, rs, flame, thermal_flag, n_bear, cam_bearing,
                         radar_bearing, near_slant, far_h, moving, depth, inten, fs, plate_q, data, passed, quiet)
        st["flame"]["held_s"] = flame_held
        st["flame"]["min_evidence_s"] = c.decision.min_flame_evidence_s
        st["reopen"]["view"] = protocol.sanitize(view)
        st["reopen"]["crossing_ref"] = protocol.sanitize(self.crossing_ref)
        st["reopen"]["max_speed_m_s"] = c.decision.reopen_max_speed_m_s
        return st

    # ------------------------------------------------------------------------------------------- state
    def _verdict_dict(self, now: float) -> dict:
        v = self.verdict
        eff = dc.effective(v, now)
        d = protocol.sanitize(eff.to_dict())
        d.update(decided_state=v.state if v is not None else None, age_s=(now - v.issued_mono) if v else None,
                 min_speed_km_h=(eff.min_speed_m_s * 3.6) if eff.min_speed_m_s is not None else None,
                 placeholder=True, placeholder_note=PLACEHOLDER_NOTE, advisory=ADVISORY)
        return d

    def snapshot(self, now: float) -> dict:
        """The latest State with the verdict re-evaluated for expiry at ``now`` (for pushes between ticks)."""
        if not self.state:
            return self._minimal_state(now)
        st = dict(self.state)
        st["verdict"] = self._verdict_dict(now)
        st["state_age_s"] = now - st.get("t_mono", now)
        return st

    def _common(self, now: float) -> dict:
        info = self.link.info()
        return {"schema": STATE_SCHEMA, "app_version": __version__, "t_mono": now, "utc": utc_now(),
                "sim": self.sim, "mode": self.mode, "source": self.source, "advisory": ADVISORY,
                "unit": info, "vehicle": dict(self.vehicle.to_dict(), placeholder_note=PLACEHOLDER_NOTE),
                "fuel": self.fuel.to_dict(), "errors": {"count": self.errors, "last": self.last_error},
                "placeholders": {"note": PLACEHOLDER_NOTE, "vehicle_limits": bool(self.vehicle.placeholder),
                                 "decision_config": True, "thermal_flame_threshold_c": self.cfg.thermal.t_flame_c,
                                 "radar_thresholds": True, "depth_uncertainties": True},
                "simlink": self.simlink.status() if self.simlink is not None else {"enabled": False}}

    def _minimal_state(self, now: float) -> dict:
        st = self._common(now)
        st.update(verdict=self._verdict_dict(now), health=self.link.health(now).to_dict())
        return protocol.sanitize(st)

    def _thumb(self, thl: Optional[ThermalLatest]) -> Optional[dict]:
        if thl is None or thl.temps_k is None or not thl.valid:
            return None
        t = thl.temps_k
        h, w = t.shape
        f = 4 if (h % 4 == 0 and w % 4 == 0) else 1
        small = t.reshape(h // f, f, w // f, f).max(axis=(1, 3)) if f > 1 else t
        lo, hi = float(small.min()), float(small.max())
        scale = 255.0 / max(hi - lo, 1e-6)
        u8 = np.clip((small - lo) * scale, 0, 255).astype(np.uint8)
        return {"w": int(u8.shape[1]), "h": int(u8.shape[0]), "enc": "u8-b64", "pool": "max",
                "t_min_c": lo - th.C_TO_K, "t_max_c": hi - th.C_TO_K,
                "pix": base64.b64encode(u8.tobytes()).decode("ascii")}

    def _state(self, now, health, verdict, thl, geo, profile, rs, flame, thermal_flag, n_bear, cam_bearing,
               radar_bearing, near_slant, far_h, moving, depth, inten, fs, plate_q, data, passed, quiet) -> dict:
        c = self.cfg
        st = self._common(now)
        st["verdict"] = self._verdict_dict(now)
        st["health"] = health.to_dict()
        ne = geo.ne if geo is not None else None
        fh = geo.fh if geo is not None else None
        # radar per-bin arrays, max-pooled for the UI
        per = rs.per_bin or {}
        factor = 1
        if per.get("range_m"):
            factor = max(1, int(math.ceil(len(per["range_m"]) / max(1, c.radar.ui_max_bins))))
        per_ui = {}
        if per:
            per_ui = {"pool_factor": factor, "range_m": _pool(per["range_m"], factor, "first")}
            for k in ("window_max_db", "window_mean_db", "baseline_db", "loss_db", "loss_z", "flicker_amp_z",
                      "flicker_phase_z", "flicker_phase_rad", "flicker_amp_db", "present_frac"):
                if k in per:
                    per_ui[k] = _pool(per[k], factor, "max")
            if "target" in per:
                per_ui["target"] = _pool(per["target"], factor, "any")
        rsd = rs.to_dict()
        rsd.pop("per_bin", None)
        rsd.update(per_bin=per_ui, bearing_deg=radar_bearing, near_edge_slant_m=near_slant, moving=moving,
                   baseline=dict(self.baseline_info), latest_frame=self._radar_meta)
        st["flame"] = {
            "status": flame.status, "reason": flame.reason,
            "thermal": {"valid": thl.valid if thl else False, "reason": (thl.reason if thl else "no fresh frame"),
                        "flame_pixels": thl.flame_pixels if thl else None, "hot_pixels": thl.hot_pixels if thl else None,
                        "t_max_c": (float(thl.temps_k.max()) - th.C_TO_K) if thl is not None and
                        thl.temps_k is not None else None, "flame_at_bearing": thermal_flag,
                        "pixels_at_bearing": n_bear, "bearing_deg": cam_bearing, "t_flame_c": c.thermal.t_flame_c,
                        "shutter": thl.shutter if thl else None, "age_s": (now - thl.rx) if thl else None,
                        "thumb": self._thumb(thl)},
            "radar": rsd,
        }
        geom = {"valid": ne is not None, "reason": geo.reason if geo is not None else "no fresh valid thermal frame",
                "slope_source": profile.source if profile is not None else None,
                "profile": {"source": profile.source, "valid": profile.valid, "reason": profile.reason,
                            "s_m": profile.s.tolist(), "dz_m": profile.dz.tolist()} if profile is not None else None,
                "camera": {"height_m": self.pose.height_m, "mount_pitch_deg": self.pose.mount_pitch_deg,
                           "mount_roll_deg": self.pose.mount_roll_deg, "mount_yaw_deg": self.pose.mount_yaw_deg,
                           "hfov_deg": self.camera.hfov_deg, "vfov_deg": self.camera.vfov_deg,
                           "pitch_source": self.mount_info.get("pitch_source")},
                "imu": {"roll_deg": (data["imu"] or {}).get("roll_deg"),
                        "pitch_deg": (data["imu"] or {}).get("pitch_deg")},
                "far_echo_m": far_h, "far_echo_slant_m": rs.far_echo_m}
        if ne is not None:
            geom.update(near_edge_m=ne.d_m, near_edge_lo_m=ne.d_lo_m, near_edge_hi_m=ne.d_hi_m,
                        bearing_deg=ne.bearing_deg, occluded=ne.occluded, ground_dz_m=ne.ground_dz_m,
                        n_columns=len(ne.columns), base_cut_off=ne.base_cut_off, cut_off_reason=ne.cut_off_reason)
        if fh is not None:
            geom.update(flame_height_m=fh[0], flame_height_lo_m=fh[1], flame_height_hi_m=fh[2])
        st["geometry"] = geom
        dd = depth.to_dict()
        dd["estimators"] = dd.pop("estimates", [])
        st["depth"] = dd
        st["intensity"] = inten.to_dict()
        st["flux"] = {"q_kw_m2": plate_q, "valid": fs.valid if fs else False,
                      "reason": fs.reason if fs else "no fresh plate sample", "dTdt_k_s": fs.dTdt if fs else None,
                      "plate_c": self._plate_row.get("plate_c"), "air_c": self._plate_row.get("air_c"),
                      "tc_plate_c": (data["tc_plate"] or {}).get("temp_c"),
                      "tc_air_c": (data["tc_air"] or {}).get("temp_c"),
                      "tc_housing_c": (data["tc_housing"] or {}).get("temp_c"),
                      "dose_tdu": self.dose.dose_tdu, "dose_complete": self.dose.complete,
                      "uncounted_s": self.dose.uncounted_s, "loss_model": self.flux_est.loss.to_dict(),
                      "crossing": {k: v for k, v in self.crossing.items() if k != "prediction"}}
        st["heat"] = self._heat(depth, inten, ne)
        g = data["gnss"] or {}
        st["gnss"] = {k: g.get(k) for k in ("fix", "lat", "lon", "alt_m", "speed_m_s", "course_deg", "hdop", "sats",
                                            "utc")}
        st["gnss"].update(speed_km_h=(g["speed_m_s"] * 3.6) if _num(g.get("speed_m_s")) else None,
                          course_used_deg=self.course_deg, moving=moving, fresh=data["gnss"] is not None)
        st["reopen"] = {"passed": passed, "quiet_s": quiet, "hold_s": c.decision.reopen_hold_s,
                        "flame_ref": self.flame_ref, "far_edge_ref": self.far_edge_ref}
        st["calibration"] = dict(self.calib.to_dict(), store=str(self.store().path), sim_store=self.sim)
        st["tc"] = {s: data[s] for s in protocol.TC_SENSORS}
        st["pi"] = data["pi"]
        return protocol.sanitize(st)

    def _heat(self, depth: dp.DepthResult, inten: dp.IntensityResult, ne) -> dict:
        out: Dict[str, Any] = {"label": heat.FDS_LABEL, "chi": self.cfg.decision.chi, "valid": False}
        if not (depth.valid and inten.valid and _num(depth.depth_m) and _num(inten.i_kw_m)):
            out["reason"] = "needs a valid depth and intensity"
            return out
        D, I = float(depth.depth_m), float(inten.i_kw_m)
        try:
            rows = []
            for d in HEAT_D_M:
                ref = heat.fds_reference(d, I)
                rows.append({"d_m": d, "closed_form_kw_m2": heat.closed_form_line_flux(d, D, I, self.cfg.decision.chi),
                             "fds_ref_kw_m2": ref.q_kw_m2, "fds_ref_extrapolated": ref.extrapolated})
            out.update(valid=True, depth_m=D, intensity_kw_m=I, curve=rows,
                       in_flame_closed_form_kw_m2=heat.in_flame_flux(D, I, self.cfg.decision.chi),
                       in_flame_fds_ref_kw_m2=heat.fds_in_flame_reference(I).q_kw_m2,
                       note="central depth and intensity; the decision uses the conservative ends")
            if ne is not None and math.isfinite(ne.d_m) and ne.d_m >= 0:
                out["at_vehicle"] = heat.compare(float(ne.d_m), D, I, self.cfg.decision.chi)
        except ValueError as exc:
            out.update(valid=False, reason=str(exc))
        return out


# ----------------------------------------------------------------------------------------------- sources
Item = Tuple[float, str, Any]          # (relative time s, "msg" | "link", payload)


def is_research_log(path: Any) -> bool:
    return (Path(path) / "wire.jsonl.gz").exists()


def iter_source(path: Any) -> Iterator[Item]:
    """Time-ordered items of a recorded session: a research-log session dir (wire.jsonl.gz, laptop receipt times
    and link up/down markers reproduced) or a Pi record dir (wfgvu.replay: Pi t_mono spacing, link always up;
    a hello is synthesised from session.json)."""
    p = Path(path)
    if is_research_log(p):
        from .research_log import iter_wire
        t0 = None
        for rec in iter_wire(p):
            rx = rec.get("rx")
            if not _num(rx):
                continue
            t0 = rx if t0 is None else t0
            if "msg" in rec:
                yield rx - t0, "msg", rec["msg"]
            elif "link" in rec:
                yield rx - t0, "link", (rec["link"] == "up", rec.get("reason", ""))
        return
    from wfgvu import replay
    sess = replay.load(p)
    t0 = sess.t0
    extra = {}
    mount = _session_mount(sess.info)
    if mount:
        extra["mount"] = mount
    hello = protocol.make("hello", unit_id=sess.unit_id, session_id=sess.session_id or "replay", sim=sess.sim,
                          t_mono=t0, t_utc=None, sensors=sorted(sess.streams), version=str(
                              sess.info.get("wfgvu_version", "?")), config_digest=protocol.config_digest(
                              sess.info.get("config", {})), **extra)
    yield 0.0, "link", (True, "replay of %s" % p.name)
    yield 0.0, "msg", hello
    merged = heapq.merge(sess.merged(), sess.events(), key=lambda m: float(m["t_mono"]))
    for m in merged:
        yield max(0.0, float(m["t_mono"]) - t0), "msg", m


def _session_mount(info: Any) -> dict:
    """Camera mount of a recorded Pi session: session.json ``config.mount`` (the unit's config), else the synthetic
    generator's ``params.mount_pitch_deg`` / ``truth.camera.mount_pitch_deg`` (older wfgvu.synth sessions); {} when
    none is present."""
    if not isinstance(info, dict):
        return {}
    cfg = info.get("config")
    if isinstance(cfg, dict) and isinstance(cfg.get("mount"), dict):
        return dict(cfg["mount"])
    par = info.get("params")
    if isinstance(par, dict) and _num(par.get("mount_pitch_deg")):
        return {"camera_pitch_deg": float(par["mount_pitch_deg"])}
    cam = (info.get("truth") or {}).get("camera") if isinstance(info.get("truth"), dict) else None
    if isinstance(cam, dict) and _num(cam.get("mount_pitch_deg")):
        return {"camera_pitch_deg": float(cam["mount_pitch_deg"])}
    return {}


def apply_item(pipe: Pipeline, kind: str, payload: Any, now: float) -> None:
    if kind == "msg":
        pipe.feed(payload, now)
    elif kind == "link":
        up, reason = payload
        pipe.set_connected(bool(up), now, reason)


def run_virtual(pipe: Pipeline, items: Iterable[Item], t0: float = 1000.0, tail_s: float = 0.0,
                on_tick: Optional[Callable[[float, dict], None]] = None, tick_hz: Optional[float] = None,
                hooks: Optional[Dict[float, Callable[[Pipeline, float], None]]] = None) -> List[Tuple[float, dict]]:
    """Deterministic, as-fast-as-possible replay on a virtual laptop clock (``now = t0 + relative time``).

    Ticks at ``tick_hz`` (default cfg.tick_hz) interleaved with the items in time order. ``hooks`` maps a relative
    time to a callable run once just before the first tick at or after it (e.g. capture a baseline). Returns the
    list of (relative tick time, state)."""
    dt = 1.0 / (tick_hz or pipe.cfg.tick_hz)
    out: List[Tuple[float, dict]] = []
    pending = sorted((hooks or {}).items())
    k = 1
    last_t = 0.0

    def run_ticks(until: float) -> None:
        nonlocal k
        while k * dt <= until:
            tr = k * dt
            while pending and pending[0][0] <= tr + 1e-9:
                pending.pop(0)[1](pipe, t0 + tr)
            st = pipe.tick(t0 + tr)
            out.append((tr, st))
            if on_tick is not None:
                on_tick(tr, st)
            k += 1

    for t_rel, kind, payload in items:
        run_ticks(t_rel - 1e-7)
        apply_item(pipe, kind, payload, t0 + t_rel)
        last_t = max(last_t, t_rel)
    run_ticks(last_t + tail_s + 1e-9)
    return out


async def play(pipe: Pipeline, path: Any, speed: float = 1.0, loop: bool = False,
               stop: Optional[asyncio.Event] = None, clock: Callable[[], float] = time.monotonic) -> None:
    """Real-time replay into a running pipeline (the server's ticker calls ``tick``). Receipt times are this
    laptop's clock at feed time; recorded spacing is divided by ``speed``."""
    if not speed > 0:
        raise ValueError("speed must be > 0")
    stop = stop or asyncio.Event()
    while not stop.is_set():
        start = clock()
        n = 0
        for t_rel, kind, payload in iter_source(path):
            due = start + t_rel / speed
            delay = due - clock()
            if delay > 0:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=delay)
                    return
                except asyncio.TimeoutError:
                    pass
            elif n % 200 == 0:
                await asyncio.sleep(0)
            if stop.is_set():
                return
            apply_item(pipe, kind, payload, clock())
            n += 1
        if not loop:
            pipe.set_connected(False, clock(), "replay ended")
            return
        await asyncio.sleep(0.5)


def load_dem(path: Optional[Any]) -> Optional[Dem]:
    return Dem.load(path) if path else None


def state_json(state: dict) -> str:
    return json.dumps(state, separators=(",", ":"), allow_nan=False)
