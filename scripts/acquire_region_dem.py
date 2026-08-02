#!/usr/bin/env python
"""Acquire a region's SRTM DEM so that it actually covers its walk bbox.

Round-3 PHASE 5, follow-up to STEP 2-3.

WHY
---
The per-fire DEMs were downloaded on each fire's ``fire_manifest.json`` bbox.
For Uljin-Samcheok that box starts at 36.85 N, while the ignition-centred walk
bbox introduced in PHASE 5 starts at **36.81 N**. The routing therefore sampled
elevation outside the raster for 405 of 7,300 walk nodes, read nodata, and
`routing/slope.py` timed those sub-segments at FLAT speed — silently.

This script re-fetches the DEM on a box that provably contains the walk bbox,
with a margin, from the same provider and the same product as the original
acquisition.

CONTRACT
--------
* **Same source, same product.** OpenTopography Global DEM API,
  ``demtype=SRTMGL1`` (1 arc-second, ~30 m), ``outputFormat=GTiff``, EPSG:4326 —
  the parameters recorded in ``docs/REPRODUCE.md`` §4c and
  ``docs/data_provenance/claude_firms_bundle_5fires_2026-07-20.md``. **No
  mosaicking across providers.** Stitching an AWS-Mapzen ``.hgt`` strip onto an
  OpenTopography raster would put a second variable inside one input, which is
  precisely what this repo refuses to do silently.
* **All or nothing.** The download lands in a temp file. It replaces the
  installed DEM only after the raster has been opened and proved to cover the
  walk bbox with the required margin. A partial or short raster is discarded.
* **Never silently widens the product.** If the response is not SRTMGL1 at 1
  arc-second, the run stops.
* **Refuses to overwrite without ``--force``.** The existing DEM is an input to
  committed artifacts.
* **Snapshot immediately.** `data/raw/**` is git-ignored; an unsnapshotted
  raster is one `rm` away from the July-23 failure.

CREDENTIALS
-----------
OpenTopography requires an API key. This script reads it from the environment
(``OPENTOPOGRAPHY_API_KEY``, or a ``.env`` file at the repo root) and **never
accepts it on the command line**, so it cannot end up in shell history, in a
process list, or in this repo. If it is absent the script stops and says so; it
does not fall back to another provider.

    export OPENTOPOGRAPHY_API_KEY=...        # or put it in .env (git-ignored)
    python scripts/acquire_region_dem.py --regions uljin_samcheok_2022

Register at https://portal.opentopography.org/ (free for academic use).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.config import config_hash, get as _cfg  # noqa: E402

API = "https://portal.opentopography.org/API/globaldem"
DEMTYPE = "SRTMGL1"
#: SRTMGL1 is 1 arc-second. Anything coarser is a different product.
ARCSEC = 1.0 / 3600.0
BACKOFF_S = (30, 60, 120)
KEY_ENV = "OPENTOPOGRAPHY_API_KEY"

#: Degrees of slack added to every side of the walk bbox. One SRTM pixel is
#: ~0.00028°, so 0.02° (~2.2 km) is ~72 pixels — enough that an edge whose
#: geometry strays just outside the bbox still samples real terrain.
DEFAULT_MARGIN_DEG = 0.02

RAW = REPO / "data" / "raw" / "firms_data"


class AcquisitionError(RuntimeError):
    """The DEM could not be acquired in a state fit to route on."""


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def read_api_key() -> str:
    """From the environment, or from a git-ignored .env. Never from argv."""
    key = os.environ.get(KEY_ENV, "").strip()
    if key:
        return key
    dotenv = REPO / ".env"
    if dotenv.exists():
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(f"{KEY_ENV}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise AcquisitionError(
        f"{KEY_ENV} is not set.\n"
        "  OpenTopography's Global DEM API requires an API key; a keyless "
        "request returns HTTP 401.\n"
        f"  Set it in the environment (export {KEY_ENV}=...) or put a line\n"
        f"      {KEY_ENV}=...\n"
        "  in the git-ignored .env at the repo root, then re-run.\n"
        "  Register free at https://portal.opentopography.org/.\n"
        "  This script will NOT substitute a different DEM provider: mixing "
        "sources inside one raster would put a second variable into every "
        "before/after comparison that uses it.")


def required_boxes(region: str) -> dict[str, tuple[float, float, float, float]]:
    """Every extent this DEM is sampled on. The fetch must cover all of them.

    Three consumers, not one:

    * the **walk bbox** — `routing/slope.py` samples edge elevation profiles;
      outside the raster it reads nodata and times the edge FLAT;
    * the **simulation canvas** — `spread_v2.grid.elevation_on_grid` reprojects
      the DEM onto the coarse grid, and `features` then replaces every missing
      cell with the grid MEAN. Both canvases were extended southward in
      `a0eaf07` and both now overrun their DEM: 10.0 % of Uiseong-Andong's cells
      and 15.6 % of Uljin-Samcheok's carry a mean-filled elevation. (Measured
      2026-08-02; the hazard is p = 0 in every one of those cells in every
      slice, so the committed fields are not contaminated — but the fill was
      silent, which is the problem.)
    * the **existing raster** — never shrink an input. Anything already covered
      stays covered, so no other consumer loses ground.
    """
    boxes: dict[str, tuple[float, float, float, float]] = {}

    table = _cfg("bbox.multi_region_walk_bbox", {}) or {}
    if region not in table:
        raise AcquisitionError(f"no walk bbox in config for {region!r}")
    boxes["walk_bbox"] = tuple(float(v) for v in table[region])

    fs = REPO / "data/processed/forward_sim_regions.json"
    if fs.exists():
        for r in json.loads(fs.read_text(encoding="utf-8")).get("regions", []):
            if r.get("fire_id") == region and r.get("simulation_bbox_wgs84"):
                boxes["simulation_canvas"] = tuple(
                    float(v) for v in r["simulation_bbox_wgs84"])

    existing = RAW / f"{region}_dem.tif"
    if existing.exists():
        import rasterio
        with rasterio.open(existing) as src:
            b = src.bounds
        boxes["existing_dem"] = (float(b.left), float(b.bottom),
                                 float(b.right), float(b.top))
    return boxes


def target_bbox(region: str, margin_deg: float) -> tuple[float, float, float, float]:
    """Union of every required extent, grown by ``margin_deg`` on every side."""
    boxes = required_boxes(region)
    W = min(b[0] for b in boxes.values()) - margin_deg
    S = min(b[1] for b in boxes.values()) - margin_deg
    E = max(b[2] for b in boxes.values()) + margin_deg
    N = max(b[3] for b in boxes.values()) + margin_deg
    return (W, S, E, N)


def fetch(bbox, key: str, dest: Path) -> dict:
    """GET the GeoTIFF with 3 retries. Returns request provenance (never the key)."""
    W, S, E, N = bbox
    params = {"demtype": DEMTYPE, "south": S, "north": N, "west": W, "east": E,
              "outputFormat": "GTiff"}
    redacted = f"{API}?{urllib.parse.urlencode(params)}&API_Key=<redacted>"
    url = f"{API}?{urllib.parse.urlencode({**params, 'API_Key': key})}"

    last = None
    for attempt in range(1, len(BACKOFF_S) + 2):
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(url, timeout=300) as resp:  # noqa: S310
                if resp.status != 200:
                    raise AcquisitionError(f"HTTP {resp.status}")
                ctype = resp.headers.get("Content-Type", "")
                body = resp.read()
            if b"<error>" in body[:512] or ctype.startswith("text") \
                    or ctype.endswith("xml"):
                # A 200 carrying an XML error body is still a failure.
                raise AcquisitionError(
                    f"provider returned {ctype!r}: {body[:300].decode(errors='replace')}")
            dest.write_bytes(body)
            return {"url_redacted": redacted, "demtype": DEMTYPE,
                    "bbox_wgs84_wsen": [W, S, E, N],
                    "content_type": ctype, "bytes": len(body),
                    "seconds": round(time.monotonic() - t0, 1),
                    "attempts": attempt}
        except Exception as exc:  # noqa: BLE001
            last = exc
            msg = str(exc)
            if "401" in msg or "403" in msg:
                raise AcquisitionError(
                    f"provider rejected the credential ({msg}). Not retried — no "
                    f"amount of waiting fixes an invalid {KEY_ENV}.") from exc
            if attempt > len(BACKOFF_S):
                break
            wait = BACKOFF_S[attempt - 1]
            print(f"      attempt {attempt} failed: {type(exc).__name__}: {msg[:160]}")
            print(f"      retrying in {wait}s ...")
            time.sleep(wait)
    raise AcquisitionError(f"exhausted {len(BACKOFF_S)} retries: {last}")


def validate(path: Path, boxes: dict, margin_deg: float) -> dict:
    """Open the raster and prove it covers EVERY required extent, or discard it."""
    import numpy as np
    import rasterio

    with rasterio.open(path) as src:
        b = src.bounds
        res_x, res_y = (abs(v) for v in src.res)
        crs = str(src.crs)
        shape = [int(src.height), int(src.width)]
        band = src.read(1, masked=True)
        nodata_frac = float(band.mask.mean()) if band.mask.shape else 0.0

    if crs.upper() not in ("EPSG:4326",):
        raise AcquisitionError(f"expected EPSG:4326, got {crs}")
    for name, res in (("x", res_x), ("y", res_y)):
        if abs(res - ARCSEC) > ARCSEC * 0.02:
            raise AcquisitionError(
                f"{name}-resolution {res:.8f}° is not 1 arc-second "
                f"({ARCSEC:.8f}°) — this is not {DEMTYPE}")

    coverage: dict[str, dict] = {}
    short_of: list[str] = []
    for name, (W, S, E, N) in boxes.items():
        slack = {"west": W - b.left, "south": S - b.bottom,
                 "east": b.right - E, "north": b.top - N}
        ok = all(v >= 0.0 for v in slack.values())
        coverage[name] = {"box_wsen": [W, S, E, N], "covered": ok,
                          "slack_deg": {k: round(v, 6) for k, v in slack.items()}}
        if not ok:
            short_of.append(name)
    if short_of:
        detail = {n: {k: v for k, v in coverage[n]["slack_deg"].items() if v < 0}
                  for n in short_of}
        raise AcquisitionError(
            f"raster does NOT cover {short_of}; short by {detail} (degrees). "
            "Discarded — a partial DEM is exactly the condition this acquisition "
            "exists to remove.")
    if nodata_frac > 0.5:
        raise AcquisitionError(
            f"{nodata_frac:.1%} of the raster is nodata — that is not a usable "
            "elevation field for this region")

    return {
        "crs": crs, "shape": shape,
        "bounds_wsen": [float(b.left), float(b.bottom), float(b.right), float(b.top)],
        "resolution_deg": [res_x, res_y],
        "is_one_arcsecond": True,
        "covers_every_required_extent": True,
        "coverage": coverage,
        "margin_deg_requested": margin_deg,
        "raster_nodata_fraction": nodata_frac,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def acquire(region: str, *, margin_deg: float, force: bool, key: str) -> dict:
    boxes = required_boxes(region)
    dest = RAW / f"{region}_dem.tif"
    print(f"\n=== {region} ===")
    for name, bb in boxes.items():
        print(f"    must cover     {name:18s} {tuple(round(v, 4) for v in bb)}")

    previous = None
    if dest.exists():
        import rasterio
        with rasterio.open(dest) as src:
            pb = src.bounds
        previous = {"path": str(dest.relative_to(REPO)),
                    "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
                    "bounds_wsen": [float(pb.left), float(pb.bottom),
                                    float(pb.right), float(pb.top)],
                    "bytes": dest.stat().st_size}
        print(f"    existing DEM   {previous['bounds_wsen']}  "
              f"sha256 {previous['sha256'][:16]}...")
        if not force:
            raise AcquisitionError(
                f"{dest.relative_to(REPO)} already exists. It is an input to "
                "committed artifacts, so replacing it is deliberate: re-run with "
                "--force. The previous digest is recorded either way.")

    fetch_bbox = target_bbox(region, margin_deg)
    print(f"    requesting     {tuple(round(v, 4) for v in fetch_bbox)}  "
          f"({DEMTYPE}, GTiff)")

    tmp_dir = Path(tempfile.mkdtemp(prefix=f"wfg-dem-{region}-"))
    tmp = tmp_dir / f"{region}_dem.tif"
    try:
        req = fetch(fetch_bbox, key, tmp)
        print(f"    downloaded     {req['bytes'] / 1048576:.1f} MB in "
              f"{req['seconds']:.0f}s")
        val = validate(tmp, boxes, margin_deg)
        print(f"    validated      {val['shape'][0]}x{val['shape'][1]} @ "
              f"1 arc-second, covers all {len(boxes)} required extent(s)")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp), str(dest))
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    shutil.rmtree(tmp_dir, ignore_errors=True)
    print(f"    installed      {dest.relative_to(REPO)}")

    return {
        "region": region,
        "acquired_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "provider": "OpenTopography Global DEM API",
        "product": DEMTYPE,
        "citation": "NASA JPL. NASA Shuttle Radar Topography Mission Global 1 "
                    "arc second [SRTMGL1] V003. NASA EOSDIS Land Processes DAAC. "
                    "doi:10.5067/MEaSUREs/SRTM/SRTMGL1.003",
        "why": "the per-fire DEM was downloaded on the fire_manifest bbox, which "
               "does not contain the PHASE-5 ignition-centred walk bbox; edges in "
               "the uncovered strip were being timed at flat speed",
        "request": req,
        "raster": val,
        "replaced": previous,
        "installed_path": str(dest.relative_to(REPO)),
        "config_hash": config_hash(),
        "git_commit": _git(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--regions", nargs="+", default=["uljin_samcheok_2022"])
    ap.add_argument("--margin-deg", type=float, default=DEFAULT_MARGIN_DEG)
    ap.add_argument("--force", action="store_true",
                    help="replace an existing DEM (its digest is recorded first)")
    ap.add_argument("--out", default=str(REPO / "data/processed/dem_acquisition.json"))
    args = ap.parse_args()

    try:
        key = read_api_key()
    except AcquisitionError as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2

    records, failed = [], []
    for region in args.regions:
        try:
            records.append(acquire(region, margin_deg=args.margin_deg,
                                   force=args.force, key=key))
        except AcquisitionError as exc:
            print(f"    FAILED — nothing installed: {exc}", file=sys.stderr)
            failed.append((region, str(exc)))
        except Exception as exc:  # noqa: BLE001
            print(f"    FAILED — nothing installed: {type(exc).__name__}: {exc}",
                  file=sys.stderr)
            failed.append((region, f"{type(exc).__name__}: {exc}"))

    if records:
        out = Path(args.out)
        prev = json.loads(out.read_text()) if out.exists() else {"acquisitions": []}
        by = {r["region"]: r for r in prev.get("acquisitions", [])}
        for r in records:
            by[r["region"]] = r
        out.write_text(json.dumps(
            {"schema_version": 1,
             "note": "DEM acquisition provenance. The rasters live in "
                     "data/raw/firms_data/ (git-ignored) and are preserved in "
                     "data/snapshots/ — snapshot immediately after acquiring.",
             "acquisitions": [by[k] for k in sorted(by)]},
            indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nwrote {out.relative_to(REPO)}")
        print("\nNEXT, in order:")
        print("  python scripts/snapshot_external.py --preset dem   # preserve it")
        print("  python scripts/snapshot_external.py --verify")
        print("  python scripts/run_multi_region_routing.py --regions "
              + " ".join(r["region"] for r in records))
        print("  python scripts/build_multi_region_comparison.py")
        print("  python scripts/build_numbers.py && make verify")

    if failed:
        print(f"\nSTOP: {len(failed)} region(s) failed; nothing was installed for "
              "them. Do NOT route on a partial DEM.", file=sys.stderr)
        for r, e in failed:
            print(f"  {r}: {e}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
