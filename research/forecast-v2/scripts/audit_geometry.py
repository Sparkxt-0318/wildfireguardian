"""Audit the actual source rasterizer without changing a single fitting label.

The represented comparison is raw supplied polygons versus an explicitly
declared Shapely make_valid polygon-only sensitivity. Agreement at this grid's
cell centres does not establish the physical correctness of either geometry.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path

from affine import Affine
import numpy as np
import pandas as pd
from pyproj import Transformer
from rasterio.features import rasterize
import shapely
from shapely.geometry import shape
from shapely.ops import transform, unary_union
from shapely.validation import explain_validity, make_valid


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as reader:
        for block in iter(lambda: reader.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def polygon_parts(geometry):
    if geometry.geom_type in ("Polygon", "MultiPolygon"):
        return geometry
    parts = []
    if hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            polygons = polygon_parts(part)
            if not polygons.is_empty:
                parts.append(polygons)
    return unary_union(parts)


def audit(environment, perimeters):
    catalog = {e["id"]: e for e in json.loads((environment / "events.json").read_text())}
    manifest_path = perimeters / "PERIMETER_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    results = []
    for event, pins in sorted(manifest["events"].items()):
        directory = perimeters / event
        geojson, states_file = directory / "perimeters.geojson", directory / "states.npz"
        if sha(geojson) != pins["geojson_sha256"] or sha(states_file) != pins["states_sha256"]:
            raise ValueError(f"Derived reference changed before audit: {event}")
        features = json.loads(geojson.read_text())["features"]
        grid = catalog[event]
        projection = Transformer.from_crs(4326, int(grid["epsg"]), always_xy=True).transform
        groups, invalid = {}, []
        for feature in features:
            original = shape(feature["geometry"])
            projected = transform(projection, original)
            broken = not original.is_valid or not projected.is_valid
            corrected = polygon_parts(make_valid(projected)) if broken else projected
            timestamp = pd.Timestamp(feature["properties"]["time_utc"])
            groups.setdefault(timestamp, []).append((projected, corrected))
            if broken:
                invalid.append(dict(source_record_id=feature["properties"].get("source_record_id", feature.get("id")),
                                    time_utc=timestamp.isoformat(), original_valid=bool(original.is_valid),
                                    projected_valid=bool(projected.is_valid), original_reason=explain_validity(original),
                                    projected_reason=explain_validity(projected), corrected_type=corrected.geom_type,
                                    corrected_empty=bool(corrected.is_empty),
                                    original_wkb_sha256=hashlib.sha256(original.wkb).hexdigest(),
                                    projected_wkb_sha256=hashlib.sha256(projected.wkb).hexdigest(),
                                    sensitivity_wkb_sha256=hashlib.sha256(corrected.wkb).hexdigest()))
        record = dict(event=event, source_records=len(features), invalid_records=len(invalid), invalid=invalid,
                      geojson_sha256=sha(geojson), represented_states_sha256=sha(states_file),
                      actual_policy="project supplied geometry, unary_union within time, rasterize all_touched=False, cumulative raster OR; no explicit repair or record skipping")
        if invalid:
            with np.load(states_file, allow_pickle=False) as data:
                times = list(pd.to_datetime(data["times"], utc=True))
                stored = data["states"].copy()
            raw, repaired = np.zeros(stored.shape[1:], dtype=np.uint8), np.zeros(stored.shape[1:], dtype=np.uint8)
            rows = []
            for index, timestamp in enumerate(times):
                pairs = groups[timestamp]
                geometries = [unary_union([p[j] for p in pairs]) for j in (0, 1)]
                burned = []
                for geometry in geometries:
                    if geometry.is_empty:
                        burned.append(np.zeros_like(raw))
                    else:
                        burned.append(rasterize([(geometry, 1)], out_shape=raw.shape,
                                                transform=Affine(*grid["transform"]), fill=0,
                                                all_touched=False, dtype="uint8"))
                raw, repaired = np.maximum(raw, burned[0]), np.maximum(repaired, burned[1])
                if not np.array_equal(raw, stored[index]):
                    raise ValueError(f"Actual raw rasterization did not reproduce stored labels: {event}, {timestamp}")
                rows.append(dict(time_utc=timestamp.isoformat(), raw_reproduces_stored=True,
                                 raw_vs_repair_changed_cells=int((raw != repaired).sum())))
            record.update(sensitivity_policy="make_valid after projection, retain polygonal components only; no data edits",
                          raw_reproduction_pass=True, per_survey_sensitivity=rows,
                          total_cell_survey_differences=sum(r["raw_vs_repair_changed_cells"] for r in rows),
                          surveys_with_differences=sum(r["raw_vs_repair_changed_cells"] > 0 for r in rows))
        results.append(record)
        print(event, "invalid", len(invalid), "cell-survey differences", record.get("total_cell_survey_differences", 0), flush=True)
    return dict(created_utc=datetime.now(timezone.utc).isoformat(), shapely=shapely.__version__,
                source_manifest_sha256=sha(manifest_path), source_policy_verified_by_reading=True,
                actual_explicit_repairs=0, actual_explicitly_skipped_records=0,
                invalid_source_records=sum(r["invalid_records"] for r in results),
                total_cell_survey_differences=sum(r.get("total_cell_survey_differences", 0) for r in results),
                records=results,
                scope="finite-grid label sensitivity, not geometric truth or field validation; fitting inputs unchanged")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", type=Path, required=True)
    parser.add_argument("--perimeters", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError("Preserve an existing geometry audit")
    with Path("/tmp/wfg/HEAVY.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = audit(args.environment, args.perimeters)
        fcntl.flock(lock, fcntl.LOCK_UN)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
