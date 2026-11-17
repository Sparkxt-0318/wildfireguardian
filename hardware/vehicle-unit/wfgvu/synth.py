"""Synthetic scenario generator: writes SIMULATED sessions in the recorded-session format (DESIGN.md section 4).

    python -m wfgvu.synth SCENARIO OUT_DIR --seed N --duration S [--fail SENSOR@T] [--freeze SENSOR@T]
                          [--fault tc_plate@T:open] [--range M] [--depth M] [--height M] [--spread M_S] [--speed M_S]
    python -m wfgvu.synth samples OUT_ROOT          # regenerate the committed sample set (samples/)

Scenarios: ``no_fire``, ``smoke_only``, ``flame_front``, ``water_mist``, ``corner_reflector``, ``crossing``,
``after_pass``, ``crossing_return``, ``crossing_return_hot``. OUT_DIR becomes a session directory (``session.json`` +
``<sensor>.jsonl.gz`` + ``events.jsonl.gz``, plus ``dem.npz`` for the return scenarios)
that ``python -m wfgvu --sim OUT_DIR`` replays and ``replay.load`` reads. Every message has ``"sim": true``;
``session.json`` has ``"sim": true``, a ``"simulated"`` notice and a ``truth`` block with the scene that generated
the data (distances, flame depth/height, kinematics, overlays, ...), so laptop code can be checked against it.

Return scenarios (``crossing_return``, ``crossing_return_hot``; the only ones that leave the road axis)
---------------------------------------------------------------------------------------------------------
The vehicle crosses the flame as in ``crossing``, drives on, turns round and stops facing the crossed road, so the
laptop's REOPENED view check (crossing in the camera view, within reopen_max_view_m, DEM line of sight) can be met:
- Path (world X along the outbound road, Y to its left, heading psi counter-clockwise from +X): straight to
  ``X_turn = far edge + turn_after_far_m``; a "teardrop" turnaround driven FORWARD at ``turn_speed_m_s`` (default
  3 m/s, above the laptop's 2 m/s reliable-course speed, so GNSS course follows the heading; no reversing): a right
  arc of radius ``turn_radius_m`` (8 m) through beta, then a left arc through 180 deg + beta, with
  cos(beta) = return_lane_m / (2 R), which ends heading back along the road on a lane ``return_lane_m`` (3 m) left
  of the outbound track; then straight back, braking at ``brake_m_s2`` to stop at ``X = far edge +
  stop_after_far_m`` (25 m) facing the crossing (``turn_after_far_m`` default 18 m). The turnaround needs about 2 R of space to the right of the road (a
  junction mouth or lay-by; the ground there is verge). Defaults: flame onset 4 s, vehicle off at 9 s, crossing at
  about 12.6 s, burn-out at 16 s, turn from about 17 s to 33 s, stop at about 36.7 s.
- The flame burns out at ``flame_out_s`` (fuel exhausted / knocked down; must be before the turn starts and after
  the vehicle has left the flame, else ValueError). From then on the burnt strip (fuel bed and the burnt zone
  beyond it, frozen where they were at burn-out) cools exponentially towards the unburnt road/verge temperature
  with time constant ``cool_tau_s`` (8 s, illustrative); the air probe's +10 C over burnt ground decays alike.
- ``crossing_return_hot``: identical, plus a hot area (burning debris / embers, ``hot_spot_c`` 600 C, 2 m along
  x 3 m across, flat on the road) that STAYS in the middle of the crossed strip after burn-out. Seen from the stop
  (~26 m, through the distance haze) it reads ~549 C, so it gives flame-temperature pixels over the crossing; it
  must never give REOPENED.
- No parked vehicle beyond the flame in these scenarios (it would stand on the return path); the sign post and
  ground clutter stay. Radar, thermal, IMU and GNSS use the full 2-D pose (radar targets and rays in the vehicle
  frame at heading psi; attitude pitch = atan(grade cos psi), roll = roll - atan(grade sin psi); GNSS course and IMU
  heading = course - psi).
- ``dem.npz``: a small SIMULATED DEM in the laptop's ``crossing.terrain.Dem`` npz format ("local-enu", lat0/lon0 =
  the start fix, 2 m cells) of exactly this session's ground plane (alt0 + grade * X), written next to the streams
  and named in session.json ``dem``. The laptop needs it (``--dem``) to show line of sight (FS-8). Bare earth only.

EVERYTHING HERE IS SIMULATED AND ILLUSTRATIVE ONLY. The physics below is a plausible toy model chosen so that the
laptop pipeline has something with the right shape to chew on. None of it is calibrated against the TC001, the
IWR6843AOP, a real flame, real smoke or a real crossing, and none of it is evidence of how a real flame looks to
these sensors. In particular the radar "flame effect" is an ASSUMPTION of this project, not a measured signature.

Scene and frames
----------------
- World x is distance along the road (the GNSS course) from the vehicle's ground point at t = 0, y is to the left,
  z is up. The road is a plane with constant grade ``grade`` (rise/run, default +0.04 = 4 % uphill ahead), so the
  ground height at along-road distance x ahead of the vehicle is ``grade * x`` relative to the vehicle's ground
  point (cross slope 0). The vehicle body sits on that plane: true pitch = atan(grade) (+ nose up), true roll =
  ``roll_deg`` (+ right side down), plus a small suspension vibration while driving.
- Vehicle-level frame (used by the laptop geometry, DESIGN 6.4): x forward along the course, y left, z up; bearings
  + right. Camera boresight = body attitude (pitch, roll) composed with the mount angles (yaw + right, pitch + up,
  roll + right side down; intrinsic, in that order). Camera height = vertical height above the ground point under
  the vehicle (``cam_height_m``, default 2.6 m from config/unit.yaml ``mount.camera_height_m``).

Thermal (TC001, 256 x 192 px, 56 x 42 deg, pinhole, no distortion)
-------------------------------------------------------------------
- Pixel (row i, col j) has its centre at continuous image coordinates (i, j); principal point ((w-1)/2, (h-1)/2);
  fx = (w/2)/tan(hfov/2), fy = (h/2)/tan(vfov/2). Camera ray of pixel (i, j) = (1, -(j-cx)/fx, -(i-cy)/fy) in
  (forward, left, up). This is the same model the laptop's ``crossing.thermal.CameraModel`` documents, so its
  near-edge geometry can be compared with ``truth``.
- Each ray is traced against: the ground plane (road |y| < 3.5 m at ambient + 8 C, verge at ambient + 2 C, burnt
  ground behind a flame front 150 C at the front cooling to ~50 C 40 m back, burning fuel bed under the flame
  700 C), boxes (a parked vehicle beyond the flame at ambient + 10 C; the corner reflector at 5 C because polished
  metal reflects the cold sky in LWIR) and the sky (240 K overhead, warmer towards the horizon).
- Participating volumes along the ray (flame, smoke, mist) are slabs between two along-road distances and two
  heights above ground. Radiance is composited far to near at a single effective wavelength of 10 um:
  ``B = eps * B(T_volume) + (1 - eps) * B_behind`` with ``eps = 1 - exp(-kappa * path_length)``.
  Flame: gas 850 C +- 80 C (blocky flicker, 16 px blocks, per frame), kappa 0.6 1/m, so a flame is optically THIN
  (a 1 m path gives eps 0.45) and reads cooler than its gas; height flickers +-15 % (1 sigma) per 8-column block.
  Smoke: 70-75 C, kappa 0.03-0.04 1/m (smoke is mostly transparent at 8-14 um); smoke-only scenes stay < 120 C.
  Mist: ambient - 6 C (evaporative cooling), kappa 0.15 1/m: a cool, partly occluding curtain. After a pass: a thin
  residual haze over the burnt zone (45 C, kappa 0.01 1/m). Path lengths are taken in the vertical along-course
  plane: the lateral obliquity of off-axis rays is ignored (at most +13 % at the image edge).
- The camera output is clipped to the gain range (low gain: -20 .. 550 C; high gain: -20 .. 150 C), so a real
  flame saturates at the ceiling. Noise: a slow global offset drift (+-0.05 K), per-row banding 0.02 K per frame
  and white pixel noise ``pixel_noise_k`` (default 0.04 K). The committed samples use ``COMPACT`` settings instead
  (no pixel noise or banding, scene in 0.25 K steps, a whole-frame offset walk of 1-2 raw counts per frame) so the
  files stay small while consecutive frames still always differ.
  Encoding is the protocol's u16-zlib-b64 (raw/64 = K); only the zlib level differs (9 instead of 1, smaller files).
- The thermal stream is generated at ``thermal_hz`` (default 4 Hz, the wire rate) rather than the TC001's ~25 Hz.

Radar (IWR6843AOP stock demo, illustrative)
-------------------------------------------
- Reduced grid: ``n_bins`` 100 x ``range_res_m`` 0.25 m (25 m) with ``n_ant`` 4 virtual antennas on a uniform
  lambda/2 azimuth line (the laptop's default ``ArrayGeometry``), 10 Hz. The default real config
  ``config/iwr6843aop_vu.cfg`` is 128 bins x 0.468 m (max 54 m) with 12 virtual antennas (a 2-D array); the old
  ``_short`` config is 512 bins x 4.9 cm (22.5 m). The synthetic grid is smaller so the samples stay small, and its
  25 m reach covers the committed scenarios only (targets beyond 25 m are capped to the grid). Change with ``--radar-bins``, ``--range-res``, ``--n-ant``. The samples also
  use 1 int16 count of noise per component and a 0.5 dB range-profile step (``COMPACT``).
- Complex heatmap ``x[bin, ant] = sum_targets A * g(az) * exp(j 4 pi r / lambda) * exp(j pi n sin(az)) * K(bin - r/res)
  + noise``, noise circular complex Gaussian with unit variance per element (scaled to ``iq_noise_counts`` int16
  counts per component on the wire), lambda = c / 62 GHz, ``K`` a 5-tap Hann-windowed sinc range kernel, ``g(az) =
  cos(az)^2`` amplitude pattern. Range r is the slant range from the radar (``radar_height_m``) to each scatterer.
  Targets: a TX/RX leakage term at r ~ 0 (+40 dB, never affected by anything), ~400 ground-clutter scatterers on the
  road and verges with Rayleigh amplitudes and power falling as r^-3 (15 dB per scatterer at 5 m), a sign post
  (22 dB, 7 m, 20 deg left), a solid object beyond the flame (parked vehicle / guardrail end, 35 dB, ~4 m beyond the
  far edge, capped to the grid) and, in ``corner_reflector``, a corner reflector at radar height (50 dB).
  Discrete targets' amplitude falls as r^-2 when the vehicle moves. A common platform phase jitter of 0.03 rad
  (engine idle) is applied to all echoes.
- Flame effect (ASSUMED, the thing the laptop's detector looks for): echoes whose line of sight from the radar
  passes through the flame volume (bins behind the flame, and clutter within the flame's extent) get, in frames
  where the flame is "on" in that path, ``10^(-L/20) * exp(j psi)``: L = ``flame_loss_db`` (default 2 dB, 1-3 dB)
  times (1 + 0.3 N(0,1)) and scaled by the fraction of the flame depth the path crosses; psi a random walk with
  step ``phase_step_rad`` (default 0.45 rad, 0.3-0.6) per frame, scaled down for paths shorter than 0.5 m.
  "Gaps": a two-state Markov chain switches the flame off in the path (clear look, g = 1) for ~30 % of frames.
  The flame itself is not a radar scatterer here. Smoke has NO radar effect. Mist: L = ``mist_loss_db`` (default
  2 dB) + amplitude flicker N(0, 0.35 dB) per frame, NO phase walk.
- ``range_profile_db`` = 10 log10(sum_n |x_n|^2) + 30 dB (non-coherent over antennas), rounded to 0.1 dB.
  ``points``: one detection per discrete target with SNR > 12 dB in that frame, in the TI convention
  (x right, y forward, z up, radial velocity < 0 when closing). ``tlv_types`` [1, 2, 4, 7].

Plate, thermocouples, IMU, GNSS, Pi
-----------------------------------
- Incident flux at the plate (vertical, facing forward, ``plate_height_m``): ahead of the flame,
  ``q = E * F``, ``F = (sin(phi_top) - sin(phi_base)) / 2`` the view factor of a vertical element to an infinitely
  wide vertical strip (the flame face, from the ground to the flame height, at distance s), E = ``flame_ep_kw_m2``
  (default 40 kW/m2); inside the flame zone ``q = q_in_kw_m2`` (default 50 kW/m2, radiative + convective immersion);
  once the flame is behind the plate 0 (it faces forward); warm burnt ground ahead adds
  ``0.25 * sigma * (Tb^4 - Ta^4)``.
- Plate temperature: thin-skin energy balance integrated with RK4 at 0.01 s, using exactly the laptop's default
  model (crossing/flux.py): ``rho*cp*d*dT/dt = alpha*q - h*(T - Ta) - eps*sigma*(T^4 - Ta^4)``, 1 mm copper
  (8960 kg/m3, 385 J/kg/K), alpha = eps = 0.95, h = 10 W/m2/K, and Ta = the air thermocouple's (lagged) value,
  because that is what the laptop uses for Ta. So ``truth`` q is the flux the laptop formula should recover, not a
  statement about real convective heating.
- Air thermocouple (engine-intake height): ambient, + up to 8 C within 4 m of the flame front, gas
  ``air_in_flame_c`` (400 C) inside the flame zone, + 10 C over burnt ground; first-order bead lag 1.5 s.
- Housing: first-order (300 s) drift towards ambient + 9 C + 1 C per 10 min (electronics), + 0.05 C per kW/m2.
  MAX31855 output: 0.25 C steps (hot junction, noise 0.1 C), 0.0625 C steps (cold junction = board temperature).
  Faults: ``open``/``short_gnd``/``short_vcc`` give temp_c null, ``spi`` gives both null (as the driver decodes).
- IMU 20 Hz: true roll/pitch + N(0, 0.05 deg), 1/16 deg steps; heading = course + 8.5 deg (magnetic, illustrative
  westerly declination); gravity vector in the body frame (x fwd, y left, z up) in m/s2.
- GNSS 5 Hz: track along the course from (lat0, lon0) (default near Uiseong, 36.39 N 128.70 E) on the WGS84
  ellipsoid (local radii), position noise first-order Gauss-Markov 0.5 m / 20 s, speed noise 0.03 m/s; the course
  is held at the road course when stopped (receiver "static hold"); fix 1, hdop 0.8, 14 satellites.
- Pi 1 Hz: CPU temperature following the housing, no throttling, 5.08 V, disk and record counters.

Failure overlays (applied to the generated streams)
--------------------------------------------------
- ``--fail SENSOR@T``: readings stop at T. Heartbeats keep ``ok`` until ``stale_s`` has passed, then ``stale``
  for 1 s, then ``no_device`` ("synthetic --fail overlay") to the end; ``rate_hz`` drops to 0.
- ``--freeze SENSOR@T``: from T every reading carries the identical ``data`` of the last reading before T, with
  ``seq`` still increasing and heartbeats still ``ok`` (the Pi cannot tell; the laptop's frozen-data check must).
- ``--fault tc_X@T:KIND``: from T the thermocouple reports ``fault`` = KIND; heartbeats say ``error``.
Each overlay is listed in ``truth.overlays`` and recorded as an ``event`` at T.

Determinism: every sensor has its own random stream derived from ``--seed``, so the same arguments give
byte-identical files (gzip mtime 0, fixed start time) and an overlay on one sensor does not change the others.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import math
import sys
import zipfile
import zlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import __version__, protocol, recorder

RETURN_SCENARIOS = ("crossing_return", "crossing_return_hot")
SCENARIOS = ("no_fire", "smoke_only", "flame_front", "water_mist", "corner_reflector", "crossing",
             "after_pass") + RETURN_SCENARIOS
FLAME_SCENARIOS = ("flame_front", "crossing") + RETURN_SCENARIOS
DEM_FILE = "dem.npz"
# Params fields used only by the return scenarios (left out of other sessions' session.json "params")
RETURN_PARAMS = ("flame_out_s", "cool_tau_s", "turn_after_far_m", "turn_radius_m", "turn_speed_m_s", "return_lane_m",
                 "brake_m_s2", "hot_spot_c", "hot_spot_len_m", "hot_spot_width_m", "dem_res_m")
SIM_NOTICE = ("SIMULATED: synthetic data from wfgvu.synth with illustrative physics only. Not a measurement, not "
              "evidence of how real flames, smoke or mist look to these sensors.")

C_TO_K = 273.15
SIGMA = 5.670374419e-8
C_LIGHT = 299792458.0
RADAR_F_HZ = 62.0e9
LAMBDA_M = C_LIGHT / RADAR_F_HZ
PLANCK_C2 = 1.438777e-2          # m K
LWIR_LAMBDA_M = 10.0e-6          # single effective wavelength for the 8-14 um band
STALE_S = {"thermal": 1.0, "radar": 1.0, "tc_plate": 1.0, "tc_housing": 1.0, "tc_air": 1.0, "imu": 0.5,
           "gnss": 2.0, "pi": 3.0}
GAIN_RANGE_C = {"low": (-20.0, 550.0), "high": (-20.0, 150.0)}
MAG_DECLINATION_DEG = -8.5       # illustrative (west); magnetic heading = true heading - declination
WGS84_A = 6378137.0
WGS84_E2 = 6.69437999014e-3
DT_PHYS = 0.01                   # s, integration step of the plate / air / housing models
T_MONO0 = 5000.0                 # recorded Pi monotonic clock at t = 0 (arbitrary uptime)


# ================================================================================================ parameters

@dataclass
class Params:
    """All knobs of a synthetic session (SI units; temperatures in C; angles in degrees)."""
    scenario: str = "no_fire"
    seed: int = 0
    duration_s: float = 50.0
    # scene
    range_m: Optional[float] = None        # flame near edge at onset / smoke / mist / reflector / burnt-zone start
    depth_m: Optional[float] = None        # flame depth / smoke or mist slab depth / burnt-zone length
    height_m: Optional[float] = None       # flame height / smoke or mist top
    spread_m_s: Optional[float] = None     # flame front spread towards the vehicle
    speed_m_s: Optional[float] = None      # vehicle cruise speed
    onset_s: float = 8.0                   # flame / smoke / mist appears (before: radar baseline window)
    t_go_s: Optional[float] = None         # vehicle starts moving
    stop_after_far_m: Optional[float] = None   # stop this far beyond the far edge (crossing / after_pass / return)
    accel_m_s2: float = 2.0
    # return scenarios (crossing_return*): turnaround and burn-out (see the module docstring)
    flame_out_s: Optional[float] = None    # flame burns out (None: never)
    cool_tau_s: float = 8.0                # burnt strip cooling time constant after burn-out
    turn_after_far_m: float = 18.0         # the turn starts this far beyond the far edge (world X)
    turn_radius_m: float = 8.0
    turn_speed_m_s: float = 3.0
    return_lane_m: float = 3.0             # return lane, left of the outbound track
    brake_m_s2: float = 1.5
    hot_spot_c: Optional[float] = None     # crossing_return_hot: hot area left over the crossing after burn-out
    hot_spot_len_m: float = 2.0
    hot_spot_width_m: float = 3.0
    dem_res_m: float = 2.0
    grade: float = 0.04
    roll_deg: float = 0.0
    ambient_c: float = 25.0
    lat0: float = 36.39
    lon0: float = 128.70
    alt0_m: float = 120.0
    course_deg: float = 30.0
    # mount (config/unit.yaml placeholders)
    cam_height_m: float = 2.6
    mount_pitch_deg: float = 0.0
    mount_roll_deg: float = 0.0
    mount_yaw_deg: float = 0.0
    radar_height_m: float = 2.6
    plate_height_m: float = 2.5
    air_probe_height_m: float = 1.0
    # flame physics (illustrative)
    flame_gas_c: float = 850.0
    flame_kappa: float = 0.6
    flame_ep_kw_m2: float = 40.0
    q_in_kw_m2: float = 50.0
    air_in_flame_c: float = 400.0
    flame_loss_db: float = 2.0
    phase_step_rad: float = 0.45
    flame_on_frac: float = 0.7
    mist_loss_db: float = 2.0
    # sensors
    gain: str = "low"
    thermal_hz: float = 4.0
    radar_hz: float = 10.0
    tc_hz: float = 10.0
    imu_hz: float = 20.0
    gnss_hz: float = 5.0
    pi_hz: float = 1.0
    n_bins: int = 100
    range_res_m: float = 0.25
    n_ant: int = 4
    iq_noise_counts: float = 2.0
    profile_step_db: float = 0.1
    pixel_noise_k: float = 0.04
    row_noise_k: float = 0.02              # per-row banding per frame
    scene_quant_k: float = 0.0             # > 0: noiseless scene rounded to this step (compact samples only)
    offset_walk: bool = False              # compact samples: whole-frame offset walk instead of pixel noise
    # session
    unit_id: str = "VU-01"
    start_utc: str = "2026-11-17T02:00:00Z"
    overlays: List[dict] = field(default_factory=list)


# Settings of the committed samples (``--compact``): smaller files, otherwise the same physics. Thermal: no white
# pixel noise and no row banding, scene rounded to 0.25 K, and a whole-frame offset walk of 1-2 raw counts per frame
# so consecutive frames always differ (as they do with a real camera's noise);
# radar: noise at 1 int16 count per component (quantisation adds ~8 % noise power), range profile in 0.5 dB steps.
COMPACT = dict(pixel_noise_k=0.0, row_noise_k=0.0, scene_quant_k=0.25, offset_walk=True, iq_noise_counts=1.0,
               profile_step_db=0.5)

SCENARIO_DEFAULTS: Dict[str, dict] = {
    "no_fire": dict(),
    "smoke_only": dict(range_m=12.0, depth_m=10.0, height_m=12.0),
    "flame_front": dict(range_m=14.0, depth_m=3.0, height_m=2.0, spread_m_s=0.05),
    "water_mist": dict(range_m=4.0, depth_m=4.0, height_m=5.0),
    "corner_reflector": dict(range_m=3.0),
    "crossing": dict(range_m=12.0, depth_m=3.0, height_m=2.0, spread_m_s=0.02, speed_m_s=5.0, t_go_s=20.0,
                     stop_after_far_m=25.0),
    "after_pass": dict(range_m=10.0, depth_m=6.0, height_m=0.0, speed_m_s=3.0, t_go_s=4.0, stop_after_far_m=25.0),
    "crossing_return": dict(range_m=12.0, depth_m=3.0, height_m=2.0, spread_m_s=0.02, speed_m_s=5.0, onset_s=4.0,
                            t_go_s=9.0, stop_after_far_m=25.0, turn_after_far_m=18.0, flame_out_s=16.0),
    "crossing_return_hot": dict(range_m=12.0, depth_m=3.0, height_m=2.0, spread_m_s=0.02, speed_m_s=5.0, onset_s=4.0,
                                t_go_s=9.0, stop_after_far_m=25.0, turn_after_far_m=18.0, flame_out_s=16.0,
                                hot_spot_c=600.0),
}


def make_params(scenario: str, **kw) -> Params:
    """Params for a scenario: dataclass defaults, then the scenario's defaults, then non-None keyword overrides."""
    if scenario not in SCENARIOS:
        raise ValueError("unknown scenario %r (choose from %s)" % (scenario, ", ".join(SCENARIOS)))
    vals = dict(SCENARIO_DEFAULTS[scenario])
    vals.update({k: v for k, v in kw.items() if v is not None})
    p = Params(scenario=scenario, **vals)
    if p.speed_m_s is None:
        p.speed_m_s = 0.0
    if p.t_go_s is None:
        p.t_go_s = 0.0
    if p.spread_m_s is None:
        p.spread_m_s = 0.0
    if p.gain not in GAIN_RANGE_C:
        raise ValueError("gain must be 'low' or 'high'")
    if p.duration_s <= 0:
        raise ValueError("duration must be > 0")
    if scenario in RETURN_SCENARIOS:
        if not (0.0 < p.return_lane_m < 2.0 * p.turn_radius_m):
            raise ValueError("return_lane_m must be in (0, 2 * turn_radius_m)")
        if not (0.0 < p.turn_speed_m_s <= p.speed_m_s and p.brake_m_s2 > 0 and p.cool_tau_s > 0):
            raise ValueError("need 0 < turn_speed_m_s <= speed_m_s, brake_m_s2 > 0, cool_tau_s > 0")
        if not (p.stop_after_far_m is not None and p.stop_after_far_m > 0.0 and p.turn_after_far_m > 0.0):
            raise ValueError("need stop_after_far_m > 0 and turn_after_far_m > 0")
    if scenario == "corner_reflector" and not (2.0 <= p.range_m <= 5.0):
        print("warning: corner_reflector range %.2f m is outside the 2-5 m test B geometry" % p.range_m,
              file=sys.stderr)
    return p


