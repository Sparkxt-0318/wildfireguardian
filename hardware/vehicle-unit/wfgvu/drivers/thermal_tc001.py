"""InfiRay P2 Pro (TC001-compatible 256x384 frame) thermal camera over UVC with OpenCV (``thermal``).

The unit's camera is an InfiRay P2 Pro (USB id 0bda:5830). It delivers the same frame format as the Topdon TC001,
so the module keeps its historical name ``thermal_tc001`` and the sensor name stays ``thermal``. ``cv2`` is an
optional import.

Device: ``cfg["index"]`` is an integer N (``/dev/videoN``) or ``"auto"`` (default in config/unit.yaml): the capture
node is found through sysfs (``find_capture_node``): every ``/sys/class/video4linux/videoN`` whose ``device`` link
leads (walking up) to a USB device with ``idVendor``/``idProduct`` = ``cfg["usb_id"]`` (default "0bda:5830") and
whose sysfs ``index`` is 0 (the capture node; UVC also creates a metadata node with index 1); the lowest N wins.
Nothing found -> ``DeviceUnavailable`` listing every video node seen. 0bda:5830 is a Realtek bridge id and is not
unique to this camera, so the frame-shape check at open (256 x 384 x 2 bytes) is the second guard.

Capture: ``cv2.VideoCapture(index, cv2.CAP_V4L2)`` with ``CAP_PROP_CONVERT_RGB = 0`` so OpenCV hands over the raw
YUYV buffer instead of converting to BGR. The camera delivers one 256 x 384 frame, 2 bytes per pixel (25 Hz):

- rows 0..191: the visible-style image (YUYV, palette applied by the camera), not used;
- rows 192..383: the 16-bit raw temperature image, little-endian (lo byte first): ``raw = hi << 8 | lo``,
  temperature ``K = raw / 64`` (1/64 K steps), so ``C = raw / 64 - 273.15``.

This layout and scale are the community-documented ones for the P2 / TC001 family "lower half" stream; they have
not been checked against a blackbody here (nor on the P2 Pro itself), and the scale is documented for the camera's high-gain range. The
camera's gain mode cannot be read through UVC, so ``gain`` is the configured value (``cfg["gain"]``), not a
measurement. Emissivity: raw values assume emissivity 1 and no atmosphere/smoke correction; flames are not
grey bodies, so absolute flame temperatures from this camera are indicative only.

``shutter`` is a heuristic: True when the raw image is bit-identical to the previous one (the camera repeats the
frame during its flat-field shutter); it is a hint, not a camera flag.

The recorder writes every frame; the server forwards thermal to clients at ``thermal_wire_hz`` (default 4 Hz).
Not verified on hardware.
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional, Tuple

import numpy as np

from .. import protocol
from .base import DeviceUnavailable, Driver, first_present

log = logging.getLogger(__name__)

CAMERA_NAME = "InfiRay P2 Pro (TC001-compatible 256x384 frame)"
DEFAULT_USB_ID = "0bda:5830"
FRAME_W = 256
FRAME_H = 384          # two stacked 256 x 192 images
IMG_H = 192


def split_frame(frame: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Raw OpenCV buffer (any shape with 256*384*2 uint8) -> (upper image bytes [192,256,2], raw u16 [192,256])."""
    a = np.asarray(frame, dtype=np.uint8)
    if a.size != FRAME_W * FRAME_H * 2:
        raise ValueError("unexpected frame size %d (want %d: %s)" % (a.size, FRAME_W * FRAME_H * 2, CAMERA_NAME))
    a = a.reshape(FRAME_H, FRAME_W, 2)
    lower = a[IMG_H:]
    raw = (lower[..., 1].astype(np.uint16) << 8) | lower[..., 0].astype(np.uint16)
    return a[:IMG_H], raw


def raw_to_kelvin(raw: np.ndarray) -> np.ndarray:
    """16-bit raw -> kelvin (float32)."""
    return (np.asarray(raw, dtype=np.float32) / np.float32(protocol.RAW_PER_K)).astype(np.float32)


def frame_from_raw(raw_u16: np.ndarray, upper: Optional[np.ndarray] = None) -> np.ndarray:
    """Build a synthetic 384 x 256 x 2 TC001-compatible buffer from a raw image (tests / synthetic sessions)."""
    raw = np.asarray(raw_u16, dtype=np.uint16)
    out = np.zeros((FRAME_H, FRAME_W, 2), dtype=np.uint8)
    if upper is not None:
        out[:IMG_H] = upper
    out[IMG_H:, :, 0] = raw & 0xFF
    out[IMG_H:, :, 1] = raw >> 8
    return out


def _read_text(path: str) -> Optional[str]:
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def _usb_parent_id(dev_link: str, stop: str) -> Optional[str]:
    """Walk up from a resolved sysfs device path to the first directory with idVendor/idProduct ("vvvv:pppp")."""
    p = os.path.realpath(dev_link)
    stop = os.path.realpath(stop)
    while p and p not in ("/", stop) and p.startswith(stop):
        v, pr = _read_text(os.path.join(p, "idVendor")), _read_text(os.path.join(p, "idProduct"))
        if v and pr:
            return "%s:%s" % (v.lower(), pr.lower())
        p = os.path.dirname(p)
    return None


