"""Proposed future NIROPS raw-release admission, independent of frozen scoring.

This adapter never runs forecasts or reads reconstructed arrival labels. It
authenticates the *whole* pinned ZIP, visits every record of every shapefile,
and compares all admitted cumulative survey states on the full event grid.
``prepare_perimeters.py`` selects 29 historical fires and cannot establish this
future inventory's completeness.

CLI: python blind_inventory.py --input-root ROOT --manifest INPUT.json \
    --manifest-sha256 PREVIOUSLY_PINNED_SHA --out REPORT.json

Input schema ``wfg.nirops-raw-inventory/1`` requires ``eligibility_policy``
and ``source_contract`` equal to the constants below, plus ``release`` (``path``,
``sha256``, complete ``member_sha256``, ``publisher_url``, ``version``,
``public_release_utc``, and ``first_public_release_attestation`` containing a
pinned ``path``/``sha256``), ``environment_sha256`` (every file recursively
under environment/), and ``states_sha256`` keyed by event ID. The attestation
JSON must bind ``archive_sha256``, ``public_release_utc`` and the literal claim
``first_public_release_containing_2026_surveys``. Hashing an attestation does
not independently verify that claim. No result from this module means READY.

The proposed exact eligibility policy is deliberately explicit: first survey
year 2026, catalog nominal year 2026, at least two distinct surveys and at least
one strictly consecutive interval <=48 hours; a cutoff must have all six
source files aligned to the full 375 m rectangle and a matching source band.
Spatially unknown values never exclude an interval or select score cells. This is an
operational first-survey-year cohort, not evidence of physical ignition year.
Missing-input exclusions describe the pinned local environmental snapshot;
they do not prove that an input is unavailable anywhere else. A full catalog
entry, including incident_number and grid metadata, is mandatory for every
raw incident whose first survey is in 2026. Missing catalog entries fail closed.

This policy and this adapter's source/dependency closure must themselves be
registered before future source access or forecasts. Wiring this adapter into
the frozen scorer and independent public-release verification remain separate
requirements. Geometry policy: reject invalid/empty/non-Polygon records,
malformed rings, deleted DBF records and non-WGS84 sources; never repair.
Custody policy: reject filesystem symlinks, including source path ancestors,
non-GeoTIFF canonical rasters, and raster dependencies outside snapshot pins.
Archive members are restricted to the five parsed SHP bundle components,
UTF-8 plain-text .txt/.md metadata, and matching UTF-8 .shp.xml metadata.
Other sidecars/formats, including every nested archive, fail closed. DBF bytes
must be exactly the header and declared records, with at most one 0x1A EOF.
"""
from __future__ import annotations

import argparse
import codecs
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import struct
import sys
import zipfile

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[3] / "forecast"))

SCHEMA = "wfg.nirops-raw-inventory/1"
POLICY = "wfg.nirops-first-survey-2026-six-source-availability/1"
CLAIM = "first_public_release_containing_2026_surveys"
SOURCE_CONTRACT = "NIROPS_v1_Incident_C_Inc_Number_UTC_naive_publisher_UTC"
CHANNELS = ("weather.temperature_2m", "weather.wind_eastward_10m", "weather.wind_northward_10m",
            "terrain.slope_degrees", "vegetation.tree_cover_percent", "biome.biome_class")
DEADLINE = pd.Timestamp("2027-12-31T23:59:00Z")


class InventoryError(ValueError):
    """Fail-closed error, optionally retaining the completed raw record ledger."""

    def __init__(self, message, report=None):
        super().__init__(message)
        self.report = report


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _no_symlink_components(path):
    """Check lexical ancestors before resolve() can erase a symlink hop."""
    absolute = Path(path).absolute()
    for component in (*reversed(absolute.parents), absolute):
        if component.is_symlink():
            raise InventoryError(f"Filesystem symlinks are not admitted: {component}")