# ================================================================================================ overlays

def parse_overlay(kind: str, spec: str) -> dict:
    """``SENSOR@T`` (fail, freeze) or ``tc_X@T:FAULT`` (fault) -> overlay dict. Raises ValueError."""
    if "@" not in spec:
        raise ValueError("overlay %r: expected SENSOR@T" % spec)
    sensor, rest = spec.split("@", 1)
    fault = None
    if kind == "fault":
        if ":" not in rest:
            raise ValueError("--fault %r: expected tc_X@T:KIND" % spec)
        rest, fault = rest.split(":", 1)
        if sensor not in protocol.TC_SENSORS:
            raise ValueError("--fault applies to thermocouples %s, not %r" % (protocol.TC_SENSORS, sensor))
        if fault not in protocol.TC_FAULTS or fault is None:
            raise ValueError("--fault kind must be one of open, short_gnd, short_vcc, spi")
    if sensor not in protocol.SENSORS:
        raise ValueError("unknown sensor %r in %r" % (sensor, spec))
    t = float(rest)
    if not math.isfinite(t) or t < 0:
        raise ValueError("overlay time must be >= 0 s")
    return {"kind": kind, "sensor": sensor, "t_s": t, "fault": fault}


# ================================================================================================ helpers

def _rot_pitch_up(deg: float) -> np.ndarray:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, 0.0, -s], [0.0, 1.0, 0.0], [s, 0.0, c]])        # forward -> (c, 0, s): nose up


def _rot_roll_right_down(deg: float) -> np.ndarray:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])        # left -> (0, c, s): right side down


