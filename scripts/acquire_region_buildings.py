#!/usr/bin/env python
"""Acquire a region's OSM ``building=*`` footprints — additively, atomically.

Round-3 PHASE 18 STEP 1.

WHY THIS IS A SEPARATE SCRIPT FROM ``acquire_region_osm.py``
-----------------------------------------------------------
``acquire_region_osm.py`` acquires a region as a unit and REFUSES a non-empty
cache directory, because re-running it would replace the walk graph — and
``docs/HANDOFF_ROUND3.md`` §5.4 forbids re-acquiring Yeongdeok's OSM data at all:
the committed 439 and 459 series are measured on that exact graph.

This script adds ONE NEW LAYER to an already-acquired region. It therefore:

* writes exactly one filename, ``buildings.geojson``, and nothing else;
* **digests every pre-existing file in the cache directory before and after,
  and exits 4 if one moved.** The prohibition is not merely respected, it is
  demonstrated on every run;
* refuses to overwrite an existing ``buildings.geojson`` without ``--force``.

CONTRACT (identical to ``acquire_region_osm.py``, deliberately)
--------------------------------------------------------------
* **All or nothing per region.** Fetched into a temporary directory and moved in
  only once complete. A partial layer is discarded, never used.
* **3 retries, 30 / 60 / 120 s backoff** — but an EMPTY result is not retried.
  ``InsufficientResponseError`` means the query matched nothing, which no amount
  of waiting will change. For buildings an empty layer is a REAL and expected
  outcome: OSM building coverage in rural Korea is sparse, and "this bbox has
  none" must be recorded as a measurement, never as a failed download.
* **Never writes acquired data only to ``data/cache/``.** Snapshot immediately
  afterwards (§5.8):

      python scripts/snapshot_external.py --preset osm
      python scripts/snapshot_external.py --verify

WHAT IS STORED
--------------
The footprint POLYGON in EPSG:4326 (what OSM holds), plus three derived columns
computed here once so that no downstream consumer has to re-decide them:

    centroid_x_5179 / centroid_y_5179   projected centroid, EPSG:5179
    footprint_area_m2                   projected footprint area

⚠ The walk graphml caches are NOT consistent about CRS — ``yeongdeok_2025`` is
stored in EPSG:4326 and the two PHASE-5 regions are stored already projected to
EPSG:5179. Anything that consumes both must read the ``crs`` graph attribute.
Writing the projected centroid into this layer means the building side, at
least, has exactly one answer.

Run:  python scripts/acquire_region_buildings.py
      python scripts/acquire_region_buildings.py --regions yeongdeok_2025
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.config import config_hash, get as _cfg  # noqa: E402
from wildfireguardian.routing.rescue import RescueConfig  # noqa: E402

BACKOFF_S = (30, 60, 120)

#: The one filename this script is allowed to create. Anything else is a bug.
LAYER = "buildings.geojson"

#: Tag columns kept when present. OSMnx returns one column per tag key seen
#: anywhere in the response, which for a whole bbox is hundreds of mostly-empty
#: columns; keeping all of them would make the layer unreadable and enormous
#: without adding anything the routing or the vulnerability proxy can use.
KEEP_COLS = (
    "building", "building:levels", "building:use", "building:material",
    "name", "name:ko", "name:en", "amenity", "shop", "office", "tourism",
    "social_facility", "healthcare", "residential", "addr:full", "addr:street",
    "addr:housenumber", "start_date",
)

DEFAULT_REGIONS = ("yeongdeok_2025", "uiseong_andong_2025", "uljin_samcheok_2022")


class EmptyResult(RuntimeError):
    """The query succeeded and matched nothing. NOT a transient failure."""


class ProtectedArtifactMoved(RuntimeError):
    """A pre-existing cache file changed. The run is aborted and reported."""


def _is_empty_result(exc: Exception) -> bool:
    return type(exc).__name__ in {"InsufficientResponseError", "EmptyOverpassResponse"}


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def sha256_file(p: Path, _chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        while block := fh.read(_chunk):
            h.update(block)
    return h.hexdigest()


def digest_dir(d: Path) -> dict[str, str]:
    """Digest every existing file in the region cache EXCEPT the layer we write."""
    if not d.exists():
        return {}
    return {p.name: sha256_file(p) for p in sorted(d.iterdir())
            if p.is_file() and p.name != LAYER}


def with_retries(what: str, fn):
    last = None
    for attempt in range(1, len(BACKOFF_S) + 2):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            if _is_empty_result(exc):
                print(f"      {what}: query matched NO features "
                      "(not a transient error — no retry)")
                raise EmptyResult(str(exc)) from exc
            last = exc
            if attempt > len(BACKOFF_S):
                break
            wait = BACKOFF_S[attempt - 1]
            print(f"      attempt {attempt} failed for {what}: "
                  f"{type(exc).__name__}: {str(exc)[:160]}")
            print(f"      retrying in {wait}s ...")
            time.sleep(wait)
    raise RuntimeError(f"{what}: exhausted {len(BACKOFF_S)} retries") from last


def fetch_buildings(region: str, bbox, dest: Path) -> dict:
    """Fetch ``building=*`` into ``dest/buildings.geojson``. Raises on failure."""
    import geopandas as gpd
    import osmnx as ox

    W, S, E, N = bbox
    tags = {"building": True}
    query = f"ox.features_from_bbox(bbox=({W}, {S}, {E}, {N}), tags={tags})"

    def _fetch():
        return ox.features_from_bbox(bbox=(W, S, E, N), tags=tags)

    print(f"      fetching building footprints ...")
    t0 = time.monotonic()
    out = dest / LAYER
    prov = {"query": query, "osmnx_version": ox.__version__,
            "bbox_wgs84_wsen": list(bbox), "crs_stored": "EPSG:4326"}

    try:
        gdf = with_retries(f"{region}/buildings", _fetch)
    except EmptyResult as exc:
        # An empty building layer is a MEASUREMENT about OSM coverage in this
        # bbox, not a download failure. Record it explicitly so a reader cannot
        # mistake "OSM has none" for "we never asked".
        out.write_text(json.dumps(
            {"type": "FeatureCollection", "features": [],
             "wfg_note": f"query matched no features in this bbox: {exc}"}),
            encoding="utf-8")
        prov.update({"n_features": 0, "empty": True, "bytes": out.stat().st_size,
                     "seconds": round(time.monotonic() - t0, 1),
                     "note": ("OSM contains no building=* feature inside THIS bbox. "
                              "That is a property of OSM coverage, not a failed "
                              "download.")})
        print("        0 features — recorded as an explicit empty layer")
        return prov

    n_raw = len(gdf)
    gdf = gdf[gdf.geometry.notna()].copy()
    n_geom = len(gdf)

    # Polygons and multipolygons only. A `building=*` node (a POI with no
    # footprint) carries no area and cannot be given one; it is counted and
    # reported, never silently promoted to a footprint.
    kinds = gdf.geometry.geom_type.value_counts().to_dict()
    poly = gdf[gdf.geometry.geom_type.isin(("Polygon", "MultiPolygon"))].copy()
    n_poly = len(poly)

    proj = poly.to_crs("EPSG:5179")
    cen = proj.geometry.centroid
    poly["centroid_x_5179"] = cen.x.to_numpy()
    poly["centroid_y_5179"] = cen.y.to_numpy()
    poly["footprint_area_m2"] = proj.geometry.area.to_numpy()

    keep = [c for c in KEEP_COLS if c in poly.columns]
    derived = ["centroid_x_5179", "centroid_y_5179", "footprint_area_m2"]
    slim = poly.reset_index()
    idcols = [c for c in ("element_type", "element", "osmid", "id") if c in slim.columns]
    slim = slim[idcols + keep + derived + ["geometry"]]
    slim = gpd.GeoDataFrame(slim, geometry="geometry", crs=poly.crs)
    slim.to_file(out, driver="GeoJSON")

    prov.update({
        "n_features_raw": int(n_raw),
        "n_features_with_geometry": int(n_geom),
        "n_polygons_kept": int(n_poly),
        "n_non_polygon_dropped": int(n_geom - n_poly),
        "geometry_types_raw": {str(k): int(v) for k, v in kinds.items()},
        "columns_kept": idcols + keep + derived,
        "columns_available": int(len(poly.columns)),
        "derived_columns_note": ("centroid_x_5179 / centroid_y_5179 / "
                                 "footprint_area_m2 computed here in EPSG:5179 so "
                                 "no consumer re-decides the projection"),
        "total_footprint_area_m2": float(poly["footprint_area_m2"].sum()),
        "empty": False,
        "bytes": out.stat().st_size,
        "seconds": round(time.monotonic() - t0, 1),
    })
    print(f"        {n_raw:,} raw -> {n_poly:,} polygons kept "
          f"({n_geom - n_poly} non-polygon dropped), "
          f"{out.stat().st_size/1048576:.1f} MB, {time.monotonic()-t0:.0f}s")
    return prov


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regions", nargs="+", default=list(DEFAULT_REGIONS))
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing buildings.geojson")
    ap.add_argument("--out",
                    default=str(REPO / "data/processed/osm_buildings_acquisition.json"))
    args = ap.parse_args()

    table = _cfg("bbox.multi_region_walk_bbox", {}) or {}
    records, failed = [], []

    for region in args.regions:
        bbox = table.get(region)
        if bbox is None:
            print(f"STOP: no walk bbox in config for {region}", file=sys.stderr)
            return 2
        cache = REPO / RescueConfig(region_name=region).osm_cache_path
        print(f"\n=== {region} ===")
        print(f"    bbox {tuple(bbox)}   -> {cache.relative_to(REPO)}/{LAYER}")

        if not cache.exists():
            print(f"STOP: {cache.relative_to(REPO)} does not exist. This script "
                  "ADDS a layer to an acquired region; it does not acquire one.",
                  file=sys.stderr)
            return 2
        if (cache / LAYER).exists() and not args.force:
            print(f"    SKIP: {LAYER} already present. Use --force to re-fetch.")
            continue

        # --- the guarantee: nothing else in this directory may move -----------
        before = digest_dir(cache)
        print(f"    digested {len(before)} pre-existing layer(s) — none may move")

        tmp = Path(tempfile.mkdtemp(prefix=f"wfg-bld-{region}-"))
        started = datetime.now(UTC)
        try:
            prov = fetch_buildings(region, tuple(bbox), tmp)
        except Exception as exc:  # noqa: BLE001
            shutil.rmtree(tmp, ignore_errors=True)
            print(f"    FAILED — partial result DISCARDED: {exc}", file=sys.stderr)
            failed.append({"region": region, "error": str(exc)})
            continue

        shutil.move(str(tmp / LAYER), str(cache / LAYER))
        shutil.rmtree(tmp, ignore_errors=True)

        after = digest_dir(cache)
        moved = {k for k in before if before[k] != after.get(k)}
        if moved:
            print(f"STOP: pre-existing artifact(s) MOVED: {sorted(moved)}",
                  file=sys.stderr)
            raise ProtectedArtifactMoved(sorted(moved))
        print(f"    verified {len(after)} pre-existing layer(s) unchanged")

        prov.update({
            "region": region,
            "acquired_utc": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "completed_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "cache_file": str((cache / LAYER).relative_to(REPO)),
            "preexisting_layers_digested": len(before),
            "preexisting_layers_unchanged": True,
            "config_hash": config_hash(), "git_commit": _git(),
        })
        records.append(prov)
        print(f"    OK -> {(cache / LAYER).relative_to(REPO)}")

    if records:
        out = Path(args.out)
        prev = json.loads(out.read_text()) if out.exists() else {"acquisitions": []}
        by = {r["region"]: r for r in prev.get("acquisitions", [])}
        for r in records:
            by[r["region"]] = r
        out.write_text(json.dumps(
            {"schema_version": 1,
             "note": ("PHASE 18 building-footprint acquisition provenance. Bytes "
                      "live in data/cache/osm/{region}/buildings.geojson and are "
                      "preserved in data/snapshots/. This script writes only that "
                      "one filename and proves every other cache file is "
                      "byte-identical before and after."),
             "acquisitions": [by[k] for k in sorted(by)]},
            indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nprovenance -> {out.relative_to(REPO)}")

    if failed:
        print(f"\n{len(failed)} region(s) FAILED: "
              f"{[f['region'] for f in failed]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
