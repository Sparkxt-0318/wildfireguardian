"""Live camera input for the "Become an ember" mode: discovery, choice, permission and capture.

    python -m wfglink cameras              # list the cameras and the one config picks
    python -m wfglink cameras --request    # also ask for camera permission (the macOS dialog)

Discovery (`list_cameras`). On macOS, pyobjc's AVFoundation gives each video device's name,
uniqueID, device type, transport and isContinuityCamera. Every device gets a kind: builtin
(the MacBook's own camera), usb (a USB UVC webcam), continuity (an iPhone or iPad through
Continuity Camera), deskview (Desk View, a cropped view of another camera) or other (a
virtual camera, for example). Continuity Camera and Desk View are never usable: the booth
uses only the MacBook's camera or a USB webcam. Each device also gets its OpenCV index,
found as OpenCV's AVFoundation backend finds it (video plus muxed devices sorted by
uniqueID). On Linux the V4L2 devices are listed (development only).

Choice (`pick_camera`): config camera.name. "auto" takes a usable USB webcam when one is
connected, else the built-in camera; any other value is a case-insensitive part of the
device name. `explain_pick` says why nothing was picked.

Permission (`request_permission`): macOS asks the user once, through a system dialog for
the app that started Python (Terminal). The request runs on the main thread before any
capture thread starts, because AVFoundation answers on the main run loop; wfglink then
sets OPENCV_AVFOUNDATION_SKIP_AUTH=1 so OpenCV never asks from a capture thread. On other
systems it returns "unsupported" and capture is tried directly.

Capture (`CameraSource`): the picked camera at camera.width x camera.height and
camera.fps, through PyAV's avfoundation input opened by device name (FFmpeg sets the
device's own format, so the picture is the real 1280x720 and not a scaled preset), else
OpenCV's AVFoundation backend by index (camera.backend chooses; auto tries PyAV first and
remembers what worked). Frames wider than camera.width are scaled down to it. frame.t is
seconds on a monotonic clock since the source first opened (the device's own timestamps
when PyAV gives them, anchored to that clock). A failure while running (an unplugged
webcam, no frame for camera.stall_s) closes the camera and opens it again with backoff
from camera.backoff_min_s to camera.backoff_max_s; read() returns None meanwhile and
`state` says "reconnecting". Center Stage (macOS) reframes the picture and would change the
scale, so wfglink turns it off for its own process (camera.center_stage).

`FakeCameraSource` plays a video file or a generated phone scene (wfglink.ember.synth) like
a camera: tests, the demo gate, Linux, and the booth when no camera is there.
"""
from __future__ import annotations

import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np

from wfglink.io.frames import Frame
from wfglink.io.sources import FileSource, Source, SourceError

KINDS = ("usb", "builtin", "other", "continuity", "deskview")
BUILTIN_NAME = re.compile(r"facetime|built-?in|내장|macbook", re.I)
CONTINUITY_NAME = re.compile(r"iphone|ipad", re.I)
DESKVIEW_NAME = re.compile(r"desk ?view", re.I)
# AVCaptureDevice.transportType four-character codes (IOKit audio transport constants).
TRANSPORTS = {0x626C746E: "bltn", 0x75736220: "usb ", 0x76697274: "virt", 0x74687562: "thun",
              0x626C7565: "blue", 0x77696669: "wifi", 0x70636920: "pci "}
STATUS = {0: "not_determined", 1: "restricted", 2: "denied", 3: "authorized"}
WHY = {
    "continuity": "Continuity Camera (an iPhone or iPad) is never used at the booth",
    "deskview": "Desk View is a cropped view of another camera, never used",
    "other": "not a built-in or USB camera (virtual?): used only when camera.name names it",
}


def _cam(cfg: dict | None) -> dict[str, Any]:
    return dict((cfg or {}).get("camera") or {})


# Discovery -------------------------------------------------------------------------------------