def list_video_nodes(sysfs_root: str = "/sys") -> List[dict]:
    """Every ``/sys/class/video4linux/videoN``: ``{"n", "name", "index", "usb_id"}`` sorted by N."""
    base = os.path.join(sysfs_root, "class", "video4linux")
    out = []
    try:
        entries = os.listdir(base)
    except OSError:
        return out
    for e in entries:
        if not (e.startswith("video") and e[5:].isdigit()):
            continue
        d = os.path.join(base, e)
        idx = _read_text(os.path.join(d, "index"))
        out.append({"n": int(e[5:]), "name": _read_text(os.path.join(d, "name")) or "",
                    "index": int(idx) if idx is not None and idx.isdigit() else None,
                    "usb_id": _usb_parent_id(os.path.join(d, "device"), sysfs_root)})
    return sorted(out, key=lambda x: x["n"])


def find_capture_node(usb_id: str = DEFAULT_USB_ID, sysfs_root: str = "/sys") -> int:
    """Lowest N whose /dev/videoN is the capture node (sysfs index 0) of a USB device with ``usb_id``."""
    want = str(usb_id).strip().lower()
    base = os.path.join(sysfs_root, "class", "video4linux")
    if not os.path.isdir(base):
        raise DeviceUnavailable("no %s (not Linux, or no V4L2 devices): cannot find %s by USB id %s"
                                % (base, CAMERA_NAME, want))
    nodes = list_video_nodes(sysfs_root)
    hits = [x["n"] for x in nodes if x["usb_id"] == want and x["index"] == 0]
    if not hits:
        seen = ", ".join("video%d (%s, usb %s, index %s)" % (x["n"], x["name"] or "?", x["usb_id"] or "none",
                                                             "?" if x["index"] is None else x["index"])
                         for x in nodes) or "no video nodes"
        raise DeviceUnavailable("no capture node for USB %s (%s); found: %s" % (want, CAMERA_NAME, seen))
    if len(hits) > 1:
        log.warning("%d capture nodes with USB id %s (video%s); using video%d", len(hits), want,
                    ", video".join(str(h) for h in hits), hits[0])
    return hits[0]


def resolve_index(cfg: dict, sysfs_root: str = "/sys") -> int:
    """``cfg["index"]``: an int (or digit string) is used as is; "auto"/missing -> ``find_capture_node``."""
    idx = (cfg or {}).get("index", "auto")
    if isinstance(idx, bool):
        raise ValueError("thermal index must be an integer or 'auto', got %r" % idx)
    if isinstance(idx, int):
        return idx
    if isinstance(idx, str) and idx.strip().isdigit():
        return int(idx.strip())
    if idx is None or (isinstance(idx, str) and idx.strip().lower() == "auto"):
        return find_capture_node(str((cfg or {}).get("usb_id") or DEFAULT_USB_ID), sysfs_root)
    raise ValueError("thermal index must be an integer or 'auto', got %r" % idx)


class ThermalTC001Driver(Driver):
    """InfiRay P2 Pro (TC001-compatible). cfg: ``index`` ("auto" or N), ``usb_id`` ("0bda:5830"), ``gain`` ("high",
    configured, not read back), ``fps`` (25). ``sysfs_root`` is a test hook for ``index: auto``."""

    def __init__(self, name, cfg, emit, sim_source=None, *, ctx=None, capture_factory=None, sysfs_root="/sys"):
        super().__init__(name, cfg, emit, sim_source, ctx=ctx)
        self._capture_factory = capture_factory
        self._sysfs_root = sysfs_root
        self._cap = None
        self._prev: Optional[np.ndarray] = None
        self.device_index: Optional[int] = None

    def open(self) -> None:
        if self._capture_factory is not None:
            cap = self._capture_factory()
        else:
            cv2 = first_present(["cv2"])
            if cv2 is None:
                raise DeviceUnavailable("python module cv2 (OpenCV) not installed")
            idx = resolve_index(self.cfg, self._sysfs_root)
            self.device_index = idx
            api = getattr(cv2, "CAP_V4L2", 0)
            cap = cv2.VideoCapture(idx, api) if api else cv2.VideoCapture(idx)
            if not cap.isOpened():
                raise DeviceUnavailable("cannot open /dev/video%d (%s)" % (idx, CAMERA_NAME))
            log.info("thermal: %s on /dev/video%d", CAMERA_NAME, idx)
            cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
        self._cap = cap
        self._prev = None
        ok, frame = self._cap.read()
        if not ok or frame is None:
            raise DeviceUnavailable("camera opened but returned no frame")
        split_frame(frame)                                  # raises if this is not a 256 x 384 (P2 Pro / TC001) stream

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

