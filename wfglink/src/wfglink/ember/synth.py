"""Synthetic phone scenes with ground truth: an indoor room seen by a webcam, with phones
showing the ember page, held and moved by people.

Room. Walls, floor and ceiling with furniture, ceiling lights, a window, an optional warm
lamp and a bare warm bulb (the size of a phone's blob: the hard negative for the static
rule), a red standby LED and an optional TV whose picture keeps changing. Lights are far
brighter than the walls, so they clip, and they glow (bloom), warm ones in warm colours.

People. Dark silhouettes (head, torso, arm) at their own depths. Each phone has a holder
standing a little behind it; passers-by walk across and hide whatever is behind them.

Phones. A dark body (71.6 x 147.6 mm) with a screen showing the ember page as
booth/ember/index.html draws it: black, with a centred disc of radius 0.36 x the screen's
shorter side and the page's radial gradient (PAGE_STOPS, interpolated as a browser does,
in premultiplied sRGB), flickering smoothly in brightness (0.85 to 1.0) and scale (0.97 to
1.0) at 2 to 6 Hz. The hand moves smoothly (a sum of slow sines on a time axis that pauses
now and then), the phone wobbles and rolls a little, turns away now and then (the screen
narrows, then the dark back shows), and is turned to the camera at its start time and away
at its end time. Screens are brighter than the room, so their centres clip like real ones.

Camera. Pinhole projection with the stated horizontal field of view; motion blur by
sub-frame sampling over the exposure; auto exposure that follows the picture's mean with a
lag (people in dark clothes make it brighten); a slight mains flicker; sensor noise;
gamma; H.264 when written to a file.

Truth per frame and phone: image position (px, camera picture, not mirrored), depth (m),
3D velocity (m/s), yaw (degrees from facing the camera), the visible fraction of the disc
(in the picture and not hidden by anyone or anything nearer), and the disc's apparent
radius (px). Static lights are listed with their boxes.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

# The ember page (booth/ember/index.html is built to this look): stop, sRGB colour, alpha.
PAGE_STOPS = ((0.00, (255, 241, 214), 1.00), (0.18, (255, 194, 102), 1.00), (0.45, (255, 138, 31), 1.00),
              (0.70, (255, 90, 0), 0.35), (1.00, (0, 0, 0), 0.00))
DISC_FRAC = 0.36                  # disc radius, fraction of the screen's shorter side
FLICKER_BRIGHTNESS = (0.85, 1.0)
FLICKER_SCALE = (0.97, 1.0)
FLICKER_HZ = (2.0, 6.0)
PHONE_BODY_M = (0.0716, 0.1476)   # a 6.1 inch phone, portrait
SCREEN_M = (0.0660, 0.1420)
BODY_RADIUS_M, SCREEN_RADIUS_M = 0.010, 0.008
DISC_R_M = DISC_FRAC * min(SCREEN_M)
STANDING_M = 2.0                  # the scenes' standing distance (phones "at 2 m" stand here)

# The fixed scene set of the validation suite (and the fake camera's scenes). z: depth of each
# phone (m); fast: quicker, wider hand motion; duty: exposure as a fraction of the frame interval.
SCENES: dict[str, dict[str, Any]] = {
    "one_at_2m": {"phones": [{"z": 2.0}], "lamp": True, "window": True, "dz": 0.02},
    "two_at_2m": {"phones": [{"z": 2.0}, {"z": 2.0}], "lamp": True, "bulb": True, "tv": True, "passers": 1, "dz": 0.02},
    "three_mixed": {"phones": [{"z": 1.5}, {"z": 2.0}, {"z": 2.5}], "lamp": True, "bulb": True, "tv": True,
                    "window": True, "passers": 1},
    "six_crowd": {"phones": [{"z": z} for z in (1.0, 1.4, 1.8, 2.2, 2.6, 3.0)], "lamp": True, "bulb": True,
                  "tv": True, "passers": 2, "ae_swing": True},
    "near_far": {"phones": [{"z": 1.0}, {"z": 3.0}], "lamp": True, "tv": True, "dz": 0.02},
    "fast": {"phones": [{"z": 2.0, "fast": True}, {"z": 2.0, "fast": True}], "lamp": True, "bulb": True,
             "duty": 1.0, "dz": 0.02},
    "empty_room": {"phones": [], "lamp": True, "bulb": True, "tv": True, "window": True, "passers": 3},
}
SUITE_SCENES = tuple(SCENES)
LIVE_SCENES: dict[str, dict[str, Any]] = {
    "booth": {"phones": [{"z": 1.6}, {"z": 2.0}, {"z": 2.4}], "lamp": True, "bulb": True, "tv": True, "passers": 1},
}


def srgb_to_linear(v: np.ndarray | float) -> np.ndarray:
    v = np.asarray(v, np.float64) / 255.0
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def page_profile(n: int = 1024, r_max: float = 1.25) -> tuple[np.ndarray, float]:
    """Linear-light BGR of the page against r / disc radius, as (n, 3), and the step in r."""
    r = np.linspace(0.0, r_max, n)
    stops = np.array([s for s, _, _ in PAGE_STOPS])
    pre = np.array([[c * a for c in rgb] for _, rgb, a in PAGE_STOPS], np.float64)   # premultiplied sRGB
    out = np.stack([np.interp(r, stops, pre[:, k], right=0.0) for k in range(3)], axis=1)
    lin = srgb_to_linear(out)
    return lin[:, ::-1].astype(np.float32), r_max / (n - 1)


_PROFILE, _PROFILE_STEP = page_profile()


def focal_px(width: int, hfov_deg: float) -> float:
    return (width / 2.0) / math.tan(math.radians(hfov_deg) / 2.0)


def _rrect_sdf(x: np.ndarray, y: np.ndarray, hw: float, hh: float, r: float) -> np.ndarray:
    qx = np.abs(x) - (hw - r)
    qy = np.abs(y) - (hh - r)
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def _smooth_bump(t: np.ndarray, t0: float, dur: float) -> np.ndarray:
    """0 outside [t0, t0 + dur], rising smoothly to 1 in the middle."""
    u = np.clip((t - t0) / max(dur, 1e-6), 0, 1)
    return 0.5 - 0.5 * np.cos(2 * np.pi * u)


def _min_jerk(u: np.ndarray) -> np.ndarray:
    u = np.clip(u, 0, 1)
    return 10 * u ** 3 - 15 * u ** 4 + 6 * u ** 5


# Scene parts ---------------------------------------------------------------------------------

@dataclass
class Trajectory:
    """A position on a fine time grid (camera coordinates, m: x right, y down, z forward)."""

    t: np.ndarray
    xyz: np.ndarray                   # (n, 3)
    vel: np.ndarray                   # (n, 3)
    yaw: np.ndarray                   # degrees, 0 facing the camera
    roll: np.ndarray                  # degrees, in the picture plane

    def at(self, t: float) -> tuple[np.ndarray, np.ndarray, float, float]:
        i = float(np.clip((t - self.t[0]) / (self.t[1] - self.t[0]), 0, len(self.t) - 1.0001))
        k = int(i)
        a = i - k
        lerp = lambda arr: arr[k] * (1 - a) + arr[k + 1] * a  # noqa: E731
        return lerp(self.xyz), lerp(self.vel), float(lerp(self.yaw)), float(lerp(self.roll))


@dataclass
class Phone:
    pid: int
    traj: Trajectory
    brightness: float                 # screen radiance relative to a white wall
    flicker: tuple[float, ...]        # f1, f2, p1, p2, f3, p3
    landscape: bool = False
    holder: "Person | None" = None

    def flick(self, t: float) -> tuple[float, float]:
        f1, f2, p1, p2, f3, p3 = self.flicker
        a = 0.6 * math.sin(2 * math.pi * f1 * t + p1) + 0.4 * math.sin(2 * math.pi * f2 * t + p2)
        b = math.sin(2 * math.pi * f3 * t + p3)
        lo, hi = FLICKER_BRIGHTNESS
        slo, shi = FLICKER_SCALE
        return lo + (hi - lo) * (0.5 + 0.5 * a), slo + (shi - slo) * (0.5 + 0.5 * b)


@dataclass
class Person:
    z: float
    x_of_t: Callable[[float], float]   # body centre x (m) at time t
    y_shoulder: float                  # shoulder height (m, camera y, down positive)
    color: tuple[float, float, float]  # linear BGR of the clothes
    skin: tuple[float, float, float]
    phone: Phone | None = None
    width: float = 0.44

    def polygons(self, t: float, cam: "CameraGeom") -> list[np.ndarray]:
        """Head, torso and (with a phone) the arm, as pixel polygons."""
        x = self.x_of_t(t)
        f, cx, cy = cam.f, cam.cx, cam.cy
        k = f / self.z
        px = lambda X, Y: (cx + k * X, cy + k * Y)  # noqa: E731
        polys = []
        hx, hy = px(x, self.y_shoulder - 0.17)
        a = np.linspace(0, 2 * np.pi, 18, endpoint=False)
        polys.append(np.stack([hx + k * 0.085 * np.cos(a), hy + k * 0.115 * np.sin(a)], 1))
        w = self.width / 2
        body = [(x - w + 0.06, self.y_shoulder), (x + w - 0.06, self.y_shoulder), (x + w, self.y_shoulder + 0.08),
                (x + w + 0.02, self.y_shoulder + 2.0), (x - w - 0.02, self.y_shoulder + 2.0), (x - w, self.y_shoulder + 0.08)]
        polys.append(np.array([px(X, Y) for X, Y in body]))
        if self.phone is not None:
            pos, _, _, _ = self.phone.traj.at(t)
            side = 1.0 if pos[0] >= x else -1.0
            sx, sy = px(x + side * (w - 0.05), self.y_shoulder + 0.05)
            kh = f / pos[2]
            hx2, hy2 = cx + kh * pos[0], cy + kh * (pos[1] + 0.06)
            d = np.array([hx2 - sx, hy2 - sy])
            n = np.array([-d[1], d[0]]) / max(np.hypot(*d), 1e-6)
            half = 0.5 * 0.085 * (k + kh) / 2
            polys.append(np.array([(sx, sy) + n * half * 1.3, (hx2, hy2) + n * half,
                                   (hx2, hy2) - n * half, (sx, sy) - n * half * 1.3]))
        return polys


@dataclass
class CameraGeom:
    width: int
    height: int
    f: float

    @property
    def cx(self) -> float:
        return (self.width - 1) / 2.0

    @property
    def cy(self) -> float:
        return (self.height - 1) / 2.0

    def project(self, xyz: np.ndarray) -> tuple[float, float, float]:
        k = self.f / xyz[2]
        return self.cx + k * xyz[0], self.cy + k * xyz[1], k


@dataclass
class Room:
    image: np.ndarray                     # linear BGR float32, before exposure
    lights: list[dict[str, Any]]          # static bright objects: name, box [x0, y0, x1, y1] px, warm
    tv: dict[str, Any] | None
    floor_y: float


def build_room(spec: dict[str, Any], cam: CameraGeom, rng: np.random.Generator) -> Room:
    W, H = cam.width, cam.height
    img = np.zeros((H, W, 3), np.float32)
    lights_layer = np.zeros_like(img)
    s = W / 1280.0
    ceil_y = int(H * rng.uniform(0.04, 0.10))
    floor_y = int(H * rng.uniform(0.66, 0.76))
    wall = np.array([0.16, 0.19, 0.22]) * rng.uniform(0.8, 1.2, 3)
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    img[:] = (wall * (1.15 - 0.3 * yy)).astype(np.float32)
    img[:ceil_y] = np.array([0.30, 0.31, 0.32], np.float32)
    floor = np.array([0.05, 0.08, 0.11]) * rng.uniform(0.8, 1.2, 3)
    img[floor_y:] = (floor * (0.8 + 0.4 * (yy[floor_y:] - yy[floor_y]) / max(1e-6, 1 - yy[floor_y]))).astype(np.float32)
    # Furniture and pictures.
    for _ in range(int(rng.integers(3, 6))):
        w, h = int(rng.uniform(60, 220) * s), int(rng.uniform(40, 160) * s)
        x0, y0 = int(rng.uniform(0, W - w)), int(rng.uniform(ceil_y + 10 * s, floor_y - h))
        col = rng.uniform(0.02, 0.25, 3).astype(np.float32)
        img[y0:y0 + h, x0:x0 + w] = col
        img[y0 + int(6 * s):y0 + h - int(6 * s), x0 + int(6 * s):x0 + w - int(6 * s)] = rng.uniform(0.03, 0.3, 3)
    sofa_w = int(rng.uniform(300, 520) * s)
    sx = int(rng.uniform(0, W - sofa_w))
    img[floor_y - int(70 * s):floor_y + int(30 * s), sx:sx + sofa_w] = rng.uniform(0.02, 0.08, 3)
    lights: list[dict[str, Any]] = []

    def add_light(name: str, mask_fn, radiance, warm: bool) -> None:
        m = np.zeros((H, W), np.uint8)
        mask_fn(m)
        ys, xs = np.nonzero(m)
        if not len(xs):
            return
        lights_layer[m > 0] = radiance
        lights.append({"name": name, "box": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())], "warm": warm})

    for i in range(int(rng.integers(1, 4))):
        cxl, w, h = rng.uniform(0.1, 0.9) * W, rng.uniform(50, 120) * s, rng.uniform(10, 22) * s
        add_light(f"ceiling_light_{i}", lambda m: cv2.ellipse(m, (int(cxl), int(ceil_y + h)), (int(w / 2), int(h / 2)),
                                                                 0, 0, 360, 255, -1),
                  np.array([14.0, 15.0, 15.0], np.float32) * rng.uniform(0.8, 1.3), False)
    if spec.get("window"):
        w, h = rng.uniform(180, 300) * s, rng.uniform(130, 200) * s
        x0, y0 = rng.uniform(0.05, 0.95) * W - w / 2, rng.uniform(ceil_y + 20 * s, floor_y - h - 30 * s)
        rad = np.array([4.0, 3.6, 3.2], np.float32) * rng.uniform(0.8, 1.4)
        add_light("window", lambda m: cv2.rectangle(m, (int(x0), int(y0)), (int(x0 + w), int(y0 + h)), 255, -1), rad, False)
        for xx in (x0 + w / 2,):
            lights_layer[int(y0):int(y0 + h), int(xx - 3 * s):int(xx + 3 * s)] = 0.0
            img[int(y0):int(y0 + h), int(xx - 3 * s):int(xx + 3 * s)] = 0.05
        lights_layer[int(y0 + h / 2 - 3 * s):int(y0 + h / 2 + 3 * s), int(x0):int(x0 + w)] = 0.0
        img[int(y0 + h / 2 - 3 * s):int(y0 + h / 2 + 3 * s), int(x0):int(x0 + w)] = 0.05
    warm = np.array([0.28, 0.62, 1.0], np.float32)
    if spec.get("lamp"):
        lx, ly = rng.uniform(0.1, 0.9) * W, rng.uniform(0.35, 0.55) * H
        sw, sh = rng.uniform(50, 80) * s, rng.uniform(40, 60) * s
        shade = np.array([[lx - sw * 0.35, ly - sh / 2], [lx + sw * 0.35, ly - sh / 2], [lx + sw / 2, ly + sh / 2],
                          [lx - sw / 2, ly + sh / 2]], np.int32)
        add_light("lamp_shade", lambda m: cv2.fillPoly(m, [shade], 255), warm * rng.uniform(2.5, 5.0), True)
        add_light("lamp_bulb", lambda m: cv2.ellipse(m, (int(lx), int(ly + sh / 2 + 4 * s)), (int(10 * s), int(6 * s)),
                                                     0, 0, 360, 255, -1), warm * 14.0, True)
        cv2.line(img, (int(lx), int(ly + sh / 2)), (int(lx), floor_y), (0.02, 0.02, 0.02), max(1, int(4 * s)))
    if spec.get("bulb"):
        bx, by = rng.uniform(0.08, 0.92) * W, rng.uniform(0.15, 0.55) * H
        r = rng.uniform(5.0, 9.0) * s
        add_light("bare_bulb", lambda m: cv2.circle(m, (int(bx), int(by)), max(2, int(r)), 255, -1),
                  warm * rng.uniform(8.0, 16.0), True)
        cv2.line(img, (int(bx), 0), (int(bx), int(by - r)), (0.02, 0.02, 0.02), max(1, int(2 * s)))
    led_x, led_y = rng.uniform(0.1, 0.9) * W, rng.uniform(floor_y - 60 * s, floor_y)
    add_light("standby_led", lambda m: cv2.circle(m, (int(led_x), int(led_y)), max(1, int(1.5 * s)), 255, -1),
              np.array([0.05, 0.05, 6.0], np.float32), True)
    tv = None
    if spec.get("tv"):
        w, h = rng.uniform(200, 280) * s, 0.0
        h = w * 9 / 16
        x0, y0 = rng.uniform(0.05, 0.95) * W - w / 2, rng.uniform(ceil_y + 40 * s, floor_y - h - 40 * s)
        x0 = float(np.clip(x0, 0, W - w - 1))
        img[int(y0 - 6 * s):int(y0 + h + 6 * s), int(x0 - 6 * s):int(x0 + w + 6 * s)] = 0.01
        tv = {"box": [int(x0), int(y0), int(x0 + w), int(y0 + h)], "seed": int(rng.integers(1 << 30))}
        lights.append({"name": "tv", "box": tv["box"], "warm": True})
    # Texture, bloom of the lights (warm lights glow warm), then the lights themselves.
    tex = cv2.GaussianBlur(rng.normal(0, 1, (H // 8 + 1, W // 8 + 1)).astype(np.float32), (0, 0), 1.5)
    tex = cv2.resize(tex, (W, H), interpolation=cv2.INTER_LINEAR)
    img *= (1.0 + 0.06 * tex)[..., None]
    glow = cv2.GaussianBlur(lights_layer, (0, 0), 5 * s) * 0.10 + cv2.GaussianBlur(lights_layer, (0, 0), 18 * s) * 0.05
    img += glow
    lit = lights_layer.max(axis=2) > 0
    img[lit] = lights_layer[lit]
    return Room(img, lights, tv, float(floor_y))


def _tv_picture(tv: dict[str, Any], t: float) -> np.ndarray:
    """The TV's picture at time t: soft coloured shapes drifting, cut every few seconds."""
    x0, y0, x1, y1 = tv["box"]
    W, Hh = x1 - x0, y1 - y0
    w, h = max(2, W // 4), max(2, Hh // 4)          # smooth content: drawn at quarter size, then enlarged
    shot = int(t // 4.0)
    rng = np.random.default_rng(tv["seed"] + shot)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    pic = np.zeros((h, w, 3), np.float32)
    pic[:] = rng.uniform(0.05, 0.4, 3)
    ts = t - shot * 4.0
    for _ in range(4):
        cx0, cy0 = rng.uniform(0, w), rng.uniform(0, h)
        vx, vy = rng.uniform(-8, 8), rng.uniform(-5, 5)
        sig = rng.uniform(0.15, 0.35) * h
        col = rng.uniform(0.0, 1.0, 3) * rng.uniform(0.4, 1.4)
        cx, cy = cx0 + vx * ts, cy0 + vy * ts
        g = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sig ** 2))
        pic += g[..., None] * col.astype(np.float32)
    return cv2.resize(pic, (W, Hh), interpolation=cv2.INTER_LINEAR)