def _inside(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise InventoryError("Input paths must be nonempty relative paths")
    lexical = root / relative
    _no_symlink_components(lexical)
    path = lexical.resolve()
    if not path.is_relative_to(root.resolve()):
        raise InventoryError("Input path escaped the declared input root")
    return path


def _pinned(root, item):
    path = _inside(root, item["path"])
    if not path.is_file() or sha256(path) != item["sha256"]:
        raise InventoryError(f"Pinned bytes missing or changed: {item['path']}")
    return path


def _utc(value, *, publisher_naive=False):
    if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)?", value.strip()):
        raise InventoryError(f"Expected a full finite survey timestamp: {value!r}")
    stamp = pd.Timestamp(value.strip())
    if pd.isna(stamp) or (stamp.tzinfo is None and not publisher_naive):
        raise InventoryError("Timestamp requires an explicit UTC offset")
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    if stamp.utcoffset().total_seconds() != 0:
        raise InventoryError("NIROPS UTC/release timestamps must have zero UTC offset")
    return stamp.tz_convert("UTC")


def _snapshot(root, pins):
    """Require exact file-set and bytes, including optional source quality flags."""
    if not isinstance(pins, dict) or not pins:
        raise InventoryError("Complete environmental snapshot pins are required")
    folder = root / "environment"
    _no_symlink_components(folder)
    files = set()
    for path in folder.rglob("*"):
        # rglob yields directory symlinks without traversing their targets.
        # Reject the node before filtering it with is_file()/is_dir().
        _no_symlink_components(path)
        if path.is_file():
            files.add(str(path.relative_to(root)))
        elif not path.is_dir():
            raise InventoryError(f"Unsupported environmental filesystem node: {path}")
    if files != set(pins) or "environment/events.json" not in pins:
        raise InventoryError("Environmental snapshot file set differs from its complete pins")
    for relative, expected in sorted(pins.items()):
        if sha256(_inside(root, relative)) != expected:
            raise InventoryError(f"Environmental source identity changed: {relative}")