def _avf():
    """pyobjc's AVFoundation (macOS only; ImportError elsewhere or when pyobjc is missing)."""
    if sys.platform != "darwin":
        raise ImportError("AVFoundation is macOS only")
    import AVFoundation  # noqa: PLC0415  (pyobjc-framework-AVFoundation, requirements.txt)

    return AVFoundation


def _call(obj: Any, name: str, default: Any = None) -> Any:
    try:
        if obj.respondsToSelector_(name):
            return getattr(obj, name)()
    except Exception:
        pass
    return default


def _fourcc(code: Any) -> str:
    try:
        code = int(code)
    except (TypeError, ValueError):
        return ""
    if code in TRANSPORTS:
        return TRANSPORTS[code]
    try:
        return "".join(chr((code >> s) & 0xFF) for s in (24, 16, 8, 0))
    except ValueError:
        return str(code)


def _mac_raw_devices() -> list[dict[str, Any]]:
    """Every AVFoundation video device as a plain dict (macOS)."""
    AVF = _avf()
    names = ["AVCaptureDeviceTypeBuiltInWideAngleCamera", "AVCaptureDeviceTypeExternal",
             "AVCaptureDeviceTypeExternalUnknown", "AVCaptureDeviceTypeContinuityCamera",
             "AVCaptureDeviceTypeDeskViewCamera"]
    types = [getattr(AVF, n) for n in names if hasattr(AVF, n)]
    found: list = []
    try:
        session = AVF.AVCaptureDeviceDiscoverySession.discoverySessionWithDeviceTypes_mediaType_position_(
            types, AVF.AVMediaTypeVideo, AVF.AVCaptureDevicePositionUnspecified)
        found = list(session.devices() or [])
    except Exception:
        pass
    # OpenCV's backend uses the older list (video plus muxed devices), sorted by uniqueID.
    legacy: list = []
    for media in (AVF.AVMediaTypeVideo, AVF.AVMediaTypeMuxed):
        try:
            legacy += list(AVF.AVCaptureDevice.devicesWithMediaType_(media) or [])
        except Exception:
            pass
    legacy_uids = [str(d.uniqueID()) for d in legacy]
    by_uid: dict[str, Any] = {}
    for dev in found + legacy:
        by_uid.setdefault(str(dev.uniqueID()), dev)
    out = []
    for uid, dev in by_uid.items():
        out.append({
            "name": str(dev.localizedName()),
            "unique_id": uid,
            "device_type": str(_call(dev, "deviceType", "") or ""),
            "transport": _fourcc(_call(dev, "transportType", 0)),
            "model_id": str(_call(dev, "modelID", "") or ""),
            "manufacturer": str(_call(dev, "manufacturer", "") or ""),
            "is_continuity": bool(_call(dev, "isContinuityCamera", False)),
            "connected": bool(_call(dev, "isConnected", True)),
            "suspended": bool(_call(dev, "isSuspended", False)),
            "in_legacy_list": uid in legacy_uids,
        })
    order = opencv_order([d["unique_id"] for d in out if d["in_legacy_list"]])
    for d in out:
        d["index"] = order.get(d["unique_id"])
    return out


def opencv_order(uids: list[str]) -> dict[str, int]:
    """OpenCV's AVFoundation device index of each uniqueID: the video and muxed devices sorted
    by uniqueID (cap_avfoundation_mac.mm compares them with NSString compare:, which orders
    these ASCII identifiers like Python does)."""
    return {uid: i for i, uid in enumerate(sorted(set(uids)))}