# Phone motion --------------------------------------------------------------------------------

def free_trajectory(rng: np.random.Generator, duration: float, z: float, anchor: tuple[float, float], *,
                    fast: bool = False, dz: float = 0.06, t_in: float = 0.0, t_out: float | None = None,
                    turns: bool = True, step: float = 0.002) -> Trajectory:
    """Smooth hand motion with pauses and turns (see the module docstring)."""
    t = np.arange(-1.0, duration + 1.0 + step, step)
    rate = np.ones_like(t)
    tt = t_in + rng.uniform(1.0, 4.0)
    while tt < duration:                                   # pauses: the hand stops, then goes on
        dur = rng.uniform(0.5, 2.0)
        rate *= 1 - (_smooth_bump(t, tt, dur) > 0.15) * _smooth_bump(t, tt, dur) ** 0.5
        tt += dur + rng.uniform(2.0, 6.0)
    rate = np.clip(rate, 0, 1)
    tau = np.cumsum(rate) * step
    amp_scale = 1.6 if fast else 1.0
    f_scale = 1.8 if fast else 1.0
    xyz = np.zeros((len(t), 3))
    xyz[:, 0], xyz[:, 1], xyz[:, 2] = anchor[0], anchor[1], z
    for axis, (a_lo, a_hi) in ((0, (0.06, 0.20)), (1, (0.04, 0.12))):
        for _ in range(3):
            a = rng.uniform(a_lo, a_hi) * amp_scale
            fq = rng.uniform(0.2, 0.9) * f_scale
            xyz[:, axis] += a * np.sin(2 * np.pi * fq * tau + rng.uniform(0, 2 * np.pi))
    xyz[:, 2] += dz * np.sin(2 * np.pi * rng.uniform(0.1, 0.4) * tau + rng.uniform(0, 6.3))
    vel = np.gradient(xyz, step, axis=0)
    yaw = 8.0 * np.sin(2 * np.pi * rng.uniform(0.1, 0.3) * t + rng.uniform(0, 6.3))
    if turns:
        tt = t_in + rng.uniform(3.0, 7.0)
        while tt < duration:
            dur, peak = rng.uniform(0.6, 1.6), rng.uniform(100, 180)
            yaw = yaw + peak * _smooth_bump(t, tt, dur)
            tt += dur + rng.uniform(5.0, 10.0)
    t_out = duration + 10 if t_out is None else t_out
    yaw = yaw + 180.0 * (1 - np.clip((t - t_in) / 0.4, 0, 1)) + 180.0 * np.clip((t - t_out) / 0.4, 0, 1)
    roll = 6.0 * np.sin(2 * np.pi * rng.uniform(0.1, 0.4) * t + rng.uniform(0, 6.3))
    return Trajectory(t, xyz, vel, yaw, roll)


