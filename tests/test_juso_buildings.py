"""NH-005 (2026-09-13): the 도로명주소 건물 layer for 영덕, committed as centroids.

Binds the manifest's counts to the artifact they describe, and the `juso` building
source to the manifest, so the numbers prose cites cannot drift from the file.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
DIR = REPO / "data/processed/external/juso_buildings_yeongdeok"
MANIFEST = DIR / "manifest.json"
GEOJSON = DIR / "buildings_47770.geojson.gz"


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def features() -> list[dict]:
    with gzip.open(GEOJSON, "rt", encoding="utf-8") as fh:
        return json.load(fh)["features"]


def test_the_manifest_counts_are_the_artifact_counts(manifest, features):
    c = manifest["counts"]
    assert len(features) == c["county_47770_buildings"]
    inside = [f for f in features if f["properties"]["inside_canonical_box"]]
    assert len(inside) == c["inside_canonical_box"]
    assert len(features) - len(inside) == c["outside_canonical_box"]
    assert sum(1 for f in inside if f["properties"].get("bul_dpn_se") == "M") == c["inside_canonical_box_main_buildings"]
    assert c["osm_share_of_juso_inside_box_pct"] == round(100.0 * c["osm_buildings_inside_walk_bbox"] / c["inside_canonical_box"], 2)


def test_inside_flag_agrees_with_the_regions_box(manifest, features):
    from wildfireguardian.utils import regions
    minx, miny, maxx, maxy = regions.lookup("yeongdeok_2025").bbox_epsg5179
    for f in features:
        p = f["properties"]
        x, y = p["centroid_x_5179"], p["centroid_y_5179"]
        assert p["inside_canonical_box"] == (minx <= x <= maxx and miny <= y <= maxy)


def test_building_ids_are_unique_and_sorted(features):
    ids = [f["properties"]["bd_mgt_sn"] for f in features]
    assert len(set(ids)) == len(ids)
    assert ids == sorted(ids)


def test_the_osm_count_in_the_manifest_is_the_registered_one(manifest):
    osm = json.loads((REPO / "data/processed/building_origin_routing.json").read_text(encoding="utf-8"))
    assert manifest["counts"]["osm_buildings_inside_walk_bbox"] == osm["regions"][0]["n_buildings"]


def test_the_juso_source_loads_the_inside_box_population(manifest):
    from wildfireguardian.buildings import SOURCES, load_buildings
    assert "juso" in SOURCES
    b = load_buildings("yeongdeok_2025", source="juso", repo=REPO)
    assert b.source == "juso"
    assert len(b) == manifest["counts"]["inside_canonical_box"]
    assert b.xy.shape == (len(b), 2) and np.isfinite(b.xy).all()
    assert len(b.ids) == len(set(b.ids)) == len(b)
    with pytest.raises(FileNotFoundError):
        load_buildings("uiseong_andong_2025", source="juso", repo=REPO)


def test_the_registry_matches_the_manifest():
    import subprocess
    import sys
    r = subprocess.run([sys.executable, str(REPO / "scripts/register_juso_buildings.py"), "--check"],
                       cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
