"""Geocoding facility addresses: the US Census Geocoder batch service (public, no key), or a
geocodes CSV prepared elsewhere (``ccn,lat,lon[,source]``).

Batch API: ``POST https://geocoding.geo.census.gov/geocoder/locations/addressbatch`` (multipart
form: ``benchmark=Public_AR_Current``, ``addressFile`` = CSV lines ``id,street,city,state,zip``).
Each response line is ``"id","input","Match|No_Match|Tie","Exact|Non_Exact","matched","lon,lat",...``.
Only ``Match`` rows are used; ties and misses are reported, never guessed.
"""
from __future__ import annotations

import csv
import io
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import BuildBlocked, Missing
from .cms import CmsFacility

CENSUS_HOST = "geocoding.geo.census.gov"
CENSUS_BATCH_URL = f"https://{CENSUS_HOST}/geocoder/locations/addressbatch"
BENCHMARK = "Public_AR_Current"


@dataclass(frozen=True)
class Geocode:
    lat: float
    lon: float
    source: str                # "census:<match type>", "cms", "file"
    matched_address: str = ""


def batch_csv(facilities: list[CmsFacility]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    for f in facilities:
        w.writerow([f.ccn, f.address, f.city, f.state, f.zip])
    return buf.getvalue()


def multipart(fields: dict[str, str], files: dict[str, tuple[str, str]]) -> tuple[bytes, str]:
    boundary = "----evacplan" + uuid.uuid4().hex
    parts: list[bytes] = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for k, (fname, content) in files.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{fname}"\r\n'
                     f"Content-Type: text/csv\r\n\r\n".encode() + content.encode() + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def parse_batch_response(text: str) -> tuple[dict[str, Geocode], dict[str, str]]:
    """``(geocodes by id, status of every id that did not match)``."""
    got: dict[str, Geocode] = {}
    failed: dict[str, str] = {}
    for row in csv.reader(io.StringIO(text)):
        if not row:
            continue
        rid, status = row[0].strip(), (row[2].strip() if len(row) > 2 else "No_Match")
        if status == "Match" and len(row) > 5 and "," in row[5]:
            lon, lat = (float(v) for v in row[5].split(","))
            kind = row[3].strip() if len(row) > 3 else ""
            got[rid] = Geocode(lat=lat, lon=lon, source=f"census:{kind}", matched_address=row[4].strip())
        else:
            failed[rid] = status
    return got, failed


def _post(url: str, body: bytes, content_type: str, timeout: float) -> str:
    req = urllib.request.Request(url, data=body, headers={"Content-Type": content_type}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def geocode_census(facilities: list[CmsFacility], *, timeout: float = 120.0,
                   post: Callable[[str, bytes, str, float], str] = _post) -> tuple[dict[str, Geocode], dict[str, str]]:
    """Geocode by CCN with the Census batch service (at most 10 000 addresses per call)."""
    if not facilities:
        return {}, {}
    body, ctype = multipart({"benchmark": BENCHMARK}, {"addressFile": ("addresses.csv", batch_csv(facilities))})
    try:
        text = post(CENSUS_BATCH_URL, body, ctype, timeout)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise BuildBlocked([Missing("geocoding of facility addresses",
                                    f"https://{CENSUS_HOST} is unreachable ({exc}); or pass --geocodes "
                                    "(CSV ccn,lat,lon) for: " + ", ".join(f.ccn for f in facilities))]) from exc
    return parse_batch_response(text)


def read_geocodes_csv(path) -> dict[str, Geocode]:
    with Path(path).open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        need = {"ccn", "lat", "lon"}
        if not need <= set(reader.fieldnames or []):
            raise ValueError(f"{path}: a geocodes CSV needs columns {sorted(need)}")
        return {r["ccn"].strip(): Geocode(lat=float(r["lat"]), lon=float(r["lon"]),
                                          source=(r.get("source") or "file").strip() or "file")
                for r in reader if r.get("lat") and r.get("lon")}


def write_geocodes_csv(path, geocodes: dict[str, Geocode]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["ccn", "lat", "lon", "source"])
        for k in sorted(geocodes):
            g = geocodes[k]
            w.writerow([k, f"{g.lat:.7f}", f"{g.lon:.7f}", g.source])
    return p
