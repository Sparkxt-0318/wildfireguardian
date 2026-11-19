"""Wire protocol between the roof unit (Pi) and the laptop (DESIGN.md section 2).

One WebSocket, ``ws://<pi>:8770/stream``; text frames, one JSON object each. This module is shared by the Pi
(server, drivers, recorder, replay, synth) and the laptop (``crossing.link``), so it has no hardware imports and
only needs the standard library plus numpy.

Envelope (every message)::

    {"v": 1, "type": "...", "unit_id": "VU-01", "session_id": "VU-01-20261117T101500Z", "sim": false,
     "t_mono": 12345.678,            # Pi time.monotonic() at creation [s]
     "t_utc": "2026-11-17T10:15:00.123Z" | null}

Types: ``hello``, ``heartbeat``, ``reading``, ``event`` (fields in ``REQUIRED``). Sensor names are fixed
(``SENSORS``); heartbeats may also use the pseudo-sensor ``"unit"`` (the server itself).

Units on the wire: temperatures in degrees C except the thermal image (kelvin, ``raw / raw_per_k``), distances in
m, speeds in m/s, angles in degrees, radar range profile in dB (20 log10 of linear magnitude), point SNR in dB.

Conventions that matter to consumers:

- ``make`` turns non-finite floats (NaN, +-inf) into ``null``: JSON has no NaN, and on the laptop ``null`` means
  "missing", which fails closed. numpy scalars/arrays are converted to plain JSON types.
- ``parse`` rejects anything malformed with ``ProtocolError`` (bad JSON, NaN/Infinity tokens, wrong version, unknown
  type or sensor, missing required key, wrong value type). Extra keys are allowed (forward compatible). ``parse``
  checks structure and types only; physical plausibility (e.g. a 5000 C thermocouple) is the laptop's job.
- ``seq`` of a ``reading`` counts every reading the driver produced (and the recorder wrote). The server sends
  thermal frames to clients at a reduced rate (default 4 Hz), so on the wire the thermal ``seq`` advances by the
  decimation step; those gaps are decimation, not loss. Real per-client losses are reported as ``event``
  ``kind="dropped"``.
- Freshness is decided by the receiver's own monotonic clock, never by ``t_mono``/``t_utc`` or ``status`` alone.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import time
import zlib
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

import numpy as np

PROTOCOL_VERSION = 1

SENSORS = ("thermal", "radar", "tc_plate", "tc_housing", "tc_air", "imu", "gnss", "pi")
TC_SENSORS = ("tc_plate", "tc_housing", "tc_air")
HEARTBEAT_SENSORS = SENSORS + ("unit",)
TYPES = ("hello", "heartbeat", "reading", "event")
STATUSES = ("ok", "no_device", "error", "stale", "sim_ended")
TC_FAULTS = (None, "open", "short_gnd", "short_vcc", "spi")

ENVELOPE = ("v", "type", "unit_id", "session_id", "sim", "t_mono", "t_utc")
REQUIRED: Dict[str, tuple] = {
    "hello": ("sensors", "version", "config_digest"),
    "heartbeat": ("sensor", "status", "detail", "last_reading_seq", "rate_hz", "seq"),
    "reading": ("sensor", "seq", "data"),
    "event": ("kind", "detail"),
}
DATA_KEYS: Dict[str, tuple] = {
    "thermal": ("w", "h", "enc", "raw_per_k", "pix", "gain", "shutter"),
    "radar": ("frame", "range_res_m", "n_bins", "range_profile_db", "az_heatmap", "points", "tlv_types",
              "frame_ok"),
    "tc_plate": ("temp_c", "cj_c", "fault"),
    "tc_housing": ("temp_c", "cj_c", "fault"),
    "tc_air": ("temp_c", "cj_c", "fault"),
    "imu": ("roll_deg", "pitch_deg", "heading_deg", "grav", "calib"),
    "gnss": ("fix", "lat", "lon", "alt_m", "speed_m_s", "course_deg", "hdop", "sats", "utc"),
    "pi": ("cpu_c", "throttled_hex", "under_voltage_now", "under_voltage_ever", "input_v", "disk_free_mb",
           "rec_bytes"),
}
# numeric-or-null scalar fields checked by parse
_NUMERIC: Dict[str, tuple] = {
    "tc_plate": ("temp_c", "cj_c"), "tc_housing": ("temp_c", "cj_c"), "tc_air": ("temp_c", "cj_c"),
    "imu": ("roll_deg", "pitch_deg", "heading_deg"),
    "gnss": ("lat", "lon", "alt_m", "speed_m_s", "course_deg", "hdop", "sats"),
    "pi": ("cpu_c", "input_v", "disk_free_mb", "rec_bytes"),
}

THERMAL_ENC = "u16-zlib-b64"
IQ_ENC = "i16-zlib-b64"
RAW_PER_K = 64.0           # TC001: 16-bit raw / 64 = kelvin


class ProtocolError(ValueError):
    """A message that does not follow this protocol. The laptop drops and counts these."""


# ----------------------------------------------------------------------------------------------- helpers

def utc_now_iso(ts: Optional[float] = None) -> str:
    """UTC wall-clock time as ``YYYY-MM-DDTHH:MM:SS.mmmZ`` (millisecond resolution)."""
    dt = datetime.fromtimestamp(time.time() if ts is None else ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (dt.microsecond // 1000)


def make_session_id(unit_id: str, ts: Optional[float] = None) -> str:
    """``<unit_id>-YYYYmmddTHHMMSSZ`` from the UTC wall clock."""
    dt = datetime.fromtimestamp(time.time() if ts is None else ts, tz=timezone.utc)
    return "%s-%s" % (unit_id, dt.strftime("%Y%m%dT%H%M%SZ"))


def config_digest(cfg: Any) -> str:
    """First 16 hex digits of sha256 over the canonical JSON of ``cfg`` (sorted keys)."""
    blob = json.dumps(sanitize(cfg), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def sanitize(obj: Any) -> Any:
    """Convert to plain JSON types: numpy -> Python, tuples -> lists, non-finite floats -> None."""
    if obj is None or isinstance(obj, (str, bool)):
        return obj
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        return f if math.isfinite(f) else None
    if isinstance(obj, dict):
        return {str(k): sanitize(v) for k, v in obj.items()}
    if isinstance(obj, np.ndarray):
        return sanitize(obj.tolist())
    if isinstance(obj, (list, tuple)):
        return [sanitize(v) for v in obj]
    if isinstance(obj, bytes):
        raise ProtocolError("raw bytes cannot go on the wire; encode them first")
    return obj


def dumps(msg: dict) -> str:
    """Compact JSON text for one message (``allow_nan=False``: call ``make``/``sanitize`` first)."""
    try:
        return json.dumps(msg, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ProtocolError("cannot serialise message: %s" % exc) from exc


# ----------------------------------------------------------------------------------------------- make / parse

def make(type: str, **fields: Any) -> dict:  # noqa: A002 - name fixed by DESIGN.md
    """Build and validate one message.

    Envelope defaults: ``v=1``, ``sim=False``, ``t_mono=time.monotonic()``, ``t_utc=utc_now_iso()``.
    ``unit_id`` and ``session_id`` are required. Synthetic generators pass their own ``t_mono``/``t_utc``.
    Raises ``ProtocolError`` if the result would not pass ``parse``.
    """
    msg: Dict[str, Any] = {"v": PROTOCOL_VERSION, "type": type}
    msg["unit_id"] = fields.pop("unit_id", None)
    msg["session_id"] = fields.pop("session_id", None)
    msg["sim"] = fields.pop("sim", False)
    t_mono = fields.pop("t_mono", None)
    msg["t_mono"] = time.monotonic() if t_mono is None else t_mono
    msg["t_utc"] = fields.pop("t_utc", "now")
    if msg["t_utc"] == "now":
        msg["t_utc"] = utc_now_iso()
    msg.update(fields)
    msg = sanitize(msg)
    validate(msg)
    return msg


def parse(text: Any) -> dict:
    """Parse one wire message (str or bytes) and validate it. Raises ``ProtocolError`` on anything malformed."""
    if isinstance(text, (bytes, bytearray)):
        try:
            text = bytes(text).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtocolError("not UTF-8") from exc
    if not isinstance(text, str):
        raise ProtocolError("message must be str or bytes")

    def _no_constants(name: str) -> Any:
        raise ProtocolError("non-finite number %s" % name)

    try:
        msg = json.loads(text, parse_constant=_no_constants)
    except ProtocolError:
        raise
    except (ValueError, RecursionError) as exc:
        raise ProtocolError("bad JSON: %s" % exc) from exc
    validate(msg)
    return msg


def _is_num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _is_int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _req(d: dict, keys: Iterable[str], where: str) -> None:
    for k in keys:
        if k not in d:
            raise ProtocolError("%s: missing key %r" % (where, k))


def validate(msg: Any) -> None:
    """Structural validation used by ``make`` and ``parse``. Raises ``ProtocolError``."""
    if not isinstance(msg, dict):
        raise ProtocolError("message is not an object")
    _req(msg, ENVELOPE, "envelope")
    if msg["v"] != PROTOCOL_VERSION or isinstance(msg["v"], bool):
        raise ProtocolError("unsupported protocol version %r" % (msg["v"],))
    mtype = msg["type"]
    if mtype not in TYPES:
        raise ProtocolError("unknown type %r" % (mtype,))
    if not isinstance(msg["unit_id"], str) or not msg["unit_id"]:
        raise ProtocolError("unit_id must be a non-empty string")
    if not isinstance(msg["session_id"], str) or not msg["session_id"]:
        raise ProtocolError("session_id must be a non-empty string")
    if not isinstance(msg["sim"], bool):
        raise ProtocolError("sim must be a bool")
    if not _is_num(msg["t_mono"]):
        raise ProtocolError("t_mono must be a finite number")
    if msg["t_utc"] is not None and not isinstance(msg["t_utc"], str):
        raise ProtocolError("t_utc must be a string or null")
    _req(msg, REQUIRED[mtype], mtype)

    if mtype == "hello":
        if not isinstance(msg["sensors"], list) or any(s not in SENSORS for s in msg["sensors"]):
            raise ProtocolError("hello.sensors must list known sensor names")
    elif mtype == "heartbeat":
        if msg["sensor"] not in HEARTBEAT_SENSORS:
            raise ProtocolError("unknown heartbeat sensor %r" % (msg["sensor"],))
        if msg["status"] not in STATUSES:
            raise ProtocolError("unknown status %r" % (msg["status"],))
        if not isinstance(msg["detail"], str):
            raise ProtocolError("heartbeat.detail must be a string")
        lrs = msg["last_reading_seq"]
        if lrs is not None and not (_is_int(lrs) and lrs >= 0):
            raise ProtocolError("last_reading_seq must be a non-negative int or null")
        if msg["rate_hz"] is not None and not _is_num(msg["rate_hz"]):
            raise ProtocolError("rate_hz must be a number or null")
        if not (_is_int(msg["seq"]) and msg["seq"] >= 0):
            raise ProtocolError("heartbeat.seq must be a non-negative int")
    elif mtype == "reading":
        sensor = msg["sensor"]
        if sensor not in SENSORS:
            raise ProtocolError("unknown sensor %r" % (sensor,))
        if not (_is_int(msg["seq"]) and msg["seq"] >= 0):
            raise ProtocolError("reading.seq must be a non-negative int")
        _validate_data(sensor, msg["data"])
    elif mtype == "event":
        if not isinstance(msg["kind"], str) or not msg["kind"]:
            raise ProtocolError("event.kind must be a non-empty string")
        if not isinstance(msg["detail"], str):
            raise ProtocolError("event.detail must be a string")


def _validate_data(sensor: str, data: Any) -> None:
    where = "%s.data" % sensor
    if not isinstance(data, dict):
        raise ProtocolError("%s must be an object" % where)
    _req(data, DATA_KEYS[sensor], where)
    for k in _NUMERIC.get(sensor, ()):
        if data[k] is not None and not _is_num(data[k]):
            raise ProtocolError("%s.%s must be a number or null" % (where, k))
    if sensor in TC_SENSORS:
        if data["fault"] not in TC_FAULTS:
            raise ProtocolError("%s.fault %r unknown" % (where, data["fault"]))
    elif sensor == "thermal":
        if data["enc"] != THERMAL_ENC:
            raise ProtocolError("%s.enc must be %r" % (where, THERMAL_ENC))
        if not (_is_int(data["w"]) and _is_int(data["h"]) and data["w"] > 0 and data["h"] > 0):
            raise ProtocolError("%s.w/h must be positive ints" % where)
        if not (_is_num(data["raw_per_k"]) and data["raw_per_k"] > 0):
            raise ProtocolError("%s.raw_per_k must be > 0" % where)
        if not isinstance(data["pix"], str):
            raise ProtocolError("%s.pix must be base64 text" % where)
        if not isinstance(data["shutter"], bool):
            raise ProtocolError("%s.shutter must be a bool" % where)
    elif sensor == "radar":
        if not _is_int(data["frame"]) or not _is_int(data["n_bins"]) or data["n_bins"] < 0:
            raise ProtocolError("%s.frame/n_bins must be ints" % where)
        if data["range_res_m"] is not None and not _is_num(data["range_res_m"]):
            raise ProtocolError("%s.range_res_m must be a number or null" % where)
        rp = data["range_profile_db"]
        if rp is not None and (not isinstance(rp, list) or not all(v is None or _is_num(v) for v in rp)):
            raise ProtocolError("%s.range_profile_db must be a list of numbers or null" % where)
        hm = data["az_heatmap"]
        if hm is not None:
            if not isinstance(hm, dict):
                raise ProtocolError("%s.az_heatmap must be an object or null" % where)
            _req(hm, ("n_ant", "enc", "iq"), where + ".az_heatmap")
            if hm["enc"] != IQ_ENC or not _is_int(hm["n_ant"]) or hm["n_ant"] <= 0:
                raise ProtocolError("%s.az_heatmap bad enc/n_ant" % where)
        pts = data["points"]
        if pts is not None:
            if not isinstance(pts, list) or any(not isinstance(p, list) or len(p) != 5 for p in pts):
                raise ProtocolError("%s.points must be [[x,y,z,doppler,snr_db],...] or null" % where)
        if not isinstance(data["tlv_types"], list) or not isinstance(data["frame_ok"], bool):
            raise ProtocolError("%s.tlv_types/frame_ok bad" % where)
    elif sensor == "imu":
        g = data["grav"]
        if g is not None and (not isinstance(g, list) or len(g) != 3 or not all(v is None or _is_num(v)
                                                                              for v in g)):
            raise ProtocolError("%s.grav must be [gx,gy,gz] or null" % where)
        c = data["calib"]
        if c is not None:
            if not isinstance(c, dict):
                raise ProtocolError("%s.calib must be an object or null" % where)
            _req(c, ("sys", "gyro", "accel", "mag"), where + ".calib")
    elif sensor == "gnss":
        if data["fix"] not in (0, 1, 2) or isinstance(data["fix"], bool):
            raise ProtocolError("%s.fix must be 0, 1 or 2" % where)
        if data["utc"] is not None and not isinstance(data["utc"], str):
            raise ProtocolError("%s.utc must be a string or null" % where)
    elif sensor == "pi":
        for k in ("under_voltage_now", "under_voltage_ever"):
            if data[k] is not None and not isinstance(data[k], bool):
                raise ProtocolError("%s.%s must be a bool or null" % (where, k))
        if data["throttled_hex"] is not None and not isinstance(data["throttled_hex"], str):
            raise ProtocolError("%s.throttled_hex must be a string or null" % where)


class Context:
    """Envelope constants of one unit session, so callers write ``ctx.make("reading", sensor=..., ...)``."""

    def __init__(self, unit_id: str = "VU-01", session_id: Optional[str] = None, sim: bool = False):
        self.unit_id = unit_id
        self.session_id = session_id or make_session_id(unit_id)
        self.sim = bool(sim)

    def make(self, type: str, **fields: Any) -> dict:  # noqa: A002
        fields.setdefault("unit_id", self.unit_id)
        fields.setdefault("session_id", self.session_id)
        fields.setdefault("sim", self.sim)
        return make(type, **fields)


# ----------------------------------------------------------------------------------------------- thermal

def encode_thermal_raw(raw_u16: np.ndarray, gain: str = "high", shutter: bool = False,
                       raw_per_k: float = RAW_PER_K) -> dict:
    """Encode a raw 16-bit TC001 temperature image [h, w] (raw / raw_per_k = K) without conversion.

    Pixels are little-endian uint16, row-major, zlib level 1, base64.
    """
    raw = np.ascontiguousarray(raw_u16, dtype="<u2")
    if raw.ndim != 2:
        raise ValueError("thermal image must be 2-D [h, w]")
    h, w = raw.shape
    pix = base64.b64encode(zlib.compress(raw.tobytes(), 1)).decode("ascii")
    return {"w": int(w), "h": int(h), "enc": THERMAL_ENC, "raw_per_k": float(raw_per_k), "pix": pix,
            "gain": gain, "shutter": bool(shutter)}


def encode_thermal(temps_k: np.ndarray, gain: str = "high", shutter: bool = False) -> dict:
    """Encode a temperature image in kelvin [h, w] as the ``thermal`` reading ``data``.

    Quantised to 1/64 K (the TC001 raw step), clipped to 0..1023.98 K. Non-finite pixels become raw 0 (0 K),
    which consumers must treat as invalid.
    """
    t = np.asarray(temps_k, dtype=np.float64)
    raw = np.where(np.isfinite(t), np.round(t * RAW_PER_K), 0.0)
    raw = np.clip(raw, 0, 65535).astype("<u2")
    return encode_thermal_raw(raw, gain=gain, shutter=shutter)


def decode_thermal(data: dict) -> np.ndarray:
    """Decode ``thermal`` data to float32 kelvin [h, w]. Raises ``ProtocolError`` if inconsistent."""
    try:
        if data["enc"] != THERMAL_ENC:
            raise ProtocolError("unknown thermal encoding %r" % (data["enc"],))
        h, w = int(data["h"]), int(data["w"])
        buf = zlib.decompress(base64.b64decode(data["pix"], validate=True))
        if len(buf) != 2 * h * w:
            raise ProtocolError("thermal pixel count %d != %d x %d" % (len(buf) // 2, h, w))
        raw = np.frombuffer(buf, dtype="<u2").reshape(h, w)
        return (raw.astype(np.float32) / np.float32(data["raw_per_k"])).astype(np.float32)
    except ProtocolError:
        raise
    except (KeyError, TypeError, ValueError, zlib.error) as exc:
        raise ProtocolError("bad thermal data: %s" % exc) from exc


# ----------------------------------------------------------------------------------------------- radar IQ

def encode_iq(c: np.ndarray) -> dict:
    """Encode a complex radar heatmap [n_bins, n_ant] as ``{"n_ant","enc":"i16-zlib-b64","iq"}``.

    Wire layout: int16 little-endian pairs (real, imag), row-major over [bin, antenna], zlib, base64. Values are
    rounded and clipped to int16 (the IWR6843 demo delivers int16 already, so that path is lossless). Note the
    TLV 4 order on the UART is (imag, real); ``radar_iwr6843`` swaps it before encoding.
    """
    a = np.asarray(c)
    if a.ndim != 2:
        raise ValueError("IQ array must be 2-D [n_bins, n_ant]")
    out = np.empty(a.shape + (2,), dtype="<i2")
    out[..., 0] = np.clip(np.round(np.nan_to_num(a.real)), -32768, 32767)
    out[..., 1] = np.clip(np.round(np.nan_to_num(a.imag)), -32768, 32767)
    return {"n_ant": int(a.shape[1]), "enc": IQ_ENC,
            "iq": base64.b64encode(zlib.compress(out.tobytes(), 1)).decode("ascii")}


def decode_iq(d: dict) -> np.ndarray:
    """Decode ``az_heatmap`` to complex64 [n_bins, n_ant]. Raises ``ProtocolError`` if inconsistent."""
    try:
        if d["enc"] != IQ_ENC:
            raise ProtocolError("unknown IQ encoding %r" % (d["enc"],))
        n_ant = int(d["n_ant"])
        buf = zlib.decompress(base64.b64decode(d["iq"], validate=True))
        if n_ant <= 0 or len(buf) % (4 * n_ant):
            raise ProtocolError("IQ length %d not a multiple of 4 * n_ant" % len(buf))
        a = np.frombuffer(buf, dtype="<i2").reshape(-1, n_ant, 2).astype(np.float32)
        return (a[..., 0] + 1j * a[..., 1]).astype(np.complex64)
    except ProtocolError:
        raise
    except (KeyError, TypeError, ValueError, zlib.error) as exc:
        raise ProtocolError("bad IQ data: %s" % exc) from exc
