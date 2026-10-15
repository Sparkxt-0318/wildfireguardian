"""`python -m wfglink calibrate`: the camera's focal length from the printed A4 target.

The target (booth/ember/calibration_target_A4.pdf, wfglink.ember.target) is held flat at
the standing spot, facing the camera, at ember.distance_m (or --distance-m) from the lens
to the centre of the sheet. Per frame (the camera's own picture, not mirrored: ArUco
markers cannot be read in a mirror):

1. The four markers are found (OpenCV ArUco, corners refined to sub-pixel); at least
   ember.calibrate.min_markers are needed.
2. The sheet's pose is solved (OpenCV solvePnP, planar IPPE, then Levenberg-Marquardt) with
   the principal point at the picture's centre, square pixels and no lens distortion, for a
   trial focal length f. The distance from the camera to the sheet's centre then scales with
   f, so f is corrected by the ratio of the stated distance to the solved one until they
   agree. A tilted sheet is handled by the pose, not mistaken for a smaller one.
3. Frames whose marker corners the solved pose reprojects worse than
   ember.calibrate.max_rms_px (RMS) are skipped.

It finishes when the last ember.calibrate.window good frames agree within
ember.calibrate.stable_frac (90th minus 10th percentile, over the median) and reports their
median, the equivalent horizontal field of view 2 atan(W / 2f) and the scale
m/px = distance / f. It writes camera.focal_px and ember.calibration (date, camera, size,
focal_px, hfov_deg, distance_m, m_per_px, target, frames, spread, rms_px) and ember.distance_m
to configs/booth_local.yaml, keeping the file's other keys.

Live, the camera picture shows fullscreen (mirrored, like a mirror, with the markers
outlined and the progress); Esc cancels. With --video FILE it runs on a recording, without a
window. Error sources: the distance is measured by hand (a 2 cm error at 2 m is 1 percent);
the print scale (the 100 mm line); lens distortion away from the picture's centre.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from wfglink.config import LOCAL_CONFIG
from wfglink.ember import target as T


def _cc(cfg: dict) -> dict[str, Any]:
    return ((cfg.get("ember") or {}).get("calibrate") or {})


class TargetDetector:
    def __init__(self):
        params = cv2.aruco.DetectorParameters()
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        params.cornerRefinementWinSize = 4
        self.det = cv2.aruco.ArucoDetector(T.dictionary(), params)

    def find(self, image: np.ndarray) -> tuple[list[int], np.ndarray, np.ndarray]:
        """(marker ids, image points (4n, 2), object points (4n, 3)) of the target's markers."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        corners, ids, _ = self.det.detectMarkers(gray)
        if ids is None:
            return [], np.zeros((0, 2)), np.zeros((0, 3))
        keep = [(int(i), c.reshape(4, 2)) for i, c in zip(ids.ravel(), corners) if int(i) in T.IDS]
        seen: dict[int, np.ndarray] = {}
        for i, c in keep:
            seen.setdefault(i, c)            # a marker id seen twice is not this target's; keep the first
        ids_ok = sorted(seen)
        if not ids_ok:
            return [], np.zeros((0, 2)), np.zeros((0, 3))
        img = np.concatenate([seen[i] for i in ids_ok]).astype(np.float64)
        return ids_ok, img, T.object_points(ids_ok)


def focal_from_view(img_pts: np.ndarray, obj_pts: np.ndarray, size: tuple[int, int], distance_m: float,
                    f0: float) -> tuple[float, float, np.ndarray, np.ndarray] | None:
    """(f, reprojection RMS px, rvec, tvec) such that the sheet's centre is distance_m away."""
    w, h = size
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    f = float(f0)
    rvec = tvec = None
    K = None
    for _ in range(30):
        K = np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]])
        ok, rvec, tvec = cv2.solvePnP(obj_pts, img_pts, K, None, flags=cv2.SOLVEPNP_IPPE)
        if not ok:
            return None
        rvec, tvec = cv2.solvePnPRefineLM(obj_pts, img_pts, K, None, rvec, tvec)
        d = float(np.linalg.norm(tvec))
        if not math.isfinite(d) or d <= 0:
            return None
        f_new = f * distance_m / d
        done = abs(f_new - f) < 1e-7 * f
        f = f_new
        if done:
            break
    K = np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]])
    rvec, tvec = cv2.solvePnPRefineLM(obj_pts, img_pts, K, None, rvec, tvec)
    proj, _ = cv2.projectPoints(obj_pts, rvec, tvec, K, None)
    rms = float(np.sqrt(np.mean(np.sum((proj.reshape(-1, 2) - img_pts) ** 2, axis=1))))
    return f, rms, rvec, tvec


