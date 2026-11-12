"""Label each real origin with its 시·군 by point-in-polygon against an official 시군구 boundary file.

Rule (pre-registered in DESIGN.md, committed before any run). A place is ESTABLISHED only if:
  1. its OSM point lies inside exactly one 시군구 polygon;
  2. the point is at least MARGIN metres from that polygon's boundary (default 50 m);
  3. its road-entry node lies inside the same polygon.
Otherwise it is NOT ESTABLISHED, with exactly one reason, checked in this order:
outside_all, multiple, near_boundary, entry_differs. Points are never snapped.

The polygons stay in the file's own CRS (read from the .prj). WGS84 points are transformed into it. Distances are
in that CRS's metres, so a projected metric CRS is required, and the script stops otherwise.

Sanity checks stop the run unless --fixture is given (synthetic test data):
  - the polygons of 의성군, 안동시, 청송군, 영양군 and 영덕군 exist, each once, under 경상북도;
  - 군위군 is not under 경상북도 (it moved to 대구광역시 in 2023-07).

Source line: given with --source, never hard-coded. It must name only what is established about the file actually
used. When the .dbf has a BASE_DATE field, the file must carry exactly one base date and the source line must contain
it (as YYYY-MM-DD), or the run stops; this catches a source line written for another edition of the file.

Output: labels.json with the sha256 of every source file, the label per origin at the chosen margin, and the counts
by region × status/reason at 0 / 25 / 50 / 100 m. A --fixture run is marked FIXTURE and must never be applied to
places.geojson.

Python 3.12. Requirements: requirements.txt (pyshp, shapely, pyproj).
Usage: python3.12 label_sigungu.py --shp <path/to/file.shp> --source "<source line>" [--archive-sha256 <hex>]
       [--places places_input.json] [--margin 50] [--out labels.json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import shapefile  # pyshp
from pyproj import CRS, Transformer
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry

FIXTURE_SOURCE = "FIXTURE (synthetic test boundaries, not an official file)"
DATE_FIELDS = ("BASE_DATE", "base_date", "BASE_YMD")
MARGINS = (0, 25, 50, 100)
REQUIRED = ("의성군", "안동시", "청송군", "영양군", "영덕군")
NAME_FIELDS = ("SIGUNGU_NM", "SIG_KOR_NM", "sigungu_nm", "SGG_NM", "NAME")
CODE_FIELDS = ("SIGUNGU_CD", "SIG_CD", "sigungu_cd", "SGG_CD", "ADM_CD")
# 시도 prefixes of a 5-digit 시군구 code: statistical (통계청) and administrative (행정안전부) numbering
GB_PREFIXES = ("37", "47")  # 경상북도
REASONS = ("outside_all", "multiple", "near_boundary", "entry_differs")


class SanityError(Exception):
    pass


@dataclass
class County:
    name: str
    code: str
    geom: BaseGeometry


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_counties(shp: Path) -> tuple[list[County], CRS, dict[str, str], list[str]]:
    prj = shp.with_suffix(".prj")
    if not prj.exists():
        raise SanityError(f"no .prj next to {shp}: the CRS cannot be read")
    crs = CRS.from_wkt(prj.read_text(encoding="utf-8", errors="replace"))
    if not crs.is_projected or crs.axis_info[0].unit_name not in ("metre", "meter"):
        raise SanityError(f"the boundary CRS is not a projected metric CRS: {crs.name}")
    cpg = shp.with_suffix(".cpg")
    encodings = [cpg.read_text().strip()] if cpg.exists() else []
    encodings += ["cp949", "utf-8"]
    last: Exception | None = None
    for enc in encodings:
        try:
            r = shapefile.Reader(str(shp), encoding=enc)
            fields = [f[0] for f in r.fields[1:]]
            name_f = next((f for f in NAME_FIELDS if f in fields), None)
            code_f = next((f for f in CODE_FIELDS if f in fields), None)
            if not name_f or not code_f:
                raise SanityError(f"name/code field not found among {fields}")
            date_f = next((f for f in DATE_FIELDS if f in fields), None)
            recs = r.records()
            out = [County(str(rec[name_f]).strip(), str(rec[code_f]).strip(), shape(geo.__geo_interface__)) for geo, rec in zip(r.shapes(), recs)]
            dates = sorted({str(rec[date_f]).strip() for rec in recs}) if date_f else []
            files = {p.name: sha256(p) for p in sorted(shp.parent.glob(shp.stem + ".*"))}
            return out, crs, files, dates
        except UnicodeDecodeError as e:
            last = e
    raise SanityError(f"could not decode the .dbf: {last}")


def sanity(counties: list[County]) -> None:
    for name in REQUIRED:
        hits = [c for c in counties if c.name == name and c.code[:2] in GB_PREFIXES]
        if len(hits) != 1:
            raise SanityError(f"{name}: expected exactly one polygon under 경상북도, found {len(hits)}")
    if any(c.name == "군위군" and c.code[:2] in GB_PREFIXES for c in counties):
        raise SanityError("군위군 is listed under 경상북도; it has been part of 대구광역시 since 2023-07 — wrong vintage?")


def iso_date(d: str) -> str:
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 and d.isdigit() else d


def check_source(source: str, dates: list[str]) -> None:
    if not source.strip():
        raise SanityError("--source is empty: name the boundary file actually used")
    if len(dates) > 1:
        raise SanityError(f"the boundary file mixes base dates {dates}: one edition expected")
    if dates and iso_date(dates[0]) not in source:
        raise SanityError(f"the source line does not name the file's base date {iso_date(dates[0])}: {source!r}")


def label_one(place: dict, counties: list[County], to_crs: Transformer, margin: float, source: str) -> dict:
    x, y = to_crs.transform(place["point"]["lon"], place["point"]["lat"])
    pt = Point(x, y)
    inside = [c for c in counties if c.geom.covers(pt)]
    base = {"source": source}
    if not inside:
        return {**base, "ko": None, "status": "not_established", "reason": "outside_all", "boundary_m": None}
    if len(inside) > 1:
        return {**base, "ko": None, "status": "not_established", "reason": "multiple", "boundary_m": None, "candidates": [c.name for c in inside]}
    c = inside[0]
    d = c.geom.boundary.distance(pt)
    if d < margin:
        return {**base, "ko": None, "status": "not_established", "reason": "near_boundary", "boundary_m": round(d, 1), "candidate": c.name}
    e = place.get("entry")
    if not e or e.get("lon") is None:
        return {**base, "ko": None, "status": "not_established", "reason": "entry_differs", "boundary_m": round(d, 1), "candidate": c.name, "entry": None}
    ex, ey = to_crs.transform(e["lon"], e["lat"])
    if not c.geom.covers(Point(ex, ey)):
        other = [o.name for o in counties if o.geom.covers(Point(ex, ey))]
        return {**base, "ko": None, "status": "not_established", "reason": "entry_differs", "boundary_m": round(d, 1), "candidate": c.name, "entry_in": other}
    return {**base, "ko": c.name, "status": "established", "reason": None, "boundary_m": round(d, 1)}


def run(shp: Path, places_path: Path, margin: float, fixture: bool, source: str | None = None, archive_sha256: str | None = None) -> dict:
    counties, crs, files, dates = read_counties(shp)
    if fixture:
        source = source or FIXTURE_SOURCE
    else:
        sanity(counties)
        check_source(source or "", dates)
    assert source is not None
    to_crs = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    places = json.loads(places_path.read_text(encoding="utf-8"))["places"]
    labels = {p["id"]: label_one(p, counties, to_crs, margin, source) for p in places}
    counts: dict[str, dict[str, dict[str, int]]] = {}
    for m in MARGINS:
        row: dict[str, dict[str, int]] = {}
        for p in places:
            lab = label_one(p, counties, to_crs, m, source)
            key = lab["ko"] if lab["status"] == "established" else lab["reason"]
            row.setdefault(p["region"], {}).setdefault(key, 0)
            row[p["region"]][key] += 1
        counts[f"{m}m"] = row
    return {
        "schema": "wfg.wkit.sigungu_labels/1",
        "fixture": fixture,
        "rule": "DESIGN.md (pre-registered): inside exactly one polygon, ≥ margin from its boundary, entry node in the same polygon",
        "margin_m": margin,
        "crs": crs.to_string(),
        "crs_name": crs.name,
        "crs_epsg": crs.to_epsg(),
        "base_dates": [iso_date(d) for d in dates],
        "source": source,
        "archive_sha256": archive_sha256,
        "source_files_sha256": files,
        "places_input_sha256": sha256(places_path),
        "labels": labels,
        "counts_by_margin": counts,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--shp", type=Path, required=True)
    ap.add_argument("--places", type=Path, default=Path(__file__).with_name("places_input.json"))
    ap.add_argument("--margin", type=float, default=50.0)
    ap.add_argument("--out", type=Path, default=Path(__file__).with_name("labels.json"))
    ap.add_argument("--fixture", action="store_true", help="synthetic test data: skip the sanity checks; output marked FIXTURE")
    ap.add_argument("--source", help="source line naming the boundary file actually used (required unless --fixture)")
    ap.add_argument("--archive-sha256", help="sha256 of the archive the files came from (recorded, not checked)")
    a = ap.parse_args(argv)
    try:
        res = run(a.shp, a.places, a.margin, a.fixture, a.source, a.archive_sha256)
    except SanityError as e:
        print(f"STOP (sanity): {e}", file=sys.stderr)
        return 2
    a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    est = sum(1 for v in res["labels"].values() if v["status"] == "established")
    print(f"{'FIXTURE ' if a.fixture else ''}{est}/{len(res['labels'])} established at {a.margin:g} m -> {a.out}")
    print(json.dumps(res["counts_by_margin"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
