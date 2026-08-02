#!/usr/bin/env python
"""Acquire a region's OSM walk/drive graphs and POIs — atomically.

Round-3 PHASE 5 STEP 2-2.

CONTRACT
--------
* **All or nothing.** Everything is fetched into a temporary directory and moved
  into ``data/cache/osm/{region}/`` only once every layer has arrived. A partial
  graph is discarded, never used — a half-downloaded network would silently
  produce "unreachable" origins that are artefacts of the download.
* **3 retries, 30 / 60 / 120 s backoff** — but an EMPTY result is not retried.
  ``InsufficientResponseError`` means the query matched nothing, which no amount
  of waiting will change.
* **Depots may legitimately be empty.** ``amenity=fire_station`` is not required:
  an empty layer is written explicitly and ``responder_side_available`` is set to
  ``false``, so downstream code reads "not applicable" rather than "zero
  dispatches". Shelters ARE required.
* **Never overwrites another region.** Destination is
  ``RescueConfig.osm_cache_path``, which is region-scoped.
* **Refuses to overwrite an existing acquisition** unless ``--force``. Yeongdeok
  is already on disk and must not be re-fetched (``docs/HANDOFF_ROUND3.md`` §5).

The query parameters are exactly Yeongdeok's, so the regions stay comparable:
``network_type='walk'`` / ``'drive'``, projected to EPSG:5179, POIs from
``amenity=shelter|community_centre`` + ``leisure=park`` and
``amenity=fire_station``, centroids taken for non-point geometries.

Run:  python scripts/acquire_region_osm.py --regions uiseong_andong_2025 uljin_samcheok_2022
"""

from __future__ import annotations

import argparse
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

#: POI layers. `required=False` means an EMPTY result is an acceptable outcome
#: for that layer, recorded explicitly rather than silently treated as zero.
POI_LAYERS = {
    "shelters": ({"amenity": ["shelter", "community_centre"], "leisure": ["park"]},
                 True),
    "fire_station": ({"amenity": "fire_station"}, False),
}


class EmptyResult(RuntimeError):
    """The query succeeded and matched nothing. NOT a transient failure."""


def _is_empty_result(exc: Exception) -> bool:
    """osmnx raises InsufficientResponseError when a query matches no features.

    That is an answer, not an outage. Retrying it with exponential backoff burns
    minutes to re-learn the same fact — which is exactly what happened on the
    first Uiseong-Andong attempt (30 + 60 + 120 s for a guaranteed-empty layer).
    """
    return type(exc).__name__ in {"InsufficientResponseError", "EmptyOverpassResponse"}


#: depots.geojson is the fire_station layer under the name the loader expects.
DEPOT_ALIAS = ("fire_station.geojson", "depots.geojson")


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def with_retries(what: str, fn):
    """Call ``fn`` with 3 retries and exponential backoff.

    An EMPTY result short-circuits: it is raised as :class:`EmptyResult`
    immediately, with no backoff, because no amount of waiting will make OSM
    contain a feature it does not contain.
    """
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


