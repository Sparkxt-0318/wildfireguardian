"""Frame sources: video files, cameras (PyAV or OpenCV backends) and synthetic demos.

Every source has the same small interface:

    src.open()            # may raise SourceError
    frame = src.read()    # Frame, or None at end of file / no frame within the timeout
    src.close()

Files are decoded with PyAV so that every frame carries its true presentation time, which
matters for phone footage recorded at a variable frame rate. Camera sources are thin
wrappers; reconnection, health checks and fallbacks live in wfglink.io.capture.
"""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from wfglink.io.frames import Frame


class SourceError(RuntimeError):
    """A source could not be opened or failed while reading."""


class Source:
    kind = "base"
    is_live = False

    def __init__(self, name: str):
        self.name = name
        self.info: dict[str, Any] = {}
        self._index = 0

    def open(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def read(self) -> Frame | None:  # pragma: no cover - interface
        raise NotImplementedError

    def close(self) -> None:
        pass

    def __enter__(self) -> "Source":
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _next_index(self) -> int:
        i = self._index
        self._index += 1
        return i


# Files ----------------------------------------------------------------------------------

class FileSource(Source):
    """Decode a video file with true timestamps.

    loop: restart at the end (booth replay); times keep increasing across loops and
          frame.meta["loop"] counts completed loops.
    realtime: pace delivery to the presentation times (live replay in the UI).
    scale: optional resize factor applied after decoding (preview only; analysis uses 1.0).
    """

    kind = "file"

    def __init__(self, path: str | os.PathLike, *, loop: bool = False, realtime: bool = False,
                 scale: float | None = None, start_s: float = 0.0):
        super().__init__(Path(path).name)
        self.path = Path(path)
        self.loop = loop
        self.realtime = realtime
        self.scale = scale
        self.start_s = float(start_s)
        self._container = None
        self._frames = None
        self._loop_count = 0
        self._loop_offset = 0.0
        self._last_t = 0.0
        self._t0_wall: float | None = None
        self._t0_media: float | None = None

    def open(self) -> None:
        import av

        if not self.path.exists():
            raise SourceError(f"file not found: {self.path}")
        try:
            self._container = av.open(str(self.path))
        except av.error.FFmpegError as exc:  # type: ignore[attr-defined]
            raise SourceError(f"cannot open {self.path}: {exc}") from exc
        stream = self._container.streams.video[0]
        stream.thread_type = "AUTO"
        rate = stream.average_rate or stream.guessed_rate
        self.info = {
            "path": str(self.path),
            "width": stream.codec_context.width,
            "height": stream.codec_context.height,
            "codec": stream.codec_context.name,
            "fps_nominal": float(rate) if rate else None,
            "duration_s": float(stream.duration * stream.time_base) if stream.duration else (
                float(self._container.duration / 1e6) if self._container.duration else None),
            "frames_declared": int(stream.frames) if stream.frames else None,
            "metadata": dict(self._container.metadata),
            "stream_metadata": dict(stream.metadata),
        }
        if self.start_s > 0:
            self._container.seek(int(self.start_s / stream.time_base), stream=stream, backward=True)
        self._frames = self._container.decode(stream)

    def _restart(self) -> None:
        self.close()
        self.open()

    def read(self) -> Frame | None:
        if self._frames is None:
            raise SourceError("source not opened")
        while True:
            try:
                vf = next(self._frames)
            except StopIteration:
                if not self.loop:
                    return None
                self._loop_count += 1
                self._loop_offset = self._last_t + (1.0 / (self.info.get("fps_nominal") or 30.0))
                self._restart()
                continue
            if vf.time is not None and vf.time < self.start_s - 1e-6:
                continue  # frames before the requested start after a keyframe seek
            break
        t_media = (vf.time if vf.time is not None else self._last_t) - self.start_s
        t = t_media + self._loop_offset
        img = vf.to_ndarray(format="bgr24")
        if self.scale and self.scale != 1.0:
            import cv2

            img = cv2.resize(img, None, fx=self.scale, fy=self.scale, interpolation=cv2.INTER_AREA)
        if self.realtime:
            now = time.monotonic()
            if self._t0_wall is None:
                self._t0_wall, self._t0_media = now, t
            wait = (t - self._t0_media) - (now - self._t0_wall)
            if wait > 0:
                time.sleep(min(wait, 0.5))
            elif wait < -0.5:  # fell behind (slow machine): resynchronise instead of racing
                self._t0_wall, self._t0_media = now, t
        self._last_t = t
        return Frame(img, t, self._next_index(), time.monotonic(),
                     {"loop": self._loop_count, "pts_s": t_media, "source": self.name})

    def close(self) -> None:
        if self._container is not None:
            self._container.close()
        self._container = None
        self._frames = None


# Cameras --------------------------------------------------------------------------------

@dataclass
class CameraSpec:
    """How to open a camera. `device` is a name (preferred), a uniqueID, or an index."""

    device: str | int
    width: int = 1920
    height: int = 1080
    fps: float = 30.0
    pixel_formats: list[str] = field(default_factory=lambda: ["", "nv12", "uyvy422", "yuyv422", "0rgb", "bgr0"])
    fps_candidates: list[float] = field(default_factory=lambda: [30.0, 29.97, 60.0, 59.94, 25.0, 24.0, 15.0])


class PyAVCameraSource(Source):
    """Camera through FFmpeg (avfoundation on macOS, v4l2 on Linux) via PyAV.

    FFmpeg sets the device's active format from video_size and framerate, which gives the
    full 1920x1080 from Continuity Camera; OpenCV's AVFoundation backend opens sessions at
    the Medium preset. Frame times come from the device clock when available.
    """

    kind = "camera"
    is_live = True

    def __init__(self, spec: CameraSpec, label: str | None = None):
        super().__init__(label or str(spec.device))
        self.spec = spec
        self._container = None
        self._frames = None
        self._t0: float | None = None

    def _input(self) -> tuple[str, str]:
        dev = self.spec.device
        if sys.platform == "darwin":
            # FFmpeg's avfoundation input is "<video>:<audio>"; a name or an FFmpeg index.
            return f"{dev}:none", "avfoundation"
        if sys.platform.startswith("linux"):
            return (dev if isinstance(dev, str) and dev.startswith("/dev/") else f"/dev/video{int(dev)}"), "v4l2"
        raise SourceError(f"PyAV camera capture is not supported on {sys.platform}")

    def open(self) -> None:
        import av

        url, fmt = self._input()
        size = f"{self.spec.width}x{self.spec.height}"
        errors: list[str] = []
        fps_list = [self.spec.fps] + [f for f in self.spec.fps_candidates if f != self.spec.fps]
        for fps in fps_list:
            for pix in self.spec.pixel_formats:
                opts = {"video_size": size, "framerate": f"{fps:g}"}
                if pix:
                    opts["pixel_format" if fmt == "avfoundation" else "input_format"] = pix
                try:
                    self._container = av.open(url, format=fmt, options=opts, timeout=(5.0, 2.0))
                except Exception as exc:  # FFmpeg reports unsupported modes as errors
                    errors.append(f"{opts}: {exc}")
                    continue
                stream = self._container.streams.video[0]
                self._frames = self._container.decode(stream)
                self.info = {"backend": "pyav", "url": url, "format": fmt, "options": opts,
                             "width": stream.codec_context.width, "height": stream.codec_context.height,
                             "fps_requested": fps, "attempts": len(errors) + 1}
                return
        raise SourceError("PyAV could not open camera " + repr(self.spec.device) + ": " + " | ".join(errors[-3:]))

    def read(self) -> Frame | None:
        if self._frames is None:
            raise SourceError("source not opened")
        try:
            vf = next(self._frames)
        except StopIteration:
            raise SourceError("camera stream ended")
        except Exception as exc:
            raise SourceError(f"camera read failed: {exc}") from exc
        now = time.monotonic()
        if vf.time is not None:
            if self._t0 is None:
                self._t0 = vf.time
            t = vf.time - self._t0
        else:
            if self._t0 is None:
                self._t0 = now
            t = now - self._t0
        return Frame(vf.to_ndarray(format="bgr24"), float(t), self._next_index(), now,
                     {"source": self.name, "backend": "pyav"})

    def close(self) -> None:
        if self._container is not None:
            try:
                self._container.close()
            except Exception:
                pass
        self._container = None
        self._frames = None


class OpenCVCameraSource(Source):
    """Camera through OpenCV (AVFoundation on macOS, V4L2 on Linux).

    On macOS the index must follow OpenCV's own ordering (video plus muxed devices sorted
    by uniqueID); wfglink.io.devices computes it from the device's uniqueID.
    """

    kind = "camera"
    is_live = True

    def __init__(self, index: int, spec: CameraSpec, label: str | None = None):
        super().__init__(label or f"opencv:{index}")
        self.index = int(index)
        self.spec = spec
        self._cap = None
        self._t0: float | None = None

    def open(self) -> None:
        import cv2

        api = cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else (cv2.CAP_V4L2 if sys.platform.startswith("linux") else cv2.CAP_ANY)
        cap = cv2.VideoCapture(self.index, api)
        if not cap.isOpened():
            raise SourceError(f"OpenCV could not open camera index {self.index}")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.spec.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.spec.height)
        cap.set(cv2.CAP_PROP_FPS, self.spec.fps)
        self._cap = cap
        self.info = {"backend": "opencv", "index": self.index,
                     "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                     "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                     "fps_reported": float(cap.get(cv2.CAP_PROP_FPS))}

    def read(self) -> Frame | None:
        if self._cap is None:
            raise SourceError("source not opened")
        ok, img = self._cap.read()
        now = time.monotonic()
        if not ok or img is None:
            return None  # OpenCV's AVFoundation grab times out after 1 s; the watchdog decides
        if self._t0 is None:
            self._t0 = now
        return Frame(img, now - self._t0, self._next_index(), now, {"source": self.name, "backend": "opencv"})

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
        self._cap = None


