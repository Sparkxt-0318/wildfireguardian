"""Frame sources: video files and synthetic demos.

Every source has the same small interface:

    src.open()            # may raise SourceError
    frame = src.read()    # Frame, or None at the end of the file
    src.close()

Files are decoded with PyAV so that every frame carries its true presentation time, which
matters for footage recorded at a variable frame rate. The booth plays files through
wfglink.io.playlist, which paces them in real time and skips frames it cannot show in time.
"""
from __future__ import annotations

import os
import time
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

    loop: restart at the end; times keep increasing across loops and
          frame.meta["loop"] counts completed loops.
    realtime: pace delivery to the presentation times.
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
                     {"loop": self._loop_count, "pts_s": t_media, "source": self.name,
                      "source_fps": self.info.get("fps_nominal")})

    def close(self) -> None:
        if self._container is not None:
            self._container.close()
        self._container = None
        self._frames = None


# Factory --------------------------------------------------------------------------------

def make_source(spec: dict[str, Any]) -> Source:
    """Build a source from a config dict.

    {"kind": "file", "path": ..., "loop": bool, "realtime": bool}
    {"kind": "synthetic", ...}  (see wfglink.io.synthetic_live)
    """
    kind = spec.get("kind")
    if kind == "file":
        return FileSource(spec["path"], loop=bool(spec.get("loop", False)),
                          realtime=bool(spec.get("realtime", False)), scale=spec.get("scale"),
                          start_s=float(spec.get("start_s", 0.0)))
    if kind == "synthetic":
        from wfglink.io.synthetic_live import SyntheticLiveSource

        return SyntheticLiveSource(**{k: v for k, v in spec.items() if k != "kind"})
    raise ValueError(f"unknown source kind {kind!r}")


def frames_to_array(frames: list[Frame]) -> np.ndarray:
    """Stack frame images (tests and small tools)."""
    return np.stack([f.image for f in frames])
