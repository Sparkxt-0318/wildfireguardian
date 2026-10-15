"""A generated phone scene: ember mode without a camera (live --synthetic, the demo gate, tests).

People in a lit room hold up phones showing the ember page (booth/ember/index.html): a black
screen with a centred glowing disc of radius 0.36 x the screen's shorter side, its radial
gradient #FFF1D6, #FFC266 at 18 percent, #FF8A1F at 45 percent, rgba(255,90,0,0.35) at 70
percent and transparent at the edge, flickering slightly (brightness 0.85 to 1.0, scale 0.97
to 1.0, smoothly at 2 to 6 Hz). The phones stand 1.2 to 2.8 m from the camera and move like
hands do (up to a few m/s), with motion blur over the exposure; one walks out of the picture
and comes back. The room has static bright objects that must never become embers: a ceiling
light, a window and a warm desk lamp.

Every frame's meta carries the truth: {"camera": label, "synthetic": True, "phones": [{"id",
"x", "y" (image px), "vx", "vy" (px/s), "z_m", "speed_m_s" (true, at its own distance),
"speed_m_s_ref" (projected to ember.distance_m, what the screen should show)}]}.

This is the booth's own simple generator. phone_scene_source() is the one place that builds
ember mode's generated scene; when core's generator and FakeCameraSource are in the tree,
it returns those instead (see its docstring), and nothing else changes.
"""
from __future__ import annotations

import math
import time

import cv2
import numpy as np

from wfglink.io.frames import Frame
from wfglink.io.sources import Source

# The ember page's look (contract with booth/ember/index.html): gradient stops as (position,
# (B, G, R), alpha), the disc radius as a fraction of the screen's shorter side.
PAGE_STOPS = [(0.0, (214, 241, 255), 1.0), (0.18, (102, 194, 255), 1.0), (0.45, (31, 138, 255), 1.0),
              (0.70, (0, 90, 255), 0.35), (1.0, (0, 90, 255), 0.0)]
PAGE_DISC_FRAC = 0.36
PHONE_M = (0.0715, 0.147)     # phone body, width and height in metres (a 6.1 inch phone)
SCREEN_M = (0.066, 0.142)     # its screen


def _disc_sprite(radius_px: int = 48) -> np.ndarray:
    """The page's disc premultiplied by its alpha over a black screen: float32 (2r+1, 2r+1, 3), 0 to 1."""
    r = radius_px
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1].astype(np.float32)
    d = np.sqrt(xx * xx + yy * yy) / r
    pos = np.array([s[0] for s in PAGE_STOPS], np.float32)
    out = np.zeros((2 * r + 1, 2 * r + 1, 3), np.float32)
    alpha = np.interp(d.ravel(), pos, [s[2] for s in PAGE_STOPS]).reshape(d.shape)
    for c in range(3):
        col = np.interp(d.ravel(), pos, [s[1][c] / 255.0 for s in PAGE_STOPS]).reshape(d.shape)
        out[..., c] = col * alpha
    out[d > 1.0] = 0.0
    return out


