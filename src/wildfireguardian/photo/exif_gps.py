"""GPS out of a photograph's EXIF. Four tags, then the bytes are gone.

Round-3 PHASE 22 STEP 2.

WHY THIS EXISTS
---------------
A 119 caller often cannot give an address. 「산 쪽에 연기가 난다」 is a report and
not a coordinate, and the operator's next ten minutes go on establishing where.
A photograph taken on the spot usually carries one already.

⚠ WHAT THIS DELIBERATELY DOES NOT DO
It does not look at the PICTURE. Nothing here infers a location from what is in
the frame — no landmark matching, no terrain matching, no model. That would be a
guess presented as a coordinate, it would need its own accuracy study before
anyone could act on it, and this project's whole stance is that a number you
cannot check is worse than no number. **EXIF only.** If the EXIF has no GPS, the
answer is "this photograph does not carry a location", not an estimate.

THE PRIVACY RULE, WHICH IS THE REASON FOR THE PACKAGE
-----------------------------------------------------
A reported photograph is somebody's personal file. So:

* **The photograph is never stored.** It arrives as bytes in memory, is read,
  and is dropped when this function returns. Nothing writes it to disk, no
  temporary file is created, and no caching layer sees it.
* **Only four EXIF tags are ever extracted** — :data:`GPS_ONLY_TAGS`, which is
  GPSLatitude/Ref and GPSLongitude/Ref inside the GPS IFD. Not the maker, not
  the model, not the timestamp, not the owner, not the serial number, not the
  thumbnail.
* **Nothing is logged.** Not the coordinate, not a filename — and a filename
  cannot leak in the first place, because the transport sends the raw bytes with
  no multipart wrapper and therefore no ``filename`` field. It never leaves the
  browser.

⚠ AN HONEST LIMIT ON "ONLY FOUR TAGS". Any EXIF parser must walk the directory
structure to find the GPS IFD, so the other tags are unavoidably *traversed* in
memory by Pillow. What this module guarantees is narrower and is the part that
matters: nothing but those four tags is ever READ OUT, returned, logged or
persisted. :func:`read_gps` returns a :class:`GpsReading` whose fields are two
floats and a sentence, and there is no other exit from this function.

WHY HEIF IS PARSED BY HAND
--------------------------
HEIC is the iPhone default, so it is not optional. Pillow in this environment
has no HEIF support (``features.check('heif')`` is False, measured), and the
usual fix — ``pillow-heif`` — bundles libheif and an HEVC decoder as a binary
wheel. That is a large dependency, outside the pure-Python rule that let
`fastapi` in, and it exists to decode PIXELS, which is the one thing this module
must never need.

So :func:`_heif_exif` walks the ISO base media container and pulls out the
``Exif`` item. It reads ``meta`` → ``iinf`` (which item is the EXIF one) →
``iloc`` (where it is), and copies that byte range. It never touches ``mdat``
image data and never constructs a decoder. Verified against a container produced
by Apple's own ImageIO, not only against one this repository synthesised.
"""

from __future__ import annotations

import io
import struct
from dataclasses import dataclass

#: The ONLY EXIF tags this module extracts, inside IFD 0x8825 (GPS).
#: 1/3 are the N/S and E/W references; 2/4 are the degree-minute-second values.
#: Written as a frozen set so a test can assert the list has not grown.
GPS_ONLY_TAGS: frozenset[int] = frozenset({1, 2, 3, 4})

#: The GPS IFD's tag in the top-level EXIF directory.
_GPS_IFD: int = 0x8825

#: Refuse anything larger rather than read it. A phone photograph is a few MiB;
#: this is generous for a JPEG or HEIC and small enough that a request cannot be
#: used to exhaust the one worker's memory.
MAX_BYTES: int = 24 * 1024 * 1024

#: The processing statement. ONE copy, carried by the API response and printed
#: on the console, so the screen and the documentation cannot drift apart.
PRIVACY_KO: str = (
    "업로드한 사진은 저장하지 않습니다. 좌표(GPS)만 읽고 즉시 폐기하며, "
    "촬영자·기기 등 EXIF 의 다른 항목은 읽지도 기록하지도 않습니다. "
    "파일명은 서버로 전송되지 않습니다.")

