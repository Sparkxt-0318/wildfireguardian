"""macOS camera helpers through pyobjc AVFoundation.

- Camera permission: request it on the main thread before any capture thread starts (the
  OpenCV backend can only ask from the main thread; wfglink sets
  OPENCV_AVFOUNDATION_SKIP_AUTH=1 and asks here instead).
- Device discovery with the properties that matter: name, uniqueID, model, device type,
  isContinuityCamera, formats (size and frame-rate ranges) and exposure, focus and white
  balance modes.
- Index mapping: OpenCV orders devices as video plus muxed devices sorted by uniqueID;
  FFmpeg's avfoundation input uses video then muxed devices in discovery order. Opening
  by name avoids most of this, but the indices are reported for the check A record.
- An exposure-lock probe (macOS only exposes locked, auto and continuous modes).

Everything here fails soft: on error the result carries an "error" string, because the
sitting 1 check must finish and report even when a call is unavailable.
"""
from __future__ import annotations

import sys
import time
from typing import Any

if sys.platform != "darwin":  # pragma: no cover - imported only on macOS
    raise ImportError("wfglink.io.macos is macOS only")

import AVFoundation as AVF  # noqa: E402
from Foundation import NSDate, NSRunLoop  # noqa: E402

try:  # CoreMedia gives format dimensions and pixel format codes
    import CoreMedia as CM  # noqa: E402
except Exception:  # pragma: no cover
    CM = None

STATUS = {0: "not_determined", 1: "restricted", 2: "denied", 3: "authorized"}
EXPOSURE_MODES = {"locked": 0, "auto": 1, "continuous": 2, "custom": 3}
FOCUS_MODES = {"locked": 0, "auto": 1, "continuous": 2}
WB_MODES = {"locked": 0, "auto": 1, "continuous": 2}


def authorization_status() -> str:
    return STATUS.get(int(AVF.AVCaptureDevice.authorizationStatusForMediaType_(AVF.AVMediaTypeVideo)), "unknown")


def request_camera_access(timeout_s: float = 60.0) -> str:
    """Ask for camera permission (shows the system prompt once). Call on the main thread."""
    status = authorization_status()
    if status != "not_determined":
        return status
    done: dict[str, bool] = {}

    def handler(granted):
        done["granted"] = bool(granted)

    AVF.AVCaptureDevice.requestAccessForMediaType_completionHandler_(AVF.AVMediaTypeVideo, handler)
    t_end = time.monotonic() + timeout_s
    while "granted" not in done and time.monotonic() < t_end:
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
    return authorization_status()


def _call(obj, name: str, default=None):
    try:
        if obj.respondsToSelector_(name):
            return getattr(obj, name)()
    except Exception:
        pass
    return default


def _fourcc(code: int) -> str:
    try:
        return "".join(chr((int(code) >> s) & 0xFF) for s in (24, 16, 8, 0))
    except Exception:
        return str(code)


def device_formats(dev) -> list[dict[str, Any]]:
    out = []
    for fmt in dev.formats() or []:
        entry: dict[str, Any] = {}
        try:
            desc = fmt.formatDescription()
            if CM is not None:
                dims = CM.CMVideoFormatDescriptionGetDimensions(desc)
                entry["width"], entry["height"] = int(dims.width), int(dims.height)
                entry["pixel_format"] = _fourcc(CM.CMFormatDescriptionGetMediaSubType(desc))
            ranges = fmt.videoSupportedFrameRateRanges() or []
            entry["fps_ranges"] = [[float(r.minFrameRate()), float(r.maxFrameRate())] for r in ranges]
        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
        out.append(entry)
    return out


def _device_types() -> list:
    names = ["AVCaptureDeviceTypeBuiltInWideAngleCamera", "AVCaptureDeviceTypeExternal",
             "AVCaptureDeviceTypeExternalUnknown", "AVCaptureDeviceTypeContinuityCamera",
             "AVCaptureDeviceTypeDeskViewCamera"]
    return [getattr(AVF, n) for n in names if hasattr(AVF, n)]


def _legacy_devices() -> list:
    """Video plus muxed devices from the deprecated API (the order OpenCV and FFmpeg use)."""
    devs = list(AVF.AVCaptureDevice.devicesWithMediaType_(AVF.AVMediaTypeVideo) or [])
    devs += list(AVF.AVCaptureDevice.devicesWithMediaType_(AVF.AVMediaTypeMuxed) or [])
    return devs


