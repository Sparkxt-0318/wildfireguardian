"""Pure parser for the TI mmWave SDK 3.x out-of-box demo UART frames (IWR6843AOP). No serial I/O here.

Frame layout (little-endian), as documented for the SDK 3.x ``mmw`` demo:

- magic word ``02 01 04 03 06 05 08 07`` (8 bytes)
- header, 8 x uint32: version, totalPacketLen, platform, frameNumber, timeCpuCycles, numDetectedObj, numTLVs,
  subFrameNumber. Header incl. magic = 40 bytes. ``totalPacketLen`` counts the whole packet including magic,
  header and the zero padding the demo adds to reach a multiple of 32 bytes.
- ``numTLVs`` x (uint32 type, uint32 length, payload[length]); ``length`` excludes the 8-byte TLV header.

TLVs used here:

- 1 detected points: numDetectedObj x float32 (x, y, z, doppler) [m, m, m, m/s]
- 2 range profile: numRangeBins x uint16. Per TI's "Understanding UART Data Output Format" page (Radar Toolbox) each
  point is the SUM over the virtual (receive) antennas of log2|x| in Q9, not one antenna's log2 magnitude. Converted
  with ``q9_to_db(value, n_virt) = 20*log10(2) * value / 512 / n_virt`` = the MEAN over the antennas of
  20 log10|x| (uncalibrated demo units), so dB thresholds mean real dB. ``parse_frame`` keeps the raw Q9 counts;
  the antenna count comes from the CLI config (``radar_iwr6843.frame_to_data``). UNVERIFIED on hardware: no EVM
  capture has confirmed the scaling yet (DESIGN.md section 3).
- 4 azimuth static heatmap: numRangeBins x numVirtualAnt x (int16 imag, int16 real)
- 7 side info: numDetectedObj x (int16 snr, int16 noise), both in units of 0.1 dB

Other TLV types are kept as raw bytes and listed in ``tlv_types``. Everything here is tested only on synthetic
byte frames built with ``build_frame``; it has not been run against a real IWR6843AOP.
"""
from __future__ import annotations

import math
import struct
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

MAGIC = bytes([0x02, 0x01, 0x04, 0x03, 0x06, 0x05, 0x08, 0x07])
HEADER_LEN = 40
_HDR = struct.Struct("<8I")
_TLV_HDR = struct.Struct("<2I")
TLV_POINTS = 1
TLV_RANGE_PROFILE = 2
TLV_NOISE_PROFILE = 3
TLV_AZ_STATIC_HEATMAP = 4
TLV_RANGE_DOPPLER = 5
TLV_STATS = 6
TLV_SIDE_INFO = 7
MAX_PACKET_LEN = 256 * 1024          # sanity bound; a 512-bin x 12-antenna heatmap frame is ~26 KB
MAX_TLVS = 32
Q9_DB = 20.0 * math.log10(2.0) / 512.0   # dB per Q9 log2 count
DEFAULT_PLATFORM = 0xA6843
DEFAULT_VERSION = 0x03060004             # SDK 3.6.0.4-style version word (any value is accepted)


class TLVError(ValueError):
    """Malformed frame: wrong magic, impossible length, or TLVs that do not fit the packet."""


def q9_to_db(values, n_virt: int = 1) -> np.ndarray:
    """Range-profile Q9 log2 counts -> dB. TLV 2 sums log2|x| over ``n_virt`` virtual antennas (TI documentation,
    UNVERIFIED on hardware), so the result is divided by ``n_virt``: mean over antennas of 20 log10|x|. The default
    ``n_virt=1`` is the plain per-count conversion (20 log10(2) / 512 dB per count)."""
    n = int(n_virt)
    if n < 1:
        raise ValueError("n_virt must be >= 1")
    return np.asarray(values, dtype=np.float64) * Q9_DB / n


def parse_header(buf: bytes) -> Dict[str, int]:
    """Parse the 40-byte header (including magic). Raises ``TLVError``."""
    if len(buf) < HEADER_LEN:
        raise TLVError("header truncated (%d < %d bytes)" % (len(buf), HEADER_LEN))
    if bytes(buf[:8]) != MAGIC:
        raise TLVError("bad magic word")
    (version, total_len, platform, frame, cycles, num_obj, num_tlvs, subframe) = _HDR.unpack_from(buf, 8)
    if total_len < HEADER_LEN or total_len > MAX_PACKET_LEN:
        raise TLVError("implausible totalPacketLen %d" % total_len)
    if num_tlvs > MAX_TLVS:
        raise TLVError("implausible numTLVs %d" % num_tlvs)
    return {"version": version, "total_len": total_len, "platform": platform, "frame": frame,
            "time_cpu_cycles": cycles, "num_obj": num_obj, "num_tlvs": num_tlvs, "subframe": subframe}