def _linux_raw_devices(root: str = "/sys/class/video4linux") -> list[dict[str, Any]]:
    """V4L2 capture nodes (development only; a camera's metadata nodes are left out)."""
    out = []
    for node in sorted(Path(root).glob("video*"), key=lambda p: int(re.sub(r"\D", "", p.name) or 0)):
        try:
            if (node / "index").exists() and int((node / "index").read_text().strip() or 0) != 0:
                continue
            name = (node / "name").read_text().strip() if (node / "name").exists() else node.name
            dev_path = str((node / "device").resolve()) if (node / "device").exists() else ""
        except OSError:
            continue
        idx = int(re.sub(r"\D", "", node.name) or 0)
        out.append({"name": name, "unique_id": f"/dev/{node.name}", "device_type": "v4l2",
                    "transport": "usb " if "/usb" in dev_path else "", "is_continuity": False,
                    "connected": True, "suspended": False, "index": idx})
    return out


def classify(dev: dict[str, Any]) -> dict[str, Any]:
    """Add kind, usable and why to a raw device dict (pure, so tests can feed fakes)."""
    d = dict(dev)
    name = str(d.get("name") or "")
    dtype = str(d.get("device_type") or "").lower().replace(" ", "")
    transport = str(d.get("transport") or "")
    if d.get("is_continuity") or "continuity" in dtype or CONTINUITY_NAME.search(name):
        kind = "continuity"
    elif "deskview" in dtype or DESKVIEW_NAME.search(name):
        kind = "deskview"
    elif transport == "bltn" or "builtin" in dtype or (not transport and BUILTIN_NAME.search(name)):
        kind = "builtin"
    elif transport == "usb " or (not transport and "external" in dtype) or (dtype == "v4l2" and transport != "virt"):
        kind = "usb"
    else:
        kind = "other"
    usable, why = kind in ("usb", "builtin", "other"), WHY.get(kind, "")
    if usable and not d.get("connected", True):
        usable, why = False, "not connected"
    elif usable and d.get("suspended"):
        usable, why = False, "suspended (is the MacBook lid closed?)"
    d.update({"kind": kind, "usable": usable, "why": why})
    d.setdefault("index", None)
    return d