def ruler_trajectory(duration: float, z: float, x0: float, path_m: float, t_move: float, move_s: float,
                     y: float = -0.05, step: float = 0.002, rng: np.random.Generator | None = None) -> Trajectory:
    """Rest at x0, a minimum-jerk move of path_m along x in move_s starting at t_move, rest."""
    t = np.arange(-1.0, duration + 1.0 + step, step)
    xyz = np.zeros((len(t), 3))
    xyz[:, 0] = x0 + path_m * _min_jerk((t - t_move) / move_s)
    xyz[:, 1] = y
    xyz[:, 2] = z
    if rng is not None:   # a hand is never perfectly still: about a millimetre of tremor
        xyz[:, 1] += 0.0008 * np.sin(2 * np.pi * 7.3 * t + rng.uniform(0, 6.3))
        xyz[:, 0] += 0.0008 * np.sin(2 * np.pi * 5.1 * t + rng.uniform(0, 6.3))
    vel = np.gradient(xyz, step, axis=0)
    return Trajectory(t, xyz, vel, np.zeros_like(t), np.zeros_like(t))


# The scene -----------------------------------------------------------------------------------

@dataclass
class PhoneScene:
    """A room with people and phones; render(t) gives the camera picture at time t."""

    name: str
    spec: dict[str, Any]
    cam: CameraGeom
    fps: float
    duration_s: float
    seed: int
    room: Room = field(init=False)
    phones: list[Phone] = field(init=False)
    people: list[Person] = field(init=False)
    extra_truth: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        rng = np.random.default_rng(self.seed)
        self.rng = rng
        self.room = build_room(self.spec, self.cam, rng)
        self.phones, self.people = [], []
        n = len(self.spec.get("phones", []))
        half_fov = math.atan(self.cam.width / 2 / self.cam.f)
        slots = (np.arange(n) + 0.5) / max(n, 1) * 2 - 1 if n else np.zeros(0)
        rng.shuffle(slots)
        for i, ph in enumerate(self.spec.get("phones", [])):
            z = float(ph["z"])
            half_w = z * math.tan(half_fov)
            ax = float(np.clip(slots[i] * 0.7 * half_w + rng.uniform(-0.05, 0.05), -0.65 * half_w, 0.65 * half_w))
            ay = rng.uniform(-0.15, 0.05)
            if "trajectory" in ph:
                traj = ph["trajectory"]
            else:
                t_in = 0.0 if i == 0 else rng.uniform(0.0, min(4.0, self.duration_s / 4))
                traj = free_trajectory(rng, self.duration_s, z, (ax, ay), fast=bool(ph.get("fast")),
                                       dz=float(self.spec.get("dz", 0.06)), t_in=t_in)
            phone = Phone(i + 1, traj, brightness=float(ph.get("brightness", rng.uniform(4.0, 8.0))),
                          flicker=(rng.uniform(*FLICKER_HZ), rng.uniform(*FLICKER_HZ), rng.uniform(0, 6.3),
                                   rng.uniform(0, 6.3), rng.uniform(*FLICKER_HZ), rng.uniform(0, 6.3)),
                          landscape=bool(ph.get("landscape", rng.random() < 0.25)))
            px0 = float(np.median(traj.xyz[:, 0]))
            holder = Person(z + rng.uniform(0.3, 0.45), (lambda t, px0=px0: px0 * 0.8),
                            float(traj.xyz[:, 1].min() + rng.uniform(-0.05, 0.05)),
                            tuple(rng.uniform(0.01, 0.06, 3)), (0.12, 0.17, 0.24), phone)
            phone.holder = holder
            self.phones.append(phone)
            self.people.append(holder)
        for j in range(int(self.spec.get("passers", 0))):
            z = rng.uniform(2.4, 4.0)
            half_w = z * math.tan(half_fov) + 0.4
            v = rng.uniform(0.5, 1.1) * (1 if rng.random() < 0.5 else -1)
            period = 2 * half_w / abs(v) + rng.uniform(3.0, 8.0)
            off = rng.uniform(0, period)

            def x_of_t(t, v=v, half_w=half_w, period=period, off=off):
                u = (t + off) % period
                return -np.sign(v) * half_w + v * u

            self.people.append(Person(z, x_of_t, rng.uniform(-0.45, -0.25), tuple(rng.uniform(0.01, 0.07, 3)),
                                      (0.12, 0.17, 0.24)))
        self.gain = 1.0
        self.duty = float(self.spec.get("duty", rng.uniform(0.5, 0.8)))
        self.noise_dn = float(self.spec.get("noise_dn", 2.0))
        bank_rng = np.random.default_rng(self.seed + 1)
        self._bank = bank_rng.standard_normal((self.cam.height + 32, self.cam.width + 32, 3)).astype(np.float32)
        self._last_t: float | None = None
        self._mains = (rng.uniform(2.0, 4.0), rng.uniform(0, 6.3))

    # truth ----------------------------------------------------------------------------------
    def truth(self, t: float) -> list[dict[str, Any]]:
        out = []
        for ph in self.phones:
            pos, vel, yaw, roll = ph.traj.at(t)
            u, v, k = self.cam.project(pos)
            r = k * DISC_R_M
            out.append({"pid": ph.pid, "x": u, "y": v, "z": float(pos[2]), "vx": float(vel[0]), "vy": float(vel[1]),
                        "vz": float(vel[2]), "yaw": float(((yaw + 180) % 360) - 180), "roll": roll, "r_px": r,
                        "vis": self._visible_fraction(ph, t, u, v, r, yaw, roll)})
        return out

    def _occluders(self, t: float, z: float, exclude: Phone | None = None) -> list[np.ndarray]:
        polys: list[np.ndarray] = []
        for p in self.people:
            if p.z < z - 0.01:
                polys += p.polygons(t, self.cam)
        for ph in self.phones:
            if ph is exclude:
                continue
            pos, _, yaw, roll = ph.traj.at(t)
            if pos[2] < z - 0.01:
                polys.append(self._body_polygon(ph, pos, yaw, roll))
        return polys

    def _body_polygon(self, ph: Phone, pos: np.ndarray, yaw: float, roll: float) -> np.ndarray:
        u, v, k = self.cam.project(pos)
        c = max(abs(math.cos(math.radians(yaw))), 0.05)
        hw, hh = PHONE_BODY_M[0] / 2 * k * c, PHONE_BODY_M[1] / 2 * k
        rr = math.radians(roll + (90.0 if ph.landscape else 0.0))
        cr, sr = math.cos(rr), math.sin(rr)
        pts = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        return np.array([(u + cr * x - sr * y, v + sr * x + cr * y) for x, y in pts])

    def _visible_fraction(self, ph: Phone, t: float, u: float, v: float, r: float, yaw: float, roll: float) -> float:
        c = math.cos(math.radians(yaw))
        if c <= 0.05:
            return 0.0
        ext = int(math.ceil(r)) + 2
        x0, y0 = int(math.floor(u)) - ext, int(math.floor(v)) - ext
        size = 2 * ext + 1
        yy, xx = np.mgrid[y0:y0 + size, x0:x0 + size].astype(np.float32)
        rr = math.radians(roll)
        dx, dy = xx - u, yy - v
        lx = math.cos(rr) * dx + math.sin(rr) * dy
        ly = -math.sin(rr) * dx + math.cos(rr) * dy
        disc = (lx / (r * c)) ** 2 + (ly / r) ** 2 <= 1.0
        total = int(disc.sum())
        if total == 0:
            return 0.0
        inside = (xx >= 0) & (xx < self.cam.width) & (yy >= 0) & (yy < self.cam.height)
        occ = np.zeros((size, size), np.uint8)
        polys = [np.round(p - (x0, y0)).astype(np.int32) for p in self._occluders(t, ph.traj.at(t)[0][2], ph)]
        if polys:
            for poly in polys:              # one call per polygon: fillPoly's even-odd rule would cut overlaps out
                cv2.fillPoly(occ, [poly], 1)
        return float((disc & inside & (occ == 0)).sum() / total)

    # rendering ------------------------------------------------------------------------------
    def render(self, t: float) -> np.ndarray:
        """The camera picture (BGR uint8) at time t (exposure centred on t)."""
        dt = (1.0 / self.fps) if self._last_t is None else max(1e-3, min(1.0, t - self._last_t))
        self._last_t = t
        frame = self.room.image.copy()
        if self.room.tv is not None:
            x0, y0, x1, y1 = self.room.tv["box"]
            frame[y0:y1, x0:x1] = _tv_picture(self.room.tv, t)
        items: list[tuple[float, int, Any]] = [(p.z, 0, p) for p in self.people]
        items += [(float(ph.traj.at(t)[0][2]), 1, ph) for ph in self.phones]
        items.sort(key=lambda it: -it[0])
        exposure = self.duty / self.fps
        for _, kind, obj in items:
            if kind == 0:
                polys = [np.round(p).astype(np.int32) for p in obj.polygons(t, self.cam)]
                for poly in polys[1:]:
                    cv2.fillPoly(frame, [poly], tuple(float(c) for c in obj.color))
                cv2.fillPoly(frame, polys[:1], tuple(float(c) for c in obj.skin))
            else:
                self._draw_phone(frame, obj, t, exposure)
        # Auto exposure: follows the picture's mean with a lag of about a second.
        small = cv2.resize(frame, (64, 36), interpolation=cv2.INTER_AREA)
        mean = float(np.clip(small, 0, 1.5).mean())
        target = 0.17 * (1.0 + (0.5 * math.sin(2 * math.pi * t / 9.0) if self.spec.get("ae_swing") else 0.0))
        want = float(np.clip(target / max(mean, 1e-3), 0.5, 2.5))
        self.gain *= (want / self.gain) ** min(1.0, dt / 1.0)
        mains = 1.0 + 0.015 * math.sin(2 * math.pi * self._mains[0] * t + self._mains[1])
        return self._camera(frame, self.gain * mains)

    def _camera(self, frame: np.ndarray, gain: float) -> np.ndarray:
        """Exposure, clipping, a webcam tone curve (square root, close to sRGB), noise, 8 bits."""
        H, W = frame.shape[:2]
        np.multiply(frame, np.float32(gain), out=frame)
        np.clip(frame, 0.0, 1.0, out=frame)
        enc = cv2.sqrt(frame)
        oy, ox = (int(v) for v in self.rng.integers(0, 32, 2))
        sigma = self.noise_dn * math.sqrt(max(gain, 0.25)) / 255.0
        cv2.scaleAdd(self._bank[oy:oy + H, ox:ox + W], sigma, enc, dst=enc)
        return cv2.convertScaleAbs(enc, alpha=255.0)

    def _draw_phone(self, frame: np.ndarray, ph: Phone, t: float, exposure: float) -> None:
        H, W = frame.shape[:2]
        pos0, _, _, _ = ph.traj.at(t - exposure / 2)
        pos1, _, _, _ = ph.traj.at(t + exposure / 2)
        u0, v0, k0 = self.cam.project(pos0)
        u1, v1, k1 = self.cam.project(pos1)
        n_sub = int(np.clip(math.ceil(math.hypot(u1 - u0, v1 - v0) / 2.5), 2, 12))
        k_max = max(k0, k1)
        bloom = 4.0 * k_max / 450.0 + 1.0
        reach = 0.5 * math.hypot(*PHONE_BODY_M) * k_max + 2        # body half-diagonal, px
        ext = reach + 3 * bloom + 2
        x0, x1 = int(math.floor(min(u0, u1) - ext)), int(math.ceil(max(u0, u1) + ext))
        y0, y1 = int(math.floor(min(v0, v1) - ext)), int(math.ceil(max(v0, v1) + ext))
        cx0, cx1, cy0, cy1 = max(0, x0), min(W, x1), max(0, y0), min(H, y1)
        if cx1 <= cx0 or cy1 <= cy0:
            return
        alpha = np.zeros((y1 - y0, x1 - x0), np.float32)
        emit = np.zeros((y1 - y0, x1 - x0, 3), np.float32)
        nprof = len(_PROFILE) - 1
        for j in range(n_sub):
            ts = t - exposure / 2 + (j + 0.5) / n_sub * exposure
            pos, _, yaw, roll = ph.traj.at(ts)
            u, v, k = self.cam.project(pos)
            # Only the box this sub-sample's phone covers is computed.
            bx0, bx1 = max(int(u - reach), x0), min(int(u + reach) + 2, x1)
            by0, by1 = max(int(v - reach), y0), min(int(v + reach) + 2, y1)
            if bx1 <= bx0 or by1 <= by0:
                continue
            yy, xx = np.mgrid[by0:by1, bx0:bx1].astype(np.float32)
            b, sc = ph.flick(ts)
            c = math.cos(math.radians(yaw))
            ac = max(abs(c), 0.05)
            rr = math.radians(roll + (90.0 if ph.landscape else 0.0))
            cr, sr = math.cos(rr), math.sin(rr)
            dx, dy = xx - np.float32(u), yy - np.float32(v)
            mx = (cr * dx + sr * dy) * np.float32(1.0 / (k * ac))
            my = (-sr * dx + cr * dy) * np.float32(1.0 / k)
            aa = np.float32(k * max(ac, 0.3))
            sl = (slice(by0 - y0, by1 - y0), slice(bx0 - x0, bx1 - x0))
            alpha[sl] += np.clip(0.5 - _rrect_sdf(mx, my, PHONE_BODY_M[0] / 2, PHONE_BODY_M[1] / 2, BODY_RADIUS_M) * aa,
                                 0, 1)
            if c > 0.05:
                scr = np.clip(0.5 - _rrect_sdf(mx, my, SCREEN_M[0] / 2, SCREEN_M[1] / 2, SCREEN_RADIUS_M) * aa, 0, 1)
                r = np.hypot(mx, my) * np.float32(1.0 / (DISC_R_M * sc * _PROFILE_STEP))
                idx = np.minimum(r.astype(np.int32), nprof)
                gain = np.float32(ph.brightness * b * (0.65 + 0.35 * c))
                emit[sl] += _PROFILE[idx] * (scr * gain)[..., None]
        alpha *= np.float32(1.0 / n_sub)
        emit *= np.float32(1.0 / n_sub)
        emit += cv2.GaussianBlur(emit, (0, 0), bloom) * np.float32(0.12)
        sx, sy = slice(cx0 - x0, cx1 - x0), slice(cy0 - y0, cy1 - y0)
        patch = frame[cy0:cy1, cx0:cx1]
        a = alpha[sy, sx][..., None]
        body = np.array([0.012, 0.012, 0.014], np.float32)
        patch *= 1.0 - a
        patch += a * body + emit[sy, sx]


