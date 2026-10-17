"""Test stand-ins for the booth's ember mode, coded against the shared contract.

FakeEmberPipeline plays core's wfglink.ember.pipeline.EmberPipeline for the booth tests
(live.ember_pipeline: ember_standin:FakeEmberPipeline, with tests/ on PYTHONPATH for child
processes). It mirrors the frame, then takes the phones from the generated scene's truth
(frame.meta["phones"], ui/phone_scene.py) or, without truth (a recording), finds bright warm
blobs and links them frame to frame, dropping blobs that do not move (room lights). It sets
the contract's attributes with setattr, as core does. It is a stand-in, not a tracker to
measure: the booth tests check what the screen does with its output.

ScriptedCamera is a camera Source whose open() can fail and whose frames can stop.
"""
from __future__ import annotations

import math
import time

import cv2
import numpy as np

from wfglink.io.frames import Frame
from wfglink.io.sources import Source, SourceError
from wfglink.render.scene import LiveState


class FakeEmberPipeline:
    def __init__(self, cfg: dict):
        cam, ember = cfg.get("camera") or {}, cfg.get("ember") or {}
        self.distance_m = float(ember.get("distance_m", 2.0))
        self.hfov_deg = float(cam.get("hfov_deg", 70.0))
        self.max_tracks = int(ember.get("max_tracks", 6))
        self.tracks: dict[int, dict] = {}
        self.next_id = 1
        self.frames = 0

    def _m_per_px(self, w: int) -> float:
        return self.distance_m / ((w / 2) / math.tan(math.radians(self.hfov_deg) / 2))

    def _blobs(self, img: np.ndarray) -> list[tuple[float, float]]:
        hot = ((img[..., 2] > 230) & (img[..., 1] > 120) & (img[..., 0] < 235)).astype(np.uint8)
        n, _, stats, cent = cv2.connectedComponentsWithStats(hot)
        return [tuple(cent[k]) for k in range(1, n) if 4 <= stats[k, cv2.CC_STAT_AREA] <= 2500]

    def process(self, frame: Frame) -> LiveState:
        self.frames += 1
        img = np.ascontiguousarray(frame.image[:, ::-1])
        h, w = img.shape[:2]
        t = float(frame.t)
        truth = frame.meta.get("phones")
        if truth is not None:
            seen = {int(p["id"]) + 100: (w - 1 - float(p["x"]), float(p["y"])) for p in truth}
        else:
            seen = {}
            free = dict(self.tracks)
            for x, y in self._blobs(img):
                best = min(free, key=lambda i: math.hypot(free[i]["pts"][-1][1] - x, free[i]["pts"][-1][2] - y), default=None)
                if best is not None and math.hypot(free[best]["pts"][-1][1] - x, free[best]["pts"][-1][2] - y) < 80:
                    seen[best] = (x, y)
                    del free[best]
                else:
                    seen[self.next_id] = (x, y)
                    self.next_id += 1
        for i, (x, y) in seen.items():
            tr = self.tracks.setdefault(i, {"pts": [], "t0": t, "moved_at": t})
            if tr["pts"] and math.hypot(tr["pts"][-1][1] - x, tr["pts"][-1][2] - y) > 1.5:
                tr["moved_at"] = t
            tr["pts"] = [p for p in tr["pts"] if t - p[0] <= 0.6] + [(t, x, y)]
        for i in [i for i in self.tracks if i not in seen]:
            del self.tracks[i]
        mpp = self._m_per_px(w)
        embers, trails, ages, cells = [], [], [], {}
        live = [(i, tr) for i, tr in self.tracks.items() if t - tr["moved_at"] < 1.0][: self.max_tracks]
        for i, tr in live:
            pts = tr["pts"]
            speed = None
            if len(pts) >= 4 and pts[-1][0] > pts[0][0]:
                dt = pts[-1][0] - pts[-4][0]
                vx, vy = (pts[-1][1] - pts[-4][1]) / dt, (pts[-1][2] - pts[-4][2]) / dt
                speed = math.hypot(vx, vy) * mpp
                cell = (min(8, int(pts[-1][2] / h * 9)), min(15, int(pts[-1][1] / w * 16)))
                cells.setdefault(cell, []).append((vx * mpp, vy * mpp))
            embers.append({"id": i, "speed_m_s": speed, "x": pts[-1][1], "y": pts[-1][2], "age_s": t - tr["t0"]})
            trails.append(np.array([(p[1], p[2]) for p in pts]))
            ages.append(0.0)
        field = np.zeros((9, 16, 3))
        for (r, c), v in cells.items():
            field[r, c] = (np.median([a for a, _ in v]), np.median([b for _, b in v]), 6)
        speeds = [e["speed_m_s"] for e in embers if e["speed_m_s"] is not None]
        s = LiveState(image=img, t=t, detections=np.array([(e["x"], e["y"]) for e in embers]).reshape(-1, 2),
                      trails=trails, trail_ages=ages, speed=float(np.median(speeds)) if speeds else None,
                      field_uvn=field, field_min_n=5)
        for k, v in (("mode", "ember"), ("embers", embers), ("ember_count", len(embers)), ("speed_unit", "m/s"),
                     ("measured_at_m", self.distance_m), ("calibrated", False), ("camera_state", "ok")):
            setattr(s, k, v)
        return s


class BrokenEmberPipeline:
    """An ember pipeline that cannot be built (a missing module, a bad install)."""

    def __init__(self, cfg: dict):
        raise ImportError("No module named 'wfglink.ember'")


class ScriptedCamera(Source):
    """A camera stand-in: open() fails while fail_open is true; frames stop after stop_after frames."""

    kind = "camera"
    is_live = True

    def __init__(self, inner: Source | None = None, fail_open: bool = False, stop_after: int | None = None,
                 name: str = "FaceTime HD Camera", open_s: float = 0.0):
        super().__init__(name)
        self.inner, self.fail_open, self.stop_after, self.open_s = inner, fail_open, stop_after, open_s
        self.opened = self.closed = 0

    def open(self) -> None:
        if self.open_s:                  # a camera that takes its time to open (a slow USB webcam)
            time.sleep(self.open_s)
        if self.fail_open:
            raise SourceError("no camera found")
        self.opened += 1
        if self.inner is not None:
            self.inner.open()

    def read(self) -> Frame | None:
        if self.stop_after is not None and self._index >= self.stop_after:
            time.sleep(0.01)
            return None
        f = self.inner.read() if self.inner is not None else Frame(np.zeros((90, 160, 3), np.uint8), time.monotonic(), 0)
        time.sleep(1 / 60)
        return Frame(f.image, time.monotonic(), self._next_index(), time.monotonic(), {"camera": self.name})

    def close(self) -> None:
        self.closed += 1
        if self.inner is not None:
            self.inner.close()
        self.inner = None            # tests keep the cameras to count opens and closes, not their pictures