#: Every outcome, with the sentence an operator reads. The wording lives HERE,
#: the way `check_in_region` owns its refusal sentence, so the transport and the
#: screen never compose it.
OUTCOMES: dict[str, str] = {
    "ok": "사진의 EXIF 에서 좌표를 읽었습니다.",
    "no_exif": (
        "사진에 위치 정보가 없습니다. EXIF 자체가 없는 사진입니다. "
        "메신저(카카오톡·문자 등)로 전달된 사진은 전송 과정에서 EXIF 가 "
        "제거되는 경우가 많습니다. 원본 사진을 받아 다시 시도하거나, "
        "지도를 클릭해 발화점을 지정하십시오."),
    "no_gps": (
        "사진에 위치 정보가 없습니다. EXIF 는 있으나 GPS 항목이 없습니다. "
        "촬영 기기의 위치 서비스가 꺼져 있었거나, 전달 과정에서 위치만 "
        "제거된 경우입니다. 지도를 클릭해 발화점을 지정하십시오."),
    "gps_incomplete": (
        "사진의 GPS 항목이 불완전해 좌표를 확정할 수 없습니다. "
        "지도를 클릭해 발화점을 지정하십시오."),
    "gps_zero": (
        "사진의 GPS 좌표가 0, 0 으로 기록되어 있습니다. 측위가 되지 않은 "
        "상태에서 촬영된 사진이므로 위치로 쓸 수 없습니다. "
        "지도를 클릭해 발화점을 지정하십시오."),
    "unsupported_format": (
        "지원하지 않는 파일 형식입니다. JPEG·HEIC·PNG 사진만 읽을 수 "
        "있습니다."),
    "malformed": (
        "사진 파일을 읽지 못했습니다. 파일이 손상되었거나 전송이 중단된 "
        "것으로 보입니다."),
    "too_large": (
        f"사진이 너무 큽니다. {MAX_BYTES // (1024 * 1024)} MiB 이하만 "
        "읽습니다."),
    "empty": "빈 파일입니다.",
}


@dataclass(frozen=True)
class GpsReading:
    """The whole answer. Two floats and a sentence, and no other exit.

    ⚠ There is deliberately no field for anything else the EXIF held. Adding
    one is the change a reviewer should stop.
    """

    outcome: str
    lat: float | None = None
    lon: float | None = None
    #: The CONTAINER format, sniffed from the first bytes. Not an EXIF field and
    #: not a device: "HEIF" says how the file was packed, not what took it.
    container: str = "unknown"

    @property
    def ok(self) -> bool:
        return self.outcome == "ok" and self.lat is not None and self.lon is not None

    @property
    def reason_ko(self) -> str:
        return OUTCOMES.get(self.outcome, OUTCOMES["malformed"])

    def as_dict(self) -> dict:
        """What may cross a wire. Enumerated, never ``asdict`` of something wider.

        ⚠ The key is ``photo_reason_ko``, not ``reason_ko``. A response that
        carries a coordinate also carries the REGION GATE's verdict, and that
        verdict owns ``reason_ko`` — it is the same sentence a map click gets,
        and the screen must be able to show it without knowing how the
        coordinate arrived. Two different questions, two different keys: this
        one answers "did the photograph give a location", the gate's answers
        "may we route from it". Merging them once already silently replaced the
        first with the second.
        """
        return {
            "source": "exif",
            "outcome": self.outcome,
            "ok": self.ok,
            "container": self.container,
            "lat": self.lat,
            "lon": self.lon,
            "photo_reason_ko": self.reason_ko,
            "privacy_ko": PRIVACY_KO,
        }


# ---------------------------------------------------------------------------
# Container sniffing — by MAGIC BYTES, never by a filename
# ---------------------------------------------------------------------------

_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

#: `ftyp` brands that are HEIF-family still images. `mif1` is the generic
#: image-file brand Apple also stamps; `heic`/`heix`/`heim`/`heis` are HEVC
#: stills, `hevc`/`hevx` sequences, `avif`/`avis` the AV1 ones. All of them keep
#: EXIF in the same `Exif` item, which is the only part this module reads.
_HEIF_BRANDS: frozenset[bytes] = frozenset({
    b"heic", b"heix", b"heim", b"heis", b"hevc", b"hevx",
    b"mif1", b"msf1", b"avif", b"avis",
})


def sniff_container(data: bytes) -> str:
    """``'JPEG'``, ``'PNG'``, ``'HEIF'`` or ``'unknown'``, from the bytes alone.

    ⚠ Never from a file extension. The transport does not receive a filename,
    and a name would be a claim about the file rather than an observation of it.
    """
    if data.startswith(_JPEG_MAGIC):
        return "JPEG"
    if data.startswith(_PNG_MAGIC):
        return "PNG"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12]
        compat = data[16:64]
        if brand in _HEIF_BRANDS or any(b in compat for b in _HEIF_BRANDS):
            return "HEIF"
    return "unknown"


# ---------------------------------------------------------------------------
# ISO base media container: find the Exif item, copy it, touch nothing else
# ---------------------------------------------------------------------------