class LiveScene:
    """A generated scene for the fake camera: renders any time t, looping every duration_s."""

    def __init__(self, name: str | dict = "booth", size: tuple[int, int] = (1280, 720), fps: float = 30.0,
                 seed: int = 1, hfov_deg: float = 70.0, duration_s: float = 120.0):
        spec = name if isinstance(name, dict) else (LIVE_SCENES.get(name) or SCENES.get(name))
        if spec is None:
            raise ValueError(f"unknown scene {name!r}; known: {', '.join(list(LIVE_SCENES) + list(SCENES))}")
        self.name = name if isinstance(name, str) else "custom"
        self.duration_s = float(duration_s)
        cam = CameraGeom(int(size[0]), int(size[1]), focal_px(int(size[0]), hfov_deg))
        self.scene = PhoneScene(self.name, spec, cam, fps, self.duration_s, seed)

    def render(self, t: float) -> np.ndarray:
        return self.scene.render(t % self.duration_s)


# Clip files for the validation suite ---------------------------------------------------------

def scene_key(name: str, spec: dict, size: tuple[int, int], fps: float, seconds: float, crf: int, seed: int,
              hfov_deg: float) -> str:
    """A short hash of everything that makes a scene clip, so a changed generator makes it again."""
    src = Path(__file__).read_bytes()
    h = hashlib.sha256(src)
    h.update(json.dumps([name, spec, list(size), fps, seconds, crf, seed, hfov_deg], sort_keys=True,
                        default=str).encode())
    return h.hexdigest()[:12]


