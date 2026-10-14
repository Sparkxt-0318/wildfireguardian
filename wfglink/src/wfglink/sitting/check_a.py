"""Check A: camera permission, devices, formats, exposure lock, capture backends, timing.

Each function returns a plain dict for the sitting report and never raises: a failure is
recorded with its error text, because the sitting must finish and report either way.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from wfglink import PROJECT_ROOT
from wfglink.io.devices import AutoCameraSource, list_cameras, pick_camera
from wfglink.io.sources import CameraSpec, OpenCVCameraSource, PyAVCameraSource, SourceError


def permission() -> dict[str, Any]:
    if sys.platform != "darwin":
        return {"status": "not_applicable", "platform": sys.platform}
    try:
        from wfglink.io import macos

        before = macos.authorization_status()
        after = macos.request_camera_access(timeout_s=60)
        return {"before": before, "status": after}
    except Exception as exc:
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}


def devices(cfg: dict) -> dict[str, Any]:
    found = list_cameras()
    devs = found.get("devices", [])
    iphone = pick_camera(devs, "iphone", cfg["camera"].get("iphone_uid"))
    webcam = pick_camera(devs, "webcam", None, cfg["camera"].get("webcam_match"))
    fps_60 = False
    if iphone:
        for f in iphone.get("formats", []):
            if f.get("width") == 1920 and f.get("height") == 1080 and any(r[1] >= 59 for r in f.get("fps_ranges", [])):
                fps_60 = True
    return {**found, "iphone": iphone and {k: iphone.get(k) for k in ("name", "unique_id", "opencv_index", "ffmpeg_index", "is_continuity_camera")},
            "webcam": webcam and {k: webcam.get(k) for k in ("name", "unique_id", "opencv_index", "ffmpeg_index")},
            "iphone_offers_1080p60": fps_60}


def exposure_probe(device: dict | None) -> dict[str, Any]:
    if device is None:
        return {"status": "skipped", "reason": "no iPhone found"}
    if sys.platform != "darwin":
        return {"status": "not_applicable"}
    try:
        from wfglink.io import macos

        return {"status": "done", **macos.probe_exposure_lock(device["unique_id"])}
    except Exception as exc:
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}


def capture_test(source, seconds: float = 6.0) -> dict[str, Any]:
    """Open a source, read for `seconds`, and measure what actually arrives."""
    out: dict[str, Any] = {"label": source.name}
    t_open = time.monotonic()
    try:
        source.open()
    except (SourceError, Exception) as exc:
        return {**out, "ok": False, "stage": "open", "error": str(exc)[:500]}
    out["open_s"] = round(time.monotonic() - t_open, 2)
    out["info"] = {k: v for k, v in getattr(source, "info", {}).items() if k not in ("metadata",)}
    frames, times, identical, lumas = 0, [], 0, []
    first_at = None
    prev = None
    t_end = time.monotonic() + seconds
    shape = None
    err = None
    try:
        while time.monotonic() < t_end:
            f = source.read()
            if f is None:
                time.sleep(0.005)
                continue
            now = time.monotonic()
            if first_at is None:
                first_at = now - t_open
            frames += 1
            times.append(now)
            shape = f.image.shape
            small = f.image[::16, ::16].astype(np.int16)
            if prev is not None and np.array_equal(small, prev):
                identical += 1
            prev = small
            lumas.append(float(small.mean()))
    except Exception as exc:
        err = str(exc)[:500]
    finally:
        try:
            source.close()
        except Exception:
            pass
    fps = (len(times) - 1) / (times[-1] - times[0]) if len(times) > 2 else 0.0
    gaps = np.diff(times) if len(times) > 2 else np.array([0.0])
    return {**out, "ok": frames > 0 and err is None, "frames": frames, "first_frame_s": first_at and round(first_at, 2),
            "fps_measured": round(fps, 2), "max_gap_ms": round(float(gaps.max() * 1000), 1),
            "width": shape[1] if shape else None, "height": shape[0] if shape else None,
            "identical_fraction": round(identical / max(frames - 1, 1), 3),
            "mean_luma": round(float(np.mean(lumas)), 1) if lumas else None, "error": err}


def capture_matrix(cfg: dict, devs: dict[str, Any], seconds: float = 6.0) -> list[dict[str, Any]]:
    """Every (role, backend, fps) combination worth testing."""
    results = []
    all_devs = devs.get("devices", [])
    for role in ("iphone", "webcam"):
        info = devs.get(role)
        if not info:
            results.append({"role": role, "ok": False, "stage": "find", "error": "device not found"})
            continue
        dev = next((d for d in all_devs if d.get("unique_id") == info["unique_id"]), info)
        fps_list = [30.0] + ([60.0] if role == "iphone" and devs.get("iphone_offers_1080p60") else [])
        for fps in fps_list:
            spec = CameraSpec(dev.get("name") if sys.platform == "darwin" else dev.get("unique_id"),
                              cfg["camera"]["width"], cfg["camera"]["height"], fps)
            r = capture_test(PyAVCameraSource(spec, label=f"{role}-pyav-{fps:g}"), seconds)
            results.append({"role": role, "backend": "pyav", "fps_requested": fps, **r})
            if dev.get("opencv_index") is not None and fps == 30.0:
                r = capture_test(OpenCVCameraSource(int(dev["opencv_index"]), spec, label=f"{role}-opencv"), seconds)
                results.append({"role": role, "backend": "opencv", "fps_requested": fps, **r})
    return results


def best_backend(results: list[dict[str, Any]], role: str, min_width: int = 1280, min_fps: float = 24.0) -> dict | None:
    good = [r for r in results if r.get("role") == role and r.get("ok") and (r.get("width") or 0) >= min_width
            and r.get("fps_measured", 0) >= min_fps and r.get("identical_fraction", 1) < 0.5]
    if not good:
        good = [r for r in results if r.get("role") == role and r.get("ok") and r.get("frames", 0) > 10]
    if not good:
        return None
    good.sort(key=lambda r: ((r.get("width") or 0) >= 1920, r.get("backend") == "pyav", r.get("fps_measured", 0)), reverse=True)
    return good[0]


def app_fallback(uid: str | None, out_json: Path, seconds: float = 6.0) -> dict[str, Any]:
    """Build the alias .app and rerun the iPhone capture test inside it (macOS only)."""
    if sys.platform != "darwin":
        return {"status": "not_applicable"}
    built = subprocess.run(["bash", str(PROJECT_ROOT / "scripts" / "make_app.sh")], capture_output=True, text=True)
    if built.returncode != 0:
        return {"status": "build_failed", "stderr": built.stderr[-1500:]}
    app = PROJECT_ROOT / "dist" / "WFGLink.app"
    out_json.unlink(missing_ok=True)
    args = ["open", "-W", "-n", str(app), "--args", "camera-test", "--out", str(out_json), "--seconds", str(seconds)]
    if uid:
        args += ["--uid", uid]
    t0 = time.monotonic()
    run = subprocess.run(args, capture_output=True, text=True, timeout=240)
    result: dict[str, Any] = {"status": "ran", "returncode": run.returncode, "elapsed_s": round(time.monotonic() - t0, 1)}
    if out_json.exists():
        result["inside_app"] = json.loads(out_json.read_text())
    else:
        result["status"] = "no_report"
        result["stderr"] = run.stderr[-1500:]
    return result


def camera_test_cli(uid: str | None, out: str, seconds: float, cfg: dict) -> int:
    """`wfglink camera-test`: permission plus capture tests, written as JSON (used inside the .app)."""
    report: dict[str, Any] = {"permission": permission()}
    devs = devices(cfg)
    if uid:
        cfg = {**cfg, "camera": {**cfg["camera"], "iphone_uid": uid}}
        devs = devices(cfg)
    report["devices"] = {k: devs.get(k) for k in ("iphone", "webcam", "iphone_offers_1080p60")}
    report["capture"] = capture_matrix(cfg, devs, seconds)
    Path(out).write_text(json.dumps(report, indent=2, default=str))
    return 0


def detector_benchmark(cfg: dict, frames: int = 60) -> dict[str, Any]:
    """Detector time per frame on synthetic frames at 720p and 1080p (compute only)."""
    import cv2

    from wfglink.detect.candidates import Detector

    out = {}
    rng = np.random.default_rng(0)
    for w, h in ((1280, 720), (1920, 1080)):
        det = Detector(cfg)
        base = rng.normal(30, 2, (h, w)).astype(np.float32)
        ts = []
        for i in range(frames):
            img = base + rng.normal(0, 2, (h, w)).astype(np.float32)
            for k in range(40):
                x, y = (37 * k + 13 * i) % (w - 20) + 10, (53 * k) % (h - 20) + 10
                cv2.circle(img, (x, y), 2, 160, -1)
            bgr = cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
            t0 = time.perf_counter()
            det.detect(bgr)
            ts.append((time.perf_counter() - t0) * 1000)
        ts = np.array(ts[10:])
        out[f"{w}x{h}"] = {"median_ms": round(float(np.median(ts)), 2), "p95_ms": round(float(np.percentile(ts, 95)), 2)}
    return out


def recommended_config(devs: dict[str, Any], results: list[dict[str, Any]], app: dict[str, Any] | None) -> dict[str, Any]:
    """Config values for configs/booth_local.yaml derived from check A."""
    rec: dict[str, Any] = {"camera": {}, "booth": {}}
    iphone = devs.get("iphone")
    best = best_backend(results, "iphone")
    if iphone:
        rec["camera"]["iphone_uid"] = iphone["unique_id"]
    if best:
        rec["camera"]["backend"] = best["backend"]
        rec["camera"]["fps"] = int(round(best.get("fps_requested", 30)))
        rec["booth"]["launcher"] = "terminal"
    elif app and app.get("inside_app"):
        inner = app["inside_app"].get("capture", [])
        best_app = best_backend(inner, "iphone")
        if best_app:
            rec["camera"]["backend"] = best_app["backend"]
            rec["camera"]["fps"] = int(round(best_app.get("fps_requested", 30)))
            rec["booth"]["launcher"] = "app"
    webcam_best = best_backend(results, "webcam")
    rec["webcam_works"] = bool(webcam_best)
    return rec
