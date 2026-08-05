#!/usr/bin/env python
"""Preserve externally-acquired data as immutable, content-addressed snapshots.

Round-3 PHASE 1-B.

WHY THIS EXISTS
---------------
``data/cache/**`` and ``data/raw/**`` are git-ignored. In Round 2 the OSMnx
graph cache was regenerated mid-session; the inputs that produced the committed
numbers no longer existed, and results moved underneath the documents. A cache
is a performance artifact — it is allowed to disappear. A snapshot is evidence —
it is not.

CONTRACT
--------
* A snapshot is **immutable**. Same bytes -> same filename -> re-running is a
  no-op. Different bytes -> a NEW file. Nothing is ever overwritten.
* Every snapshot carries a sibling ``.sha256`` in the standard ``shasum -a 256``
  format, so integrity is checkable with no project code at all.
* ``MANIFEST.json`` records acquisition time, byte size, digest, the origin
  path, the acquisition parameters, the config hash and the git commit.

COMPRESSION
-----------
Large XML-ish payloads (``.graphml``) are stored gzipped. Compression is a
*storage* decision, never an identity one:

* the ``hash8`` in the filename and the ``.sha256`` sidecar are ALWAYS the
  digest of the **uncompressed** bytes — the thing that was actually acquired;
* the gzip stream is written with ``mtime=0`` so the same input always produces
  byte-identical output and re-running stays idempotent;
* ``MANIFEST.json`` additionally carries ``stored_file`` / ``stored_sha256`` /
  ``stored_bytes`` so the on-disk artifact is checkable too.

Check an uncompressed snapshot with no project code::

    cd data/snapshots && shasum -a 256 -c osm-shelters_*.sha256

Check a compressed one::

    gunzip -c osm-walk_*.graphml.gz | shasum -a 256     # == the .sha256 sidecar

FILENAME RULE
-------------
``{source}_{region}_{YYYYMMDD}_{hash8}.{ext}``

``source`` and ``region`` are normalised to use ``-`` internally (``osm-walk``,
``yeongdeok-2025``) so that splitting the stem on ``_`` always yields exactly
four fields. ``hash8`` is the first 8 hex chars of the sha256 of the contents.

``YYYYMMDD`` is the **acquisition** date, taken from the source file's mtime,
not today's date — a snapshot taken now of a file fetched last week must record
last week. The manifest states which clock was used.

Run:
    python scripts/snapshot_external.py --preset osm      # the Round-2 loss
    python scripts/snapshot_external.py --preset osm --include-httpcache
    python scripts/snapshot_external.py --verify
    python scripts/snapshot_external.py path/to/file.tif --source firms --region yeongdeok-2025
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.config import config_hash, get as _cfg  # noqa: E402

SNAP_DIR = REPO / _cfg("paths.snapshots_dir", "data/snapshots")
MANIFEST = SNAP_DIR / "MANIFEST.json"
_FIELD_RE = re.compile(r"[^0-9a-zA-Z-]+")

#: Extensions stored gzipped. XML-ish payloads only; already-compressed formats
#: (.tif, .nc, .zip, .gz) would only get bigger.
COMPRESS_EXTS: frozenset[str] = frozenset({"graphml", "xml", "gml", "osm"})
#: Below this size compression is not worth the loss of `shasum -c` ergonomics.
COMPRESS_MIN_BYTES: int = 1 << 20  # 1 MiB

#: Sources kept out of git (recorded in MANIFEST, but too bulky / derivable).
#: Their digests stay in the manifest so a future fetch can be compared.
UNCOMMITTED_SOURCES: frozenset[str] = frozenset({"osm-httpcache"})

#: FIRMS bundle manifests. Small, and the 2026-07-23 regeneration of
#: fire_manifest.json silently changed the simulation canvas (docs/grid_extent.md),
#: so these ARE committed.
FIRMS_PRESET: list[tuple[str, str, str]] = [
    ("data/raw/firms_data/fire_manifest.json", "firms-manifest",
     "FIRMS bundle index: per-fire bbox, ignition point, detection counts"),
    ("data/raw/firms_data/data_layers_manifest.json", "firms-layers",
     "per-fire raster paths/shapes + burnable_frac + WorldCover class map"),
]

#: The OSM preset — exactly the artifacts that were lost in Round 2.
#: (origin path, source id, layer description)
#: Regions whose OSM layers are snapshotted by --preset osm. Yeongdeok is the
#: Round-2 loss; the others are the PHASE-5 multi-region extension.
OSM_REGIONS: tuple[str, ...] = ("yeongdeok_2025", "uljin_samcheok_2022",
                                "uiseong_andong_2025")

#: The DEM preset. The rest of the FIRMS bundle is digest-only (41 MB), but the
#: per-region DEM is different in kind: `routing/slope.py` samples it directly,
#: and where it has no data the edge is silently timed FLAT. An input whose
#: absence changes a result without raising must be RECOVERABLE, not merely
#: recognisable, so these bytes are stored.
DEM_REGIONS: tuple[str, ...] = ("yeongdeok_2025", "uljin_samcheok_2022",
                                "uiseong_andong_2025")

OSM_PRESET: list[tuple[str, str, str]] = [
    ("data/cache/osm/yeongdeok_2025/walk.graphml", "osm-walk",
     "OSMnx network_type='walk' graph, reprojected to EPSG:5179"),
    ("data/cache/osm/yeongdeok_2025/drive.graphml", "osm-drive",
     "OSMnx network_type='drive' graph, reprojected to EPSG:5179"),
    ("data/cache/osm/yeongdeok_2025/shelters.geojson", "osm-shelters",
     "OSM refuge/assembly POIs used as evacuation destinations"),
    ("data/cache/osm/yeongdeok_2025/depots.geojson", "osm-depots",
     "OSM depot POIs used as responder origins (119안전센터 proxy)"),
    ("data/cache/osm/yeongdeok_2025/fire_station.geojson", "osm-firestation",
     "OSM amenity=fire_station POIs (source layer behind depots)"),
    # PHASE 18. Additive: acquired by scripts/acquire_region_buildings.py, which
    # writes this filename and no other and proves every pre-existing layer is
    # byte-identical before and after.
    ("data/cache/osm/yeongdeok_2025/buildings.geojson", "osm-buildings",
     "OSM building=* footprint polygons (EPSG:4326) + projected centroid/area"),
]


def sha256_file(p: Path, _chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        while block := fh.read(_chunk):
            h.update(block)
    return h.hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _norm(field: str) -> str:
    """Normalise a filename field: underscores -> hyphens, safe chars only."""
    return _FIELD_RE.sub("-", field.replace("_", "-")).strip("-")


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:  # noqa: BLE001
        return None


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"schema_version": 1, "snapshots": []}


def save_manifest(man: dict) -> None:
    man["updated_utc"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    man["snapshots"].sort(key=lambda e: (e["source"], e["snapshot_file"]))
    MANIFEST.write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def digest_only(paths, source: str, region: str, man: dict) -> int:
    """Record digests WITHOUT copying the bytes.

    The FIRMS bundle is ~41 MB of rasters and detections — too bulky to commit,
    but its identity still has to be pinned so a future bundle can be compared
    file-by-file against the one that produced the committed results.
    """
    n = 0
    for p in sorted(paths):
        if not p.is_file():
            continue
        digest = sha256_file(p)
        acquired = datetime.fromtimestamp(p.stat().st_mtime, UTC)
        name = (f"{_norm(source)}_{_norm(region)}_{acquired.strftime('%Y%m%d')}"
                f"_{digest[:8]}.{p.suffix.lstrip('.') or 'bin'}")
        entry = {
            "snapshot_file": name,
            "sha256": digest,
            "bytes": p.stat().st_size,
            "stored_file": None,
            "stored_bytes": 0,
            "stored_sha256": None,
            "compression": "none",
            "committed_to_git": False,
            "digest_only": True,
            "source": _norm(source),
            "region": _norm(region),
            "layer": "FIRMS bundle member (digest recorded, bytes not stored)",
            "origin_path": str(p.relative_to(REPO)) if p.is_relative_to(REPO) else str(p),
            "acquired_utc": acquired.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "acquired_clock": "source file mtime (not snapshot time)",
            "snapshotted_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "parameters": {},
            "config_hash": config_hash(),
            "git_commit": _git_commit(),
        }
        man["snapshots"] = [e for e in man["snapshots"] if e["snapshot_file"] != name]
        man["snapshots"].append(entry)
        n += 1
    return n


def _gzip_bytes(raw: bytes) -> bytes:
    """Deterministic gzip: mtime=0 and no filename field, so bytes are stable."""
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=9, mtime=0) as fh:
        fh.write(raw)
    return buf.getvalue()


def _should_compress(ext: str, size: int, mode: str) -> bool:
    if mode == "never":
        return False
    if mode == "always":
        return True
    return ext in COMPRESS_EXTS and size >= COMPRESS_MIN_BYTES


def snapshot_one(
    origin: Path, source: str, region: str, *, layer: str = "",
    parameters: dict | None = None, man: dict | None = None, compress: str = "auto",
) -> tuple[Path, bool]:
    """Store ``origin`` in the snapshot store. Returns (stored_path, newly_created).

    Identity — the ``hash8`` in the name and the ``.sha256`` sidecar — is always
    taken from the UNCOMPRESSED bytes, whether or not the file is stored gzipped.
    """
    if not origin.exists():
        raise FileNotFoundError(origin)
    raw_size = origin.stat().st_size
    digest = sha256_file(origin)                    # identity = uncompressed content
    acquired = datetime.fromtimestamp(origin.stat().st_mtime, UTC)
    ext = origin.suffix.lstrip(".") or "bin"
    name = f"{_norm(source)}_{_norm(region)}_{acquired.strftime('%Y%m%d')}_{digest[:8]}.{ext}"

    gz = _should_compress(ext, raw_size, compress)
    stored_name = f"{name}.gz" if gz else name
    dest = SNAP_DIR / stored_name

    if dest.exists():
        # Immutability guard: same name must mean same *original* bytes.
        on_disk = (sha256_bytes(gzip.decompress(dest.read_bytes())) if gz
                   else sha256_file(dest))
        if on_disk != digest:
            raise RuntimeError(
                f"HASH COLLISION on {stored_name}: refusing to overwrite an existing "
                "snapshot. This should be impossible; investigate before proceeding.")
        created = False
    else:
        SNAP_DIR.mkdir(parents=True, exist_ok=True)
        if gz:
            dest.write_bytes(_gzip_bytes(origin.read_bytes()))
        else:
            shutil.copy2(origin, dest)
        created = True

    # Sidecar always names the UNCOMPRESSED artifact and its digest.
    (SNAP_DIR / f"{name}.sha256").write_text(f"{digest}  {name}\n", encoding="utf-8")

    if man is not None:
        entry = {
            "snapshot_file": name,               # logical (uncompressed) identity
            "sha256": digest,                    # digest of the acquired bytes
            "bytes": raw_size,
            "stored_file": stored_name,          # what is actually on disk
            "stored_bytes": dest.stat().st_size,
            "stored_sha256": sha256_file(dest),
            "compression": "gzip(mtime=0,level=9)" if gz else "none",
            "committed_to_git": _norm(source) not in UNCOMMITTED_SOURCES,
            "source": _norm(source),
            "region": _norm(region),
            "layer": layer,
            "origin_path": str(origin.relative_to(REPO)) if origin.is_relative_to(REPO)
                           else str(origin),
            "acquired_utc": acquired.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "acquired_clock": "source file mtime (not snapshot time)",
            "snapshotted_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "parameters": parameters or {},
            "config_hash": config_hash(),
            "git_commit": _git_commit(),
        }
        man["snapshots"] = [e for e in man["snapshots"] if e["snapshot_file"] != name]
        man["snapshots"].append(entry)
    return dest, created


def verify(man: dict) -> int:
    """Re-hash every manifest entry against the UNCOMPRESSED digest.

    Entries flagged ``committed_to_git: false`` are local-only by design; if they
    are absent this is reported as ``absent`` (not a failure), because a fresh
    clone legitimately will not have them.
    """
    bad = absent = drifted = 0
    entries = man["snapshots"]
    digest_entries = [e for e in entries if e.get("digest_only")]
    stored_entries = [e for e in entries if not e.get("digest_only")]
    print(f"verifying {len(entries)} snapshot(s) in {SNAP_DIR.relative_to(REPO)} "
          f"({len(stored_entries)} stored, {len(digest_entries)} digest-only) ...")

    # Digest-only entries hold no bytes of their own. Re-hash the ORIGIN instead:
    # that is what tells us whether the bundle on disk is still the one that
    # produced the committed results.
    for e in digest_entries:
        origin = REPO / e["origin_path"]
        if not origin.exists():
            print(f"  absent    {e['snapshot_file']}  (digest-only, origin not present)")
            absent += 1
            continue
        got = sha256_file(origin)
        if got != e["sha256"]:
            print(f"  DRIFTED   {e['origin_path']}\n"
                  f"            recorded {e['sha256'][:32]}...\n"
                  f"            on disk  {got[:32]}...")
            drifted += 1
        else:
            print(f"  ok        {e['snapshot_file']}  (digest-only, origin matches)")

    for e in stored_entries:
        stored = SNAP_DIR / e.get("stored_file", e["snapshot_file"])
        gz = e.get("compression", "none").startswith("gzip")
        if not stored.exists():
            if not e.get("committed_to_git", True):
                print(f"  absent    {e['snapshot_file']}  (local-only, not in git — expected)")
                absent += 1
            else:
                print(f"  MISSING   {e['snapshot_file']}")
                bad += 1
            continue
        raw = gzip.decompress(stored.read_bytes()) if gz else stored.read_bytes()
        got = sha256_bytes(raw)
        if got != e["sha256"]:
            print(f"  CORRUPT   {e['snapshot_file']}\n"
                  f"            expected {e['sha256']}\n            got      {got}")
            bad += 1
        else:
            tag = f", stored {e['stored_bytes']:,} B gz" if gz else ""
            print(f"  ok        {e['snapshot_file']}  ({e['bytes']:,} B{tag})")
    parts = []
    if absent:
        parts.append(f"{absent} local-only/digest-only absent")
    if drifted:
        parts.append(f"{drifted} DIGEST-ONLY ORIGIN DRIFTED (external data changed "
                     "under us — see docs/DATA_LOSS_2026-07-24.md)")
    print("VERIFY:", "all present snapshots intact" if bad == 0 else f"{bad} FAILURE(S)",
          f"({'; '.join(parts)})" if parts else "")
    # Origin drift is a real finding, not a corruption: the snapshot store itself
    # is intact. Report it loudly but do not fail the store's integrity check.
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="explicit files to snapshot")
    ap.add_argument("--source", help="source id for explicit files (e.g. firms, srtm)")
    ap.add_argument("--region", default=_cfg("project.region_name", "yeongdeok_2025"))
    ap.add_argument("--preset", choices=["osm", "firms", "dem", "all"],
                    help="snapshot a known bundle")
    ap.add_argument("--include-httpcache", action="store_true",
                    help="also snapshot the raw Overpass HTTP responses (~27 MB)")
    ap.add_argument("--verify", action="store_true", help="re-hash existing snapshots and exit")
    ap.add_argument("--compress", choices=["auto", "never", "always"], default="auto",
                    help="auto = gzip .graphml/.xml over 1 MiB (identity stays uncompressed)")
    args = ap.parse_args()

    man = load_manifest()
    if args.verify:
        return 1 if verify(man) else 0

    targets: list[tuple[Path, str, str, dict]] = []
    n_digest = 0
    if args.preset in ("firms", "all"):
        # Manifests are committed: the 2026-07-23 regeneration of fire_manifest.json
        # silently changed the simulation canvas (docs/grid_extent.md).
        for rel, src, layer in FIRMS_PRESET:
            p = REPO / rel
            if p.exists():
                targets.append((p, src, layer, {"bundle_dir": "data/raw/firms_data"}))
            else:
                print(f"  skip (absent): {rel}")
        # The bulk bundle is ~41 MB: digests only, no bytes stored.
        # The DEMs of the multi-region set are STORED in full by --preset dem, so
        # recording them a second time as digest-only would say "bytes not kept"
        # about bytes that are kept.
        stored_elsewhere = ({f"{r}_dem.tif" for r in DEM_REGIONS}
                            if args.preset in ("dem", "all") else set())
        bulk = [q for q in sorted((REPO / "data/raw/firms_data").glob("*"))
                if q.is_file() and q.name not in
                ({"fire_manifest.json", "data_layers_manifest.json"} | stored_elsewhere)]
        n_digest = digest_only(bulk, "firms-bundle", args.region, man)
        if n_digest:
            nb = sum(q.stat().st_size for q in bulk)
            print(f"  digest-only: {n_digest} FIRMS bundle file(s), {nb:,} B "
                  f"({nb / 1024 / 1024:.1f} MB) NOT stored — digests in MANIFEST only")

    if args.preset in ("dem", "all"):
        for region in DEM_REGIONS:
            p = REPO / "data/raw/firms_data" / f"{region}_dem.tif"
            if not p.exists():
                print(f"  skip (absent): {p.relative_to(REPO)}")
                continue
            params = {"region": region, "product": "SRTMGL1 (1 arc-second, ~30 m)",
                      "provider": "OpenTopography Global DEM API",
                      "walk_bbox_wsen":
                          (_cfg("bbox.multi_region_walk_bbox", {}) or {}).get(region)}
            targets.append((p, "srtm-dem",
                            "SRTM elevation raster sampled by routing/slope.py and "
                            "reprojected onto the spread_v2 simulation grid",
                            params))

    if args.preset in ("osm", "all"):
        bbox = _cfg("bbox.road_network.wgs84_wsen", None)
        params = {"osmnx_query": f"ox.graph_from_bbox(bbox={bbox}, network_type=...)",
                  "bbox_wgs84_wsen": bbox,
                  "reprojected_to": _cfg("project.crs", "EPSG:5179")}
        for region in OSM_REGIONS:
            for rel, src, layer in OSM_PRESET:
                p = REPO / rel.replace("yeongdeok_2025", region)
                if p.exists():
                    targets.append((p, src, layer,
                                    {**params, "region": region}))
                elif region == "yeongdeok_2025":
                    print(f"  skip (absent): {p.relative_to(REPO)}")
        if args.include_httpcache:
            for p in sorted((REPO / "data/cache/osm/_httpcache").glob("*.json")):
                targets.append((p, "osm-httpcache",
                                "raw Overpass API response as cached by OSMnx", params))

    for f in args.files:
        if not args.source:
            print("--source is required with explicit files", file=sys.stderr)
            return 2
        targets.append((Path(f).resolve(), args.source, "", {}))

    if not targets and not n_digest:
        ap.print_help()
        return 2

    n_new = n_dup = 0
    total = 0
    print(f"snapshot store: {SNAP_DIR.relative_to(REPO)}")
    for p, src, layer, params in targets:
        region = params.get("region", args.region)
        dest, created = snapshot_one(p, src, region, layer=layer,
                                     parameters=params, man=man, compress=args.compress)
        total += dest.stat().st_size
        n_new += created
        n_dup += (not created)
        print(f"  {'NEW ' if created else 'dup '} {dest.name}  ({dest.stat().st_size:,} B)"
              f"  <- {p.relative_to(REPO) if p.is_relative_to(REPO) else p}")
    save_manifest(man)
    print(f"\n{n_new} new, {n_dup} already present; {total:,} bytes covered.")
    print(f"manifest: {MANIFEST.relative_to(REPO)} ({len(man['snapshots'])} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