def write_scene_clip(scene: PhoneScene, out_dir: str | Path, crf: int = 23, stem: str | None = None) -> dict[str, Any]:
    """Render the whole scene to <stem>.mp4 (H.264) with <stem>_truth.npz and <stem>.json."""
    from wfglink.synth.degrade import VideoWriter

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = stem or scene.name
    n = int(round(scene.duration_s * scene.fps))
    times = np.arange(n) / scene.fps
    keys = ("x", "y", "z", "vx", "vy", "vz", "yaw", "r_px", "vis")
    arr = {k: np.full((n, len(scene.phones)), np.nan) for k in keys}
    video = out / f"{stem}.mp4"
    with VideoWriter(video, (scene.cam.width, scene.cam.height), scene.fps, crf=crf, preset="veryfast",
                     encoder_threads=2) as wr:
        for i, t in enumerate(times):
            img = scene.render(float(t))
            for j, tr in enumerate(scene.truth(float(t))):
                for k in keys:
                    arr[k][i, j] = tr[k]
            wr.write(img, float(t))
    np.savez_compressed(out / f"{stem}_truth.npz", t=times, pid=np.array([p.pid for p in scene.phones]), **arr)
    meta = {"name": scene.name, "spec": scene.spec, "size": [scene.cam.width, scene.cam.height], "fps": scene.fps,
            "seconds": scene.duration_s, "focal_px": scene.cam.f, "seed": scene.seed, "crf": crf,
            "lights": scene.room.lights, **scene.extra_truth}
    (out / f"{stem}.json").write_text(json.dumps(meta, indent=2, default=_jsonable), encoding="utf-8")
    return {"video": str(video), "truth": str(out / f"{stem}_truth.npz"), "meta": meta}


