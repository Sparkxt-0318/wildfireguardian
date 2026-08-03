"""Guards for the demonstration screen (Round-3 PHASE 8).

The screen is shown to judges on a venue network that will be unreliable or
absent, so the properties that matter are not visual:

1. **It is self-contained.** One file, no fetch, no CDN, no tile server, no
   storage API. A screen that degrades when the wifi drops fails in front of an
   audience.
2. **It replays; it does not compute.** Every number on it came out of a
   PHASE-6 run.
3. **The numbers on it are the committed ones.** A demo that quietly shows
   different figures from the paper is worse than no demo.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCREEN = REPO / "demo" / "operator_screen.html"
CANONICAL = REPO / "data" / "processed" / "real_roads_real_hazard_canonical.json"

pytestmark = pytest.mark.skipif(
    not SCREEN.exists(),
    reason="operator screen not built (scripts/build_operator_screen.py)")


def html() -> str:
    return SCREEN.read_text(encoding="utf-8")


def payload() -> dict:
    m = re.search(r"^const D = (\{.*\});$", html(), flags=re.M)
    assert m, "the inlined payload could not be found"
    return json.loads(m.group(1))


# ---------------------------------------------------------------------------
# 1. Self-contained
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("api", [
    "fetch(", "XMLHttpRequest", "WebSocket", "EventSource", "navigator.sendBeacon",
    "localStorage", "sessionStorage", "indexedDB", "serviceWorker",
    "import(", "@import",
])
def test_no_network_or_storage_api_is_used(api):
    src = html()
    # The word may appear inside an authored comment saying it is not used.
    body = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    body = re.sub(r"^\s*//.*$", "", body, flags=re.M)
    assert api not in body, f"{api} appears in executable source"


def test_no_external_reference_of_any_kind():
    src = html()
    urls = set(re.findall(r"https?://[^\s\"'<>)]+", src))
    # The SVG namespace is an XML identifier, not a resource that is fetched.
    urls.discard("http://www.w3.org/2000/svg")
    assert urls == set(), f"external references: {urls}"
    for tag in ("<img", "<link", "<iframe", "<object", "<embed", "<video",
                "<audio", "@font-face", "srcset="):
        assert tag not in src.lower(), tag


def test_there_is_exactly_one_file_and_no_sidecar():
    assert SCREEN.suffix == ".html"
    assert not (SCREEN.parent / "operator_screen").exists()
    assert not list(SCREEN.parent.glob("operator_screen.*.js"))
    assert not list(SCREEN.parent.glob("operator_screen.*.css"))


def test_it_opens_from_a_file_url_without_a_server():
    """No absolute paths, no `/`-rooted references that a file:// load breaks."""
    src = html()
    assert 'src="/' not in src and "href=\"/" not in src
    assert "file://" not in src


# ---------------------------------------------------------------------------
# 2. Replay only — no live polling, no computation
# ---------------------------------------------------------------------------


def test_no_live_polling_is_wired_in():
    """The word FIRMS is REQUIRED on the status bar — it names the detection
    source. What must be absent is a polling MECHANISM."""
    src = html()
    for token in ("FIRMS_MAP_KEY", "api/area", "firms.modaps", "setInterval(",
                  "map_key"):
        assert token.lower() not in src.lower(), token
    assert "FIRMS NRT" in src, "the detection source must still be named"


def test_the_page_declares_itself_a_replay_everywhere_it_matters():
    src, d = html(), payload()
    assert "재생 모드" in src
    assert "재생 모드" in d["scope"]["mode_banner"]
    assert "사전 계산" in src, "the screen must say the surface is pre-computed"


def test_the_era5_lag_is_on_the_status_bar():
    d = payload()
    assert "ERA5는 약 5일 지연 발행" in d["scope"]["weather"]
    assert d["scope"]["detection"] == "화점 탐지: 실시간 (FIRMS NRT)"


def test_the_coverage_caveat_is_on_the_status_bar():
    assert payload()["coverage_pct"] == 32.6
    assert "보행망 커버리지" in html()


# ---------------------------------------------------------------------------
# 3. The numbers are the committed ones
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not CANONICAL.exists(), reason="canonical artifact absent")
def test_the_counts_match_the_committed_canonical_run():
    committed = json.loads(CANONICAL.read_text())["arms"]["slope_digraph_canonical"]
    c = payload()["counts"]
    assert c == committed["counts"], (
        "the screen must not show figures that differ from the committed run")
    assert sum(c.values()) == committed["n_origins_scanned"] == 458


def test_every_origin_is_plotted_not_just_the_actionable_ones():
    d = payload()
    assert len(d["origins"]) == sum(d["counts"].values()) == 458
    by = {}
    for o in d["origins"]:
        by[o["bucket"]] = by.get(o["bucket"], 0) + 1
    assert by["both_safe"] == d["counts"]["both_safe"] == 414
    assert by["naive_into_FA_safe"] == 42
    assert by["no_safe_route"] == 2


def test_the_dispatch_rows_are_the_actionable_points_most_urgent_first():
    d = payload()
    rows = d["actionable"]
    assert len(rows) == d["counts"]["naive_into_FA_safe"] + d["counts"]["no_safe_route"]
    keys = [(r["closing_window_min"] is None,
             r["closing_window_min"] if r["closing_window_min"] is not None else 1e9)
            for r in rows]
    assert keys == sorted(keys), "same ordering rule as the A4 sheet"


def test_the_hazard_surface_is_the_canonical_field():
    d = payload()
    assert d["npz_sha256"] == "81b4e4d159daa7a8"
    assert len(d["bands"]) == len(d["grid"]["times_min"]) == 5


def test_the_probability_bands_are_discrete_and_labelled():
    d = payload()
    assert len(d["band_labels"]) == len(d["band_fills"]) == 4
    for lbl in d["band_labels"]:
        assert re.fullmatch(r"[01]\.\d\d–[01]\.\d\d", lbl), lbl
    lo = [float(x.split("–")[0]) for x in d["band_labels"]]
    hi = [float(x.split("–")[1]) for x in d["band_labels"]]
    assert lo == sorted(lo) and hi == sorted(hi), "bands must ascend"
    assert lo[1:] == hi[:-1], "bands must be contiguous, with no gap"


def test_both_routes_are_real_polylines_from_the_run():
    d = payload()
    assert d["routes"], "at least one route pair must be present"
    r = d["routes"][0]
    assert len(r["naive_xy"]) > 2 and len(r["fa_xy"]) > 2
    assert r["naive_enters_hazard"] is True, (
        "the pair drawn is a future-aware-only origin: the fire-blind route "
        "walks into the fire, which is the whole point of showing two")
    assert r["fa_enters_hazard"] is False


def test_the_hotspots_share_one_clock_with_the_hazard_surface():
    d = payload()
    ts = [h["t"] for h in d["hotspots"]]
    assert ts == sorted(ts)
    assert min(ts) == 0.0, "the field's t=0 is the first overpass"
    assert max(ts) <= d["grid"]["times_min"][-1]


def test_no_coordinate_reaches_the_dispatch_table():
    """The map is coordinates; the operational list is not, on screen too."""
    for r in payload()["actionable"]:
        assert "x" not in r or isinstance(r.get("label"), str)
        assert r.get("label")
        assert not re.search(r"\b1\d{6}", r["label"] or "")