def _polygon(raw):
    """Strict SHP ring/topology admission; no buffer(0), make_valid or dropping."""
    from shapely.geometry import LinearRing, Polygon, shape
    if raw.shapeType != 5:
        raise InventoryError("Only 2D SHP Polygon records are supported")
    points = np.asarray(raw.points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 2 or not np.isfinite(points).all():
        raise InventoryError("Polygon coordinates must be finite 2D positions")
    if np.any(np.abs(points[:, 0]) > 180) or np.any(np.abs(points[:, 1]) > 90):
        raise InventoryError("Polygon coordinates are outside WGS84 longitude/latitude bounds")
    cuts = list(raw.parts) + [len(points)]
    if not cuts or cuts[0] != 0 or any(a >= b for a, b in zip(cuts, cuts[1:])):
        raise InventoryError("Invalid SHP polygon part offsets")
    shells, holes = [], []
    for a, b in zip(cuts, cuts[1:]):
        ring = points[a:b]
        if len(ring) < 4 or not np.array_equal(ring[0], ring[-1]):
            raise InventoryError("SHP rings must be closed with at least four vertices")
        line = LinearRing(ring)
        polygon = Polygon(ring)
        if not line.is_simple or not line.is_valid or not polygon.is_valid or polygon.area <= 0:
            raise InventoryError("Invalid polygon ring geometry")
        (holes if line.is_ccw else shells).append(polygon)
    if not shells or any(sum(shell.contains(hole) for shell in shells) != 1 for hole in holes):
        raise InventoryError("SHP hole must be strictly inside exactly one clockwise exterior")
    geometry = shape(raw.__geo_interface__)
    if (geometry.geom_type not in ("Polygon", "MultiPolygon") or geometry.is_empty
            or not geometry.is_valid or geometry.area <= 0):
        raise InventoryError("Invalid Polygon/MultiPolygon topology")
    return geometry.__geo_interface__


def _archive(root, release):
    """Read authenticated member bytes directly, never a detached extracted SHP."""
    import shapefile
    from pyproj import CRS
    archive = _pinned(root, release)
    inventory, features, failures, member_hashes, source_layers = {}, {}, [], {}, []
    with zipfile.ZipFile(archive) as source:
        entries = source.infolist()
        names = [e.filename for e in entries if not e.is_dir()]
        if len(names) != len(set(names)) or len(names) != len({n.casefold() for n in names}):
            raise InventoryError("Duplicate or case-colliding archive members")
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if (path.is_absolute() or ".." in path.parts or "\\" in entry.filename
                    or ((entry.external_attr >> 16) & 0o170000) == 0o120000):
                raise InventoryError("Unsafe archive member path or symlink")
            if entry.is_dir() and entry.file_size:
                raise InventoryError("Archive directory entries must not contain payload bytes")
            if not entry.is_dir():
                member_hashes[entry.filename] = _digest(source.read(entry))
        if member_hashes != release.get("member_sha256"):
            raise InventoryError("Complete archive member set or member bytes differ from pins")
        lookup = {n.casefold(): n for n in names}
        layers = sorted(n for n in names if n.lower().endswith(".shp"))
        if not layers:
            raise InventoryError("Archive has no SHP source")
        components = (".shp", ".dbf", ".shx", ".prj", ".cpg")
        for name in names:
            lower = name.casefold()
            if PurePosixPath(lower).suffix in components:
                continue
            text_metadata = PurePosixPath(lower).suffix in (".txt", ".md")
            linked_xml = lower.endswith(".shp.xml") and lower[:-4] in lookup
            if not (text_metadata or linked_xml):
                raise InventoryError(f"Archive contains an unhandled member format: {name}")
            try:
                text = source.read(name).decode("utf-8-sig", errors="strict")
            except UnicodeError as error:
                raise InventoryError(f"Allowed metadata must be UTF-8 plain text: {name}") from error
            if any(ord(c) < 32 and c not in "\t\n\r" for c in text):
                raise InventoryError(f"Allowed metadata contains binary/control payload: {name}")
        if any(PurePosixPath(n).suffix.lower() in (".dbf", ".shx", ".prj", ".cpg")
               and (n[:-4] + ".shp").casefold() not in lookup for n in names):
            raise InventoryError("Orphaned source bundle component without its SHP")
        for layer in layers:
            stem = layer[:-4]
            required = [stem + suffix for suffix in (".shp", ".dbf", ".shx", ".prj", ".cpg")]
            if any(n.casefold() not in lookup for n in required):
                raise InventoryError(f"Incomplete SHP/DBF/SHX/PRJ/CPG bundle: {layer}")
            members = {suffix: lookup[(stem + suffix).casefold()]
                       for suffix in (".shp", ".dbf", ".shx", ".prj", ".cpg")}
            blobs = {suffix: source.read(name) for suffix, name in members.items()}
            if not CRS.from_wkt(blobs[".prj"].decode("utf-8-sig")).equals(CRS.from_epsg(4326), ignore_axis_order=True):
                raise InventoryError("survey_states requires an explicitly WGS84 EPSG:4326 source")
            encoding = blobs[".cpg"].decode("ascii").strip()
            encoding = codecs.lookup("utf-8" if encoding == "65001" else encoding).name
            dbf, shx, shp = blobs[".dbf"], blobs[".shx"], blobs[".shp"]
            if len(dbf) < 32 or len(shx) < 100 or len(shp) < 100 or (len(shx) - 100) % 8:
                raise InventoryError("Malformed/truncated source headers")
            count = struct.unpack_from("<I", dbf, 4)[0]
            header, record_size = struct.unpack_from("<HH", dbf, 8)
            if count != (len(shx) - 100) // 8:
                raise InventoryError("SHP/DBF/SHX record counts or byte lengths disagree")
            payload_end = header + count * record_size
            if (payload_end > len(dbf)
                    or len(dbf) not in (payload_end, payload_end + 1)
                    or (len(dbf) == payload_end + 1 and dbf[payload_end:] != b"\x1a")):
                raise InventoryError("DBF payload must contain exactly declared records and at most one EOF byte")
            if struct.unpack_from(">I", shp, 24)[0] * 2 != len(shp):
                raise InventoryError("SHP declared byte length differs from archive bytes")
            source_layers.append(dict(shapefile_member=layer, record_count=count, source_members=members))
            with shapefile.Reader(shp=io.BytesIO(shp), dbf=io.BytesIO(dbf), shx=io.BytesIO(shx),
                                  encoding=encoding, encodingErrors="strict") as reader:
                fields = [field[0] for field in reader.fields[1:]]
                if any(fields.count(k) != 1 for k in ("Incident_C", "Inc Number", "UTC")):
                    raise InventoryError("Missing or duplicated NIROPS v1 membership/time fields")
                next_offset = 100
                for index in range(count):
                    record_id = f"{layer}:{index}"
                    offset, size = (v * 2 for v in struct.unpack_from(">II", shx, 100 + index * 8))
                    dbf_bytes = dbf[header + index * record_size:header + (index + 1) * record_size]
                    provenance = dict(source_record_id=record_id, source_members=members,
                                      dbf_record_sha256=_digest(dbf_bytes),
                                      shp_record_sha256=_digest(shp[offset:offset + size + 8]))
                    try:
                        if (offset != next_offset or offset + size + 8 > len(shp)
                                or struct.unpack_from(">II", shp, offset) != (index + 1, size // 2)):
                            raise InventoryError("Noncontiguous or inconsistent SHP record offsets/lengths")
                        if dbf_bytes[:1] != b" ":
                            raise InventoryError("Deleted/unhandled DBF record flag")
                        record = reader.record(index).as_dict()
                        if any(record[k] is None for k in ("Incident_C", "Inc Number", "UTC")):
                            raise InventoryError("Missing incident membership/time field value")
                        event, number = (str(record[k]).strip() for k in ("Incident_C", "Inc Number"))
                        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", event) or event in (".", "..") or not number:
                            raise InventoryError("Missing/unsafe incident membership fields")
                        stamp = _utc(str(record["UTC"]), publisher_naive=True)
                        entry = inventory.setdefault(event, dict(event=event, incident_number=number, records=[]))
                        if entry["incident_number"] != number:
                            raise InventoryError("Incident_C maps to conflicting incident numbers")
                        provenance.update(incident_number=number, time_utc=stamp.isoformat())
                        entry["records"].append(provenance)
                        geometry = _polygon(reader.shape(index))
                        features.setdefault(event, []).append(dict(type="Feature", id=record_id, geometry=geometry,
                                                                   properties=dict(time_utc=stamp.isoformat())))
                        provenance["geometry_admission"] = "STRICT_VALID_NO_REPAIR"
                    except Exception as error:
                        failure = dict(provenance, geometry_admission="FAILED", error=f"{type(error).__name__}: {error}")
                        failures.append(failure)
                        provenance["geometry_admission"] = "FAILED"
                    next_offset = offset + size + 8
                if next_offset != len(shp):
                    raise InventoryError("SHP contains unindexed trailing record bytes")
    for entry in inventory.values():
        times = sorted({r["time_utc"] for r in entry["records"]})
        entry.update(first_published_survey_utc=times[0], first_survey_year=_utc(times[0]).year,
                     ordered_distinct_times=times, record_count=len(entry["records"]))
    return dict(archive_sha256=release["sha256"], member_sha256=member_hashes,
                source_layers=source_layers, raw_record_count=sum(layer["record_count"] for layer in source_layers),
                incidents=[inventory[k] for k in sorted(inventory)], record_failures=failures), features


def _grid(event):
    from pyproj import CRS
    try:
        values = event["transform"]
        if (len(values) != 6 or not np.isfinite(values).all() or list(values[:2]) != [375, 0]
                or values[3] != 0 or values[4] != -375
                or type(event["height"]) is not int or type(event["width"]) is not int
                or min(event["height"], event["width"]) < 1):
            raise InventoryError("Event grid must be a positive full rectangle with north-up 375m cells")
        crs = CRS.from_epsg(event["epsg"])
        if not crs.is_projected or any(abs(a.unit_conversion_factor - 1) > 1e-12 for a in crs.axis_info):
            raise InventoryError("Event grid CRS must use projected metres")
    except (KeyError, TypeError, ValueError) as error:
        raise InventoryError(f"Missing/invalid declared event grid: {event.get('id')}") from error


def _intervals(times):
    """Exact nanosecond rule: no tolerance that admits an interval above 48h."""
    limit = 48 * 3600 * 10**9
    return [(a, b) for a, b in zip(times, times[1:]) if 0 < b.value - a.value <= limit]


def _availability(root, event, cutoffs, environment_pins):
    """Objectively inspect canonical source paths; never accept supplied exclusions."""
    from wildfire.data import load_data
    import rasterio
    reasons = []
    for channel in CHANNELS:
        category, variable = channel.split(".")
        relative = f"environment/regions/{event['id']}/{category}/{variable}_375m.tif"
        if not _inside(root, relative).is_file():
            reasons.append(dict(code="MISSING_SOURCE_FILE", path=relative))
            continue
        with rasterio.open(_inside(root, relative)) as source:
            if source.driver != "GTiff":
                raise InventoryError(f"Canonical source must be a GeoTIFF, not {source.driver}: {relative}")
            for dependency in source.files:
                path = Path(dependency)
                if not path.is_absolute():
                    path = _inside(root, relative).parent / path
                _no_symlink_components(path)
                path = path.resolve()
                if (not path.is_relative_to((root / "environment").resolve())
                        or str(path.relative_to(root)) not in environment_pins):
                    raise InventoryError(f"Raster dependency is outside the pinned environmental snapshot: {dependency}")
            if (source.crs is None or source.crs.to_epsg() != event["epsg"]
                    or list(source.transform)[:6] != event["transform"]
                    or source.shape != (event["height"], event["width"])):
                reasons.append(dict(code="SOURCE_GRID_UNAVAILABLE", path=relative,
                                    actual_shape=list(source.shape), actual_transform=list(source.transform)[:6],
                                    actual_epsg=None if source.crs is None else source.crs.to_epsg()))
            if source.count < 1:
                reasons.append(dict(code="MISSING_SOURCE_BAND", path=relative))
    if reasons:
        return reasons
    start, end = _utc(event["start_utc"]), _utc(event["end_utc"])
    if start > end or start != start.floor("h") or end != end.floor("h"):
        raise InventoryError("Catalog environmental coverage must be an ordered whole-hour range")
    for cutoff in sorted(set(cutoffs)):
        hour = cutoff.floor("h")
        if not start <= hour <= end:
            reasons.append(dict(code="MISSING_CUTOFF_TIME", cutoff_utc=hour.isoformat()))
            continue
        try:
            with load_data(root / "environment", events=[event["id"]], sequence_length=1, patch_size=None,
                           channels=CHANNELS, categorical_encoding="raw", include_fire_labels=False,
                           time_range=(hour.isoformat(), hour.isoformat())) as dataset:
                if len(dataset) != 1 or tuple(dataset.channel_names) != CHANNELS:
                    raise InventoryError("Source channel schema or cutoff sample differs from the fixed six channels")
                # Read without labels to verify referenced bands and quality-flag
                # grid/time support. Never select incidents/cases using values.
                dataset[0]
        except FileNotFoundError as error:
            path = Path(error.filename).resolve() if error.filename else None
            if path is None or not path.is_relative_to((root / "environment").resolve()) or path.exists():
                raise InventoryError("Unverifiable missing environmental metadata") from error
            reasons.append(dict(code="MISSING_SOURCE_METADATA", path=str(path.relative_to(root))))
        except IndexError as error:
            if "band index" not in str(error):
                raise
            reasons.append(dict(code="MISSING_SOURCE_BAND", cutoff_utc=hour.isoformat(), detail=str(error)))
        except ValueError as error:
            if "Raster does not match event reference grid:" not in str(error):
                raise
            reasons.append(dict(code="SOURCE_GRID_UNAVAILABLE", cutoff_utc=hour.isoformat(), detail=str(error)))
    return reasons


def _states(root, event, features, expected_sha):
    from pyproj import Transformer
    from shapely.geometry import shape
    from shapely.ops import transform
    from wildfire.survival import survey_states
    projection = Transformer.from_crs(4326, event["epsg"], always_xy=True).transform
    for feature in features:
        projected = transform(projection, shape(feature["geometry"]))
        if projected.is_empty or not projected.is_valid or not np.isfinite(projected.bounds).all():
            raise InventoryError(f"Geometry becomes invalid on the declared grid: {feature['id']}")
    times, states = survey_states(features, event)
    relative = f"perimeters/{event['id']}/states.npz"
    path = _pinned(root, dict(path=relative, sha256=expected_sha))
    with np.load(path, allow_pickle=False) as prepared:
        if "times" not in prepared or "states" not in prepared:
            raise InventoryError("Prepared reference must contain times and full states")
        observed_times = [_utc(str(t)) for t in prepared["times"]]
        observed_states = prepared["states"]
        if (observed_times != times or observed_states.shape != states.shape or observed_states.dtype != states.dtype
                or not np.isin(observed_states, (0, 1)).all() or not np.array_equal(observed_states, states)):
            raise InventoryError(f"Prepared states differ from all raw records/full ordered survey states: {event['id']}")
    return dict(path=relative, sha256=expected_sha, survey_count=len(times),
                source_record_ids=sorted(f["id"] for f in features),
                state_array_sha256=_digest(states.tobytes(order="C")),
                geometry_policy="STRICT_VALID_NO_REPAIR", full_rectangle=True, all_touched=False)


def validate_inventory(input_root, manifest_path, expected_manifest_sha256):
    """Validate local custody and return a ledger; public release remains unverified.

    A caller incorporating this into future scoring must additionally enforce
    independent release verification and preregistration of this exact source
    closure. The supplied manifest hash alone establishes neither condition.
    """
    root, manifest_path = Path(input_root).absolute(), Path(manifest_path)
    _no_symlink_components(root)
    root = root.resolve()
    if sha256(manifest_path) != expected_manifest_sha256:
        raise InventoryError("Inventory input manifest differs from its previously pinned hash")
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get("schema") != SCHEMA or manifest.get("eligibility_policy") != POLICY
            or manifest.get("source_contract") != SOURCE_CONTRACT):
        raise InventoryError("Exact future inventory schema and eligibility policy are required")
    release = manifest["release"]
    if not release.get("publisher_url", "").startswith("https://") or not release.get("version"):
        raise InventoryError("Explicit publisher URL and release version are required")
    released = _utc(release["public_release_utc"])
    if released > DEADLINE:
        raise InventoryError("Release is after the fixed 2027 deadline")
    attestation = json.loads(_pinned(root, release["first_public_release_attestation"]).read_text())
    if (attestation.get("archive_sha256") != release["sha256"] or attestation.get("claim") != CLAIM
            or _utc(attestation["public_release_utc"]) != released):
        raise InventoryError("First-public-release attestation is not bound to these exact release bytes/time")
    _snapshot(root, manifest["environment_sha256"])
    raw, features = _archive(root, release)
    report = dict(schema=SCHEMA, eligibility_policy=POLICY, status="INVALID", manifest_sha256=expected_manifest_sha256,
                  release_identity=dict(publisher_url=release["publisher_url"], version=release["version"],
                                        public_release_utc=released.isoformat(), archive_sha256=release["sha256"],
                                        attestation_status="CALLER_ATTESTATION_NOT_EXTERNALLY_VERIFIED",
                                        attestation_sha256=release["first_public_release_attestation"]["sha256"]),
                  raw_inventory=raw, admitted_events=[], exclusions=[], cases=[],
                  execution_status="NOT_READY_FOR_2026_EXECUTION",
                  registration_status="PROPOSED_ADAPTER_REQUIRES_OWNER_ADOPTION_AND_SOURCE_PINNING",
                  source_sha256={"blind_inventory.py": sha256(HERE)},
                  limitations=["First-survey year is an operational predicate, not proven physical ignition year.",
                               "Public-first-release identity/time require independent external verification.",
                               "This proposed adapter/policy and dependency closure require pre-access registration.",
                               "This independent adapter is not wired into the frozen blind scorer.",
                               "Missing-input exclusions establish absence/invalidity only in the pinned local snapshot."])
    if raw["record_failures"]:
        raise InventoryError("Raw record admission failures; no cohort admitted", report)
    if any(_utc(t) > released for entry in raw["incidents"] for t in entry["ordered_distinct_times"]):
        raise InventoryError("Published survey timestamp is after declared public release", report)
    catalog = json.loads((root / "environment/events.json").read_text())
    if not isinstance(catalog, list) or any(not isinstance(e, dict) or "id" not in e for e in catalog):
        raise InventoryError("Complete event catalog must be a list of identified event records", report)
    by_id = {e["id"]: e for e in catalog}
    if len(by_id) != len(catalog):
        raise InventoryError("Duplicate event catalog identities", report)
    raw_ids = {e["event"] for e in raw["incidents"]}
    if any(e.get("country") == "US" and e.get("year") == 2026 and e["id"] not in raw_ids for e in catalog):
        raise InventoryError("2026 US catalog contains an incident absent from the complete raw release", report)
    admitted = set()
    for entry in raw["incidents"]:
        name = entry["event"]
        if entry["first_survey_year"] != 2026:
            report["exclusions"].append(dict(event=name, reason="FIRST_SURVEY_YEAR_NOT_2026"))
            continue
        if name not in by_id:
            raise InventoryError(f"Raw 2026 incident omitted from full event catalog: {name}", report)
        event = by_id[name]
        if event.get("incident_number") != entry["incident_number"] or event.get("country") != "US":
            raise InventoryError(f"Catalog/source incident membership mismatch: {name}", report)
        if type(event.get("year")) is not int:
            raise InventoryError(f"Explicit integer catalog nominal year required: {name}", report)
        if event["year"] != 2026:
            report["exclusions"].append(dict(event=name, reason="CATALOG_NOMINAL_YEAR_NOT_2026"))
            continue
        times = [_utc(t) for t in entry["ordered_distinct_times"]]
        intervals = _intervals(times)
        if not intervals:
            report["exclusions"].append(dict(event=name, reason="NO_CONSECUTIVE_INTERVAL_LE_48H"))
            continue
        _grid(event)
        supported = []
        for a, b in intervals:
            missing = _availability(root, event, [a], manifest["environment_sha256"])
            if missing:
                report["exclusions"].append(dict(event=name, cutoff=a.isoformat(), endpoint=b.isoformat(),
                                                   reason="OBJECTIVELY_VERIFIED_LOCAL_MISSING_INPUTS", evidence=missing))
            else:
                supported.append((a, b))
        if not supported:
            continue
        pins = manifest.get("states_sha256", {})
        if name not in pins:
            raise InventoryError(f"Eligible raw incident omitted from full prepared state pins: {name}", report)
        derived = _states(root, event, features[name], pins[name])
        admitted.add(name)
        report["admitted_events"].append(dict(event=name, **derived))
        report["cases"].extend(dict(event=name, cutoff=a.isoformat(), endpoint=b.isoformat(), year=2026,
                                    reference_kind="nirops_mapped_extent") for a, b in supported)
    if set(manifest.get("states_sha256", {})) != admitted:
        raise InventoryError("Prepared state pins must match exactly admitted incidents, without selected exclusions", report)
    report["status"] = "LOCAL_INVENTORY_VALIDATED_EXTERNAL_RELEASE_UNVERIFIED"
    report["admitted_event_count"] = len(admitted)
    report["case_count"] = len(report["cases"])
    report["environment_sha256"] = manifest["environment_sha256"]
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = validate_inventory(args.input_root, args.manifest, args.manifest_sha256)
        code = 0
    except Exception as error:
        report = getattr(error, "report", None) or dict(schema=SCHEMA, status="INVALID")
        report["execution_status"] = "NOT_READY_FOR_2026_EXECUTION"
        report["error"] = f"{type(error).__name__}: {error}"
        code = 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.out.with_name(args.out.name + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    temporary.replace(args.out)
    print(json.dumps(dict(status=report["status"], report=str(args.out), ready=False)))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