class Calibrator:
    """Feed frames; it says when the focal length is stable and what it is."""

    def __init__(self, cfg: dict, distance_m: float):
        c = _cc(cfg)
        self.distance_m = float(distance_m)
        self.min_markers = int(c.get("min_markers", 3))
        self.max_rms = float(c.get("max_rms_px", 1.5))
        self.window = int(c.get("window", 30))
        self.stable_frac = float(c.get("stable_frac", 0.01))
        self.hfov0 = float((cfg.get("camera") or {}).get("hfov_deg", 70.0))
        self.det = TargetDetector()
        self.good: list[tuple[float, float]] = []      # (f, rms)
        self.frames = 0
        self.size: tuple[int, int] | None = None
        self.last: dict[str, Any] = {}

    def add(self, image: np.ndarray) -> dict[str, Any]:
        """This frame's result: markers (ids and image corners), f and rms when solved."""
        self.frames += 1
        h, w = image.shape[:2]
        if self.size not in (None, (w, h)):
            self.good.clear()                          # the picture size changed: start again
        self.size = (w, h)
        ids, img, obj = self.det.find(image)
        out: dict[str, Any] = {"ids": ids, "corners": img, "ok": False}
        if len(ids) >= self.min_markers:
            f0 = (w / 2.0) / math.tan(math.radians(self.hfov0) / 2.0)
            got = focal_from_view(img, obj, (w, h), self.distance_m, f0)
            if got is not None:
                f, rms, _, _ = got
                out.update({"f": f, "rms": rms})
                if rms <= self.max_rms:
                    self.good.append((f, rms))
                    out["ok"] = True
        self.last = out
        return out

    def spread(self, fs: np.ndarray) -> float:
        return float((np.percentile(fs, 90) - np.percentile(fs, 10)) / np.median(fs))

    def stable(self) -> bool:
        if len(self.good) < self.window:
            return False
        fs = np.array([f for f, _ in self.good[-self.window:]])
        return self.spread(fs) <= self.stable_frac

    def progress(self) -> float:
        return min(1.0, len(self.good) / max(self.window, 1))

    def result(self, require_stable: bool = True) -> dict[str, Any]:
        if not self.good or self.size is None:
            raise ValueError("the target was never found: hold it flat at the standing spot, facing the camera, "
                             "with all four corner markers in the picture")
        use = self.good[-self.window:] if self.stable() else self.good
        if require_stable and not self.stable():
            raise ValueError(f"no stable result: {len(self.good)} good frames, spread "
                             f"{self.spread(np.array([f for f, _ in self.good[-self.window:]])):.4f}")
        fs = np.array([f for f, _ in use])
        f = float(np.median(fs))
        w, h = self.size
        return {"focal_px": round(f, 2), "hfov_deg": round(math.degrees(2 * math.atan(w / 2.0 / f)), 2),
                "distance_m": self.distance_m, "m_per_px": round(self.distance_m / f, 7), "size": [w, h],
                "frames": len(fs), "spread": round(self.spread(fs), 5),
                "rms_px": round(float(np.median([r for _, r in use])), 3), "stable": self.stable(),
                "target": T.DESCRIPTION}