def list_cameras(raw: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Every camera as {name, unique_id, index, kind, usable, why, ...}: USB webcams first, then
    the built-in camera, then the rest; by name within a kind. `raw` replaces discovery (tests)."""
    if raw is None:
        try:
            if sys.platform == "darwin":
                raw = _mac_raw_devices()
            elif sys.platform.startswith("linux"):
                raw = _linux_raw_devices()
            else:
                raw = []
        except Exception:
            raw = []
    devs = [classify(d) for d in raw]
    return sorted(devs, key=lambda d: (KINDS.index(d["kind"]), d["name"].lower(), str(d["unique_id"])))


def pick_camera(cfg: dict | None, devices: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """The camera config camera.name picks, or None. "auto": the first usable USB webcam, else the
    built-in camera (never a virtual one). Otherwise the first usable device whose name contains
    camera.name (any case); naming only unusable devices (an iPhone) picks nothing."""
    want = str(_cam(cfg).get("name") or "auto").strip()
    devs = list_cameras() if devices is None else [d if "kind" in d else classify(d) for d in devices]
    usable = [d for d in devs if d["usable"]]
    if want.lower() == "auto":
        for kind in ("usb", "builtin"):
            for d in usable:
                if d["kind"] == kind:
                    return d
        return None
    for d in usable:
        if want.lower() in d["name"].lower():
            return d
    return None


def explain_pick(cfg: dict | None, devices: list[dict[str, Any]] | None = None) -> str:
    """Why pick_camera found nothing (or which camera it picks)."""
    want = str(_cam(cfg).get("name") or "auto").strip()
    devs = list_cameras() if devices is None else [d if "kind" in d else classify(d) for d in devices]
    got = pick_camera(cfg, devs)
    if got is not None:
        return f"camera.name {want!r} picks {got['name']} ({got['kind']})"
    if not devs:
        return "no camera found: connect the USB webcam (or open the MacBook lid) and try again"
    if want.lower() == "auto":
        return ("no built-in or USB camera is usable (" + "; ".join(f"{d['name']}: {d['why']}" for d in devs)
                + "): connect a USB webcam, or set camera.name in configs/booth_local.yaml")
    named = [d for d in devs if want.lower() in d["name"].lower()]
    if named:
        return f"camera.name {want!r} matches only " + "; ".join(f"{d['name']} ({d['why']})" for d in named)
    return (f"no camera name contains {want!r} (found: {', '.join(d['name'] for d in devs)}): "
            "set camera.name in configs/booth_local.yaml to part of one of these names, or to auto")


# Permission ------------------------------------------------------------------------------------

def permission_status() -> str:
    """authorized, denied, restricted or not_determined (macOS); unsupported elsewhere or when
    pyobjc is missing (capture is then tried directly)."""
    if sys.platform != "darwin":
        return "unsupported"
    try:
        AVF = _avf()
        return STATUS.get(int(AVF.AVCaptureDevice.authorizationStatusForMediaType_(AVF.AVMediaTypeVideo)),
                          "not_determined")
    except Exception:
        return "unsupported"


def request_permission(timeout_s: float = 30.0) -> str:
    """Ask for camera permission once (the macOS dialog) and return the status. Call it on the
    main thread before any capture thread starts: AVFoundation answers on the main run loop,
    which this spins for up to timeout_s. From another thread it only reports the status."""
    status = permission_status()
    if status != "not_determined" or threading.current_thread() is not threading.main_thread():
        return status
    try:
        AVF = _avf()
        from Foundation import NSDate, NSRunLoop  # noqa: PLC0415  (pyobjc-framework-Cocoa)
    except Exception:
        return "unsupported"
    answered: dict[str, bool] = {}

    def handler(granted: bool) -> None:
        answered["granted"] = bool(granted)

    AVF.AVCaptureDevice.requestAccessForMediaType_completionHandler_(AVF.AVMediaTypeVideo, handler)
    t_end = time.monotonic() + float(timeout_s)
    while "granted" not in answered and time.monotonic() < t_end:
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
    return permission_status()


PERMISSION_FIX = ("open System Settings, Privacy and Security, Camera, turn on Terminal (the app that "
                  "runs wfglink), quit Terminal and open it again")


def video_effects() -> dict[str, Any]:
    """macOS video effects that change the picture (Control Center, Video Effects): Center Stage,
    Portrait, Studio Light, Reactions. True when on; {} elsewhere."""
    if sys.platform != "darwin":
        return {}
    out: dict[str, Any] = {}
    try:
        cls = _avf().AVCaptureDevice
    except Exception:
        return out
    for key, sel in (("center_stage", "isCenterStageEnabled"), ("portrait", "isPortraitEffectEnabled"),
                     ("studio_light", "isStudioLightEnabled"), ("reactions", "reactionEffectsEnabled")):
        try:
            if hasattr(cls, sel):
                out[key] = bool(getattr(cls, sel)())
        except Exception:
            pass
    return out


def _mac_prepare(cfg: dict | None) -> None:
    """Before capture on macOS: OpenCV must not ask for permission from a capture thread (wfglink
    asks on the main thread), and Center Stage is turned off for this process unless
    camera.center_stage is true (it reframes the picture, which changes the scale)."""
    if sys.platform != "darwin":
        return
    os.environ["OPENCV_AVFOUNDATION_SKIP_AUTH"] = "1"
    if bool(_cam(cfg).get("center_stage", False)):
        return
    try:
        cls = _avf().AVCaptureDevice
        if hasattr(cls, "setCenterStageControlMode_"):
            cls.setCenterStageControlMode_(1)      # AVCaptureCenterStageControlModeApp: this app decides
            cls.setCenterStageEnabled_(False)
    except Exception:
        pass


# Capture backends ------------------------------------------------------------------------------

class _PyAVCamera:
    """FFmpeg's avfoundation input (macOS, by device name) or v4l2 (Linux) through PyAV."""

    name = "pyav"

    def __init__(self, device: dict[str, Any], width: int, height: int, fps: float, devices: list[dict]):
        self.device, self.width, self.height, self.fps = device, int(width), int(height), float(fps)
        self.others = [d for d in devices if d.get("unique_id") != device.get("unique_id")]
        self._container = None
        self._stream = None
        self._ready: list = []
        self.options: dict[str, str] = {}

    def open(self, timeout_s: float) -> None:
        import av

        if sys.platform == "darwin":
            fmt, pix_key = "avfoundation", "pixel_format"
            if any(d.get("name") == self.device.get("name") for d in self.others):
                raise SourceError("two cameras share this name, so FFmpeg cannot tell them apart")
            url = f"{self.device['name']}:none"
        elif sys.platform.startswith("linux"):
            fmt, pix_key = "v4l2", "input_format"
            url = str(self.device.get("unique_id"))
        else:
            raise SourceError(f"PyAV capture is not supported on {sys.platform}")
        if fmt not in av.formats_available:
            raise SourceError(f"this PyAV build has no {fmt} input")
        sizes = list(dict.fromkeys([(self.width, self.height), (1280, 720), (1920, 1080), (640, 480)]))
        rates = list(dict.fromkeys([self.fps, 30.0, 29.97, 25.0, 24.0, 15.0, 60.0]))
        errors = []
        for w, h in sizes:
            for fps in rates:
                opts = {"video_size": f"{w}x{h}", "framerate": f"{fps:g}"}
                if fmt == "v4l2":
                    opts[pix_key] = "mjpeg"
                try:
                    self._container = av.open(url, format=fmt, options=opts, timeout=(timeout_s, 2.0))
                except Exception as exc:   # FFmpeg reports an unsupported size or rate as an error
                    errors.append(f"{w}x{h}@{fps:g}: {str(exc)[:80]}")
                    continue
                self._stream = self._container.streams.video[0]
                self.options = opts
                return
        raise SourceError("PyAV could not open the camera: " + " | ".join(errors[-2:]))

    def read(self, wait_s: float = 1.0) -> tuple[np.ndarray, float | None] | None:
        """The next frame, or None when none came within wait_s. FFmpeg's avfoundation input
        answers EAGAIN while no new frame is ready, and PyAV raises that out of demux(), which
        ends the generator; so each read starts a fresh demux() and waits on EAGAIN."""
        if self._container is None:
            raise SourceError("camera not open")
        if self._ready:
            vf = self._ready.pop(0)
            return vf.to_ndarray(format="bgr24"), (float(vf.time) if vf.time is not None else None)
        t_end = time.monotonic() + wait_s
        while True:
            try:
                for packet in self._container.demux(self._stream):
                    frames = list(packet.decode())       # a compressed camera stream may return several
                    if frames:
                        vf, self._ready = frames[0], frames[1:]
                        return vf.to_ndarray(format="bgr24"), (float(vf.time) if vf.time is not None else None)
                    if packet.size == 0:
                        raise SourceError("the camera stream ended")
                raise SourceError("the camera stream ended")
            except BlockingIOError:                   # EAGAIN: no new frame yet
                if time.monotonic() >= t_end:
                    return None
                time.sleep(0.002)
            except SourceError:
                raise
            except EOFError:
                raise SourceError("the camera stream ended") from None
            except Exception as exc:
                raise SourceError(f"camera read failed: {str(exc)[:80]}") from exc

    def close(self) -> None:
        if self._container is not None:
            try:
                self._container.close()
            except Exception:
                pass
        self._container = None
        self._stream = None


class _OpenCVCamera:
    """OpenCV's AVFoundation backend (macOS) or V4L2 (Linux), by index."""

    name = "opencv"

    def __init__(self, device: dict[str, Any], width: int, height: int, fps: float, devices: list[dict]):
        self.device, self.width, self.height, self.fps = device, int(width), int(height), float(fps)
        self._cap = None
        self.options: dict[str, str] = {}

    def open(self, timeout_s: float) -> None:
        import cv2

        idx = self.device.get("index")
        if idx is None:
            raise SourceError("OpenCV has no index for this camera")
        api = (cv2.CAP_AVFOUNDATION if sys.platform == "darwin"
               else cv2.CAP_V4L2 if sys.platform.startswith("linux") else cv2.CAP_ANY)
        cap = cv2.VideoCapture(int(idx), api)
        if not cap.isOpened():
            cap.release()
            raise SourceError(f"OpenCV could not open camera index {idx}")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        self._cap = cap
        self.options = {"index": str(idx)}

    def read(self) -> tuple[np.ndarray, float | None] | None:
        if self._cap is None:
            raise SourceError("camera not open")
        ok, img = self._cap.read()        # AVFoundation's grab gives up after about 1 s
        return (img, None) if ok and img is not None else None

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
        self._cap = None


BACKENDS: dict[str, Callable[..., Any]] = {"pyav": _PyAVCamera, "opencv": _OpenCVCamera}


class CameraSource(Source):
    """The picked camera as a Source (see the module docstring).

    open() raises SourceError when no usable camera is there (state "no_camera"), when macOS
    camera permission is missing (state "denied" or "not_determined"), or when no backend
    delivers a first frame within camera.open_timeout_s. After a successful open, read() never
    raises for a camera failure: it returns None while the camera is opened again with backoff.
    """

    kind = "camera"
    is_live = True
    _winners: dict[str, str] = {}      # uniqueID -> the backend that worked last (per process)

    def __init__(self, cfg: dict | None = None, device: dict[str, Any] | None = None,
                 clock: Callable[[], float] = time.monotonic, devices: Callable[[], list[dict]] | None = None,
                 backends: dict[str, Callable[..., Any]] | None = None):
        super().__init__("camera")
        c = _cam(cfg)
        self.cfg = cfg or {}
        self.width, self.height = int(c.get("width", 1280)), int(c.get("height", 720))
        self.fps = float(c.get("fps", 30))
        b = str(c.get("backend", "auto"))
        self.order = ["pyav", "opencv"] if b == "auto" else [b]
        self.open_timeout_s = float(c.get("open_timeout_s", 8.0))
        self.stall_s = float(c.get("stall_s", 2.0))
        self.backoff_min_s, self.backoff_max_s = float(c.get("backoff_min_s", 0.5)), float(c.get("backoff_max_s", 5.0))
        self.device = device
        self.clock = clock
        self._list = devices or list_cameras
        self._backends = backends or BACKENDS
        self.state = "closed"
        self.backend: str | None = None
        self.last_error = ""
        self.failures = 0
        self.reopens = 0
        self._inner = None
        self._pending: tuple[np.ndarray, float | None] | None = None
        self._t0: float | None = None
        self._anchor: tuple[float, float] | None = None     # (device time, source time) of the first frame after an open
        self._last_t = -1.0
        self._last_frame_wall = 0.0
        self._next_open = 0.0
        self._backoff = self.backoff_min_s
        self._opened = False

    # open and close ------------------------------------------------------------------------
    def open(self) -> None:
        status = permission_status()
        if status in ("denied", "restricted", "not_determined"):
            self.state = "denied" if status != "not_determined" else "not_determined"
            hint = (PERMISSION_FIX if status != "not_determined"
                    else "run python -m wfglink cameras --request in Terminal and allow the camera")
            raise SourceError(f"camera permission is {status}: {hint}")
        _mac_prepare(self.cfg)
        devs = self._list()
        if self.device is None:
            self.device = pick_camera(self.cfg, devs)
        if self.device is None:
            self.state = "no_camera"
            raise SourceError(explain_pick(self.cfg, devs))
        self.name = str(self.device.get("name") or "camera")
        self._open_backend(devs)
        self._opened = True
        self.state = "ok"

    def _open_backend(self, devs: list[dict]) -> None:
        uid = str(self.device.get("unique_id"))
        order = [b for b in self.order if b in self._backends]
        if self._winners.get(uid) in order:
            order.remove(self._winners[uid])
            order.insert(0, self._winners[uid])
        errors = []
        for name in order:
            inner = self._backends[name](self.device, self.width, self.height, self.fps, devs)
            try:
                inner.open(self.open_timeout_s)
                first = self._first_frame(inner)
            except Exception as exc:
                errors.append(f"{name}: {str(exc)[:120]}")
                try:
                    inner.close()
                except Exception:
                    pass
                continue
            self._inner, self._pending, self.backend = inner, first, name
            self._winners[uid] = name
            self._anchor = None
            h, w = first[0].shape[:2]
            self.info = {"name": self.name, "unique_id": uid, "kind": self.device.get("kind"), "backend": name,
                         "options": dict(getattr(inner, "options", {}) or {}), "native_size": [w, h],
                         "size": list(self._out_size(w, h)), "fps_requested": self.fps}
            self._last_frame_wall = self.clock()
            return
        raise SourceError(f"{self.name} did not open: " + "; ".join(errors))

    def _first_frame(self, inner) -> tuple[np.ndarray, float | None]:
        t_end = self.clock() + self.open_timeout_s
        while self.clock() < t_end:
            got = inner.read()
            if got is not None:
                return got
            time.sleep(0.01)
        raise SourceError(f"no frame within {self.open_timeout_s:g} s")

    def close(self) -> None:
        if self._inner is not None:
            try:
                self._inner.close()
            except Exception:
                pass
        self._inner = None
        self._pending = None
        self._opened = False
        self.state = "closed"

    # reading ---------------------------------------------------------------------------------
    def _out_size(self, w: int, h: int) -> tuple[int, int]:
        if w <= self.width:
            return w, h
        return self.width, int(round(h * self.width / w))

    def _fail(self, why: str) -> None:
        self.failures += 1
        self.last_error = why
        if self._inner is not None:
            try:
                self._inner.close()
            except Exception:
                pass
        self._inner = None
        self._pending = None
        self.state = "reconnecting"
        self._next_open = self.clock() + self._backoff
        self._backoff = min(self._backoff * 2.0, self.backoff_max_s)

    def _reopen(self) -> bool:
        try:
            devs = self._list()
            uid = self.device.get("unique_id") if self.device else None
            dev = next((d for d in devs if d.get("unique_id") == uid and d.get("usable")), None)
            if dev is None:
                dev = pick_camera(self.cfg, devs)
            if dev is None:
                raise SourceError(explain_pick(self.cfg, devs))
            self.device, self.name = dev, str(dev.get("name") or "camera")
            self._open_backend(devs)
        except Exception as exc:
            self._fail(str(exc)[:160])
            return False
        self.reopens += 1
        self.state = "ok"
        return True

    def read(self) -> Frame | None:
        if not self._opened:
            raise SourceError("source not opened")
        now = self.clock()
        if self._inner is None:
            if now < self._next_open:
                time.sleep(min(0.05, max(0.0, self._next_open - now)))
                return None
            if not self._reopen():
                return None
        got, self._pending = self._pending, None
        if got is None:
            try:
                got = self._inner.read()
            except Exception as exc:
                self._fail(str(exc)[:160])
                return None
            if got is None:
                if self.clock() - self._last_frame_wall > self.stall_s:
                    self._fail(f"no frame for {self.stall_s:g} s")
                return None
        img, t_dev = got
        now = self.clock()
        self._last_frame_wall = now
        self._backoff = self.backoff_min_s
        if self._t0 is None:
            self._t0 = now
        t_wall = now - self._t0
        t = t_wall
        if t_dev is not None:
            # The device's own timestamps are steadier than delivery times; anchored at the
            # first frame after each open, and re-anchored when they drift from the clock.
            if self._anchor is None or abs(self._anchor[1] + (t_dev - self._anchor[0]) - t_wall) > 0.25:
                self._anchor = (t_dev, t_wall)
            t = self._anchor[1] + (t_dev - self._anchor[0])
        if t <= self._last_t:
            t = self._last_t + 1e-3
        self._last_t = t
        h, w = img.shape[:2]
        ow, oh = self._out_size(w, h)
        if (ow, oh) != (w, h):
            import cv2

            img = cv2.resize(img, (ow, oh), interpolation=cv2.INTER_AREA)
        self.state = "ok"
        return Frame(np.ascontiguousarray(img), float(t), self._next_index(), now,
                     {"camera": self.name, "backend": self.backend, "source": "camera",
                      "unique_id": self.device.get("unique_id") if self.device else None})


# Fake camera -----------------------------------------------------------------------------------

class FakeCameraSource(Source):
    """A video file, or a generated phone scene, played like a camera.

    path: a video file (looped); otherwise `scene` names a generated scene of
    wfglink.ember.synth.SCENES (default "booth": three phones in a room), rendered live.
    realtime: pace frames to the clock (a file plays at its own speed; a generated scene is
    rendered at the time on the clock, so motion stays true when rendering is slow). Without
    realtime, frames come as fast as they can be made, with their own media times.
    frame.meta has "camera" ("fake: <name>"), "fake": True and "synthetic" (generated or not).
    """

    kind = "camera"
    is_live = True

    def __init__(self, path: str | os.PathLike | None = None, *, scene: str | dict | None = None,
                 realtime: bool = True, loop: bool = True, cfg: dict | None = None, seed: int = 1,
                 size: tuple[int, int] | None = None, fps: float | None = None):
        label = Path(path).name if path else str(scene if isinstance(scene, str) else "scene")
        super().__init__(f"fake: {label}")
        self.path = Path(path) if path else None
        self.scene = scene or "booth"
        self.realtime, self.loop = bool(realtime), bool(loop)
        self.cfg = cfg or {}
        c = _cam(cfg)
        self.size = tuple(size) if size else (int(c.get("width", 1280)), int(c.get("height", 720)))
        self.fps = float(fps or c.get("fps", 30))
        self.seed = int(seed)
        self.state = "closed"
        self._file: FileSource | None = None
        self._scene = None
        self._t0: float | None = None
        self._n = 0
        self._last_t = -1.0

    def open(self) -> None:
        if self.path is not None:
            self._file = FileSource(self.path, loop=self.loop, realtime=self.realtime)
            self._file.open()
            self.info = {"name": self.name, "path": str(self.path), **self._file.info}
        else:
            from wfglink.ember.synth import LiveScene

            self._scene = LiveScene(self.scene, size=self.size, fps=self.fps, seed=self.seed)
            self.info = {"name": self.name, "scene": self._scene.name, "size": list(self.size), "fps": self.fps}
        self._t0 = time.monotonic()
        self._n = 0
        self.state = "ok"

    def read(self) -> Frame | None:
        if self._file is not None:
            f = self._file.read()
            if f is None:
                return None
            return Frame(f.image, f.t, self._next_index(), time.monotonic(),
                         {"camera": self.name, "fake": True, "synthetic": False, "source": "fake_camera"})
        if self._scene is None:
            raise SourceError("source not opened")
        if self.realtime:
            due = self._t0 + self._n / self.fps
            wait = due - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            t = time.monotonic() - self._t0
            self._n = max(self._n + 1, int(t * self.fps) + 1)
        else:
            t = self._n / self.fps
            self._n += 1
        if not self.loop and t > self._scene.duration_s:
            return None
        t = max(t, self._last_t + 1e-3)
        self._last_t = t
        img = self._scene.render(t)
        return Frame(img, float(t), self._next_index(), time.monotonic(),
                     {"camera": self.name, "fake": True, "synthetic": True, "source": "fake_camera"})

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
        self._file = None
        self._scene = None
        self.state = "closed"
