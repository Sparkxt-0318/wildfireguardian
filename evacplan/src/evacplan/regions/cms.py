"""CMS Provider Data Catalog: the nursing-home provider file (dataset ``4pq5-n9py``, "Provider
Information", file ``NH_ProviderInfo_<Mon><Year>.csv``; public data).

Fields used: CMS certification number (CCN), provider name, address, city, state, ZIP, county,
number of certified beds, average number of residents per day and, when present, latitude and
longitude (newer files) or a ``Location`` field ending in ``(lat, lon)`` (older files). Column
names have changed across releases, so headers are matched by normalised aliases.
"""
from __future__ import annotations

import csv
import io
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import BuildBlocked, Missing

CMS_HOST = "data.cms.gov"
CMS_DATASET_ID = "4pq5-n9py"
CMS_METASTORE_URL = f"https://{CMS_HOST}/provider-data/api/1/metastore/schemas/dataset/items/{CMS_DATASET_ID}"

ALIASES: dict[str, tuple[str, ...]] = {
    "ccn": ("cms certification number ccn", "cms certification number", "federal provider number", "provnum", "ccn"),
    "name": ("provider name", "provname", "facility name"),
    "address": ("provider address", "address", "street address"),
    "city": ("city town", "provider city", "city"),
    "state": ("state", "provider state"),
    "zip": ("zip code", "provider zip code", "zip"),
    "county": ("county parish", "provider county name", "county name", "county"),
    "beds": ("number of certified beds", "bedcert", "certified beds"),
    "residents": ("average number of residents per day", "restot"),
    "lat": ("latitude", "lat"),
    "lon": ("longitude", "lon", "lng"),
    "location": ("location",),
}
REQUIRED = ("ccn", "name", "address", "city", "state", "zip", "beds")
_LOC = re.compile(r"\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)\s*$")


@dataclass(frozen=True)
class CmsFacility:
    ccn: str
    name: str
    address: str
    city: str
    state: str
    zip: str
    county: str
    certified_beds: int | None
    avg_residents: float | None
    lat: float | None = None
    lon: float | None = None
    coord_source: str | None = None        # "cms" when the file carries coordinates

    def one_line_address(self) -> str:
        return f"{self.address}, {self.city}, {self.state} {self.zip}"


def _norm(h: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", h.lower()).split())


def _columns(header: list[str]) -> dict[str, str]:
    by_norm = {_norm(h): h for h in header}
    out = {}
    for field, names in ALIASES.items():
        for n in names:
            if n in by_norm:
                out[field] = by_norm[n]
                break
    missing = [f for f in REQUIRED if f not in out]
    if missing:
        raise ValueError(f"not a CMS nursing-home provider file: no column for {missing} (header: {header[:12]}...)")
    return out


def _float(s: str | None) -> float | None:
    try:
        v = float(str(s).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return v


def read_provider_file(source) -> list[CmsFacility]:
    """Parse the provider CSV (a path, or the CSV text itself)."""
    text = source if isinstance(source, str) and "\n" in source else Path(source).read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    cols = _columns(list(reader.fieldnames or []))
    out: list[CmsFacility] = []
    for row in reader:
        def get(f: str) -> str:
            return (row.get(cols[f]) or "").strip() if f in cols else ""
        lat, lon, src = _float(get("lat")), _float(get("lon")), None
        if lat is None or lon is None:
            m = _LOC.search(get("location"))
            lat, lon = (float(m.group(1)), float(m.group(2))) if m else (None, None)
        if lat is not None and lon is not None:
            src = "cms"
        beds = _float(get("beds"))
        out.append(CmsFacility(
            ccn=get("ccn"), name=get("name"), address=get("address"), city=get("city"), state=get("state").upper(),
            zip=get("zip")[:5], county=get("county"), certified_beds=None if beds is None else int(round(beds)),
            avg_residents=_float(get("residents")), lat=lat, lon=lon, coord_source=src))
    return out


def select(facilities: list[CmsFacility], *, states=None, bbox_lonlat=None) -> list[CmsFacility]:
    """Facilities in ``states`` and, if given, inside ``bbox_lonlat`` = (west, south, east, north)
    (facilities without coordinates are kept until geocoded)."""
    keep = []
    for f in facilities:
        if states and f.state not in set(states):
            continue
        if bbox_lonlat is not None and f.lat is not None and f.lon is not None:
            w, s, e, n = bbox_lonlat
            if not (w <= f.lon <= e and s <= f.lat <= n):
                continue
        keep.append(f)
    return keep


def download_provider_file(dest, *, timeout: float = 60.0, opener=urllib.request.urlopen) -> Path:
    """Download the current provider file via the catalog's metastore (needs ``data.cms.gov``)."""
    try:
        with opener(CMS_METASTORE_URL, timeout=timeout) as r:
            meta = json.loads(r.read().decode())
        urls = [d.get("downloadURL") for d in meta.get("distribution", []) if str(d.get("downloadURL", "")).endswith(".csv")]
        if not urls:
            raise ValueError("the CMS metastore lists no CSV distribution for the provider file")
        with opener(urls[0], timeout=timeout) as r:
            data = r.read()
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise BuildBlocked([Missing("CMS nursing-home provider file",
                                    f"https://{CMS_HOST} (Provider Data Catalog dataset {CMS_DATASET_ID}) "
                                    f"is unreachable ({exc}); or pass the NH_ProviderInfo CSV with --cms")]) from exc
    p = Path(dest)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p