def _jsonable(o: Any) -> Any:
    if isinstance(o, Trajectory):
        return "trajectory"
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def load_truth(stem_path: str | Path) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    p = Path(stem_path)
    z = np.load(p.with_name(p.stem + "_truth.npz"))
    meta = json.loads(p.with_suffix(".json").read_text(encoding="utf-8"))
    return {k: z[k] for k in z.files}, meta


def make_scene(name: str, *, size: tuple[int, int] = (1280, 720), fps: float = 30.0, seconds: float = 20.0,
               seed: int = 0, hfov_deg: float = 70.0, spec: dict | None = None) -> PhoneScene:
    spec = dict(spec or SCENES[name])
    cam = CameraGeom(int(size[0]), int(size[1]), focal_px(int(size[0]), hfov_deg))
    return PhoneScene(name, spec, cam, fps, float(seconds), int(seed))


def ruler_scene(*, size: tuple[int, int] = (1280, 720), fps: float = 30.0, z: float = 2.0, path_m: float = 1.0,
                move_s: float = 1.0, rest_s: float = 1.5, seed: int = 0, hfov_deg: float = 70.0,
                tv: bool = False) -> PhoneScene:
    """One phone at the standing distance: rest at the 0 mark, a 1 m move in about 1 s, rest
    (the ember_ruler recording, with known truth)."""
    seconds = 2 * rest_s + move_s + 0.5
    rng = np.random.default_rng(seed + 7)
    traj = ruler_trajectory(seconds, z, -path_m / 2, path_m, rest_s, move_s, rng=rng)
    spec = {"phones": [{"z": z, "trajectory": traj, "landscape": False}], "lamp": True, "tv": tv, "dz": 0.0}
    sc = make_scene("ruler", size=size, fps=fps, seconds=seconds, seed=seed, hfov_deg=hfov_deg, spec=spec)
    sc.extra_truth = {"ruler": {"t_move": rest_s, "move_s": move_s, "path_m": path_m, "z": z}}
    return sc


