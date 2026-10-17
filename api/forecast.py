"""Recorded forecast output as GeoJSON: the c651 export (next-hour new-burn probability and its validity mask) plus
the recorded packet's present-fire array, on the region's 375 m EPSG:5179 grid, polygons in WGS84. No inference."""
from __future__ import annotations

import json
import threading

import numpy as np

from .errors import unprocessable
from .provenance import sha256_file
from .regions import tag_to_iso, to_wgs84

_cache: dict = {}
_lock = threading.Lock()


def forecast_collection(region, sset, identity, only_nonzero=False) -> dict:
    tag = sset.tag
    if tag not in region.exports:
        raise unprocessable("FORECAST_UNAVAILABLE", "no recorded forecast export for %s at %s" % (region.id, tag_to_iso(tag)))
    npz_path, rec_path = region.exports[tag]
    arrays_path = sset.packet_dir / "constructed_arrays.npz"
    hashes = {"forecast_export": sha256_file(npz_path), "forecast_record": sha256_file(rec_path),
              "packet/constructed_arrays.npz": sha256_file(arrays_path), "packet/NATIVE_METADATA.json": sha256_file(sset.packet_dir / "NATIVE_METADATA.json")}
    key = (region.id, tag, tuple(sorted(hashes.items())))
    with _lock:
        base = _cache.get(key)
    if base is None:
        base = _build(region, sset, identity, npz_path, rec_path, arrays_path, hashes)
        with _lock:
            _cache[key] = base
    feats = base["features"]
    if only_nonzero:
        feats = [f for f in feats if f["properties"]["p_new_burn_1h"] > 0 or f["properties"]["burning_now"]]
    out = dict(base)
    out["features"] = feats
    out["provenance"] = identity.base(**base["provenance_fields"])
    out.pop("provenance_fields")
    return out


def _build(region, sset, identity, npz_path, rec_path, arrays_path, hashes) -> dict:
    record = json.loads(rec_path.read_text())
    md = json.loads((sset.packet_dir / "NATIVE_METADATA.json").read_text())
    if record.get("checkpoint_sha256") != identity.checkpoint:
        raise unprocessable("CHECKPOINT_MISMATCH", "recorded export was not produced by the selected checkpoint")
    if record.get("npz_sha256") != hashes["forecast_export"]:
        raise unprocessable("INPUT_CHANGED", "forecast export hash differs from its record")
    if md["identity"]["forecast_export_sha256"] != hashes["forecast_export"]:
        raise unprocessable("INPUT_CHANGED", "packet was built from a different forecast export")
    with np.load(npz_path, allow_pickle=False) as z:
        q = z["new_burn_probability"].copy()
        valid = z["probability_valid"].copy()
        aff = [float(v) for v in z["affine_transform"]]
    with np.load(arrays_path, allow_pickle=False) as z:
        current = z["current_active"].copy()
        known_burned = z["mask__known_burned"].copy() if "mask__known_burned" in z.files else None
    H, W = q.shape
    if current.shape != (H, W):
        raise unprocessable("GRID_MISMATCH", "forecast and packet grids differ")
    a, _, c, _, e, f = aff
    cols = np.arange(W + 1); rows = np.arange(H + 1)
    X, Y = np.meshgrid(c + cols * a, f + rows * e)          # corner lattice, north-up rows
    LON, LAT = to_wgs84(X.ravel(), Y.ravel())
    LON = LON.reshape(H + 1, W + 1); LAT = LAT.reshape(H + 1, W + 1)
    feats = []
    for r in range(H):
        for k in range(W):
            ring = [[float(LON[r, k]), float(LAT[r, k])], [float(LON[r, k + 1]), float(LAT[r, k + 1])],
                    [float(LON[r + 1, k + 1]), float(LAT[r + 1, k + 1])], [float(LON[r + 1, k]), float(LAT[r + 1, k])],
                    [float(LON[r, k]), float(LAT[r, k])]]
            v = bool(valid[r, k])
            p = float(q[r, k]) if v and np.isfinite(q[r, k]) else 0.0
            props = {"row": r, "col": k, "p_new_burn_1h": p, "valid": v, "burning_now": bool(current[r, k])}
            if known_burned is not None:
                props["known_burned"] = bool(known_burned[r, k])
            feats.append({"type": "Feature", "id": "r%dc%d" % (r, k), "geometry": {"type": "Polygon", "coordinates": [ring]},
                          "properties": props})
    lon_all, lat_all = LON.ravel(), LAT.ravel()
    return {"type": "FeatureCollection", "region": region.id, "input_time": tag_to_iso(sset.tag),
            "bbox": [float(lon_all.min()), float(lat_all.min()), float(lon_all.max()), float(lat_all.max())],
            "grid": {"crs": "EPSG:5179", "resolution_m": abs(a), "rows": H, "cols": W, "affine_transform": aff,
                     "row_order": "north-up (row 0 is the northern edge)"},
            "features": feats,
            "provenance_fields": {"region": region.id, "input_time": tag_to_iso(sset.tag), "graph_id": region.graph.revision,
                                  "input_hashes": hashes, "scenario_set_id": sset.scenario_set_id,
                                  "scenario_ids": list(sset.scenario_ids), "fire_input_type": "recorded",
                                  "forecast_event": record.get("event"), "forecast_cutoff": record.get("cutoff_utc")}}