def parse_frame(buf: bytes) -> dict:
    """Parse one complete frame starting at ``buf[0]`` (the magic word).

    Returns the header fields plus ``tlv_types`` (list, in packet order), ``points`` float32 [n, 4] or None,
    ``side_info`` int16 [n, 2] (snr, noise in 0.1 dB) or None, ``range_profile_q9`` uint16 [bins] or None,
    ``az_heatmap`` complex64 flat [bins * n_ant] (real + j imag) or None, ``other`` {type: bytes}.
    Raises ``TLVError`` on bad magic, a packet shorter than ``totalPacketLen``, or a TLV that overruns.
    """
    buf = bytes(buf)
    hdr = parse_header(buf)
    total = hdr["total_len"]
    if len(buf) < total:
        raise TLVError("frame truncated (%d < totalPacketLen %d)" % (len(buf), total))
    out: dict = dict(hdr)
    out.update({"tlv_types": [], "points": None, "side_info": None, "range_profile_q9": None,
                "az_heatmap": None, "other": {}})
    off = HEADER_LEN
    for _ in range(hdr["num_tlvs"]):
        if off + 8 > total:
            raise TLVError("TLV header overruns packet at offset %d" % off)
        ttype, tlen = _TLV_HDR.unpack_from(buf, off)
        off += 8
        if tlen > total - off:
            raise TLVError("TLV type %d length %d overruns packet" % (ttype, tlen))
        payload = buf[off:off + tlen]
        off += tlen
        out["tlv_types"].append(int(ttype))
        if ttype == TLV_POINTS:
            if tlen % 16:
                raise TLVError("points TLV length %d not a multiple of 16" % tlen)
            out["points"] = np.frombuffer(payload, dtype="<f4").reshape(-1, 4).copy()
        elif ttype == TLV_RANGE_PROFILE:
            if tlen % 2:
                raise TLVError("range profile TLV length %d odd" % tlen)
            out["range_profile_q9"] = np.frombuffer(payload, dtype="<u2").copy()
        elif ttype == TLV_AZ_STATIC_HEATMAP:
            if tlen % 4:
                raise TLVError("heatmap TLV length %d not a multiple of 4" % tlen)
            a = np.frombuffer(payload, dtype="<i2").reshape(-1, 2).astype(np.float32)
            out["az_heatmap"] = (a[:, 1] + 1j * a[:, 0]).astype(np.complex64)   # (imag, real) on the wire
        elif ttype == TLV_SIDE_INFO:
            if tlen % 4:
                raise TLVError("side info TLV length %d not a multiple of 4" % tlen)
            out["side_info"] = np.frombuffer(payload, dtype="<i2").reshape(-1, 2).copy()
        else:
            out["other"][int(ttype)] = payload
    if out["points"] is not None and len(out["points"]) != hdr["num_obj"]:
        raise TLVError("points TLV has %d points, header says %d" % (len(out["points"]), hdr["num_obj"]))
    if out["side_info"] is not None and len(out["side_info"]) != hdr["num_obj"]:
        raise TLVError("side info has %d entries, header says %d" % (len(out["side_info"]), hdr["num_obj"]))
    return out


def _plausible_header_at(buf: bytes, pos: int) -> bool:
    """True if a parseable header starts at ``pos`` (used to detect a frame cut short by the next frame)."""
    try:
        parse_header(buf[pos:pos + HEADER_LEN])
        return True
    except TLVError:
        return False


