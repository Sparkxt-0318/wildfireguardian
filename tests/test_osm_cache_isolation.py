"""Acquiring one region must never overwrite another's OSM cache.

Round-3 PHASE 5 STEP 1-②.

THE FAILURE THIS PREVENTS
-------------------------
The OSM loaders write fixed filenames — ``walk.graphml``, ``drive.graphml``,
``shelters.geojson``, ``depots.geojson`` — into ``cfg.osm_cache_dir``. Until now
that directory did not depend on the region, so fetching a second region would
have silently overwritten the first with a graph for a different bbox. Nothing
would have raised; the next run would simply have routed Yeongdeok origins over
Uiseong roads.

That is structurally the same event as the 2026-07-23 walk-graph loss
(``docs/DATA_LOSS_2026-07-24.md``): a fixed path plus a new fetch. The fix is
``RescueConfig.osm_cache_path`` = ``{osm_cache_dir}/{region_name}/``, and these
tests hold it in place.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from wildfireguardian.routing.rescue import RescueConfig

REPO = Path(__file__).resolve().parents[1]
CACHE_FILES = ("walk.graphml", "drive.graphml", "shelters.geojson",
               "depots.geojson", "fire_station.geojson")
REGIONS = ("yeongdeok_2025", "uiseong_andong_2025", "uljin_samcheok_2022")


def test_cache_path_is_scoped_by_region():
    base = RescueConfig(osm_cache_dir="/tmp/wfg-cache")
    for region in REGIONS:
        cfg = replace(base, region_name=region)
        assert cfg.osm_cache_path == Path("/tmp/wfg-cache") / region
        assert cfg.osm_cache_path.name == region


def test_two_regions_never_share_a_cache_directory():
    base = RescueConfig(osm_cache_dir="/tmp/wfg-cache")
    paths = {r: replace(base, region_name=r).osm_cache_path for r in REGIONS}
    assert len(set(paths.values())) == len(REGIONS)
    for a in REGIONS:
        for b in REGIONS:
            if a == b:
                continue
            for f in CACHE_FILES:
                assert paths[a] / f != paths[b] / f


def test_writing_one_region_leaves_the_other_untouched(tmp_path):
    """The end-to-end property, exercised on real files.

    Simulates two acquisitions writing the same fixed filenames and asserts the
    first region's bytes survive. Under the old flat layout this assertion fails.
    """
    base = RescueConfig(osm_cache_dir=str(tmp_path))
    first = replace(base, region_name="yeongdeok_2025")
    second = replace(base, region_name="uiseong_andong_2025")

    first.osm_cache_path.mkdir(parents=True, exist_ok=True)
    for f in CACHE_FILES:
        (first.osm_cache_path / f).write_bytes(b"YEONGDEOK-" + f.encode())
    before = {f: hashlib.sha256((first.osm_cache_path / f).read_bytes()).hexdigest()
              for f in CACHE_FILES}

    # A second acquisition writes the SAME filenames.
    second.osm_cache_path.mkdir(parents=True, exist_ok=True)
    for f in CACHE_FILES:
        (second.osm_cache_path / f).write_bytes(b"UISEONG-" + f.encode())

    after = {f: hashlib.sha256((first.osm_cache_path / f).read_bytes()).hexdigest()
             for f in CACHE_FILES}
    assert after == before, "the second region overwrote the first"
    for f in CACHE_FILES:
        assert (first.osm_cache_path / f).read_bytes().startswith(b"YEONGDEOK-")
        assert (second.osm_cache_path / f).read_bytes().startswith(b"UISEONG-")


def test_the_migrated_yeongdeok_cache_is_where_the_loader_looks():
    cfg = RescueConfig()
    d = REPO / cfg.osm_cache_path
    if not d.exists():
        pytest.skip("OSM cache absent in this checkout")
    for f in ("walk.graphml", "drive.graphml", "shelters.geojson", "depots.geojson"):
        assert (d / f).exists(), f"{f} missing from {d}"
    # And nothing is left at the old flat location, which would shadow nothing
    # but would certainly confuse the next reader.
    flat = REPO / "data" / "cache" / "osm"
    for f in CACHE_FILES:
        assert not (flat / f).exists(), (
            f"{f} still sits at the old flat path {flat}; the migration is "
            "incomplete and a future region fetch could still collide")


def test_migrated_cache_still_matches_the_snapshot_store():
    """The move must have preserved bytes, not just filenames."""
    cfg = RescueConfig()
    d = REPO / cfg.osm_cache_path
    man_path = REPO / "data" / "snapshots" / "MANIFEST.json"
    if not (d.exists() and man_path.exists()):
        pytest.skip("cache or snapshot manifest absent")
    man = json.loads(man_path.read_text())
    by_origin = {e["origin_path"]: e for e in man["snapshots"]}
    checked = 0
    for f in CACHE_FILES:
        e = by_origin.get(f"data/cache/osm/{cfg.region_name}/{f}")
        if e is None or not (d / f).exists():
            continue
        got = hashlib.sha256((d / f).read_bytes()).hexdigest()
        assert got == e["sha256"], f"{f} drifted from its snapshot"
        checked += 1
    assert checked >= 4, f"expected to verify at least 4 files, checked {checked}"