class PhoneSceneSource(Source):
    """Phones showing the ember page in a lit room, rendered live (see the module docstring)."""

    kind = "synthetic"
    is_live = True

    def __init__(self, width: int = 1280, height: int = 720, fps: float = 30.0, phones: int = 4, seed: int = 0,
                 realtime: bool = True, hfov_deg: float = 70.0, distance_m: float = 2.0, exposure_s: float = 1 / 60,
                 label: str = "synthetic phones", **_: object):
        super().__init__(label)
        self.w, self.h, self.fps = int(width), int(height), float(fps)
        self.realtime = bool(realtime)
        self.rng = np.random.default_rng(seed)
        self.focal_px = (self.w / 2) / math.tan(math.radians(hfov_deg) / 2)
        self.ref_m = float(distance_m)
        self.exposure_s = float(exposure_s)
        self._t = 0.0
        self._wall0: float | None = None
        self._sprite = _disc_sprite()
        self._bg = self._room()
        self._noise = [self._noise_pair() for _ in range(4)]
        self._phones = [self._new_phone(k, phones) for k in range(phones)]
        self.info = {"backend": "synthetic", "width": self.w, "height": self.h, "fps": self.fps,
                     "focal_px": self.focal_px, "distance_m": self.ref_m}

    # Scene ---------------------------------------------------------------------------------
    def _room(self) -> np.ndarray:
        """A lit room: wall, floor, door, poster, and the static bright objects."""
        h, w, rng = self.h, self.w, self.rng
        yy = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
        wall = np.array([118, 128, 136], np.float32) * (1.05 - 0.25 * yy)               # light grey-beige (B, G, R)
        img = np.repeat(wall, w, axis=1)
        floor = int(0.78 * h)
        img[floor:] = np.array([60, 72, 84], np.float32)
        tex = cv2.GaussianBlur(rng.normal(0, 1, (h // 4, w // 4)).astype(np.float32), (0, 0), 2)
        img += 4.0 * cv2.resize(tex, (w, h))[..., None]
        img = np.clip(img, 0, 255).astype(np.uint8)
        cv2.rectangle(img, (int(0.08 * w), int(0.18 * h)), (int(0.2 * w), floor), (70, 92, 120), -1)          # door
        cv2.rectangle(img, (int(0.55 * w), int(0.2 * h)), (int(0.68 * w), int(0.42 * h)), (90, 60, 50), -1)    # poster
        cv2.rectangle(img, (int(0.36 * w), 0), (int(0.62 * w), int(0.035 * h)), (255, 255, 255), -1)          # ceiling light
        cv2.rectangle(img, (int(0.80 * w), int(0.12 * h)), (int(0.97 * w), int(0.5 * h)), (250, 244, 236), -1)  # window
        cv2.circle(img, (int(0.72 * w), int(0.62 * h)), max(6, int(0.018 * w)), (120, 205, 255), -1)          # warm desk lamp
        img = cv2.GaussianBlur(img, (0, 0), 1.2)
        glow = cv2.GaussianBlur(np.where(img.max(axis=2, keepdims=True) > 200, img, 0).astype(np.float32), (0, 0), 9)
        return np.clip(img + 0.5 * glow, 0, 255).astype(np.uint8)

    def _noise_pair(self) -> tuple[np.ndarray, np.ndarray]:
        n = self.rng.normal(0, 2.2, (self.h, self.w, 1)).astype(np.float32).repeat(3, axis=2)
        return np.clip(n, 0, 255).astype(np.uint8), np.clip(-n, 0, 255).astype(np.uint8)

    def _new_phone(self, k: int, n: int) -> dict:
        rng = self.rng
        return {"id": k, "z": float(rng.uniform(1.2, 2.8)),
                "home": (float((k + 0.5) / n * 2.4 - 1.2), float(rng.uniform(-0.15, 0.15))),   # metres from the optical axis
                "ax": rng.uniform(0.15, 0.45, 2), "fx": rng.uniform(0.12, 0.55, 2), "px": rng.uniform(0, 2 * math.pi, 2),
                "ay": rng.uniform(0.08, 0.3, 2), "fy": rng.uniform(0.15, 0.6, 2), "py": rng.uniform(0, 2 * math.pi, 2),
                "ff": rng.uniform(2.0, 6.0, 2), "fp": rng.uniform(0, 2 * math.pi, 2), "tilt": float(rng.uniform(-12, 12)),
                "away": (8.0, 6.0) if k == n - 1 else None}                                     # walks out at 8 s for 6 s, every 20 s

    def _pos_m(self, ph: dict, t: float) -> tuple[float, float]:
        x = ph["home"][0] + sum(a * math.sin(2 * math.pi * f * t + p) for a, f, p in zip(ph["ax"], ph["fx"], ph["px"]))
        y = ph["home"][1] + sum(a * math.sin(2 * math.pi * f * t + p) for a, f, p in zip(ph["ay"], ph["fy"], ph["py"]))
        if ph["away"] is not None:
            start, dur = ph["away"]
            u = (t % 20.0) - start
            if 0.0 <= u <= dur:
                x += 3.0 * math.sin(math.pi * u / dur)                                          # walks off to the side and back
        return x, y

    def _to_px(self, xm: float, ym: float, z: float) -> tuple[float, float]:
        return self.w / 2 + xm * self.focal_px / z, self.h * 0.45 + ym * self.focal_px / z

    # Rendering -----------------------------------------------------------------------------
    def _draw_person(self, img: np.ndarray, ph: dict, t: float) -> None:
        z = ph["z"]
        xm = ph["home"][0] + 0.3 * sum(a * math.sin(2 * math.pi * f * t + p) for a, f, p in zip(ph["ax"], ph["fx"], ph["px"]))
        if ph["away"] is not None:
            u = (t % 20.0) - ph["away"][0]
            if 0.0 <= u <= ph["away"][1]:
                xm += 3.0 * math.sin(math.pi * u / ph["away"][1])
        cx, cy = self._to_px(xm, 0.0, z)
        s = self.focal_px / z
        color = (52 + 10 * ph["id"], 46, 44)
        cv2.ellipse(img, (int(cx), int(cy + 0.55 * s)), (int(0.24 * s), int(0.6 * s)), 0, 0, 360, color, -1)   # torso
        cv2.circle(img, (int(cx), int(cy - 0.22 * s)), int(0.11 * s), (88, 110, 140), -1)                     # head

    def _draw_phone(self, img: np.ndarray, ph: dict, t: float) -> dict | None:
        z = ph["z"]
        s = self.focal_px / z
        flick = 0.925 + 0.075 * math.sin(2 * math.pi * ph["ff"][0] * t + ph["fp"][0]) * math.cos(math.pi * ph["ff"][1] * t + ph["fp"][1])
        scale = 0.985 + 0.015 * math.sin(2 * math.pi * ph["ff"][1] * t + ph["fp"][0])
        x0, y0 = self._to_px(*self._pos_m(ph, t), z)
        dt = 1e-3
        x1, y1 = self._to_px(*self._pos_m(ph, t + dt), z)
        vx, vy = (x1 - x0) / dt, (y1 - y0) / dt
        if not (-0.1 * self.w < x0 < 1.1 * self.w):
            return None
        # The phone body and its black screen (the page's background), at mid exposure.
        bw, bh = PHONE_M[0] * s, PHONE_M[1] * s
        xm, ym = x0 + vx * self.exposure_s / 2, y0 + vy * self.exposure_s / 2
        box = cv2.boxPoints(((xm, ym), (bw, bh), ph["tilt"])).astype(np.int32)
        cv2.fillConvexPoly(img, box, (26, 24, 24), lineType=cv2.LINE_AA)
        sbox = cv2.boxPoints(((xm, ym), (SCREEN_M[0] * s, SCREEN_M[1] * s), ph["tilt"])).astype(np.int32)
        cv2.fillConvexPoly(img, sbox, (14, 12, 12), lineType=cv2.LINE_AA)
        # The glowing disc spread over the exposure (motion blur), plus the lens's soft bloom,
        # added as light in a patch around the phone.
        r = max(2, int(round(PAGE_DISC_FRAC * min(SCREEN_M) * s * scale)))
        spr = cv2.resize(self._sprite, (2 * r + 1, 2 * r + 1), interpolation=cv2.INTER_AREA) * (1.35 * flick)
        n_sub = 1 + min(8, int(math.hypot(vx, vy) * self.exposure_s / max(1.0, r * 0.5)))
        centres = [(int(round(x0 + vx * self.exposure_s * (k + 0.5) / n_sub)), int(round(y0 + vy * self.exposure_s * (k + 0.5) / n_sub)))
                   for k in range(n_sub)]
        m = r + 24                                                     # the bloom reaches about 3 sigma
        xa, xb = max(0, min(c[0] for c in centres) - m), min(self.w, max(c[0] for c in centres) + m + 1)
        ya, yb = max(0, min(c[1] for c in centres) - m), min(self.h, max(c[1] for c in centres) + m + 1)
        if xa < xb and ya < yb:
            acc = np.zeros((yb - ya, xb - xa, 3), np.float32)
            for cx, cy in centres:
                pa, pb, qa, qb = cy - r - ya, cy + r + 1 - ya, cx - r - xa, cx + r + 1 - xa
                sy0, sx0 = max(0, -pa), max(0, -qa)
                pa, qa, pb, qb = max(pa, 0), max(qa, 0), min(pb, yb - ya), min(qb, xb - xa)
                if pa < pb and qa < qb:
                    acc[pa:pb, qa:qb] += spr[sy0:sy0 + pb - pa, sx0:sx0 + qb - qa] / n_sub
            light = acc + 0.35 * cv2.GaussianBlur(acc, (0, 0), 8.0)
            patch = img[ya:yb, xa:xb].astype(np.float32) + light * 255.0
            img[ya:yb, xa:xb] = np.clip(patch, 0, 255).astype(np.uint8)
        sp = math.hypot(vx, vy)
        return {"id": ph["id"], "x": round(float(x0), 2), "y": round(float(y0), 2), "vx": round(float(vx), 2),
                "vy": round(float(vy), 2), "z_m": round(z, 3), "speed_m_s": round(sp * z / self.focal_px, 4),
                "speed_m_s_ref": round(sp * self.ref_m / self.focal_px, 4)}

    def open(self) -> None:
        self._wall0 = time.monotonic()

    def read(self) -> Frame | None:
        t = self._t
        img = self._bg.copy()
        truth = []
        for ph in sorted(self._phones, key=lambda q: -q["z"]):        # far ones first
            self._draw_person(img, ph, t)
        for ph in sorted(self._phones, key=lambda q: -q["z"]):
            d = self._draw_phone(img, ph, t)
            if d is not None and 0 <= d["x"] < self.w and 0 <= d["y"] < self.h:
                truth.append(d)
        frame = img
        pos, neg = self._noise[self._index % len(self._noise)]
        frame = cv2.subtract(cv2.add(frame, pos), neg)
        self._t += 1.0 / self.fps
        if self.realtime and self._wall0 is not None:
            wait = (self._wall0 + self._t) - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            elif wait < -0.5:
                self._wall0 = time.monotonic() - self._t
        return Frame(frame, t, self._next_index(), time.monotonic(),
                     {"camera": self.name, "synthetic": True, "phones": sorted(truth, key=lambda d: d["id"])})


def phone_scene_source(cfg: dict | None = None, seed: int | None = None, realtime: bool = True) -> Source:
    """Ember mode's generated phone scene, played like a camera (live --synthetic, the demo gate).

    Core's FakeCameraSource renders wfglink.ember.synth's "booth" scene (phones showing the
    ember page in a room), the scenes the ember detector and tracker were built on, at the
    camera's configured size. Its frames carry meta {"camera": name, "synthetic": True}.
    PhoneSceneSource above stays for tests that need a scene without core's renderer.
    """
    from wfglink.io.camera import FakeCameraSource

    cfg = cfg or {}
    if seed is None:
        seed = int((cfg.get("booth") or {}).get("synthetic_seed", 1))
    return FakeCameraSource(scene="booth", realtime=realtime, cfg=cfg, seed=seed)