def acquire(region: str, bbox, dest: Path) -> dict:
    """Fetch every layer into ``dest`` (a temp dir). Raises if any layer fails."""
    import geopandas as gpd
    import osmnx as ox

    W, S, E, N = bbox
    prov: dict = {"osmnx_version": ox.__version__, "bbox_wgs84_wsen": list(bbox),
                  "layers": {}}

    for kind in ("walk", "drive"):
        def _fetch(kind=kind):
            G = ox.graph_from_bbox(bbox=(W, S, E, N), network_type=kind)
            return ox.project_graph(G, to_crs="EPSG:5179")
        print(f"      fetching {kind} graph ...")
        t0 = time.monotonic()
        G = with_retries(f"{region}/{kind} graph", _fetch)
        out = dest / f"{kind}.graphml"
        ox.save_graphml(G, out)
        prov["layers"][f"{kind}.graphml"] = {
            "query": f"ox.graph_from_bbox(bbox=({W}, {S}, {E}, {N}), "
                     f"network_type='{kind}')",
            "reprojected_to": "EPSG:5179",
            "n_nodes": int(G.number_of_nodes()),
            "n_edges": int(G.number_of_edges()),
            "bytes": out.stat().st_size,
            "seconds": round(time.monotonic() - t0, 1),
        }
        print(f"        {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges, "
              f"{out.stat().st_size/1048576:.1f} MB, {time.monotonic()-t0:.0f}s")

    for name, (tags, required) in POI_LAYERS.items():
        def _fetch(tags=tags):
            gdf = ox.features_from_bbox(bbox=(W, S, E, N), tags=tags)
            gdf = gdf[gdf.geometry.notna()].copy()
            gdf["geometry"] = gdf.geometry.centroid
            return gdf
        print(f"      fetching {name} POIs ...")
        query = f"ox.features_from_bbox(bbox=({W}, {S}, {E}, {N}), tags={tags})"
        try:
            gdf = with_retries(f"{region}/{name} POIs", _fetch)
        except EmptyResult as exc:
            if required:
                raise
            # Write an EMPTY FeatureCollection rather than skipping the file, so
            # downstream code reads "zero features" instead of "file missing" and
            # cannot mistake absence-of-data for absence-of-acquisition.
            out = dest / f"{name}.geojson"
            out.write_text(json.dumps(
                {"type": "FeatureCollection", "features": [],
                 "wfg_note": f"query matched no features in this bbox: {exc}"}),
                encoding="utf-8")
            prov["layers"][f"{name}.geojson"] = {
                "query": query, "n_features": 0, "bytes": out.stat().st_size,
                "empty": True,
                "note": ("OSM contains no matching feature inside THIS bbox. "
                         "That is a property of the bbox and of OSM coverage, "
                         "not a failed download."),
            }
            print(f"        0 features — recorded as an explicit empty layer")
            continue
        out = dest / f"{name}.geojson"
        gdf.to_file(out, driver="GeoJSON")
        prov["layers"][f"{name}.geojson"] = {
            "query": query, "n_features": int(len(gdf)),
            "bytes": out.stat().st_size, "empty": False,
        }
        print(f"        {len(gdf)} features, {out.stat().st_size/1024:.0f} KB")
        _ = gpd

    src, alias = DEPOT_ALIAS
    shutil.copy2(dest / src, dest / alias)
    n_depots = prov["layers"][src]["n_features"]
    prov["layers"][alias] = {"copy_of": src,
                             "note": "the loader expects depots.geojson"}
    prov["depot_count"] = n_depots
    prov["responder_side_available"] = n_depots > 0
    if n_depots == 0:
        prov["responder_side_note"] = (
            "NO depots in this bbox, so the RESPONDER side cannot run for this "
            "region: build_dispatch_list has no origin to dispatch from. The "
            "resident-side metric (the 459-series 3-way split) is unaffected and "
            "IS the cross-region comparison metric. Recorded as 'not applicable', "
            "never as zero-dispatch.")
        print(f"      ⚠ depot_count = 0 -> responder_side_available = False")
    return prov


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regions", nargs="+",
                    default=["uiseong_andong_2025", "uljin_samcheok_2022"])
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing acquisition (NOT for Yeongdeok)")
    ap.add_argument("--out", default=str(REPO / "data/processed/osm_acquisition.json"))
    args = ap.parse_args()

    table = _cfg("bbox.multi_region_walk_bbox", {}) or {}
    records, failed = [], []

    for region in args.regions:
        bbox = table.get(region)
        if bbox is None:
            print(f"STOP: no walk bbox in config for {region}", file=sys.stderr)
            return 2
        cfg = RescueConfig(region_name=region)
        final = REPO / cfg.osm_cache_path
        print(f"\n=== {region} ===")
        print(f"    bbox {tuple(bbox)}   -> {final.relative_to(REPO)}")
        if final.exists() and any(final.iterdir()) and not args.force:
            print(f"    SKIP: already acquired ({len(list(final.iterdir()))} files). "
                  "Use --force to re-acquire.")
            continue

        tmp = Path(tempfile.mkdtemp(prefix=f"wfg-acq-{region}-"))
        started = datetime.now(UTC)
        try:
            prov = acquire(region, tuple(bbox), tmp)
        except Exception as exc:  # noqa: BLE001
            shutil.rmtree(tmp, ignore_errors=True)
            print(f"    FAILED — partial result DISCARDED: {exc}", file=sys.stderr)
            failed.append({"region": region, "error": str(exc)})
            continue
        final.parent.mkdir(parents=True, exist_ok=True)
        if final.exists():
            shutil.rmtree(final)
        shutil.move(str(tmp), str(final))
        prov.update({
            "region": region,
            "acquired_utc": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "completed_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "cache_dir": str(final.relative_to(REPO)),
            "config_hash": config_hash(), "git_commit": _git(),
        })
        records.append(prov)
        print(f"    OK -> {final.relative_to(REPO)}")

    if records:
        out = Path(args.out)
        prev = json.loads(out.read_text()) if out.exists() else {"acquisitions": []}
        by = {r["region"]: r for r in prev.get("acquisitions", [])}
        for r in records:
            by[r["region"]] = r
        out.write_text(json.dumps(
            {"schema_version": 1,
             "note": "Acquisition provenance. Bytes live in data/cache/osm/{region}/ "
                     "and are preserved in data/snapshots/.",
             "acquisitions": [by[k] for k in sorted(by)]},
            indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nwrote {out.relative_to(REPO)}")

    if failed:
        print(f"\nSTOP: {len(failed)} region(s) failed; partial results discarded.",
              file=sys.stderr)
        for f in failed:
            print(f"  {f['region']}: {f['error']}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