def _rot_yaw_right(deg: float) -> np.ndarray:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]])        # forward -> (c, -s, 0): to the right


def planck(t_k):
    """Relative spectral radiance at 10 um (constant factors dropped)."""
    return 1.0 / np.expm1(PLANCK_C2 / (LWIR_LAMBDA_M * np.asarray(t_k, dtype=float)))


def inv_planck(b):
    return PLANCK_C2 / (LWIR_LAMBDA_M * np.log1p(1.0 / np.maximum(np.asarray(b, dtype=float), 1e-300)))


def _epoch(utc: str) -> float:
    s = utc.rstrip("Z")
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp()


def encode_thermal_compact(temps_k: np.ndarray, gain: str, shutter: bool = False) -> dict:
    """``thermal`` data in the protocol's exact format (u16 LE raw = round(K*64), zlib, base64), compressed at zlib
    level 9 instead of the driver's level 1. Any zlib decoder (``protocol.decode_thermal``) reads both."""
    t = np.asarray(temps_k, dtype=np.float64)
    raw = np.clip(np.round(np.where(np.isfinite(t), t, 0.0) * protocol.RAW_PER_K), 0, 65535).astype("<u2")
    h, w = raw.shape
    pix = base64.b64encode(zlib.compress(raw.tobytes(), 9)).decode("ascii")
    return {"w": int(w), "h": int(h), "enc": protocol.THERMAL_ENC, "raw_per_k": float(protocol.RAW_PER_K),
            "pix": pix, "gain": gain, "shutter": bool(shutter)}


def encode_iq_compact(c: np.ndarray) -> dict:
    """``az_heatmap`` in the protocol's exact format (int16 LE real/imag pairs, zlib, base64) at zlib level 9."""
    a = np.asarray(c)
    out = np.empty(a.shape + (2,), dtype="<i2")
    out[..., 0] = np.clip(np.round(a.real), -32768, 32767)
    out[..., 1] = np.clip(np.round(a.imag), -32768, 32767)
    return {"n_ant": int(a.shape[1]), "enc": protocol.IQ_ENC,
            "iq": base64.b64encode(zlib.compress(out.tobytes(), 9)).decode("ascii")}


def _q(x: float, step: float) -> float:
    """Quantise to a sensor step, returned as a short float."""
    return float(round(round(x / step) * step, 6))


# ================================================================================================ scene / kinematics

class Scene:
    """Time-dependent truth: vehicle motion, flame / smoke / mist / burnt-zone positions (world x along the road)."""

    def __init__(self, p: Params):
        self.p = p
        sc = p.scenario
        self.flame = sc in FLAME_SCENARIOS
        self.smoke_only = sc == "smoke_only"
        self.mist = sc == "water_mist"
        self.after = sc == "after_pass"
        self.reflector = sc == "corner_reflector"
        self.two_d = sc in RETURN_SCENARIOS
        n = int(round(p.duration_s / DT_PHYS)) + 1
        self.t = np.arange(n) * DT_PHYS
        if self.two_d:
            self.path = self._return_path()
            self.sig, self.v = self._motion_path()
            pose = [self._pose_at(float(si)) for si in self.sig]
            self.s = np.array([q[0] for q in pose])            # world X (along the outbound road)
            self.y = np.array([q[1] for q in pose])
            self.psi = np.array([q[2] for q in pose])
            self._check_return()
        else:
            self.s, self.v = self._motion()

    # ---------------------------------------------------------------- flame geometry (world x)
    def flame_present(self, t: float) -> bool:
        if self.p.flame_out_s is not None and t >= self.p.flame_out_s:
            return False
        return self.flame and t >= self.p.onset_s

    def out_decay(self, t: float) -> Optional[float]:
        """Return scenarios after burn-out: exp(-(t - flame_out_s) / cool_tau_s), else None."""
        if not self.two_d or self.p.flame_out_s is None or t < self.p.flame_out_s:
            return None
        return math.exp(-(t - self.p.flame_out_s) / self.p.cool_tau_s)

    def strip_at_out(self) -> Tuple[float, float, float]:
        """World x of the fuel bed's near / far edge and of the burnt zone's end, frozen at burn-out."""
        xn = float(self.near_w(self.p.flame_out_s))
        xf = float(self.far_w(self.p.flame_out_s))
        return xn, xf, xf + 40.0

    def hot_spot(self) -> Optional[Tuple[float, float, float, float, float]]:
        """crossing_return_hot: (x_centre, y_centre, length along x, width across, T [C]) of the hot area left in
        the middle of the crossed strip after burn-out, else None."""
        if not self.two_d or self.p.hot_spot_c is None or self.p.flame_out_s is None:
            return None
        xn, xf, _ = self.strip_at_out()
        return 0.5 * (xn + xf), 0.0, self.p.hot_spot_len_m, self.p.hot_spot_width_m, float(self.p.hot_spot_c)

    def ground_k_2d(self, t: float, xw: np.ndarray, yw: np.ndarray) -> np.ndarray:
        """Return scenarios: ground temperature [K] at world points (x along the outbound road, y left)."""
        p = self.p
        amb = p.ambient_c
        base = np.where(np.abs(yw) < 3.5, amb + 8.0, amb + 2.0) + C_TO_K
        tg = base
        if self.flame_present(t):
            xn_w, xf_w = float(self.near_w(t)), float(self.far_w(t))
            inb = (xw >= xf_w) & (xw <= xf_w + 40.0)
            frac = np.clip((xw - xf_w) / 40.0, 0.0, 1.0)
            tg = np.where(inb, 150.0 + (50.0 - 150.0) * frac + C_TO_K, tg)
            tg = np.where((xw >= xn_w) & (xw <= xf_w), 700.0 + C_TO_K, tg)
            return tg
        dec = self.out_decay(t)
        if dec is None:
            return tg
        xn, xf, xe = self.strip_at_out()
        frac = np.clip((xw - xf) / max(xe - xf, 1e-6), 0.0, 1.0)
        prof = np.where((xw >= xn) & (xw <= xf), 700.0, 150.0 + (50.0 - 150.0) * frac) + C_TO_K
        strip = (xw >= xn) & (xw <= xe)
        tg = np.where(strip, base + (prof - base) * dec, tg)
        hs = self.hot_spot()
        if hs is not None:
            xc, yc, ln, wd, tc = hs
            tg = np.where((np.abs(xw - xc) <= ln / 2.0) & (np.abs(yw - yc) <= wd / 2.0), tc + C_TO_K, tg)
        return tg

    def near_w(self, t):
        """World x of the flame's near edge (base of the front facing the vehicle)."""
        return self.p.range_m - self.p.spread_m_s * np.maximum(np.asarray(t, dtype=float) - self.p.onset_s, 0.0)

    def far_w(self, t):
        return self.near_w(t) + self.p.depth_m

    def burnt_zone(self, t: float) -> Optional[Tuple[float, float, float, float]]:
        """(x0, x1, T at x0 [C], T at x1 [C]) of warm burnt ground, or None."""
        dec = self.out_decay(t)
        if dec is not None:                      # return scenarios after burn-out: frozen and cooling
            _, xf, xe = self.strip_at_out()
            amb = self.p.ambient_c
            return xf, xe, amb + (150.0 - amb) * dec, amb + (50.0 - amb) * dec
        if self.flame and t >= self.p.onset_s:
            x0 = float(self.far_w(t))
            return x0, x0 + 40.0, 150.0, 50.0
        if self.after:
            return self.p.range_m, self.p.range_m + self.p.depth_m, 95.0, 70.0
        return None

    def _stop_target(self) -> Optional[float]:
        if self.p.stop_after_far_m is None:
            return None
        if self.two_d:
            return self.path["x_stop"]
        if self.flame:
            return float(self.far_w(self.p.t_go_s)) + self.p.stop_after_far_m
        if self.after:
            return self.p.range_m + self.p.depth_m + self.p.stop_after_far_m
        return None

    def _motion(self) -> Tuple[np.ndarray, np.ndarray]:
        p = self.p
        s = np.zeros_like(self.t)
        v = np.zeros_like(self.t)
        target = self._stop_target()
        a = p.accel_m_s2
        si, vi = 0.0, 0.0
        for i, ti in enumerate(self.t):
            s[i], v[i] = si, vi
            if p.speed_m_s <= 0 or ti < p.t_go_s:
                continue
            if target is not None and (target - si) <= vi * vi / (2 * a) + 1e-9:
                acc = -a if vi > 0 else 0.0
            elif vi < p.speed_m_s:
                acc = a
            else:
                acc = 0.0
            vn = min(max(vi + acc * DT_PHYS, 0.0), p.speed_m_s)
            if target is not None and acc < 0 and vn <= 0.0:
                vn = 0.0
            si += 0.5 * (vi + vn) * DT_PHYS
            vi = vn
        return s, v

    # ---------------------------------------------------------------- return scenarios: 2-D path
    def _return_path(self) -> dict:
        """Teardrop turnaround (module docstring). Path length sigma: straight to x_turn, right arc R*beta, left arc
        R*(pi + beta), then straight back along -X on the return lane to x_stop."""
        p = self.p
        far0 = float(self.far_w(p.t_go_s))
        r = p.turn_radius_m
        beta = math.acos(p.return_lane_m / (2.0 * r))
        x_turn = far0 + p.turn_after_far_m
        x_back = x_turn + 2.0 * r * math.sin(beta)
        x_stop = far0 + p.stop_after_far_m
        sig_ts = x_turn
        sig_te = sig_ts + r * beta + r * (math.pi + beta)
        sig_stop = sig_te + (x_back - x_stop)
        if x_back - x_stop < p.turn_speed_m_s ** 2 / (2.0 * p.brake_m_s2) + 1.0:
            raise ValueError("return leg too short to brake: turn_after_far_m - stop_after_far_m too small")
        return {"far_edge_x_at_t_go": far0, "radius_m": r, "beta_rad": beta, "x_turn": x_turn, "x_back": x_back,
                "y_return": 2.0 * r * math.cos(beta), "x_stop": x_stop, "sig_ts": sig_ts, "sig_te": sig_te,
                "sig_stop": sig_stop}

    def _pose_at(self, sig: float) -> Tuple[float, float, float]:
        """(X, Y, psi [rad, counter-clockwise from +X]) at path length sig."""
        g = self.path
        r, beta, xt = g["radius_m"], g["beta_rad"], g["x_turn"]
        if sig <= g["sig_ts"]:
            return sig, 0.0, 0.0
        d = sig - g["sig_ts"]
        if d <= r * beta:                                       # right arc, centre (xt, -r)
            phi = d / r
            return xt + r * math.sin(phi), -r + r * math.cos(phi), -phi
        d -= r * beta
        if d <= r * (math.pi + beta):                           # left arc, centre (xt + 2r sin b, -r + 2r cos b)
            psi = -beta + d / r
            cx, cy = xt + 2.0 * r * math.sin(beta), -r + 2.0 * r * math.cos(beta)
            return cx + r * math.sin(psi), cy - r * math.cos(psi), psi
        d -= r * (math.pi + beta)
        return g["x_back"] - d, g["y_return"], math.pi

    def _motion_path(self) -> Tuple[np.ndarray, np.ndarray]:
        """Speed along the path: accelerate at accel_m_s2 up to speed_m_s, brake at brake_m_s2 to turn_speed_m_s
        before the turn, hold it through the turn and the return leg, brake to a stop at x_stop."""
        p, g = self.p, self.path
        sig = np.zeros_like(self.t)
        v = np.zeros_like(self.t)
        si, vi = 0.0, 0.0
        b, vt = p.brake_m_s2, p.turn_speed_m_s
        for i, ti in enumerate(self.t):
            sig[i], v[i] = si, vi
            if p.speed_m_s <= 0 or ti < p.t_go_s:
                continue
            if si >= g["sig_stop"] - 1e-4:
                si, vi = g["sig_stop"], 0.0
                continue
            env = p.speed_m_s
            if si < g["sig_ts"]:
                env = min(env, math.sqrt(vt * vt + 2.0 * b * (g["sig_ts"] - si)))
            else:
                env = min(env, vt)
            env = min(env, math.sqrt(2.0 * b * max(g["sig_stop"] - si, 0.0)))
            vn = max(min(vi + p.accel_m_s2 * DT_PHYS, env), 0.0)
            si = min(si + 0.5 * (vi + vn) * DT_PHYS, g["sig_stop"])
            vi = vn
        return sig, v

    def _check_return(self) -> None:
        """The flame model is 1-D along the outbound road: it must be out before the vehicle leaves the road axis,
        and the vehicle must have crossed it while it burned."""
        p = self.p
        on = np.array([self.flame_present(float(ti)) for ti in self.t])
        off_axis = (np.abs(self.psi) > 1e-12) | (np.abs(self.y) > 1e-12)
        if np.any(on & off_axis):
            raise ValueError("flame_out_s must be before the turn starts (the flame model is 1-D)")
        if p.flame_out_s is not None:
            k = int(np.searchsorted(self.t, p.flame_out_s))
            if k < self.t.size and self.s[k] <= float(self.far_w(p.flame_out_s)):
                raise ValueError("flame_out_s must be after the vehicle has crossed the flame")

    def times(self) -> dict:
        """Return scenarios: first times (s) the turn starts / ends and the vehicle stops (None if not reached)."""
        g = self.path

        def first(mask):
            k = np.flatnonzero(mask)
            return round(float(self.t[k[0]]), 3) if k.size else None
        return {"t_turn_start_s": first(self.sig > g["sig_ts"]), "t_turn_end_s": first(self.sig >= g["sig_te"]),
                "t_stop_s": first(self.sig >= g["sig_stop"] - 1e-4)}

    def pose(self, t: float) -> Tuple[float, float, float, float]:
        """(X, Y, psi [rad], speed) at time t (return scenarios; X along the road, Y = 0, psi = 0 otherwise)."""
        x, v = self.pos(t)
        if not self.two_d:
            return float(x), 0.0, 0.0, float(v)
        return (float(x), float(np.interp(t, self.t, self.y)), float(np.interp(t, self.t, self.psi)), float(v))

    def pos(self, t) -> Tuple[np.ndarray, np.ndarray]:
        return np.interp(t, self.t, self.s), np.interp(t, self.t, self.v)

    def vib_pitch_deg(self, t: float) -> float:
        """Suspension pitch vibration while driving (deterministic, +-0.3 deg at 5 m/s)."""
        _, v = self.pos(t)
        return float(0.06 * v * math.sin(2 * math.pi * 1.7 * t) * min(1.0, v))

    def attitude(self, t: float) -> Tuple[float, float]:
        """True body (pitch, roll) in degrees. Return scenarios: the 4 % grade is along world X, so pitch =
        atan(grade cos psi) and roll = roll - atan(grade sin psi) (+ right side down)."""
        if self.two_d:
            psi = float(np.interp(t, self.t, self.psi))
            return (math.degrees(math.atan(self.p.grade * math.cos(psi))) + self.vib_pitch_deg(t),
                    self.p.roll_deg - math.degrees(math.atan(self.p.grade * math.sin(psi))))
        return math.degrees(math.atan(self.p.grade)) + self.vib_pitch_deg(t), self.p.roll_deg

    # ---------------------------------------------------------------- truth series
    def flux_and_air(self):
        """True incident flux at the plate q [kW/m2], true air temperature at the probe and the probe's lagged
        value [C], on the physics grid."""
        p = self.p
        t, s = self.t, self.s
        q = np.zeros_like(t)
        air = np.full_like(t, p.ambient_c)
        if self.flame:
            on = t >= p.onset_s
            if p.flame_out_s is not None:
                on = on & (t < p.flame_out_s)
            xn = self.near_w(t) - s
            xf = self.far_w(t) - s
            inside = on & (xn <= 0) & (xf >= 0)
            ahead = on & (xn > 0)
            sd = np.where(ahead, xn, 1.0)
            zp = p.plate_height_m - p.grade * sd             # plate height above the ground at the flame front
            f = 0.5 * (np.sin(np.arctan2(p.height_m - zp, sd)) - np.sin(np.arctan2(-zp, sd)))
            q = np.where(ahead, p.flame_ep_kw_m2 * f, q)
            q = np.where(inside, p.q_in_kw_m2, q)
            air = np.where(inside, p.air_in_flame_c, air)
            near = ahead & (xn < 4.0)
            air = np.where(near, air + 8.0 * (1.0 - xn / 4.0), air)
        for i, ti in enumerate(t):
            if self.out_decay(ti) is not None:
                q[i], air[i] = self._flux_air_after_out(i)
                continue
            bz = self.burnt_zone(ti)
            if bz is None:
                continue
            x0, x1, t0c, t1c = bz
            xr0 = x0 - s[i]
            xr1 = x1 - s[i]
            if xr0 <= 0 <= xr1:
                air[i] += 10.0
            if -1.0 <= xr0 <= 5.0 or (xr0 <= 0 <= xr1):
                tb = t0c + C_TO_K
                ta = p.ambient_c + C_TO_K
                q[i] += 0.25 * SIGMA * (tb ** 4 - ta ** 4) / 1000.0
        tau = 1.5
        air_s = np.empty_like(air)
        a = p.ambient_c
        for i in range(len(t)):
            a += (air[i] - a) * DT_PHYS / tau
            air_s[i] = a
        return q, air, air_s

    def _flux_air_after_out(self, i: int) -> Tuple[float, float]:
        """Return scenarios after burn-out, physics index i: (true incident flux at the plate [kW/m2], true air
        temperature [C]). Over the burnt strip: 0.25 * sigma * (Tg^4 - Ta^4) from the (cooling) ground under the
        vehicle and the air probe + 10 C * decay. The hot spot (crossing_return_hot) adds eps * sigma * (Th^4 - Ta^4)
        * F, F = A cos(t_plate) cos(t_spot) / (pi r^2) (small flat patch to the vertical, forward-facing plate)."""
        p = self.p
        ti = float(self.t[i])
        x, y, psi = float(self.s[i]), float(self.y[i]), float(self.psi[i])
        dec = self.out_decay(ti)
        ta = p.ambient_c + C_TO_K
        xn, _, xe = self.strip_at_out()
        q, air = 0.0, p.ambient_c
        if xn <= x <= xe:
            tg = float(self.ground_k_2d(ti, np.array([x]), np.array([y]))[0])
            q += 0.25 * SIGMA * max(tg ** 4 - ta ** 4, 0.0) / 1000.0
            air += 10.0 * dec
        hs = self.hot_spot()
        if hs is not None:
            xc, yc, ln, wd, tc = hs
            dx, dy = xc - x, yc - y
            dz = p.grade * dx - p.plate_height_m
            r = math.sqrt(dx * dx + dy * dy + dz * dz)
            c_plate = (dx * math.cos(psi) + dy * math.sin(psi)) / r
            c_spot = -dz / r
            if c_plate > 0 and c_spot > 0:
                f = ln * wd * c_plate * c_spot / (math.pi * r * r)
                q += 0.95 * SIGMA * ((tc + C_TO_K) ** 4 - ta ** 4) * f / 1000.0
        return q, air

    def plate(self, q: np.ndarray, ta_c: np.ndarray) -> np.ndarray:
        """Plate temperature [C] by RK4 on rho*cp*d*dT/dt = alpha*q - h*(T-Ta) - eps*sigma*(T^4-Ta^4)."""
        rcd = 8960.0 * 385.0 * 0.001
        alpha, eps, h = 0.95, 0.95, 10.0
        out = np.empty_like(q)
        tk = self.p.ambient_c + C_TO_K

        def f(tp, qq, ta):
            return (alpha * qq * 1000.0 - h * (tp - ta) - eps * SIGMA * (tp ** 4 - ta ** 4)) / rcd

        for i in range(len(q)):
            out[i] = tk - C_TO_K
            if i + 1 == len(q):
                break
            ta0, ta1 = ta_c[i] + C_TO_K, ta_c[i + 1] + C_TO_K
            q0, q1 = q[i], q[i + 1]
            qm, tam = 0.5 * (q0 + q1), 0.5 * (ta0 + ta1)
            k1 = f(tk, q0, ta0)
            k2 = f(tk + 0.5 * DT_PHYS * k1, qm, tam)
            k3 = f(tk + 0.5 * DT_PHYS * k2, qm, tam)
            k4 = f(tk + DT_PHYS * k3, q1, ta1)
            tk += DT_PHYS * (k1 + 2 * k2 + 2 * k3 + k4) / 6.0
        return out

    def housing(self, q: np.ndarray) -> np.ndarray:
        p = self.p
        out = np.empty_like(q)
        th = p.ambient_c + 9.0
        for i, ti in enumerate(self.t):
            teq = p.ambient_c + 9.0 + ti / 600.0 + 0.05 * q[i]
            th += (teq - th) * DT_PHYS / 300.0
            out[i] = th
        return out