# The A4 calibration target held at the standing spot --------------------------------------------

def target_clip(path: str | Path, *, size: tuple[int, int] = (1280, 720), fps: float = 30.0, seconds: float = 3.0,
                hfov_deg: float = 70.0, distance_m: float = 2.0, tilt_deg: tuple[float, float, float] = (6.0, -9.0, 3.0),
                offset_m: tuple[float, float] = (0.08, -0.05), crf: int = 20, seed: int = 0) -> dict[str, Any]:
    """Render the printed target held by a person at distance_m (camera to the sheet's centre),
    tilted by tilt_deg (about x, y, z), with a little hand motion, room, noise and H.264.
    Returns the true focal length and pose."""
    from wfglink.ember import target as T
    from wfglink.synth.degrade import VideoWriter

    rng = np.random.default_rng(seed)
    cam = CameraGeom(int(size[0]), int(size[1]), focal_px(int(size[0]), hfov_deg))
    room = build_room({"lamp": True, "window": True}, cam, rng)
    ppm = 4.0
    tex = T.target_image(ppm, paper=0.75, ink=0.03)
    th, tw = tex.shape
    K = np.array([[cam.f, 0, cam.cx], [0, cam.f, cam.cy], [0, 0, 1.0]])
    holder = Person(distance_m + 0.35, lambda t: offset_m[0], offset_m[1] - 0.05, (0.03, 0.03, 0.04), (0.12, 0.17, 0.24))
    bank = rng.standard_normal((cam.height, cam.width, 3)).astype(np.float32)
    n = int(round(seconds * fps))
    with VideoWriter(Path(path), (cam.width, cam.height), fps, crf=crf, preset="veryfast", encoder_threads=2) as wr:
        for i in range(n):
            t = i / fps
            rx, ry, rz = (np.radians(a + 0.4 * math.sin(2 * math.pi * 0.7 * t + j)) for j, a in enumerate(tilt_deg))
            Rx = np.array([[1, 0, 0], [0, math.cos(rx), -math.sin(rx)], [0, math.sin(rx), math.cos(rx)]])
            Ry = np.array([[math.cos(ry), 0, math.sin(ry)], [0, 1, 0], [-math.sin(ry), 0, math.cos(ry)]])
            Rz = np.array([[math.cos(rz), -math.sin(rz), 0], [math.sin(rz), math.cos(rz), 0], [0, 0, 1]])
            R = Rz @ Ry @ Rx
            d = np.array([offset_m[0] + 0.004 * math.sin(2 * math.pi * 0.9 * t), offset_m[1], 0.0])
            d[2] = math.sqrt(distance_m ** 2 - d[0] ** 2 - d[1] ** 2)
            # texture px -> sheet metres (centre origin) -> camera
            S = np.array([[1 / (1000 * ppm), 0, -T.PAGE_MM[0] / 2000], [0, 1 / (1000 * ppm), -T.PAGE_MM[1] / 2000], [0, 0, 1]])
            Hm = K @ np.column_stack([R[:, 0], R[:, 1], d]) @ S
            frame = room.image.copy()
            polys = [np.round(p).astype(np.int32) for p in holder.polygons(t, cam)]
            for poly in polys:
                cv2.fillPoly(frame, [poly], (0.03, 0.03, 0.04))
            warped = cv2.warpPerspective(tex, Hm, (cam.width, cam.height), flags=cv2.INTER_AREA)
            mask = cv2.warpPerspective(np.ones_like(tex), Hm, (cam.width, cam.height), flags=cv2.INTER_LINEAR)
            light = 0.35
            frame = frame * (1 - mask[..., None]) + (warped * light)[..., None] * np.array([1.0, 1.0, 0.97], np.float32)
            frame = np.clip(frame * 1.0, 0, 1).astype(np.float32)
            enc = np.sqrt(frame) * 255.0 + np.roll(bank, i * 7, axis=1) * 2.0
            wr.write(np.clip(enc, 0, 255).astype(np.uint8), t)
    return {"focal_px": cam.f, "distance_m": distance_m, "tilt_deg": list(tilt_deg), "size": [cam.width, cam.height]}
