"""No new science: the field, the interval code and the checker are byte-for-byte the research files; the instance
rules equal research/kcf-replay/replay.py; the 읍·면 table and registry are what they say."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import pytest

PRODUCT = Path(__file__).resolve().parents[1]
REPO = PRODUCT.parents[1]
PKG = PRODUCT / "wfg_roadlayer"

PAIRS = [
    (PKG / "vendor/deadline_field/core.py", REPO / "research/harness-2026-11/F-3.1/deadline_field/core.py"),
    (PKG / "vendor/deadline_field/intervals.py", REPO / "research/harness-2026-11/F-3.1/deadline_field/intervals.py"),
    (PKG / "vendor/kcf_theorem/checker.py", REPO / "research/kcf-theorem/checker.py"),
]


@pytest.mark.parametrize("ours,theirs", PAIRS, ids=[p[0].name for p in PAIRS])
def test_vendored_byte_identical(ours, theirs):
    assert ours.read_bytes() == theirs.read_bytes()


def test_verifier_imports_only_stdlib_and_checker():
    src = (PKG / "verifier/verify_certificate.py").read_text(encoding="utf-8")
    imports = {l.split()[1].split(".")[0] for l in src.splitlines() if l.startswith(("import ", "from "))}
    assert imports <= {"__future__", "gzip", "hashlib", "heapq", "json", "sys", "fractions", "pathlib", "checker"}, imports


def test_registry_hashes_match_repository_files():
    reg = json.loads((PRODUCT / "data/regions.json").read_text(encoding="utf-8"))
    for rid, r in reg["regions"].items():
        p = REPO / r["places"]["repo_path"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == r["places"]["sha256"], rid
        rows = {x["path"]: x["sha256"] for x in json.loads((REPO / "data/routing/INPUT_FILES.json").read_text())} \
            if (REPO / "data/routing/INPUT_FILES.json").is_file() else {}
        if rows:
            assert rows[r["graph"]["archive_member"]] == r["graph"]["sha256"]


def test_towns_cover_every_origin_and_agree_with_sigungu():
    reg = json.loads((PRODUCT / "data/regions.json").read_text(encoding="utf-8"))
    for rid, r in reg["regions"].items():
        feats = json.loads((REPO / r["places"]["repo_path"]).read_text(encoding="utf-8"))["features"]
        origins = {f["properties"]["id"]: f["properties"] for f in feats if f["properties"]["role"] == "origin"}
        towns = {x["place_id"]: x for x in csv.DictReader(open(PRODUCT / r["towns"], encoding="utf-8"))}
        assert set(towns) == set(origins), rid
        for pid, t in towns.items():
            sg = origins[pid].get("sigungu") or {}
            if sg.get("status") == "established":
                assert t["sigungu"] == sg["ko"], pid
            assert t["method"] in ("legal_ri_unique", "legal_ri_ambiguous_nearest", "name_contains_legal", "nearest_established", "unknown")
            assert (t["eupmyeon"] == "") == (t["method"] == "unknown")
        # every 읍·면 lies in exactly one 시·군
        by_town = {}
        for t in towns.values():
            if t["eupmyeon"]:
                by_town.setdefault(t["eupmyeon"], set()).add(t["sigungu"])
        assert all(len(v) == 1 for v in by_town.values()), by_town


def test_instance_rules_equal_kcf_replay(cache):
    """build_instance / accept give the same masks as research/kcf-replay/replay.py Region.instance / accept."""
    np = pytest.importorskip("numpy")  # noqa: F841
    if not (REPO / "data/routing/graphs/uiseong_andong_2025/graph.json").is_file():
        pytest.skip("replay.py reads data/routing (tools/fetch_routing_inputs.py)")
    sys.path.insert(0, str(REPO / "research/kcf-replay"))
    import replay  # noqa: E402
    from wfg_roadlayer import engine, fireinput, regiondata
    R = replay.Region("uiseong_andong_2025")
    reg = regiondata.Region("uiseong_andong_2025", cache)
    fire = fireinput.load_geotiff(PRODUCT / "examples/fire_arrival_20250325T0300Z_MEASURED_8h.tif", reg.road,
                                  issue_utc=regiondata.parse_utc("2025-03-25T03:00:00Z"), horizon_min=None)
    close_s = fire.arrival_s
    H = fire.horizon_s
    theirs = R.instance(close_s, H)
    ours = engine.build_instance(reg.road, close_s, H)
    assert ours.B == theirs.B and ours.W == theirs.W
    for node in {s["node"] for s in reg.shelters}:
        assert engine.accept(reg.road, close_s, node, H, 120) == R.accept(close_s, node, H)