# ================================================================================================ thermal

class ThermalRenderer:
    """Ray-traced TC001 frames (see module docstring). Returns apparent temperature in K, [192, 256]."""

    W, H = 256, 192
    HFOV, VFOV = 56.0, 42.0

    def __init__(self, p: Params, scene: Scene, rng: np.random.Generator):
        self.p, self.scene, self.rng = p, scene, rng
        self.cx, self.cy = (self.W - 1) / 2.0, (self.H - 1) / 2.0
        self.fx = (self.W / 2.0) / math.tan(math.radians(self.HFOV) / 2.0)
        self.fy = (self.H / 2.0) / math.tan(math.radians(self.VFOV) / 2.0)
        jj, ii = np.meshgrid(np.arange(self.W, dtype=float), np.arange(self.H, dtype=float))
        self.v_cam = np.stack([np.ones(ii.size), -(jj.ravel() - self.cx) / self.fx, -(ii.ravel() - self.cy) / self.fy])
        self.mount = (_rot_yaw_right(p.mount_yaw_deg) @ _rot_pitch_up(p.mount_pitch_deg)
                      @ _rot_roll_right_down(p.mount_roll_deg))
        self.col = jj.ravel().astype(int)
        self.row = ii.ravel().astype(int)
        self.drift = 0.0
        self.offset_counts = 0
        lo, hi = GAIN_RANGE_C[p.gain]
        self.clip_k = (lo + C_TO_K, hi + C_TO_K)

    def rays(self, pitch: float, roll: float) -> np.ndarray:
        r = _rot_pitch_up(pitch) @ _rot_roll_right_down(roll) @ self.mount @ self.v_cam
        return r / np.linalg.norm(r, axis=0)

    @staticmethod
    def _slab(c, H, c_path, x0, x1, z_lo, z_hi, x_stop):
        """Entry x and path length of the ray (height above ground H + c*x) inside x0..x1, z_lo..z_hi.
        The path length is taken in the vertical along-course plane (c_path = vertical slope of the ray):
        the lateral obliquity of off-axis rays is ignored (at most 1/cos(28 deg) = +13 % at the image edge)."""
        cs = np.where(np.abs(c) < 1e-12, 1e-12, c)
        a_lo = (z_lo - H) / cs
        a_hi = (z_hi - H) / cs
        pos = cs > 0
        lo = np.maximum.reduce([np.full_like(c, max(x0, 1e-3)), np.where(pos, a_lo, a_hi)])
        hi = np.minimum.reduce([np.full_like(c, x1), np.where(pos, a_hi, a_lo), x_stop])
        dx = np.maximum(hi - lo, 0.0)
        return np.where(dx > 0, lo, np.inf), dx * np.sqrt(1.0 + c_path * c_path)

    def render(self, t: float) -> np.ndarray:
        p, sc = self.p, self.scene
        if sc.out_decay(t) is not None:
            return self._render_2d(t)
        pitch, roll = sc.attitude(t)
        u = self.rays(pitch, roll)
        ux = np.maximum(u[0], 1e-9)
        k = u[2] / ux
        m = u[1] / ux
        H = p.cam_height_m
        g = p.grade
        c = k - g
        s_v, _ = sc.pos(t)
        s_v = float(s_v)
        fwd = u[0] > 1e-6
        x_max = 400.0
        x_g = np.where(fwd & (c < 0), H / np.where(c < 0, -c, 1.0), np.inf)
        x_g = np.where(x_g > x_max, np.inf, x_g)
        amb = p.ambient_c + C_TO_K

        # -------- background: sky / ground / boxes
        elev = np.arctan(k)                      # vertical slope of the ray in the along-course plane
        t_sky = 240.0 + 45.0 * np.exp(-np.maximum(elev, 0.0) / 0.12)
        xg_f = np.where(np.isfinite(x_g), x_g, 0.0)
        yg = m * xg_f
        xw = xg_f + s_v
        t_gnd = np.where(np.abs(yg) < 3.5, amb + 8.0, amb + 2.0)
        bz = sc.burnt_zone(t)
        if bz is not None:
            x0, x1, t0c, t1c = bz
            inb = (xw >= x0) & (xw <= x1)
            frac = np.clip((xw - x0) / max(x1 - x0, 1e-6), 0.0, 1.0)
            t_gnd = np.where(inb, (t0c + (t1c - t0c) * frac) + C_TO_K, t_gnd)
        flame_on = sc.flame_present(t)
        if flame_on:
            xn_w, xf_w = float(sc.near_w(t)), float(sc.far_w(t))
            bed = (xw >= xn_w) & (xw <= xf_w)
            t_gnd = np.where(bed, 700.0 + C_TO_K, t_gnd)
        # haze towards the horizon
        hz = np.clip(xg_f / 300.0, 0.0, 1.0)
        t_gnd = (1 - hz) * t_gnd + hz * (amb - 10.0)
        b_bg = np.where(np.isfinite(x_g), planck(t_gnd), planck(t_sky))
        x_bg = np.where(np.isfinite(x_g), x_g, np.inf)
        for box in self._boxes(t):
            bx0, by, bw, bz0, bz1, btk = box
            xo = bx0 - s_v
            if xo <= 0.2:
                continue
            fh = H + c * xo
            hit = fwd & (xo < x_bg) & (fh >= bz0) & (fh <= bz1) & (np.abs(m * xo - by) <= bw / 2.0)
            b_bg = np.where(hit, planck(btk), b_bg)
            x_bg = np.where(hit, xo, x_bg)

        # -------- participating volumes
        vols = self._volumes(t, s_v)
        if vols:
            entries, epss, bvs = [], [], []
            for x0, x1, z_lo, z_hi, kappa, tvol in vols:
                ent, path = self._slab(c, H, k, x0, x1, z_lo, z_hi, x_bg)
                ent = np.where(fwd, ent, np.inf)
                path = np.where(fwd, path, 0.0)
                entries.append(ent)
                epss.append(1.0 - np.exp(-kappa * path))
                bvs.append(planck(tvol) * np.ones_like(c))
            E = np.stack(entries)
            EP = np.stack(epss)
            BV = np.stack(bvs)
            order = np.argsort(-np.where(np.isfinite(E), E, -1.0), axis=0)    # far to near
            b = b_bg
            for rnk in range(E.shape[0]):
                idx = order[rnk][None, :]
                ep = np.take_along_axis(EP, idx, axis=0)[0]
                bv = np.take_along_axis(BV, idx, axis=0)[0]
                b = ep * bv + (1.0 - ep) * b
        else:
            b = b_bg
        return self._sensor(inv_planck(b), t)

    def _render_2d(self, t: float) -> np.ndarray:
        """Return scenarios after burn-out (the flame is out, so the scene is ground and sky only): rays in the
        vehicle-level frame turned to world X/Y with the heading psi, hit on the ground plane z = grade * X."""
        p, sc = self.p, self.scene
        x_v, y_v, psi, _ = sc.pose(t)
        pitch, roll = sc.attitude(t)
        u = self.rays(pitch, roll)
        cps, sps = math.cos(psi), math.sin(psi)
        dxw = u[0] * cps - u[1] * sps
        dyw = u[0] * sps + u[1] * cps
        H = p.cam_height_m
        den = p.grade * dxw - u[2]
        fwd = u[0] > 1e-6
        tt = np.where(fwd & (den > 1e-12), H / np.where(den > 1e-12, den, 1.0), np.inf)
        tt = np.where(tt * np.maximum(u[0], 0.0) > 400.0, np.inf, tt)
        hit = np.isfinite(tt)
        t0 = np.where(hit, tt, 0.0)
        amb = p.ambient_c + C_TO_K
        t_gnd = sc.ground_k_2d(t, x_v + dxw * t0, y_v + dyw * t0)
        hz = np.clip(t0 * u[0] / 300.0, 0.0, 1.0)
        t_gnd = (1 - hz) * t_gnd + hz * (amb - 10.0)
        elev = np.arctan(u[2] / np.maximum(u[0], 1e-9))
        t_sky = 240.0 + 45.0 * np.exp(-np.maximum(elev, 0.0) / 0.12)
        b = np.where(hit, planck(t_gnd), planck(t_sky))
        return self._sensor(inv_planck(b), t)

    def _sensor(self, temps: np.ndarray, t: float) -> np.ndarray:
        p = self.p
        if p.scene_quant_k > 0:                  # compact samples: scene in steps, noise added after
            temps = np.round(temps / p.scene_quant_k) * p.scene_quant_k

        # -------- sensor: drift, row banding, pixel noise, gain clip
        img = temps.reshape(self.H, self.W)
        if not p.offset_walk:
            self.drift = 0.98 * self.drift + self.rng.normal(0.0, 0.01)
            img = img + self.drift + 0.05 * math.sin(2 * math.pi * t / 37.0)
        if p.row_noise_k > 0:
            img = img + self.rng.normal(0.0, p.row_noise_k, size=(self.H, 1))
        if p.pixel_noise_k > 0:
            img = img + self.rng.normal(0.0, p.pixel_noise_k, size=img.shape)
        if p.offset_walk:
            # compact samples: instead of the drift, a whole-frame offset random walk of 1-2 raw counts (1/64 K) per
            # frame, reflected at +-20 counts, so that no two consecutive frames are identical (a real camera's noise
            # guarantees that) while the files stay small
            step = int(self.rng.integers(1, 3)) * (1 if self.rng.random() < 0.5 else -1)
            if abs(self.offset_counts + step) > 20:
                step = -step
            self.offset_counts += step
            img = img + self.offset_counts / protocol.RAW_PER_K
        return np.clip(img, *self.clip_k)

    def _boxes(self, t: float):
        """(x_world, y, width_y, z_lo, z_hi above ground, T [K]) front faces."""
        p, sc = self.p, self.scene
        out = []
        if p.scenario not in RETURN_SCENARIOS:        # no parked vehicle on the return path
            xo = solid_object_x(p)
            out.append((xo, -0.5, 2.0, 0.0, 1.6, p.ambient_c + 10.0 + C_TO_K))
        if sc.reflector:
            zc = p.radar_height_m - p.grade * p.range_m
            out.append((p.range_m, 0.0, 0.3, zc - 0.15, zc + 0.15, 5.0 + C_TO_K))
        return out

    def _volumes(self, t: float, s_v: float):
        """Participating slabs in vehicle-relative x: (x0, x1, z_lo, z_hi, kappa [1/m], T [K] scalar or array)."""
        p, sc = self.p, self.scene
        vols = []
        if sc.flame_present(t):
            xn = float(sc.near_w(t)) - s_v
            xf = float(sc.far_w(t)) - s_v
            fr = int(round(t * p.thermal_hz))
            rng = np.random.default_rng([p.seed, 7, fr])
            nbc = self.W // 8 + 1
            hfac = np.clip(1.0 + 0.15 * rng.normal(size=nbc), 0.6, 1.4)
            z_hi = p.height_m * hfac[self.col // 8]
            tg = p.flame_gas_c + 80.0 * rng.normal(size=(self.H // 16 + 1, self.W // 16 + 1))
            tgas = tg[self.row // 16, self.col // 16] + C_TO_K
            vols.append((xn, xf, 0.0, z_hi, p.flame_kappa, tgas))
            vols.append((xn, xf + 6.0, p.height_m * 1.4, p.height_m * 1.4 + 10.0, 0.03, 70.0 + C_TO_K))
        if sc.smoke_only and t >= p.onset_s:
            vols.append((p.range_m - s_v, p.range_m + p.depth_m - s_v, 0.0, p.height_m, 0.04, 75.0 + C_TO_K))
        if sc.mist and t >= p.onset_s:
            vols.append((p.range_m - s_v, p.range_m + p.depth_m - s_v, 0.0, p.height_m, 0.15,
                         p.ambient_c - 6.0 + C_TO_K))
        if sc.after:
            vols.append((p.range_m - s_v, p.range_m + p.depth_m - s_v, 0.0, 4.0, 0.01, 45.0 + C_TO_K))
        return vols


def solid_object_x(p: Params) -> float:
    """World x of the solid object (parked vehicle / guardrail end) used as the echo beyond the flame."""
    max_r = p.n_bins * p.range_res_m
    if p.scenario in FLAME_SCENARIOS:
        x = p.range_m + p.depth_m + 4.0
    else:
        x = 19.0
    return float(min(x, max_r - 1.5))


# ================================================================================================ radar

class RadarSim:
    """Synthetic IWR6843 heatmap / range profile / points (see module docstring)."""

    def __init__(self, p: Params, scene: Scene, rng: np.random.Generator):
        self.p, self.scene, self.rng = p, scene, rng
        crng = np.random.default_rng([p.seed, 11])            # static scene, independent of overlays and duration
        max_r = p.n_bins * p.range_res_m
        n = 400
        xs = crng.uniform(1.0, max_r + 5.0, n)
        ys = crng.uniform(-8.0, 8.0, n)
        amp = (crng.normal(size=n) + 1j * crng.normal(size=n)) / math.sqrt(2)
        amp *= 10 ** (15.0 / 20.0)                              # 15 dB per scatterer at the 5 m reference
        # (x_world, y, z above ground, complex amp, ref range, range exponent, kind)
        self.sc_x = xs
        self.sc_y = ys
        self.sc_z = np.zeros(n)
        self.sc_amp = amp
        self.sc_rref = np.full(n, 5.0)
        self.sc_exp = np.full(n, 1.5)
        self.sc_disc = np.zeros(n, bool)
        self.targets: List[dict] = []
        self._add_target("sign_post", 7.0, 2.5, 1.5, 22.0, crng)
        if p.scenario not in RETURN_SCENARIOS:        # no parked vehicle on the return path
            self._add_target("solid_object", solid_object_x(p), -0.5, 0.8, 35.0, crng)
        if scene.reflector:
            self._add_target("corner_reflector", p.range_m, 0.0, p.radar_height_m - p.grade * p.range_m, 50.0, crng)
        self.psi = 0.0
        self.on = True
        self.frame_no = 0
        k = np.arange(-2, 3)
        self._k = k

    def _add_target(self, kind, x, y, z, snr_db, crng):
        p = self.p
        r0 = self._slant(x, y, z, 0.0)
        self.sc_x = np.append(self.sc_x, x)
        self.sc_y = np.append(self.sc_y, y)
        self.sc_z = np.append(self.sc_z, z)
        amp = 10 ** (snr_db / 20.0) * np.exp(1j * crng.uniform(-math.pi, math.pi))
        self.sc_amp = np.append(self.sc_amp, amp)
        self.sc_rref = np.append(self.sc_rref, r0)
        self.sc_exp = np.append(self.sc_exp, 2.0)
        self.sc_disc = np.append(self.sc_disc, True)
        self.targets.append({"kind": kind, "x_world_m": float(x), "y_m": float(y), "z_above_ground_m": float(z),
                             "range_at_t0_m": round(float(r0), 3),
                             "bearing_at_t0_deg": round(math.degrees(math.atan2(-y, x)), 2),
                             "snr_db_at_t0": snr_db, "index": len(self.sc_x) - 1})

    def _slant(self, x, y, z, s_v):
        p = self.p
        dx = np.asarray(x) - s_v
        zs = p.grade * dx + np.asarray(z)
        return np.sqrt(dx ** 2 + np.asarray(y) ** 2 + (zs - p.radar_height_m) ** 2)

    def _flame_path(self, dx, y, zs, xn, xf, h):
        """Horizontal path length (m) of each line of sight radar -> scatterer inside the flame volume."""
        p = self.p
        hr = p.radar_height_m
        # height above ground along the LOS: f(x) = hr + (zs - hr) * x / dx - grade * x
        c = (zs - hr) / np.maximum(dx, 1e-6) - p.grade
        cs = np.where(np.abs(c) < 1e-12, 1e-12, c)
        a0 = (0.0 - hr) / cs
        a1 = (h - hr) / cs
        pos = cs > 0
        lo = np.maximum.reduce([np.full_like(dx, max(xn, 0.0)), np.where(pos, a0, a1)])
        hi = np.minimum.reduce([np.full_like(dx, xf), np.where(pos, a1, a0), dx])
        return np.maximum(hi - lo, 0.0)

    def frame(self, t: float) -> dict:
        p, sc, rng = self.p, self.scene, self.rng
        s_v, v_v = sc.pos(t)
        s_v, v_v = float(s_v), float(v_v)
        if sc.two_d:
            # return scenarios: scatterers in the vehicle frame at heading psi (x forward, y left); the ground height
            # follows world X. While the flame burns the vehicle is on the road axis (psi = 0, Y = 0).
            _, y_v, psi, _ = sc.pose(t)
            dxw, dyw = self.sc_x - s_v, self.sc_y - y_v
            dx = dxw * math.cos(psi) + dyw * math.sin(psi)
            sc_y = -dxw * math.sin(psi) + dyw * math.cos(psi)
            zs = p.grade * dxw + self.sc_z
        else:
            dx = self.sc_x - s_v
            sc_y = self.sc_y
            zs = p.grade * dx + self.sc_z
        r = np.sqrt(dx ** 2 + sc_y ** 2 + (zs - p.radar_height_m) ** 2)
        az = np.arctan2(-sc_y, np.maximum(dx, 1e-6))
        el = np.arcsin(np.clip((zs - p.radar_height_m) / np.maximum(r, 1e-6), -1, 1))
        vis = (dx > 0.3) & (np.abs(az) < math.radians(70)) & (r < (p.n_bins + 2) * p.range_res_m)
        amp = self.sc_amp * (self.sc_rref / np.maximum(r, 0.3)) ** self.sc_exp * np.cos(az) ** 2
        jitter = rng.normal(0.0, 0.03)
        gain = np.ones(r.size, complex)
        # ---- flame effect (assumed)
        flame_info = {"on": False}
        if sc.flame_present(t):
            if self.on and rng.random() < (1 - p.flame_on_frac) * 0.5:
                self.on = False
            elif not self.on and rng.random() < p.flame_on_frac * 0.5:
                self.on = True
            xn = float(sc.near_w(t)) - s_v
            xf = float(sc.far_w(t)) - s_v
            L = self._flame_path(dx, sc_y, zs, xn, xf, p.height_m)
            if self.on:
                self.psi += rng.normal(0.0, p.phase_step_rad)
                ldb = max(p.flame_loss_db * (1.0 + 0.3 * rng.normal()), 0.0)
                w = np.clip(L / max(p.depth_m, 0.5), 0.0, 1.0)
                wp = np.clip(L / 0.5, 0.0, 1.0)
                gain = np.where(L > 0, 10 ** (-ldb * w / 20.0) * np.exp(1j * self.psi * wp), gain)
            flame_info = {"on": bool(self.on), "psi": self.psi}
        elif sc.mist and t >= p.onset_s:
            behind = dx > (p.range_m - s_v)
            ldb = p.mist_loss_db + rng.normal(0.0, 0.35)
            gain = np.where(behind, 10 ** (-ldb / 20.0), gain)
        # ---- assemble the heatmap
        nb, na = p.n_bins, p.n_ant
        ant = np.arange(na)
        echo = amp * gain * np.exp(1j * (4 * math.pi * r / LAMBDA_M + jitter))
        echo = np.where(vis, echo, 0.0)
        steer = np.exp(1j * math.pi * np.outer(np.sin(az), ant))           # [targets, ant], positions n*lambda/2
        rb = r / p.range_res_m
        b0 = np.round(rb).astype(int)
        x = np.zeros((nb, na), complex)
        for dk in self._k:
            bins = b0 + dk
            off = bins - rb
            ker = np.sinc(off) * 0.5 * (1 + np.cos(np.pi * np.clip(off, -3, 3) / 3.0))
            ok = vis & (bins >= 0) & (bins < nb)
            np.add.at(x, bins[ok], (echo[ok] * ker[ok])[:, None] * steer[ok])
        x[0:3, :] += 10 ** (40.0 / 20.0) * np.array([1.0, 0.4, 0.1])[:, None] * np.exp(1j * 0.3)   # TX/RX leakage
        x += (rng.normal(size=(nb, na)) + 1j * rng.normal(size=(nb, na))) / math.sqrt(2)
        counts = x * (p.iq_noise_counts * math.sqrt(2))
        prof = 10 * np.log10(np.sum(np.abs(x) ** 2, axis=1) + 1e-12) + 30.0
        # ---- points: discrete targets with SNR > 12 dB in this frame
        pts = []
        for tg in self.targets:
            i = tg["index"]
            if not vis[i]:
                continue
            snr = 20 * math.log10(abs(amp[i] * gain[i]) + 1e-12) + 10 * math.log10(na)
            if snr <= 12.0:
                continue
            ri, ai, ei = float(r[i]), float(az[i]), float(el[i])
            pts.append([round(ri * math.cos(ei) * math.sin(ai), 2), round(ri * math.cos(ei) * math.cos(ai), 2),
                        round(ri * math.sin(ei), 2), round(-v_v * math.cos(ai) * math.cos(ei), 2), round(snr, 1)])
        data = {"frame": self.frame_no + 1, "range_res_m": p.range_res_m, "n_bins": nb,
                "range_profile_db": [round(round(float(v) / p.profile_step_db) * p.profile_step_db, 2) for v in prof],
                "az_heatmap": encode_iq_compact(counts),
                "points": pts, "tlv_types": [1, 2, 4, 7], "frame_ok": True}
        self.frame_no += 1
        return data


# ================================================================================================ generation

def _times(rate_hz: float, duration: float, rng: np.random.Generator, offset: float) -> np.ndarray:
    n = int(math.floor((duration - offset) * rate_hz)) + 1
    t = offset + np.arange(max(n, 0)) / rate_hz
    t = t + rng.uniform(-0.002, 0.002, size=t.size)          # driver timing jitter
    t = t[(t >= 0) & (t <= duration)]
    return np.round(t, 4)


def _latlon(p: Params, x_m, d_north_m=0.0, d_east_m=0.0):
    """Along-course distance x (m) from (lat0, lon0), plus north/east offsets (m) -> (lat, lon) degrees.
    Local WGS84 radii of curvature at lat0 (meridian M, prime vertical N); fine over a few km."""
    phi = math.radians(p.lat0)
    s2 = math.sin(phi) ** 2
    m_rad = WGS84_A * (1 - WGS84_E2) / (1 - WGS84_E2 * s2) ** 1.5
    n_rad = WGS84_A / math.sqrt(1 - WGS84_E2 * s2)
    c = math.radians(p.course_deg)
    north = np.asarray(x_m, dtype=float) * math.cos(c) + d_north_m
    east = np.asarray(x_m, dtype=float) * math.sin(c) + d_east_m
    return p.lat0 + np.degrees(north / m_rad), p.lon0 + np.degrees(east / (n_rad * math.cos(phi)))


class _Gen:
    def __init__(self, p: Params):
        self.p = p
        self.scene = Scene(p)
        self.t_epoch0 = _epoch(p.start_utc)
        self.session_id = "%s-%s-synth-%s-s%d" % (
            p.unit_id, datetime.fromtimestamp(self.t_epoch0, tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            p.scenario.replace("_", "-"), p.seed)
        for o in p.overlays:                                  # distinct ids for overlay variants
            self.session_id += "-%s-%s%g%s" % (o["kind"], o["sensor"].replace("_", ""), o["t_s"],
                                               ("-" + o["fault"].replace("_", "")) if o.get("fault") else "")
        self.ctx = protocol.Context(p.unit_id, self.session_id, sim=True)
        self.q, self.air_true, self.air_s = self.scene.flux_and_air()
        self.plate = self.scene.plate(self.q, self.air_s)
        self.house = self.scene.housing(self.q)

    def rng(self, sensor: str) -> np.random.Generator:
        return np.random.default_rng([self.p.seed, protocol.SENSORS.index(sensor) + 1])

    def at(self, series: np.ndarray, t: float) -> float:
        return float(np.interp(t, self.scene.t, series))

    def utc(self, t: float) -> str:
        return protocol.utc_now_iso(self.t_epoch0 + t)

    def latlon_xy(self, x: float, y: float) -> Tuple[float, float]:
        """World (X along the outbound course, Y to its left) in m -> (lat, lon) degrees (no GNSS error)."""
        c = math.radians(self.p.course_deg)
        lat, lon = _latlon(self.p, x, y * math.sin(c), -y * math.cos(c))
        return float(lat), float(lon)

    def _truth_return(self, tr: dict) -> None:
        """truth blocks of the return scenarios: path, burn-out, hot spot, DEM, intended laptop reading."""
        p, sc = self.p, self.scene
        g = sc.path
        lat_s, lon_s = self.latlon_xy(g["x_stop"], g["y_return"])
        tr["return_path"] = dict(
            model="teardrop turnaround driven forward: straight to x_turn, right arc R through beta, left arc R through "
                  "180 deg + beta, straight back on the return lane, stop at x_stop facing back along the road",
            x_turn_m=round(g["x_turn"], 3), radius_m=g["radius_m"], beta_deg=round(math.degrees(g["beta_rad"]), 3),
            return_lane_y_m=round(g["y_return"], 3), x_back_m=round(g["x_back"], 3), x_stop_m=round(g["x_stop"], 3),
            stop_lat=round(lat_s, 7), stop_lon=round(lon_s, 7),
            heading_at_stop_deg=round((p.course_deg + 180.0) % 360.0, 3),
            far_edge_x_at_t_go_m=round(g["far_edge_x_at_t_go"], 3),
            stop_beyond_far_edge_m=p.stop_after_far_m, turn_speed_m_s=p.turn_speed_m_s,
            yaw_rate_deg_s=round(math.degrees(p.turn_speed_m_s / g["radius_m"]), 3), brake_m_s2=p.brake_m_s2,
            space_right_of_road_m=round(2.0 * g["radius_m"] - g["y_return"], 3), **sc.times())
        xn, xf, xe = sc.strip_at_out() if p.flame_out_s is not None else (None, None, None)
        tr["burn_out"] = {"flame_out_s": p.flame_out_s, "cool_tau_s": p.cool_tau_s,
                          "fuel_bed_world_m": [xn, xf], "burnt_zone_world_m": [xf, xe],
                          "model": "after flame_out_s the strip cools: T = T_unburnt + (T_at_out - T_unburnt) * "
                                   "exp(-(t - flame_out_s) / cool_tau_s); fuel bed 700 C, burnt zone 150 -> 50 C at "
                                   "burn-out (illustrative)"}
        hs = sc.hot_spot()
        tr["hot_spot"] = None if hs is None else {
            "x_centre_world_m": round(hs[0], 3), "y_centre_m": hs[1], "length_m": hs[2], "width_m": hs[3],
            "temp_c": hs[4], "from_s": p.flame_out_s, "kind": "flat hot area (burning debris / embers) on the road, "
            "left in the middle of the crossed strip; flame-temperature pixels (>= 300 C) in the camera"}
        tr["intended"] = {"flame_state_after_onset": "FLAME until flame_out_s", "first_solid_echo": None,
                          "dem": "pass %s to the laptop (--dem): REOPENED needs DEM line of sight" % DEM_FILE}
        if hs is None:
            tr["intended"]["verdict_after_stop"] = ("REOPENED once the vehicle has stopped facing the crossed road "
                                                    "and the quiet conditions held reopen_hold_s (if every other "
                                                    "condition holds)")
        else:
            tr["intended"]["verdict_after_stop"] = "never REOPENED (hot area over the crossing)"

    def dem_arrays(self) -> dict:
        """Return scenarios: the session's ground plane (alt0 + grade * X) as a crossing.terrain.Dem npz
        ("local-enu" about the start fix, cell-centre values, row 0 north). Covers the outbound road from 30 m
        behind the start to 30 m past the turnaround and the turnaround's space, with 20 m margins."""
        p, g = self.p, self.scene.path
        res = float(p.dem_res_m)
        r = g["radius_m"]
        xs = (-30.0, g["x_back"] + r + 30.0)
        ys = (g["y_return"] - 2.0 * r - 20.0, g["y_return"] + 20.0)
        c = math.radians(p.course_deg)
        corners = [(x * math.sin(c) - y * math.cos(c), x * math.cos(c) + y * math.sin(c)) for x in xs for y in ys]
        e0 = math.floor(min(q[0] for q in corners) / res) * res
        e1 = math.ceil(max(q[0] for q in corners) / res) * res
        n0 = math.floor(min(q[1] for q in corners) / res) * res
        n1 = math.ceil(max(q[1] for q in corners) / res) * res
        w, h = int(round((e1 - e0) / res)), int(round((n1 - n0) / res))
        east = e0 + (np.arange(w) + 0.5) * res                 # local-enu cell centres (sphere R = 6371008.8 m)
        north = n1 - (np.arange(h) + 0.5) * res
        ee, nn = np.meshgrid(east, north)
        r_sph = 6371008.8
        lat = p.lat0 + np.degrees(nn / r_sph)
        lon = p.lon0 + np.degrees(ee / (r_sph * math.cos(math.radians(p.lat0))))
        phi = math.radians(p.lat0)                             # back to this generator's WGS84 local frame
        s2 = math.sin(phi) ** 2
        m_rad = WGS84_A * (1 - WGS84_E2) / (1 - WGS84_E2 * s2) ** 1.5
        n_rad = WGS84_A / math.sqrt(1 - WGS84_E2 * s2)
        n_s = np.radians(lat - p.lat0) * m_rad
        e_s = np.radians(lon - p.lon0) * n_rad * math.cos(phi)
        x_w = n_s * math.cos(c) + e_s * math.sin(c)
        z = (p.alt0_m + p.grade * x_w).astype(np.float32)
        return {"z": z, "x0": np.float64(e0), "y_top": np.float64(n1), "res": np.float64(res),
                "crs": np.array("local-enu"), "lat0": np.float64(p.lat0), "lon0": np.float64(p.lon0)}

    # ---------------------------------------------------------------- per-sensor readings: list of (t, data)
    def thermal(self) -> List[Tuple[float, dict]]:
        rng = self.rng("thermal")
        rend = ThermalRenderer(self.p, self.scene, rng)
        out = []
        for t in _times(self.p.thermal_hz, self.p.duration_s, rng, 0.05):
            out.append((float(t), encode_thermal_compact(rend.render(float(t)), self.p.gain)))
        return out

    def radar(self) -> List[Tuple[float, dict]]:
        rng = self.rng("radar")
        sim = RadarSim(self.p, self.scene, rng)
        self.radar_targets = sim.targets
        return [(float(t), sim.frame(float(t))) for t in _times(self.p.radar_hz, self.p.duration_s, rng, 0.07)]

    def tc(self, sensor: str) -> List[Tuple[float, dict]]:
        rng = self.rng(sensor)
        series = {"tc_plate": self.plate, "tc_air": self.air_s, "tc_housing": self.house}[sensor]
        off = {"tc_plate": 0.01, "tc_housing": 0.03, "tc_air": 0.05}[sensor]
        out = []
        for t in _times(self.p.tc_hz, self.p.duration_s, rng, off):
            v = self.at(series, t) + rng.normal(0.0, 0.1)
            cj = self.at(self.house, t) + 1.5 + rng.normal(0.0, 0.03)
            out.append((float(t), {"temp_c": _q(v, 0.25), "cj_c": _q(cj, 0.0625), "fault": None}))
        return out

    def imu(self) -> List[Tuple[float, dict]]:
        rng = self.rng("imu")
        out = []
        for t in _times(self.p.imu_hz, self.p.duration_s, rng, 0.02):
            pitch, roll = self.scene.attitude(float(t))
            pr, rr = pitch + rng.normal(0, 0.05), roll + rng.normal(0, 0.05)
            body = _rot_pitch_up(pitch) @ _rot_roll_right_down(roll)
            gv = body.T @ np.array([0.0, 0.0, -9.80665])
            crs_true = self.p.course_deg
            if self.scene.two_d:
                crs_true = self.p.course_deg - math.degrees(self.scene.pose(float(t))[2])
            hd = (crs_true - MAG_DECLINATION_DEG + rng.normal(0, 0.3)) % 360.0
            out.append((float(t), {"roll_deg": _q(rr, 0.0625), "pitch_deg": _q(pr, 0.0625),
                                   "heading_deg": _q(hd, 0.0625), "grav": [_q(float(v), 0.01) for v in gv],
                                   "calib": {"sys": 3, "gyro": 3, "accel": 3, "mag": 3}}))
        return out

    def gnss(self) -> List[Tuple[float, dict]]:
        rng = self.rng("gnss")
        p = self.p
        out = []
        dt = 1.0 / p.gnss_hz
        a = math.exp(-dt / 20.0)
        en = rng.normal(0, 0.5, 2)                               # north, east position error (m)
        for t in _times(p.gnss_hz, p.duration_s, rng, 0.0):
            en = a * en + math.sqrt(1 - a * a) * rng.normal(0, 0.5, 2)
            s, v = self.scene.pos(float(t))
            if self.scene.two_d:
                # return scenarios: Y (left of the outbound course) -> north/east; course = heading (static hold
                # at the current heading when stopped)
                _, y, psi, _ = self.scene.pose(float(t))
                c = math.radians(p.course_deg)
                lat, lon = _latlon(p, float(s), float(en[0]) + y * math.sin(c), float(en[1]) - y * math.cos(c))
                crs0 = p.course_deg - math.degrees(psi)
            else:
                lat, lon = _latlon(p, float(s), float(en[0]), float(en[1]))
                crs0 = p.course_deg
            spd = max(float(v) + rng.normal(0, 0.03), 0.0)
            crs = (crs0 + (rng.normal(0, 0.5) if v > 0.5 else 0.0)) % 360.0
            alt = p.alt0_m + p.grade * float(s) + rng.normal(0, 0.3)
            out.append((float(t), {"fix": 1, "lat": round(float(lat), 7), "lon": round(float(lon), 7),
                                   "alt_m": round(alt, 1), "speed_m_s": round(spd, 2), "course_deg": round(crs, 1),
                                   "hdop": 0.8, "sats": 14, "utc": self.utc(float(t))}))
        return out

    def pi(self) -> List[Tuple[float, dict]]:
        rng = self.rng("pi")
        out = []
        for i, t in enumerate(_times(self.p.pi_hz, self.p.duration_s, rng, 0.5)):
            cpu = 48.0 + 0.5 * (self.at(self.house, t) - self.p.ambient_c) + rng.normal(0, 0.3)
            out.append((float(t), {"cpu_c": round(cpu, 1), "throttled_hex": "0x0", "under_voltage_now": False,
                                   "under_voltage_ever": False, "input_v": round(5.08 + rng.normal(0, 0.005), 3),
                                   "disk_free_mb": round(20000.0 - 1.6 * t, 1), "rec_bytes": int(1.6e6 * t)}))
        return out

    # ---------------------------------------------------------------- overlays, heartbeats, assembly
    def apply_overlays(self, sensor: str, readings: List[Tuple[float, dict]]):
        ovs = sorted((o for o in self.p.overlays if o["sensor"] == sensor), key=lambda o: o["t_s"])
        fail_t = None
        for o in ovs:
            if o["kind"] == "fail":
                fail_t = o["t_s"] if fail_t is None else min(fail_t, o["t_s"])
                readings = [(t, d) for t, d in readings if t < o["t_s"]]
            elif o["kind"] == "freeze":
                before = [d for t, d in readings if t < o["t_s"]]
                if before:
                    frozen = before[-1]
                    readings = [(t, d if t < o["t_s"] else json.loads(json.dumps(frozen))) for t, d in readings]
            elif o["kind"] == "fault":
                fk = o["fault"]
                new = []
                for t, d in readings:
                    if t >= o["t_s"]:
                        d = dict(d, temp_c=None, fault=fk)
                        if fk == "spi":
                            d["cj_c"] = None
                    new.append((t, d))
                readings = new
        return readings, fail_t

    def heartbeats(self, sensor: str, readings: List[Tuple[float, dict]], fail_t: Optional[float]):
        stale_s = STALE_S[sensor]
        times = np.array([t for t, _ in readings])
        hbs = []
        t = 0.25
        seq = 0
        while t <= self.p.duration_s + 1e-9:
            n = int(np.searchsorted(times, t, side="right"))
            last_seq = n - 1 if n > 0 else None
            recent = times[(times > t - 2.0) & (times <= t)]
            rate = (len(recent) - 1) / max(recent[-1] - recent[0], 1e-6) if len(recent) >= 2 else 0.0
            if n == 0:
                status, detail = "stale", "starting"
            else:
                age = t - times[n - 1]
                last = readings[n - 1][1]
                if fail_t is not None and t >= fail_t + stale_s + 1.0:
                    status, detail = "no_device", "synthetic --fail overlay: device lost at %.2f s" % fail_t
                elif sensor in protocol.TC_SENSORS and last.get("fault"):
                    status, detail = "error", "thermocouple fault: %s" % last["fault"]
                elif age > stale_s:
                    status, detail = "stale", "no good reading for %.1f s" % age
                else:
                    status, detail = "ok", "sim"
            hbs.append((round(t, 4), dict(sensor=sensor, status=status, detail=detail, last_reading_seq=last_seq,
                                          rate_hz=round(float(rate), 2), seq=seq)))
            seq += 1
            t += 0.5
        return hbs

    def messages(self) -> List[dict]:
        p = self.p
        gens = {"thermal": self.thermal, "radar": self.radar, "imu": self.imu, "gnss": self.gnss, "pi": self.pi}
        msgs: List[Tuple[float, int, dict]] = []
        order = 0
        self.counts = {}
        for sensor in protocol.SENSORS:
            readings = self.tc(sensor) if sensor in protocol.TC_SENSORS else gens[sensor]()
            readings, fail_t = self.apply_overlays(sensor, readings)
            self.counts[sensor] = len(readings)
            for i, (t, d) in enumerate(readings):
                m = self.ctx.make("reading", sensor=sensor, seq=i, data=d, t_mono=round(T_MONO0 + t, 4),
                                  t_utc=self.utc(t))
                msgs.append((t, order, m))
                order += 1
            for t, hb in self.heartbeats(sensor, readings, fail_t):
                m = self.ctx.make("heartbeat", t_mono=round(T_MONO0 + t, 4), t_utc=self.utc(t), **hb)
                msgs.append((t, order, m))
                order += 1
        msgs.append((0.0, -1, self.ctx.make("event", kind="sim_note", detail=SIM_NOTICE, t_mono=T_MONO0,
                                            t_utc=self.utc(0.0))))
        for o in p.overlays:
            det = "synthetic overlay %s %s@%.2f%s" % (o["kind"], o["sensor"], o["t_s"],
                                                     (":" + o["fault"]) if o.get("fault") else "")
            msgs.append((o["t_s"], order, self.ctx.make("event", kind="synth_overlay", detail=det,
                                                        t_mono=round(T_MONO0 + o["t_s"], 4),
                                                        t_utc=self.utc(o["t_s"]))))
            order += 1
        msgs.sort(key=lambda x: (x[0], x[1]))
        return [m for _, _, m in msgs]

    # ---------------------------------------------------------------- truth
    def truth(self) -> dict:
        p, sc = self.p, self.scene
        pitch0, roll0 = sc.attitude(0.0)
        tr: dict = {
            "notice": SIM_NOTICE,
            "scenario": p.scenario,
            "seed": p.seed,
            "duration_s": p.duration_s,
            "t_mono_at_t0": T_MONO0,
            "time_note": "t_s below = recorded t_mono - t_mono_at_t0",
            "ground": {"model": "plane", "grade": p.grade, "cross_slope": 0.0,
                       "note": "ground height ahead = grade * along-course distance, relative to the vehicle's "
                               "ground point"},
            "camera": {"model": "pinhole, no distortion", "w": ThermalRenderer.W, "h": ThermalRenderer.H,
                       "hfov_deg": ThermalRenderer.HFOV, "vfov_deg": ThermalRenderer.VFOV,
                       "principal_point": "((w-1)/2, (h-1)/2), pixel centres at integer coordinates",
                       "height_m": p.cam_height_m, "mount_pitch_deg": p.mount_pitch_deg,
                       "mount_roll_deg": p.mount_roll_deg, "mount_yaw_deg": p.mount_yaw_deg,
                       "gain": p.gain, "gain_range_c": list(GAIN_RANGE_C[p.gain]),
                       "thermal_hz": p.thermal_hz, "pixel_noise_k": p.pixel_noise_k},
            "attitude_true_deg": {"pitch_static": round(pitch0, 4), "roll": roll0,
                                  "note": "pitch = atan(grade) + suspension vibration while driving"},
            "radar": {"n_bins": p.n_bins, "range_res_m": p.range_res_m, "n_ant": p.n_ant,
                      "array": "uniform linear, positions n*lambda/2, steering exp(j*pi*n*sin(bearing)), "
                               "bearing + right", "radar_hz": p.radar_hz, "height_m": p.radar_height_m,
                      "lambda_m": LAMBDA_M, "iq_noise_counts": p.iq_noise_counts,
                      "targets": [{k: v for k, v in tg.items() if k != "index"}
                                  for tg in getattr(self, "radar_targets", [])],
                      "flame_effect": None, "mist_effect": None},
            "vehicle": {"lat0": p.lat0, "lon0": p.lon0, "course_deg": p.course_deg, "speed_m_s": p.speed_m_s,
                        "t_go_s": p.t_go_s, "accel_m_s2": p.accel_m_s2,
                        "stop_at_world_m": sc._stop_target()},
            "mount_heights_m": {"camera": p.cam_height_m, "radar": p.radar_height_m, "plate": p.plate_height_m,
                                "air_probe": p.air_probe_height_m},
            "baseline_window_s": None,
            "flame": None, "smoke": None, "mist": None, "burnt_zone": None, "corner_reflector": None,
            "overlays": p.overlays,
            "intended": {},
        }
        if p.scenario in ("smoke_only", "flame_front", "water_mist", "crossing") + RETURN_SCENARIOS:
            tr["baseline_window_s"] = [0.5, max(0.5, p.onset_s - 0.5)]
        elif p.scenario in ("no_fire", "corner_reflector"):
            tr["baseline_window_s"] = [0.5, p.duration_s]
        elif p.scenario == "after_pass":
            tr["baseline_window_s"] = [0.5, max(0.5, p.t_go_s - 0.5)]
        if sc.flame:
            tr["flame"] = {"onset_s": p.onset_s, "near_edge_world_m_at_onset": p.range_m, "depth_m": p.depth_m,
                           "height_m": p.height_m, "height_flicker_rel_sigma": 0.15, "spread_m_s": p.spread_m_s,
                           "gas_c": p.flame_gas_c, "kappa_1_m": p.flame_kappa, "bearing_deg": 0.0,
                           "lateral_extent": "infinite line fire across the road",
                           "near_edge_world_m": "range_m - spread_m_s * (t - onset_s)"}
            tr["radar"]["flame_effect"] = {"loss_db": p.flame_loss_db, "loss_rel_sigma": 0.3,
                                           "phase_step_rad": p.phase_step_rad, "on_fraction": p.flame_on_frac,
                                           "applies_to": "echoes whose line of sight crosses the flame volume"}
            tr["smoke"] = {"with_flame": True, "kappa_1_m": 0.03, "temp_c": 70.0, "radar_effect": False}
            tr["intended"] = {"flame_state_after_onset": "FLAME", "flame_state_before_onset": "NO_FLAME",
                              "first_solid_echo": "solid_object beyond the far edge"}
        if sc.smoke_only:
            tr["smoke"] = {"onset_s": p.onset_s, "near_world_m": p.range_m, "depth_m": p.depth_m,
                           "top_m": p.height_m, "kappa_1_m": 0.04, "temp_c": 75.0, "radar_effect": False}
            tr["intended"] = {"flame_state": "NO_FLAME", "thermal_max_c": "< 120"}
        if sc.mist:
            tr["mist"] = {"onset_s": p.onset_s, "near_world_m": p.range_m, "depth_m": p.depth_m,
                          "top_m": p.height_m, "kappa_1_m": 0.15, "temp_c": p.ambient_c - 6.0}
            tr["radar"]["mist_effect"] = {"loss_db": p.mist_loss_db, "amp_flicker_db": 0.35, "phase_walk": False,
                                          "applies_to": "echoes beyond the mist's near edge"}
            tr["intended"] = {"flame_state": "NO_FLAME", "radar": "loss and small amplitude flicker, no phase walk",
                              "thermal": "cool"}
        if sc.reflector:
            tr["corner_reflector"] = {"range_world_m": p.range_m, "bearing_deg": 0.0,
                                      "height_m": "at radar height", "snr_db": 50.0, "thermal_c": 5.0}
            tr["intended"] = {"flame_state": "NO_FLAME", "radar": "strong static echo at range_world_m"}
        if sc.after:
            tr["burnt_zone"] = {"near_world_m": p.range_m, "far_world_m": p.range_m + p.depth_m,
                                "ground_c": [95.0, 70.0], "flame": False}
            lat, lon = _latlon(p, p.range_m + p.depth_m)
            tr["burnt_zone"]["far_edge_lat"] = round(float(lat), 7)
            tr["burnt_zone"]["far_edge_lon"] = round(float(lon), 7)
            tr["intended"] = {"flame_state": "NO_FLAME", "flame_pixels": 0, "plate_flux": "< 1 kW/m2",
                              "verdict_when_held_30_s_after_passing": "REOPENED (if every other condition holds)"}
        if p.scenario == "no_fire":
            tr["intended"] = {"flame_state": "NO_FLAME"}
        # flux pulse and measured thickness
        q, t, v, s = self.q, sc.t, sc.v, sc.s
        dt = DT_PHYS
        above = q > 5.0
        tr["flux"] = {"plate": {"thickness_m": 0.001, "rho": 8960.0, "cp": 385.0, "absorptivity": 0.95,
                                "emissivity": 0.95, "h_w_m2_k": 10.0, "ta": "tc_air (lagged) value"},
                      "flame_ep_kw_m2": p.flame_ep_kw_m2, "q_in_kw_m2": p.q_in_kw_m2,
                      "peak_q_kw_m2": round(float(q.max()), 3),
                      "tdu_true": round(float(np.sum(np.maximum(q, 0.0) ** (4.0 / 3.0)) * dt), 3),
                      "time_above_5_kw_m2_s": round(float(above.sum() * dt), 3),
                      "peak_plate_c": round(float(self.plate.max()), 2),
                      "peak_air_c": round(float(self.air_s.max()), 2)}
        if p.scenario in ("crossing",) + RETURN_SCENARIOS:
            mt = float(above.sum() * dt * (v[above].mean() if above.any() else 0.0))
            xn = sc.near_w(t) - s
            xf = sc.far_w(t) - s
            inside = (t >= p.onset_s) & (xn <= 0) & (xf >= 0)
            ti = t[inside]
            tr["measured_thickness_m"] = round(mt, 3)
            tr["measured_thickness_def"] = ("true incident flux > 5 kW/m2 duration x mean true speed over it "
                                            "(calibrate.measure_thickness definition, no plate lag); includes the "
                                            "radiant halo ahead of the flame, so it exceeds depth_m")
            tr["crossing"] = {"t_enter_flame_s": round(float(ti[0]), 3) if ti.size else None,
                              "t_exit_flame_s": round(float(ti[-1]), 3) if ti.size else None,
                              "speed_in_flame_m_s": round(float(v[inside].mean()), 3) if ti.size else None,
                              "depth_true_m": p.depth_m,
                              "far_edge_world_m_at_crossing": round(float(sc.far_w(ti[0])), 3) if ti.size
                              else None}
            if ti.size:
                lat, lon = _latlon(p, float(sc.far_w(ti[0])))
                tr["crossing"]["far_edge_lat"] = round(float(lat), 7)
                tr["crossing"]["far_edge_lon"] = round(float(lon), 7)
        if sc.two_d:
            self._truth_return(tr)
        # per-second timeline
        rows = []
        for ts in np.arange(0.0, p.duration_s + 1e-9, 1.0):
            sv, vv = sc.pos(ts)
            pitch, roll = sc.attitude(float(ts))
            if sc.two_d:
                _, yv, psi, _ = sc.pose(float(ts))
                lat, lon = self.latlon_xy(float(sv), yv)
            else:
                lat, lon = _latlon(p, float(sv))
            row = {"t_s": round(float(ts), 3), "s_m": round(float(sv), 3), "speed_m_s": round(float(vv), 3),
                   "lat": round(float(lat), 7), "lon": round(float(lon), 7), "pitch_deg": round(pitch, 4),
                   "roll_deg": round(roll, 4), "q_kw_m2": round(self.at(self.q, ts), 3),
                   "plate_c": round(self.at(self.plate, ts), 3), "air_c": round(self.at(self.air_s, ts), 3)}
            if sc.two_d:
                row.update(x_m=round(float(sv), 3), y_m=round(yv, 3),
                           course_deg=round((p.course_deg - math.degrees(psi)) % 360.0, 2))
            if sc.flame_present(float(ts)):
                row["near_edge_m"] = round(float(sc.near_w(ts) - sv), 3)
                row["far_edge_m"] = round(float(sc.far_w(ts) - sv), 3)
                row["flame_height_m"] = p.height_m
            rows.append(row)
        tr["timeline"] = rows
        tr["timeline_note"] = ("near_edge_m / far_edge_m: along-course distance from the vehicle (camera and radar "
                               "at s = 0) to the flame base front / back, present only while the flame burns")
        if sc.two_d:
            tr["timeline_note"] += ("; return scenarios: s_m = x_m = world X along the outbound road, y_m to its "
                                    "left, course_deg = true heading (GNSS course while moving)")
        return tr


def generate(scenario: str, out_dir, seed: int = 0, duration: Optional[float] = None,
             overlays: Sequence[dict] = (), **kw) -> Path:
    """Write one synthetic session to ``out_dir`` and return its path. ``kw`` are ``Params`` fields."""
    p = make_params(scenario, seed=int(seed), duration_s=duration, **kw)
    p.overlays = [dict(o) for o in overlays]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for f in list(out.glob("*.jsonl.gz")) + [out / "session.json", out / DEM_FILE]:   # stale files of an earlier run
        if f.exists():
            f.unlink()
    g = _Gen(p)
    msgs = g.messages()
    params = {k: v for k, v in asdict(p).items()
              if k != "overlays" and (p.scenario in RETURN_SCENARIOS or k not in RETURN_PARAMS)}
    info = {"unit_id": p.unit_id, "session_id": g.session_id, "sim": True, "simulated": SIM_NOTICE,
            "started_utc": protocol.utc_now_iso(g.t_epoch0), "ended_utc": protocol.utc_now_iso(g.t_epoch0
                                                                                              + p.duration_s),
            "scenario": p.scenario, "generator": "wfgvu.synth %s" % __version__,
            "params": params,
            "config": {"synthetic": True, "sensors": {s: {"stale_s": STALE_S[s]} for s in protocol.SENSORS},
                       "mount": session_mount(p)},
            "truth": g.truth()}
    if g.scene.two_d:
        arrs = g.dem_arrays()
        write_npz(out / DEM_FILE, arrs)
        info["dem"] = {"file": DEM_FILE, "format": "crossing.terrain.Dem npz: z float32 [h, w] (row 0 north, cell-centre "
                       "elevations, m), x0 / y_top (m), res (m), crs, lat0 / lon0",
                       "crs": "local-enu", "lat0": p.lat0, "lon0": p.lon0, "res_m": float(arrs["res"]),
                       "shape": list(arrs["z"].shape), "simulated": True,
                       "note": "SIMULATED: exactly this session's synthetic ground plane (alt0 + grade * X along the "
                               "outbound course), bare earth only. Pass it to the laptop with --dem <session>/%s"
                               % DEM_FILE}
    recorder.write_session(out, info, msgs)
    return out


def write_npz(path, arrays: dict) -> None:
    """np.savez_compressed equivalent with fixed zip timestamps (byte-identical output for the same arrays)."""
    with zipfile.ZipFile(str(path), "w", zipfile.ZIP_DEFLATED) as zf:
        for k, a in arrays.items():
            buf = io.BytesIO()
            np.lib.format.write_array(buf, np.asanyarray(a), allow_pickle=False)
            zi = zipfile.ZipInfo(k + ".npy", date_time=(1980, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            zf.writestr(zi, buf.getvalue())


def session_mount(p: "Params") -> dict:
    """The mount this synthetic session was rendered with, in config/unit.yaml ``mount`` key names. Written to
    session.json ``config.mount`` so the Pi's sim ``hello`` (and a laptop replay) use the pitch the frames were rendered
    with, not the unit.yaml default (synth renders a level camera unless ``--mount-pitch`` is given)."""
    return {"camera_height_m": p.cam_height_m, "camera_pitch_deg": p.mount_pitch_deg,
            "camera_roll_deg": p.mount_roll_deg, "camera_yaw_deg": p.mount_yaw_deg,
            "radar_height_m": p.radar_height_m, "plate_height_m": p.plate_height_m,
            "tc_air_height_m": p.air_probe_height_m, "source": "wfgvu.synth render parameters"}


# ================================================================================================ samples

SAMPLES = (
    ("no_fire", "no_fire", dict(duration=40.0)),
    ("smoke_only", "smoke_only", dict(duration=40.0)),
    ("flame_front", "flame_front", dict(duration=45.0)),
    ("water_mist", "water_mist", dict(duration=40.0)),
    ("corner_reflector_3m", "corner_reflector", dict(duration=40.0, range_m=3.0)),
    ("crossing", "crossing", dict(duration=45.0)),
    ("after_pass", "after_pass", dict(duration=55.0)),
    ("flame_front_fail_radar", "flame_front", dict(duration=40.0, overlays=[parse_overlay("fail", "radar@20")])),
    ("flame_front_freeze_thermal", "flame_front",
     dict(duration=40.0, overlays=[parse_overlay("freeze", "thermal@20")])),
    # REOPENED end to end: radar decimated to 4 Hz so the two 68 s sessions keep samples/ under 5 MB
    ("crossing_return", "crossing_return", dict(duration=68.0, radar_hz=4.0)),
    ("crossing_return_hot", "crossing_return_hot", dict(duration=68.0, radar_hz=4.0)),
)


def make_samples(root, seed: int = 1) -> List[Path]:
    """Regenerate the committed sample set (``COMPACT`` settings, seed 1). Returns the session directories."""
    out = []
    for name, scen, kw in SAMPLES:
        kw = dict(kw)
        ov = kw.pop("overlays", ())
        kw.update(COMPACT)
        out.append(generate(scen, Path(root) / name, seed=seed, overlays=ov, **kw))
    return out


# ================================================================================================ CLI

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m wfgvu.synth",
                                 description="Write a SIMULATED session (illustrative physics only).")
    ap.add_argument("scenario", choices=SCENARIOS + ("samples",),
                    help="scenario, or 'samples' to regenerate the committed sample set under OUT_DIR")
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--duration", type=float, help="seconds (default 50)")
    ap.add_argument("--fail", action="append", default=[], metavar="SENSOR@T", help="sensor stops at T s")
    ap.add_argument("--freeze", action="append", default=[], metavar="SENSOR@T", help="same data repeats from T s")
    ap.add_argument("--fault", action="append", default=[], metavar="tc_X@T:KIND",
                    help="thermocouple fault from T s (open, short_gnd, short_vcc, spi)")
    ap.add_argument("--range", dest="range_m", type=float, metavar="M",
                    help="flame near edge at onset / smoke / mist near edge / reflector range / burnt-zone start")
    ap.add_argument("--depth", dest="depth_m", type=float, metavar="M")
    ap.add_argument("--height", dest="height_m", type=float, metavar="M")
    ap.add_argument("--spread", dest="spread_m_s", type=float, metavar="M_S")
    ap.add_argument("--speed", dest="speed_m_s", type=float, metavar="M_S")
    ap.add_argument("--grade", type=float, help="road grade rise/run (default 0.04)")
    ap.add_argument("--roll", dest="roll_deg", type=float, help="vehicle roll, deg, + right side down")
    ap.add_argument("--onset", dest="onset_s", type=float, help="flame/smoke/mist onset, s (default 8)")
    ap.add_argument("--mount-pitch", dest="mount_pitch_deg", type=float)
    ap.add_argument("--cam-height", dest="cam_height_m", type=float)
    ap.add_argument("--thermal-hz", dest="thermal_hz", type=float)
    ap.add_argument("--pixel-noise", dest="pixel_noise_k", type=float, help="white pixel noise, K (default 0.04)")
    ap.add_argument("--radar-bins", dest="n_bins", type=int)
    ap.add_argument("--range-res", dest="range_res_m", type=float)
    ap.add_argument("--n-ant", dest="n_ant", type=int)
    ap.add_argument("--flame-loss", dest="flame_loss_db", type=float, help="dB (default 2)")
    ap.add_argument("--phase-step", dest="phase_step_rad", type=float, help="rad per frame (default 0.45)")
    ap.add_argument("--gain", choices=("low", "high"))
    ap.add_argument("--compact", action="store_true", help="the committed samples' small-file settings")
    ap.add_argument("--lat0", type=float)
    ap.add_argument("--lon0", type=float)
    ap.add_argument("--course", dest="course_deg", type=float)
    ap.add_argument("--radar-hz", dest="radar_hz", type=float)
    ap.add_argument("--flame-out", dest="flame_out_s", type=float, help="return scenarios: flame burns out at T s")
    a = ap.parse_args(argv)
    if a.scenario == "samples":
        for pth in make_samples(a.out_dir, seed=a.seed if a.seed else 1):
            print(pth)
        return 0
    try:
        ovs = ([parse_overlay("fail", s) for s in a.fail] + [parse_overlay("freeze", s) for s in a.freeze]
               + [parse_overlay("fault", s) for s in a.fault])
        kw = {k: getattr(a, k) for k in ("range_m", "depth_m", "height_m", "spread_m_s", "speed_m_s", "grade",
                                         "roll_deg", "onset_s", "mount_pitch_deg", "cam_height_m", "thermal_hz",
                                         "pixel_noise_k", "n_bins", "range_res_m", "n_ant", "flame_loss_db",
                                         "phase_step_rad", "gain", "lat0", "lon0", "course_deg", "radar_hz",
                                         "flame_out_s")}
        if a.compact:
            for k, v in COMPACT.items():
                if kw.get(k) is None:
                    kw[k] = v
        out = generate(a.scenario, a.out_dir, seed=a.seed, duration=a.duration, overlays=ovs, **kw)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