def _boxes(buf: bytes, start: int, end: int):
    """Yield ``(type, payload_start, box_end)`` for one level of boxes.

    Stops at the first malformed length rather than guessing, so a truncated
    file produces "malformed" and not a wrong answer.
    """
    off = start
    while off + 8 <= end:
        size = int.from_bytes(buf[off:off + 4], "big")
        typ = buf[off + 4:off + 8].decode("latin1", "replace")
        hdr = 8
        if size == 1:                                  # 64-bit largesize
            if off + 16 > end:
                return
            size = int.from_bytes(buf[off + 8:off + 16], "big")
            hdr = 16
        elif size == 0:                                # box runs to the end
            size = end - off
        if size < hdr or off + size > end:
            return
        yield typ, off + hdr, off + size
        off += size


def _exif_item_id(d: bytes, s: int, e: int) -> int | None:
    """The item_ID whose item_type is ``Exif``, from an ``iinf`` box."""
    ver = d[s]
    p = s + 4                                          # FullBox header
    if ver == 0:
        p += 2                                         # entry_count u16
    else:
        p += 4                                         # entry_count u32
    for typ, s2, e2 in _boxes(d, p, e):
        if typ != "infe":
            continue
        v2 = d[s2]
        q = s2 + 4
        if v2 < 2:                                     # no item_type before v2
            continue
        if v2 == 2:
            iid = int.from_bytes(d[q:q + 2], "big"); q += 2
        else:
            iid = int.from_bytes(d[q:q + 4], "big"); q += 4
        q += 2                                         # item_protection_index
        if d[q:q + 4] == b"Exif":
            return iid
    return None


def _item_extent(d: bytes, s: int, e: int, want: int) -> tuple[int, int] | None:
    """``(offset, length)`` of item ``want``, from an ``iloc`` box."""
    ver = d[s]
    p = s + 4
    if p + 2 > e:
        return None
    b0, b1 = d[p], d[p + 1]
    p += 2
    osz, lsz = b0 >> 4, b0 & 0x0F
    bsz, isz = b1 >> 4, b1 & 0x0F
    if ver < 2:
        count = int.from_bytes(d[p:p + 2], "big"); p += 2
    else:
        count = int.from_bytes(d[p:p + 4], "big"); p += 4

    def take(n: int, at: int) -> tuple[int, int]:
        return (int.from_bytes(d[at:at + n], "big") if n else 0), at + n

    for _ in range(count):
        if p > e:
            return None
        if ver < 2:
            iid = int.from_bytes(d[p:p + 2], "big"); p += 2
        else:
            iid = int.from_bytes(d[p:p + 4], "big"); p += 4
        if ver in (1, 2):
            p += 2                                     # construction_method
        p += 2                                         # data_reference_index
        base, p = take(bsz, p)
        extent_count = int.from_bytes(d[p:p + 2], "big"); p += 2
        for _ in range(extent_count):
            if ver in (1, 2) and isz:
                _idx, p = take(isz, p)
            eo, p = take(osz, p)
            el, p = take(lsz, p)
            if iid == want:
                return base + eo, el
    return None


class _BrokenContainer(Exception):
    """The file is not a whole HEIF, as opposed to a HEIF without EXIF.

    ⚠ The distinction is the point. A truncated upload that reported
    「위치 정보가 없습니다」 would be a quiet failure wearing an honest sentence:
    the operator would go and click the map when what they should do is send the
    photograph again. A HEIF with no ``meta`` box is not a HEIF.
    """


def _heif_exif(d: bytes) -> bytes | None:
    """The raw EXIF/TIFF block out of an ISO base media container.

    Reads ``meta`` → ``iinf`` → ``iloc`` and copies exactly that byte range. It
    never enters ``mdat`` for image data and constructs no decoder.

    Returns ``None`` when the container is intact but carries no EXIF item.
    Raises :class:`_BrokenContainer` when the container itself does not hold
    together.
    """
    meta = next(((s, e) for t, s, e in _boxes(d, 0, len(d)) if t == "meta"), None)
    if meta is None:
        raise _BrokenContainer("no meta box")
    ms, me = meta[0] + 4, meta[1]                      # `meta` is a FullBox
    item_id = None
    saw_iinf = False
    for typ, s, e in _boxes(d, ms, me):
        if typ == "iinf":
            saw_iinf = True
            item_id = _exif_item_id(d, s, e)
            if item_id is not None:
                break
    if not saw_iinf:
        raise _BrokenContainer("meta box carries no iinf")
    if item_id is None:
        return None                                    # intact, simply no EXIF
    for typ, s, e in _boxes(d, ms, me):
        if typ != "iloc":
            continue
        loc = _item_extent(d, s, e, item_id)
        if loc is None:
            raise _BrokenContainer("iloc has no extent for the Exif item")
        off, length = loc
        if off < 0 or length <= 4 or off + length > len(d):
            raise _BrokenContainer("Exif item extends past the end of the file")
        payload = d[off:off + length]
        # The Exif item payload begins with a 4-byte big-endian count of bytes
        # to skip before the TIFF header (usually 6, for "Exif\0\0").
        skip = int.from_bytes(payload[:4], "big")
        if 4 + skip > len(payload):
            raise _BrokenContainer("Exif item is shorter than its own prefix")
        return payload[4 + skip:]
    raise _BrokenContainer("an Exif item is declared but never located")