def write_local(record: dict[str, Any], path: str | Path = LOCAL_CONFIG) -> Path:
    """Write camera.focal_px, ember.distance_m and ember.calibration into configs/booth_local.yaml,
    keeping its other keys (its comments are not kept)."""
    import yaml

    p = Path(path)
    doc: dict[str, Any] = {}
    if p.exists():
        doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    doc.setdefault("camera", {})["focal_px"] = record["focal_px"]
    em = doc.setdefault("ember", {})
    em["distance_m"] = record["distance_m"]
    em["calibration"] = record
    head = ("# Machine-specific settings (not in git). python -m wfglink calibrate rewrites camera.focal_px,\n"
            "# ember.distance_m and ember.calibration and keeps the other keys (comments are not kept).\n")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(head + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return p


def calibrate_video(video: str | Path, cfg: dict, distance_m: float) -> dict[str, Any]:
    """Run the calibration on a recording (no window)."""
    from wfglink.io.sources import FileSource

    cal = Calibrator(cfg, distance_m)
    with FileSource(video) as src:
        while True:
            f = src.read()
            if f is None:
                break
            cal.add(f.image)
            if cal.stable():
                break
    res = cal.result(require_stable=False)
    res.update({"camera": None, "source": str(video)})
    return res


TEXT = {
    "hold": ("A4 표적을 서는 자리에서 카메라를 향해 평평하게 들어 주세요",
             "Hold the A4 target flat at the standing spot, facing the camera"),
    "markers": ("표시 {n}/4개 보임", "{n} of 4 markers seen"),
    "measuring": ("측정 중 {p}%", "Measuring {p}%"),
    "saved": ("저장했습니다: 초점거리 {f:.0f} px, 화각 {h:.1f}°, {d:g} m에서 1 px = {mm:.2f} mm",
              "Saved: focal length {f:.0f} px, field of view {h:.1f}°, 1 px = {mm:.2f} mm at {d:g} m"),
    "esc": ("Esc 취소", "Esc cancels"),
}


def calibrate_live(cfg: dict, distance_m: float, *, screen: str | None = None, timeout_s: float | None = None,
                   source: Any = None) -> dict[str, Any] | None:
    """Fullscreen preview with the camera; returns the result, or None when cancelled or timed out."""
    from wfglink.ember.preview import Overlay, run_preview

    c = _cc(cfg)
    timeout_s = float(timeout_s or c.get("timeout_s", 90))
    cal = Calibrator(cfg, distance_m)
    state: dict[str, Any] = {"result": None}

    def on_frame(frame) -> Overlay:
        r = cal.add(frame.image)
        w = frame.image.shape[1]
        polys = [np.column_stack([w - 1 - q[:, 0], q[:, 1]]) for q in r["corners"].reshape(-1, 4, 2)]
        lines = [TEXT["hold"][0], TEXT["hold"][1], TEXT["markers"][0].format(n=len(r["ids"])) + "  ·  "
                 + TEXT["markers"][1].format(n=len(r["ids"]))]
        if state["result"] is None and cal.stable():
            res = cal.result()
            state["result"] = res
        if state["result"] is not None:
            res = state["result"]
            mm = res["m_per_px"] * 1000
            lines = [TEXT["saved"][0].format(f=res["focal_px"], h=res["hfov_deg"], d=distance_m, mm=mm),
                     TEXT["saved"][1].format(f=res["focal_px"], h=res["hfov_deg"], d=distance_m, mm=mm)]
            return Overlay(lines=lines, polygons=polys, done=True, color="#30D158", text_color="#30D158")
        if cal.good:
            p = int(round(100 * cal.progress()))
            lines.append(TEXT["measuring"][0].format(p=p) + "  ·  " + TEXT["measuring"][1].format(p=p))
        lines.append(TEXT["esc"][0] + "  ·  " + TEXT["esc"][1])
        # Green outlines once the markers fit the sheet; orange while they are seen but do not fit.
        return Overlay(lines=lines, polygons=polys, color="#30D158" if r["ok"] else "#FF9F0A")

    info = run_preview(cfg, on_frame, screen=screen, timeout_s=timeout_s, source=source, done_hold_s=4.0)
    res = state["result"]
    if res is None and not info.get("cancelled") and len(cal.good) >= cal.window:
        res = cal.result(require_stable=False)     # timed out unsteady: the median, marked not stable
    if res is None:
        return None
    res.update({"camera": info.get("camera"), "unique_id": info.get("unique_id"), "backend": info.get("backend")})
    return res