class FrameSync:
    """Find frames in a byte stream fed in arbitrary chunks.

    ``feed(chunk) -> list[frame dict]``. Bytes before a magic word are discarded and counted
    (``garbage_bytes``). A candidate frame is accepted only if it parses; if another plausible header begins
    inside the candidate before it is complete, the candidate was cut short (UART overrun, reset): it is counted
    in ``truncated`` and parsing restarts at the inner header, so bytes of the next frame are never decoded as
    part of the previous one. Frames that fail ``parse_frame`` are counted in ``bad_frames`` and skipped.
    """

    def __init__(self):
        self.buf = bytearray()
        self.frames = 0
        self.garbage_bytes = 0
        self.bad_frames = 0
        self.truncated = 0
        self.last_error: Optional[str] = None

    def stats(self) -> Dict[str, int]:
        return {"frames": self.frames, "garbage_bytes": self.garbage_bytes, "bad_frames": self.bad_frames,
                "truncated": self.truncated}

    def feed(self, chunk: bytes) -> List[dict]:
        self.buf.extend(chunk)
        out: List[dict] = []
        while True:
            i = self.buf.find(MAGIC)
            if i < 0:
                keep = len(MAGIC) - 1                       # a magic word may straddle two reads
                drop = max(0, len(self.buf) - keep)
                self.garbage_bytes += drop
                del self.buf[:drop]
                break
            if i > 0:
                self.garbage_bytes += i
                del self.buf[:i]
            if len(self.buf) < HEADER_LEN:
                break
            try:
                hdr = parse_header(self.buf)
            except TLVError as exc:
                self.bad_frames += 1
                self.garbage_bytes += 1
                self.last_error = str(exc)
                del self.buf[:1]                            # skip this magic, look for the next one
                continue
            total = hdr["total_len"]
            inner = self._inner_header(min(total, len(self.buf)))
            if inner == -1:
                break                                       # possible inner header not complete yet: wait
            if inner is not None:
                self.truncated += 1
                self.last_error = "frame %d cut short at %d of %d bytes" % (hdr["frame"], inner, total)
                del self.buf[:inner]
                continue
            if len(self.buf) < total:
                break
            try:
                frame = parse_frame(bytes(self.buf[:total]))
            except TLVError as exc:
                self.bad_frames += 1
                self.last_error = str(exc)
                del self.buf[:1]
                continue
            del self.buf[:total]
            self.frames += 1
            out.append(frame)
        return out

    def _inner_header(self, end: int) -> Optional[int]:
        """Offset of a plausible header inside the candidate, -1 if one may start but is incomplete, else None."""
        pos = 1
        while True:
            j = self.buf.find(MAGIC, pos, end)
            if j < 0:
                return None
            if len(self.buf) - j < HEADER_LEN:
                return -1
            if _plausible_header_at(self.buf, j):
                return j
            pos = j + 1


def iter_frames(data: bytes, chunk: int = 4096):
    """Yield frames from a recorded raw UART byte string (e.g. ``radar_uart.bin``)."""
    sync = FrameSync()
    for k in range(0, len(data), chunk):
        for f in sync.feed(data[k:k + chunk]):
            yield f


# ----------------------------------------------------------------------------------------------- synthetic frames

def pack_points(xyzv: np.ndarray) -> bytes:
    """TLV 1 payload from float [n, 4] (x, y, z, doppler)."""
    return np.ascontiguousarray(xyzv, dtype="<f4").reshape(-1, 4).tobytes()


def pack_range_profile(q9: Sequence[int]) -> bytes:
    """TLV 2 payload from uint16 Q9 log2 counts."""
    return np.ascontiguousarray(q9, dtype="<u2").tobytes()


def pack_heatmap(c: np.ndarray) -> bytes:
    """TLV 4 payload from complex [bins, n_ant] (written as int16 imag, real)."""
    a = np.asarray(c).reshape(-1)
    out = np.empty((a.size, 2), dtype="<i2")
    out[:, 0] = np.clip(np.round(a.imag), -32768, 32767)
    out[:, 1] = np.clip(np.round(a.real), -32768, 32767)
    return out.tobytes()


def pack_side_info(snr_noise_01db: np.ndarray) -> bytes:
    """TLV 7 payload from int [n, 2] (snr, noise) in 0.1 dB."""
    return np.ascontiguousarray(snr_noise_01db, dtype="<i2").reshape(-1, 2).tobytes()


def build_frame(frame_number: int, tlvs: Sequence[Tuple[int, bytes]], num_obj: int = 0,
                version: int = DEFAULT_VERSION, platform: int = DEFAULT_PLATFORM, time_cpu_cycles: int = 0,
                subframe: int = 0, pad_to: int = 32) -> bytes:
    """Build a synthetic demo frame (for tests and synthetic sessions; not captured from hardware)."""
    body = b"".join(_TLV_HDR.pack(t, len(p)) + p for t, p in tlvs)
    total = HEADER_LEN + len(body)
    if pad_to:
        total = int(math.ceil(total / float(pad_to)) * pad_to)
    hdr = MAGIC + _HDR.pack(version, total, platform, frame_number, time_cpu_cycles, num_obj, len(tlvs),
                            subframe)
    return hdr + body + b"\x00" * (total - HEADER_LEN - len(body))
