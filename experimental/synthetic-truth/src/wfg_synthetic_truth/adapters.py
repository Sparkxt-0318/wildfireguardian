"""Source-identified arrival readers with explicit units, grids and uncertainty.

These readers do not infer flaming residence, fuel, thermal exposure or physical
truth from burned extents. Interval observations cannot become exact packets.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path

import numpy as np
from pyproj import CRS


def utc_seconds(value):
    """Require an explicit UTC-aware, whole-second clock, never host local time."""
    if isinstance(value, (int, np.integer)) and not isinstance(value, (bool, np.bool_)):
        return int(value)
    if not isinstance(value, str):
        raise ValueError("Aware ISO time or integer Unix seconds required")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.microsecond:
        raise ValueError("Aware whole-second time required")
    return int(dt.astimezone(timezone.utc).timestamp())


@dataclass(frozen=True)
class GridSpec:
    shape: tuple
    affine: tuple
    epsg: int

    def __post_init__(self):
        if len(self.shape) != 2 or any(isinstance(x, bool) or not isinstance(x, (int, np.integer)) or x <= 0 for x in self.shape):
            raise ValueError("Positive integer grid shape required")
        t = np.asarray(self.affine, dtype=float)
        if t.shape != (6,) or not np.isfinite(t).all() or t[0] <= 0 or t[4] >= 0 or t[1] != 0 or t[3] != 0:
            raise ValueError("North-up nonrotated affine required")
        crs = CRS.from_epsg(int(self.epsg))
        if not crs.is_projected or any(a.unit_conversion_factor != 1 for a in crs.axis_info[:2]):
            raise ValueError("Projected metre EPSG grid required")

    def require_alignment(self, shape, affine, epsg):
        if tuple(shape) != tuple(self.shape) or tuple(affine) != tuple(self.affine) or int(epsg) != self.epsg:
            raise ValueError("Grid alignment mismatch; no implicit resampling")


def _source(path, *, source_id, planning_ids=(), expected_sha256=None, planning_hashes=()):
    if not isinstance(source_id, str) or not source_id:
        raise ValueError("Explicit source identity required")
    if source_id in planning_ids:
        raise ValueError("TRUTH_LEAKAGE: source identity used for planning")
    data = Path(path).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("Source SHA256 mismatch")
    if digest in planning_hashes:
        raise ValueError("TRUTH_LEAKAGE: source bytes used for planning")
    return data, {"source_id": source_id, "path": str(Path(path).resolve()), "sha256": digest}


@dataclass
class ArrivalTruth:
    lower_s: np.ndarray
    upper_s: np.ndarray
    known: np.ndarray
    never: np.ndarray
    grid: GridSpec
    source: dict
    kind: str
    interpretation: str
    point_model: bool = False

    def __post_init__(self):
        if any(np.shape(a) != tuple(self.grid.shape) for a in (self.lower_s, self.upper_s, self.known, self.never)):
            raise ValueError("Truth grid shape mismatch")
        if self.known.dtype != np.bool_ or self.never.dtype != np.bool_ or (self.never & ~self.known).any():
            raise ValueError("Boolean truth support masks required")
        if np.isnan(self.lower_s[self.known]).any() or np.isnan(self.upper_s[self.known]).any() or (self.lower_s[self.known] > self.upper_s[self.known]).any():
            raise ValueError("Invalid supported arrival bounds")

    def exact_ignition(self):
        """Return only an identified complete arrival model; no thermal packet."""
        if not self.point_model or not self.known.all() or not np.array_equal(self.lower_s, self.upper_s):
            return {"status": "UNSCORABLE", "reason": "No complete point arrival model", "ignition_time_s": None}
        return {"status": "MODEL_RELATIVE_ARRIVAL_ONLY", "ignition_time_s": self.lower_s.copy(),
                "reason": "Flaming residence and thermal law still require independent declared inputs"}

    def report(self):
        return {"kind": self.kind, "source": self.source, "shape": list(self.grid.shape),
                "affine": list(self.grid.affine), "epsg": self.grid.epsg,
                "known_cells": int(self.known.sum()), "unknown_cells": int((~self.known).sum()),
                "never_cells": int(self.never.sum()), "point_model": self.point_model,
                "status": self.exact_ignition()["status"], "interpretation": self.interpretation}


def reconstructed_arrival(path, *, grid, origin_utc, cutoff_utc, units, source_id,
                          std_path=None, std_multiplier=2.0, expected_std_sha256=None, **identity):
    """Read GeoTIFF reconstruction; optional +/- multiplier*SD is not a calibrated CI.

    Raster nodata and negative reconstruction values are unknown. Pre-cutoff
    arrivals become negative seconds after the explicit origin shift. No cell
    is inferred never-burned from nodata or the final mapped extent.
    """
    import rasterio
    from rasterio.io import MemoryFile
    if units not in {"seconds", "minutes", "hours"}:
        raise ValueError("Explicit arrival units required")
    scale = {"seconds": 1, "minutes": 60, "hours": 3600}[units]
    blob, source = _source(path, source_id=source_id, **identity)
    def read(data):
        with MemoryFile(data) as mem, mem.open() as ds:
            if ds.count != 1:
                raise ValueError("One arrival raster band required")
            grid.require_alignment((ds.height, ds.width), tuple(ds.transform)[:6], ds.crs.to_epsg())
            a = ds.read(1, masked=True)
            return np.asarray(a.data, float), ~np.ma.getmaskarray(a)
    a, valid = read(blob)
    valid &= np.isfinite(a) & (a >= 0)
    t = a*scale + utc_seconds(origin_utc)-utc_seconds(cutoff_utc)
    sd = np.zeros(grid.shape)
    if std_path is not None:
        if not np.isfinite(std_multiplier) or std_multiplier < 0:
            raise ValueError("Nonnegative finite SD multiplier required")
        # A separate SD source is independently hash-bound, including its bytes.
        b, sd_source = _source(std_path, source_id=source_id+":sd", expected_sha256=expected_std_sha256, planning_ids=identity.get("planning_ids", ()), planning_hashes=identity.get("planning_hashes", ()))
        sd, sv = read(b)
        valid &= sv & np.isfinite(sd) & (sd >= 0)
        sd = sd*scale*std_multiplier
        source["std_source"] = sd_source
    source.update(origin_utc=origin_utc, cutoff_utc=cutoff_utc, units=units, std_multiplier=std_multiplier if std_path else None)
    return ArrivalTruth(np.where(valid, t-sd, np.nan), np.where(valid, t+sd, np.nan), valid,
                        np.zeros(grid.shape, bool), grid, source, "reconstructed_arrival",
                        "Reconstructed model arrival; nodata unknown; SD bounds descriptive, not calibrated ignition confidence", std_path is None)


def observed_perimeters(path, *, grid, cutoff_utc, source_id, expected_event=None, **identity):
    """Rasterize positive WGS84 mapped extents at cell centres, retaining intervals.

    NIROPS publisher times can be estimated and mapping does not observe exact
    ignition, extinction or survey-negative coverage. Thus every mapped cell
    has (-infinity, first-map-clock] arrival bounds, conditional on acquisition
    clock semantics. Every unmapped cell remains unknown. Never creates a point
    truth packet, even when the map covers the full target rectangle.
    """
    from rasterio.features import rasterize
    from rasterio.transform import Affine
    from shapely.geometry import shape, mapping
    from shapely.ops import transform
    from shapely.validation import explain_validity
    from pyproj import Transformer
    blob, source = _source(path, source_id=source_id, **identity)
    collection = json.loads(blob)
    if collection.get("type") != "FeatureCollection" or "crs" in collection:
        raise ValueError("RFC7946 WGS84 FeatureCollection without custom CRS required")
    lower = np.full(grid.shape, np.nan); upper = lower.copy(); known = np.zeros(grid.shape, bool)
    tr = Transformer.from_crs(4326, grid.epsg, always_xy=True)
    records = []; seen = set(); unusable = []
    for feature in collection["features"]:
        props = feature["properties"]
        if expected_event is not None and props.get("Incident_C") != expected_event:
            raise ValueError("Observed source event identity mismatch")
        rid = props["source_record_id"]
        if rid in seen:
            raise ValueError("Duplicate source record identity")
        seen.add(rid)
        t = utc_seconds(props["time_utc"])-utc_seconds(cutoff_utc)
        geometry = shape(feature["geometry"])
        if not geometry.is_valid or geometry.geom_type not in ("Polygon", "MultiPolygon") or geometry.is_empty:
            unusable.append({"source_record_id": rid, "reason": "Invalid/empty/nonpolygon geometry; no automatic repair", "geometry_type": geometry.geom_type, "geometry_validity": explain_validity(geometry)})
            continue
        if not (-180 <= geometry.bounds[0] <= geometry.bounds[2] <= 180 and -90 <= geometry.bounds[1] <= geometry.bounds[3] <= 90):
            raise ValueError("Coordinates outside WGS84 longitude/latitude domain")
        projected = transform(tr.transform, geometry)
        mask = rasterize([(mapping(projected), 1)], out_shape=grid.shape, transform=Affine(*grid.affine), all_touched=False, fill=0).astype(bool)
        upper[mask] = np.minimum(np.where(known[mask], upper[mask], np.inf), t)
        known |= mask
        records.append({"source_record_id": rid, "time_utc": props["time_utc"], "time_quality": props.get("time_quality", "publisher_clock_may_be_estimated"), "cause": "mapped_burned_extent_not_ignition"})
    if unusable:
        # Refuse the collection rather than silently publishing a repaired or
        # selectively filtered observation truth. Original bytes stay bound.
        known[:] = False; upper[:] = np.nan
    lower[known] = -np.inf
    source.update(records=records, unusable_records=unusable, cutoff_utc=cutoff_utc, coverage="No survey-negative footprint supplied", rasterization="cell centre, positive extents only")
    return ArrivalTruth(lower, upper, known, np.zeros(grid.shape, bool), grid, source, "observed_perimeters",
                        "Conditional publisher-clock arrival upper bounds; no exact ignition or physical unburned/never inference")


def external_simulator(path, *, reference_path, cutoff_utc, source_id, expected_reference_sha256=None, expected_event=None, **identity):
    """Read the repository's stored FARSITE NPZ arrival-output format.

    arrival_minutes is relative to metadata's engine origin. Finite negative
    no_burn_value means never only on explicit Boolean valid coverage. Outside
    coverage stays unknown. Reference affine/EPSG must match the output shape;
    no implicit resampling. This is deterministic scenario evidence, not fire
    observations, and this reader does not execute the native simulator.
    """
    blob, source = _source(path, source_id=source_id, **identity)
    rb, ref = _source(reference_path, source_id=source_id+":reference", expected_sha256=expected_reference_sha256,
                      planning_ids=identity.get("planning_ids", ()), planning_hashes=identity.get("planning_hashes", ()))
    with np.load(io.BytesIO(rb), allow_pickle=False) as r:
        grid = GridSpec(tuple(r["burned_area"].shape[-2:]), tuple(r["affine_transform"].reshape(-1)[:6]), int(r["epsg"].item()))
        if expected_event is not None and ("event_id" not in r or str(r["event_id"].item()) != expected_event):
            raise ValueError("Simulator reference event identity mismatch")
        if "time_utc" in r and utc_seconds(r["time_utc"].reshape(-1)[0].item()) != utc_seconds(cutoff_utc):
            raise ValueError("Reference cutoff mismatch")
    with np.load(io.BytesIO(blob), allow_pickle=False) as a:
        raw = np.asarray(a["arrival_minutes"], float)
        cover = a["valid"]
        if cover.dtype != np.bool_ or cover.shape not in (grid.shape, (1, 1, *grid.shape)) or raw.shape != grid.shape:
            raise ValueError("Boolean coverage and aligned arrival shape required")
        cover = cover.reshape(grid.shape)
        meta = json.loads(str(a["metadata_json"].item()))
        if "affine_transform" in a or "epsg" in a:
            grid.require_alignment(raw.shape, a["affine_transform"], a["epsg"].item())
        if "coordinates" in a:
            from pyproj import Transformer
            rr, cc = np.indices(grid.shape)
            x = grid.affine[2]+(cc+.5)*grid.affine[0]
            y = grid.affine[5]+(rr+.5)*grid.affine[4]
            lon, lat = Transformer.from_crs(grid.epsg, 4326, always_xy=True).transform(x, y)
            expected = np.stack([lat, lon], axis=-1)
            if a["coordinates"].shape != expected.shape or not np.allclose(a["coordinates"], expected, rtol=0, atol=1e-8):
                raise ValueError("Simulator coordinate/grid alignment mismatch")
    if meta.get("arrival_units") != "minutes" or meta.get("grid_alignment") != "caller_verified_no_resampling_in_importer":
        raise ValueError("Missing documented units/alignment metadata")
    origin = utc_seconds(meta["arrival_origin_time_utc"]); cutoff = utc_seconds(cutoff_utc)
    sentinel = meta["no_burn_value"]
    if isinstance(sentinel, bool) or not np.isfinite(sentinel) or sentinel >= 0 or cutoff < origin:
        raise ValueError("Invalid simulator sentinel/engine clock")
    never = cover & (raw == sentinel)
    if not np.isfinite(raw[cover]).all() or ((raw < 0) & cover & ~never).any():
        raise ValueError("Invalid on-domain simulator arrival")
    t = np.where(never, np.inf, raw*60+origin-cutoff)
    t = np.where(cover, t, np.nan)
    source.update(reference=ref, metadata=meta, cutoff_utc=cutoff_utc)
    return ArrivalTruth(t.copy(), t, cover, never, grid, source, "external_simulator",
                        "Stored deterministic FARSITE scenario, conditional on declared simulation coverage and alignment", True)
