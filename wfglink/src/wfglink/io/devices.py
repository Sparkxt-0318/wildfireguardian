"""Camera discovery, role-based selection and the automatic backend choice.

Roles:
- "iphone": the Continuity Camera (isContinuityCamera, never Desk View), or a saved
  uniqueID, or a name containing "iPhone".
- "webcam": an external camera that is not the iPhone and not the MacBook's built-in
  FaceTime camera (that one faces the presenter, not the iPad). Override with a name
  regex in camera.webcam_match.

AutoCameraSource tries the configured backends in order (PyAV first, because it sets the
device's full-resolution format; then OpenCV) and remembers which one worked, so the
choice made during sitting 1 needs no code change, only a config default.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from wfglink.io.frames import Frame
from wfglink.io.sources import CameraSpec, OpenCVCameraSource, PyAVCameraSource, Source, SourceError

BUILTIN_PATTERN = re.compile(r"facetime|built-?in|macbook", re.I)


def list_cameras() -> dict[str, Any]:
    """{"platform": ..., "devices": [...]} with name, unique_id and both index orderings."""
    if sys.platform == "darwin":
        try:
            from wfglink.io import macos

            return {"platform": "darwin", **macos.discover()}
        except Exception as exc:
            return {"platform": "darwin", "devices": [], "error": f"{type(exc).__name__}: {exc}"}
    if sys.platform.startswith("linux"):
        devices = []
        for node in sorted(Path("/sys/class/video4linux").glob("video*")):
            idx = int(re.sub(r"\D", "", node.name) or 0)
            name = (node / "name").read_text().strip() if (node / "name").exists() else node.name
            devices.append({"name": name, "unique_id": f"/dev/{node.name}", "opencv_index": idx,
                            "ffmpeg_index": idx, "is_continuity_camera": False, "is_desk_view": False,
                            "device_type": "v4l2"})
        return {"platform": "linux", "devices": devices}
    return {"platform": sys.platform, "devices": []}


def pick_camera(devices: list[dict], role: str, saved_uid: str | None = None,
                name_match: str | None = None) -> dict | None:
    usable = [d for d in devices if not d.get("is_desk_view") and d.get("connected", True)]
    if saved_uid:
        for d in usable:
            if d.get("unique_id") == saved_uid:
                return d
    if name_match:
        rx = re.compile(name_match, re.I)
        for d in usable:
            if rx.search(d.get("name", "")):
                return d
    if role == "iphone":
        for d in usable:
            if d.get("is_continuity_camera"):
                return d
        for d in usable:
            if re.search(r"iphone", d.get("name", ""), re.I):
                return d
        return None
    if role == "webcam":
        for d in usable:
            if d.get("is_continuity_camera") or re.search(r"iphone", d.get("name", ""), re.I):
                continue
            if BUILTIN_PATTERN.search(d.get("name", "")) or "builtin" in d.get("device_type", "").lower():
                continue
            return d
        return None
    raise ValueError(f"unknown camera role {role!r}")


class AutoCameraSource(Source):
    """Open a camera with the first backend that works; remember the winner per device."""

    kind = "camera"
    is_live = True
    _winners: dict[str, str] = {}

    def __init__(self, device: dict, spec: CameraSpec, backends: list[str], label: str | None = None):
        super().__init__(label or device.get("name", "camera"))
        self.device = device
        self.spec = spec
        self.backends = list(backends)
        self.inner: Source | None = None
        self.attempts: list[dict[str, Any]] = []

    def _make(self, backend: str) -> Source:
        if backend == "pyav":
            dev = self.device.get("name") if sys.platform == "darwin" else self.device.get("unique_id")
            return PyAVCameraSource(CameraSpec(dev, self.spec.width, self.spec.height, self.spec.fps), label=self.name)
        if backend == "opencv":
            idx = self.device.get("opencv_index")
            if idx is None:
                raise SourceError("device has no OpenCV index")
            return OpenCVCameraSource(int(idx), self.spec, label=self.name)
        raise SourceError(f"unknown backend {backend!r}")

    def open(self) -> None:
        uid = str(self.device.get("unique_id"))
        order = list(self.backends)
        if uid in self._winners and self._winners[uid] in order:
            order.remove(self._winners[uid])
            order.insert(0, self._winners[uid])
        errors = []
        for backend in order:
            try:
                src = self._make(backend)
                src.open()
            except Exception as exc:
                errors.append(f"{backend}: {exc}")
                self.attempts.append({"backend": backend, "ok": False, "error": str(exc)})
                continue
            self.inner = src
            self._winners[uid] = backend
            self.info = {**src.info, "device": self.device.get("name"), "unique_id": uid}
            self.attempts.append({"backend": backend, "ok": True})
            return
        raise SourceError("; ".join(errors) or "no backend")

    def read(self) -> Frame | None:
        if self.inner is None:
            raise SourceError("source not opened")
        f = self.inner.read()
        if f is not None:
            f.index = self._next_index()
        return f

    def close(self) -> None:
        if self.inner is not None:
            self.inner.close()
        self.inner = None


def camera_backends(cfg: dict) -> list[str]:
    b = cfg.get("camera", {}).get("backend", "auto")
    return ["pyav", "opencv"] if b == "auto" else [b]