# ---------------------------------------------------------------------------
# DMS -> decimal
# ---------------------------------------------------------------------------


def _to_float(v) -> float | None:
    """A rational, an int or a float; anything else is not a number here."""
    try:
        f = float(v)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    if f != f or f in (float("inf"), float("-inf")):   # NaN / inf
        return None
    return f


def _dms_to_degrees(value) -> float | None:
    """``(deg, min, sec)`` to decimal degrees, unsigned."""
    if value is None:
        return None
    try:
        parts = list(value)
    except TypeError:
        return None
    if len(parts) < 2:
        return None
    nums = [_to_float(p) for p in parts[:3]]
    if any(n is None for n in nums):
        return None
    while len(nums) < 3:
        nums.append(0.0)
    deg, minutes, seconds = nums
    if not (0 <= minutes < 60 and 0 <= seconds < 60):
        return None
    return abs(deg) + minutes / 60.0 + seconds / 3600.0


def _signed(mag: float | None, ref, positive: str, negative: str) -> float | None:
    """Apply the N/S or E/W reference. A MISSING reference is not guessed."""
    if mag is None:
        return None
    if not isinstance(ref, str):
        return None
    r = ref.strip().upper()[:1]
    if r == positive:
        return mag
    if r == negative:
        return -mag
    return None


# ---------------------------------------------------------------------------


def _gps_ifd(data: bytes, container: str) -> dict | None:
    """The GPS IFD as a plain dict, or ``None`` when there is no EXIF at all.

    Returns an EMPTY dict when EXIF exists but carries no GPS directory — the
    caller needs that distinction, because "no EXIF" and "EXIF without GPS" have
    different likely causes and therefore different sentences.
    """
    from PIL import Image                              # noqa: PLC0415

    if container == "HEIF":
        blob = _heif_exif(data)
        if blob is None:
            return None
        exif = Image.Exif()
        # Pillow wants the "Exif\0\0" prefix; HEIF payloads may arrive without.
        exif.load(blob if blob[:6] == b"Exif\x00\x00" else b"Exif\x00\x00" + blob)
    else:
        # ⚠ `Image.open` parses the header only. `.load()` is never called, so
        # the pixels are not decoded — this reads metadata and stops.
        with Image.open(io.BytesIO(data)) as im:
            exif = im.getexif()

    if not exif:
        return None
    try:
        gps = exif.get_ifd(_GPS_IFD)
    except Exception:
        return None
    return dict(gps) if gps else {}


def read_gps(data: bytes) -> GpsReading:
    """Read GPS out of a photograph's EXIF. The bytes are not kept.

    ``data`` is the whole file. Nothing else about it is inspected, nothing is
    written anywhere, and nothing is logged.
    """
    if not data:
        return GpsReading("empty")
    if len(data) > MAX_BYTES:
        return GpsReading("too_large")

    container = sniff_container(data)
    if container == "unknown":
        return GpsReading("unsupported_format")

    try:
        gps = _gps_ifd(data, container)
    except Exception:
        # A parser that raises on a broken file must say "broken file", not
        # crash the request and not silently answer "no location".
        return GpsReading("malformed", container=container)

    if gps is None:
        return GpsReading("no_exif", container=container)
    if not gps:
        return GpsReading("no_gps", container=container)

    # ⚠ THE ONLY FOUR VALUES THAT ARE EVER READ OUT.
    picked = {k: gps.get(k) for k in sorted(GPS_ONLY_TAGS)}
    if picked.get(2) is None and picked.get(4) is None:
        return GpsReading("no_gps", container=container)

    lat_mag = _dms_to_degrees(picked.get(2))
    lon_mag = _dms_to_degrees(picked.get(4))
    lat = _signed(lat_mag, picked.get(1), "N", "S")
    lon = _signed(lon_mag, picked.get(3), "E", "W")

    if lat is None or lon is None:
        return GpsReading("gps_incomplete", container=container)
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        return GpsReading("gps_incomplete", container=container)
    # Cameras that never got a fix write 0/0. It is a real coordinate in the
    # Gulf of Guinea and never a Korean wildfire report, so it is refused with
    # its own sentence rather than passed to the region gate to be refused
    # there for the wrong reason.
    if abs(lat) < 1e-9 and abs(lon) < 1e-9:
        return GpsReading("gps_zero", container=container)

    return GpsReading("ok", lat=float(lat), lon=float(lon), container=container)


__all__ = [
    "GPS_ONLY_TAGS", "MAX_BYTES", "OUTCOMES", "PRIVACY_KO", "GpsReading",
    "read_gps", "sniff_container",
]