def discover() -> dict[str, Any]:
    """All video capture devices with their properties and both index orderings."""
    result: dict[str, Any] = {"devices": []}
    try:
        legacy = _legacy_devices()
    except Exception as exc:
        legacy = []
        result["legacy_error"] = f"{type(exc).__name__}: {exc}"
    try:
        session = AVF.AVCaptureDeviceDiscoverySession.discoverySessionWithDeviceTypes_mediaType_position_(
            _device_types(), AVF.AVMediaTypeVideo, AVF.AVCaptureDevicePositionUnspecified)
        found = list(session.devices() or [])
    except Exception as exc:
        found = []
        result["discovery_error"] = f"{type(exc).__name__}: {exc}"
    by_uid = {}
    for dev in found + legacy:
        uid = str(dev.uniqueID())
        by_uid.setdefault(uid, dev)
    opencv_order = sorted([str(d.uniqueID()) for d in legacy])
    ffmpeg_order = [str(d.uniqueID()) for d in legacy]
    for uid, dev in by_uid.items():
        info: dict[str, Any] = {
            "name": str(dev.localizedName()),
            "unique_id": uid,
            "model_id": str(_call(dev, "modelID", "")),
            "manufacturer": str(_call(dev, "manufacturer", "")),
            "device_type": str(_call(dev, "deviceType", "")),
            "is_continuity_camera": bool(_call(dev, "isContinuityCamera", False)),
            "connected": bool(_call(dev, "isConnected", True)),
            "opencv_index": opencv_order.index(uid) if uid in opencv_order else None,
            "ffmpeg_index": ffmpeg_order.index(uid) if uid in ffmpeg_order else None,
            "in_discovery_session": any(str(d.uniqueID()) == uid for d in found),
        }
        info["is_desk_view"] = "deskview" in info["device_type"].lower().replace(" ", "") or "desk view" in info["name"].lower()
        try:
            info["exposure_modes"] = [k for k, v in EXPOSURE_MODES.items() if dev.isExposureModeSupported_(v)]
            info["focus_modes"] = [k for k, v in FOCUS_MODES.items() if dev.isFocusModeSupported_(v)]
            info["white_balance_modes"] = [k for k, v in WB_MODES.items() if dev.isWhiteBalanceModeSupported_(v)]
        except Exception as exc:
            info["modes_error"] = f"{type(exc).__name__}: {exc}"
        info["formats"] = device_formats(dev)
        result["devices"].append(info)
    return result


def device_by_uid(uid: str):
    for dev in _legacy_devices():
        if str(dev.uniqueID()) == uid:
            return dev
    return AVF.AVCaptureDevice.deviceWithUniqueID_(uid)


def probe_exposure_lock(uid: str) -> dict[str, Any]:
    """Try to lock exposure, focus and white balance, then restore continuous modes."""
    out: dict[str, Any] = {"unique_id": uid}
    dev = device_by_uid(uid)
    if dev is None:
        return {**out, "error": "device not found"}
    try:
        ok, err = dev.lockForConfiguration_(None)
    except Exception as exc:
        return {**out, "error": f"lockForConfiguration raised {type(exc).__name__}: {exc}"}
    if not ok:
        return {**out, "error": f"lockForConfiguration failed: {err}"}
    try:
        for kind, setter, supported, modes in (
            ("exposure", "setExposureMode_", "isExposureModeSupported_", EXPOSURE_MODES),
            ("focus", "setFocusMode_", "isFocusModeSupported_", FOCUS_MODES),
            ("white_balance", "setWhiteBalanceMode_", "isWhiteBalanceModeSupported_", WB_MODES),
        ):
            can_lock = bool(getattr(dev, supported)(modes["locked"]))
            out[f"{kind}_lock_supported"] = can_lock
            if can_lock:
                try:
                    getattr(dev, setter)(modes["locked"])
                    out[f"{kind}_lock_set"] = True
                except Exception as exc:
                    out[f"{kind}_lock_set"] = f"{type(exc).__name__}: {exc}"
                if getattr(dev, supported)(modes["continuous"]):
                    getattr(dev, setter)(modes["continuous"])
    finally:
        dev.unlockForConfiguration()
    return out


def mac_versions() -> dict[str, str]:
    import platform

    return {"macos": platform.mac_ver()[0], "machine": platform.machine()}
