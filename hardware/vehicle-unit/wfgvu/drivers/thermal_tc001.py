"""Topdon TC001 thermal camera over UVC with OpenCV (``thermal``). ``cv2`` is an optional import.

Capture: ``cv2.VideoCapture(index, cv2.CAP_V4L2)`` with ``CAP_PROP_CONVERT_RGB = 0`` so OpenCV hands over the raw
YUYV buffer instead of converting to BGR. The TC001 delivers one 256 x 384 frame, 2 bytes per pixel (25 Hz):

- rows 0..191: the visible-style image (YUYV, palette applied by the camera), not used;
- rows 192..383: the 16-bit raw temperature image, little-endian (lo byte first): ``raw = hi << 8 | lo``,
  temperature ``K = raw / 64`` (1/64 K steps), so ``C = raw / 64 - 273.15``.

This layout and scale are the community-documented ones for the TC001/P2-family "lower half" stream; they have
not been checked against a blackbody here, and the scale is documented for the camera's high-gain range. The
camera's gain mode cannot be read through UVC, so ``gain`` is the configured value (``cfg["gain"]``), not a
measurement. Emissivity: raw values assume emissivity 1 and no atmosphere/smoke correction; flames are not
grey bodies, so absolute flame temperatures from this camera are indicative only.

``shutter`` is a heuristic: True when the raw image is bit-identical to the previous one (the camera repeats the
frame during its flat-field shutter); it is a hint, not a camera flag.

The recorder writes every frame; the server forwards thermal to clients at ``thermal_wire_hz`` (default 4 Hz).
Not verified on hardware.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np

from .. import protocol
from .base import DeviceUnavailable, Driver, first_present

FRAME_W = 256
FRAME_H = 384          # two stacked 256 x 192 images
IMG_H = 192


def split_frame(frame: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Raw OpenCV buffer (any shape with 256*384*2 uint8) -> (upper image bytes [192,256,2], raw u16 [192,256])."""
    a = np.asarray(frame, dtype=np.uint8)
    if a.size != FRAME_W * FRAME_H * 2:
        raise ValueError("unexpected TC001 frame size %d (want %d)" % (a.size, FRAME_W * FRAME_H * 2))
    a = a.reshape(FRAME_H, FRAME_W, 2)
    lower = a[IMG_H:]
    raw = (lower[..., 1].astype(np.uint16) << 8) | lower[..., 0].astype(np.uint16)
    return a[:IMG_H], raw


def raw_to_kelvin(raw: np.ndarray) -> np.ndarray:
    """16-bit raw -> kelvin (float32)."""
    return (np.asarray(raw, dtype=np.float32) / np.float32(protocol.RAW_PER_K)).astype(np.float32)


def frame_from_raw(raw_u16: np.ndarray, upper: Optional[np.ndarray] = None) -> np.ndarray:
    """Build a synthetic 384 x 256 x 2 TC001 buffer from a raw image (tests / synthetic sessions)."""
    raw = np.asarray(raw_u16, dtype=np.uint16)
    out = np.zeros((FRAME_H, FRAME_W, 2), dtype=np.uint8)
    if upper is not None:
        out[:IMG_H] = upper
    out[IMG_H:, :, 0] = raw & 0xFF
    out[IMG_H:, :, 1] = raw >> 8
    return out


class ThermalTC001Driver(Driver):
    """cfg: ``index`` (0), ``gain`` ("high"), ``fps`` (25)."""

    def __init__(self, name, cfg, emit, sim_source=None, *, ctx=None, capture_factory=None):
        super().__init__(name, cfg, emit, sim_source, ctx=ctx)
        self._capture_factory = capture_factory
        self._cap = None
        self._prev: Optional[np.ndarray] = None

    def open(self) -> None:
        if self._capture_factory is not None:
            cap = self._capture_factory()
        else:
            cv2 = first_present(["cv2"])
            if cv2 is None:
                raise DeviceUnavailable("python module cv2 (OpenCV) not installed")
            idx = int(self.cfg.get("index", 0))
            api = getattr(cv2, "CAP_V4L2", 0)
            cap = cv2.VideoCapture(idx, api) if api else cv2.VideoCapture(idx)
            if not cap.isOpened():
                raise DeviceUnavailable("cannot open video device %d" % idx)
            cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
        self._cap = cap
        self._prev = None
        ok, frame = self._cap.read()
        if not ok or frame is None:
            raise DeviceUnavailable("camera opened but returned no frame")
        split_frame(frame)                                  # raises if this is not a TC001-shaped stream

    def read(self) -> List[dict]:
        ok, frame = self._cap.read()
        if not ok or frame is None:
            raise IOError("frame grab failed")
        _, raw = split_frame(frame)
        shutter = self._prev is not None and np.array_equal(raw, self._prev)
        self._prev = raw
        return [protocol.encode_thermal_raw(raw, gain=str(self.cfg.get("gain", "high")), shutter=bool(shutter))]

    def close(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            finally:
                self._cap = None

