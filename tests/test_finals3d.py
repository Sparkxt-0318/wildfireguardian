"""The 3D booth replay (web/finals3d.html) draws only what its payload says, and the payload
says only what the committed evidence allows.

What is pinned here, and why each one matters at the booth:

* the page is offline: no URL, no network construct, fonts vendored (no wifi at the venue);
* no EM/EN dash in the visible text (the font-subset rule every shipped screen follows);
* the deadline bracket is a bracket: for every building node and every walking speed the
  pessimistic deadline (fire burning from the previous clear look) is never later than the
  optimistic one (fire burning from when it was seen). A violation would mean the page
  draws a green house that the record says could already be cut off;
* the counts the page computes live equal the counts ``scripts/build_finals3d.py`` recorded
  in ``data/processed/finals3d/finals3d_scene.json`` (same rule, decoded independently);
* the payload is the one the scene record hashed.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

PAGE = REPO / "web/finals3d.html"
PAYLOAD = REPO / "web/assets/finals3d/data.js"
BUNDLE = REPO / "web/assets/finals3d/app.js"
SCENE = REPO / "data/processed/finals3d/finals3d_scene.json"

#: The one absolute URL the three.js bundle carries: the XHTML namespace it passes to
#: ``document.createElementNS``. An identifier, never fetched (the same reasoning as the
#: SVG namespace that ``check_screen_assets.NAMESPACE_IDENTIFIERS`` already allows).
BUNDLE_NAMESPACES = {"http://www.w3.org/1999/xhtml"}


def _payload() -> dict:
    text = PAYLOAD.read_text(encoding="utf-8")
    assert text.startswith("window.WFG3D=") and text.rstrip().endswith(";")
    return json.loads(text[len("window.WFG3D="):].rstrip().rstrip(";"))


def _arr(s: str, dtype) -> np.ndarray:
    return np.frombuffer(base64.b64decode(s), dtype=dtype)


def test_the_page_passes_the_screen_gates():
    from check_screen_assets import check_file
    assert check_file(PAGE) == []


def test_the_bundle_reaches_no_host():
    from check_screen_assets import check_offline
    found = [f for f in check_offline(BUNDLE.read_text(encoding="utf-8"))
             if not any(ns in f.detail for ns in BUNDLE_NAMESPACES)]
    assert found == []
    assert check_offline(PAYLOAD.read_text(encoding="utf-8")) == []


def test_the_page_loads_only_local_files():
    html = PAGE.read_text(encoding="utf-8")
    for src in ("assets/finals3d/data.js", "assets/finals3d/app.js"):
        assert f'src="{src}"' in html
        assert (REPO / "web" / src).exists()
    for font in ("IBMPlexSansKR-Regular", "IBMPlexSansKR-SemiBold", "IBMPlexMono-Regular"):
        assert (REPO / f"web/assets/fonts/{font}.woff2").exists()


def test_the_payload_arrays_agree_on_their_lengths():
    d = _payload()
    t = d["terrain"]
    assert len(_arr(t["h"], np.int16)) == t["nx"] * t["ny"]
    assert len(_arr(t["sea"], np.uint8)) == t["nx"] * t["ny"]
    f = d["fire"]
    assert len(_arr(f["first_pass"], np.uint8)) == f["ncols"] * f["nrows"]
    assert len(_arr(f["forecast_min"], np.uint16)) == f["ncols"] * f["nrows"]
    b = d["buildings"]
    for key, dt in (("x", np.uint16), ("y", np.uint16), ("size", np.uint8), ("floors", np.uint8), ("node", np.int32)):
        assert len(_arr(b[key], dt)) == b["n"], key
    node = _arr(b["node"], np.int32)
    assert node.max() < d["nodes"]["n"]
    for s in d["speeds"]:
        p = d["nodes"]["per_speed"][s]
        for key, dt in (("lsdR", np.int16), ("lsdL", np.int16), ("walkR", np.uint16)):
            assert len(_arr(p[key], dt)) == d["nodes"]["n"], (s, key)


def test_the_deadline_bracket_is_a_bracket():
    d = _payload()
    for s in d["speeds"]:
        p = d["nodes"]["per_speed"][s]
        lo, hi = _arr(p["lsdL"], np.int16), _arr(p["lsdR"], np.int16)
        assert (lo <= hi).all(), f"speed {s}: {int((lo > hi).sum())} nodes with L later than R"
        assert ((hi >= 0) | (lo < 0)).all(), f"speed {s}: never-safe under R but safe under L"


def _counts(lo, hi, weights, t):
    late = (hi < 0) | (t > hi)
    open_ = ~late & (lo >= 0) & (t <= lo)
    unk = ~late & ~open_
    return {"walk_out_open": int(weights[open_].sum()), "undetermined": int(weights[unk].sum()),
            "too_late": int(weights[late].sum())}


def test_the_page_counts_equal_the_recorded_counts():
    d = _payload()
    scene = json.loads(SCENE.read_text(encoding="utf-8"))
    node = _arr(d["buildings"]["node"], np.int32)
    weights = np.bincount(node[node >= 0], minlength=d["nodes"]["n"])
    # the scene record counts the whole routable population; the page draws the ROI, which
    # holds all of it (asserted, so a narrower ROI cannot silently change what is counted)
    assert int(weights.sum()) == scene["buildings_routable_total"] == scene["buildings_routable_in_roi"]
    for s in d["speeds"]:
        p = d["nodes"]["per_speed"][s]
        lo, hi = _arr(p["lsdL"], np.int16), _arr(p["lsdR"], np.int16)
        for t, rec in scene["status_counts_buildings"][s].items():
            if not t.isdigit():
                continue
            assert _counts(lo, hi, weights, int(t)) == rec, (s, t)
        assert scene["status_counts_buildings"][s]["bracket_violations"] == 0


def test_the_scene_record_hashes_this_payload():
    scene = json.loads(SCENE.read_text(encoding="utf-8"))
    assert scene["web_payload_sha256"] == hashlib.sha256(PAYLOAD.read_bytes()).hexdigest()


def test_the_page_says_it_is_a_replay_and_what_is_exaggerated():
    html = PAGE.read_text(encoding="utf-8")
    assert "재생 모드" in html and "실시간 예측이 아닙니다" in html
    src = (REPO / "web/src/finals3d/main.js").read_text(encoding="utf-8")
    assert "과장 표시" in src


@pytest.mark.parametrize("speed", ["1.2", "0.7", "0.5"])
def test_every_speed_the_page_offers_has_a_run(speed):
    d = _payload()
    assert speed in d["speeds"]
    assert (REPO / f"data/processed/finals3d/lsd_R_{speed}.json").exists()
    assert (REPO / f"data/processed/finals3d/lsd_L_{speed}.json").exists()
    assert f'data-speed="{speed}"' in PAGE.read_text(encoding="utf-8")


def test_the_optimistic_reading_reproduces_the_committed_truth_classes():
    """The R run at the committed elderly speed IS the K-SPREAD metric-4 truth: same router,
    same step hazard, same building population. Its per-building classes must equal the
    ones ``leaderboard_v0_2.json`` recorded, or the page is not drawing the repository's
    own observation-graded deadlines."""
    sys.path.insert(0, str(REPO / "scripts" / "benchmark"))
    from kspread_metrics import lsd_class

    d = _payload()
    node = _arr(d["buildings"]["node"], np.int32)
    weights = np.bincount(node[node >= 0], minlength=d["nodes"]["n"])
    hi = _arr(d["nodes"]["per_speed"]["0.7"]["lsdR"], np.int16)
    got: dict[str, int] = {}
    for v, w in zip(hi, weights):
        c = lsd_class(float(v))
        got[c] = got.get(c, 0) + int(w)
    lb = json.loads((REPO / "data/processed/benchmark/leaderboard_v0_2.json").read_text(encoding="utf-8"))
    truth = lb["tracks"]["hindcast"][0]["per_event"]["yeongdeok_2025"]["decision_shift"]["lsd_class_buildings_truth"]
    assert got == truth