# Factory --------------------------------------------------------------------------------

def make_source(spec: dict[str, Any]) -> Source:
    """Build a source from a config dict.

    {"kind": "file", "path": ..., "loop": bool, "realtime": bool}
    {"kind": "camera", "backend": "pyav" | "opencv", "device": name|uniqueID|index, "index": int,
     "width": .., "height": .., "fps": ..}
    {"kind": "synthetic", ...}  (see wfglink.io.synthetic_live)
    """
    kind = spec.get("kind")
    if kind == "file":
        return FileSource(spec["path"], loop=bool(spec.get("loop", False)),
                          realtime=bool(spec.get("realtime", False)), scale=spec.get("scale"),
                          start_s=float(spec.get("start_s", 0.0)))
    if kind == "camera":
        cs = CameraSpec(device=spec.get("device", 0), width=int(spec.get("width", 1920)),
                        height=int(spec.get("height", 1080)), fps=float(spec.get("fps", 30.0)))
        if spec.get("backend", "pyav") == "opencv":
            return OpenCVCameraSource(int(spec.get("index", 0)), cs, label=spec.get("label"))
        return PyAVCameraSource(cs, label=spec.get("label"))
    if kind == "synthetic":
        from wfglink.io.synthetic_live import SyntheticLiveSource

        return SyntheticLiveSource(**{k: v for k, v in spec.items() if k != "kind"})
    raise ValueError(f"unknown source kind {kind!r}")


def frames_to_array(frames: list[Frame]) -> np.ndarray:
    """Stack frame images (tests and small tools)."""
    return np.stack([f.image for f in frames])
