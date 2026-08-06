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
SCREENS = REPO / "outputs" / "live" / "screens"
SCREEN = REPO / "demo" / "operator_screen.html"          # the Yeongdeok copy
CANONICAL = REPO / "data" / "processed" / "real_roads_real_hazard_canonical.json"
UA = REPO / "data" / "processed" / "real_roads_real_hazard_uiseong_andong_2025.json"

#: Every built screen. Both regions are checked by the same properties — a
#: guard that only holds for the region it was written against is not a guard.
#: The per-region directories hold the FIRMS/replay screens; the manual-trigger
#: screen is a sibling file and is covered by tests/test_manual_trigger.py.
ALL = sorted(SCREENS.glob("*/operator_screen.html")) if SCREENS.exists() else []

pytestmark = pytest.mark.skipif(
    not SCREEN.exists() or not ALL,
    reason="operator screens not built (scripts/build_operator_screen.py)")


def html(path: Path = SCREEN) -> str:
    return path.read_text(encoding="utf-8")


def payload(path: Path = SCREEN) -> dict:
    m = re.search(r"^const D = (\{.*\});$", html(path), flags=re.M)
    assert m, f"the inlined payload could not be found in {path}"
    return json.loads(m.group(1))


def by_region() -> dict[str, dict]:
    return {payload(p)["region"]: payload(p) for p in ALL}


# ---------------------------------------------------------------------------
# 1. Self-contained
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("screen", ALL, ids=lambda p: p.parent.name)
@pytest.mark.parametrize("api", [
    "fetch(", "XMLHttpRequest", "WebSocket", "EventSource", "navigator.sendBeacon",
    "localStorage", "sessionStorage", "indexedDB", "serviceWorker",
    "import(", "@import",
])
def test_no_network_or_storage_api_is_used(api, screen):
    src = html(screen)
    # The word may appear inside an authored comment saying it is not used.
    body = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    body = re.sub(r"^\s*//.*$", "", body, flags=re.M)
    assert api not in body, f"{api} appears in executable source"


@pytest.mark.parametrize("screen", ALL, ids=lambda p: p.parent.name)
def test_no_external_reference_of_any_kind(screen):
    src = html(screen)
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


@pytest.mark.parametrize("screen", ALL, ids=lambda p: p.parent.name)
def test_no_live_polling_is_wired_in(screen):
    """The word FIRMS is REQUIRED on the status bar — it names the detection
    source. What must be absent is a polling MECHANISM."""
    src = html(screen)
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
    # PHASE 21: the separator is a TILDE, not an EN dash. Two reasons, and the
    # second is the one that would have bitten in the hall:
    #   · a range is written with a tilde by the project's own typographic rule
    #     (scripts/check_screen_assets.py), and the tilde is exactly a digit's
    #     advance in the shipped face, so it cannot nudge a numeric column;
    #   · the shipped font subset contains NO EN dash glyph, so the old labels
    #     would now render as tofu on the legend.
    for lbl in d["band_labels"]:
        assert re.fullmatch(r"[01]\.\d\d~[01]\.\d\d", lbl), lbl
    lo = [float(x.split("~")[0]) for x in d["band_labels"]]
    hi = [float(x.split("~")[1]) for x in d["band_labels"]]
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


# ---------------------------------------------------------------------------
# 8. Two regions, two jobs — and the properties must hold for both
# ---------------------------------------------------------------------------


def test_both_regions_are_built():
    regions = set(by_region())
    assert regions == {"yeongdeok_2025", "uiseong_andong_2025"}, regions


@pytest.mark.parametrize("screen", ALL, ids=lambda p: p.parent.name)
def test_every_screen_names_its_own_hazard_field(screen):
    """The field name is carried, never assumed. An early version hard-coded
    routing_demo_canonical.npz and mislabelled the Uiseong-Andong surface."""
    d = payload(screen)
    expected = ("routing_demo_canonical.npz" if d["region"] == "yeongdeok_2025"
                else f"hazard_{d['region']}.npz")
    assert d["npz_name"] == expected
    assert d["npz_name"] in html(screen)


@pytest.mark.parametrize("screen", ALL, ids=lambda p: p.parent.name)
def test_every_screen_carries_its_own_coverage_figure(screen):
    d = payload(screen)
    assert d["coverage_pct"] == {"yeongdeok_2025": 32.6,
                                 "uiseong_andong_2025": 99.2}[d["region"]]


@pytest.mark.skipif(not UA.exists(), reason="Uiseong-Andong artifact absent")
def test_the_uiseong_andong_counts_match_its_committed_run():
    committed = json.loads(UA.read_text())["arms"]["slope_digraph_canonical"]
    d = by_region()["uiseong_andong_2025"]
    assert d["counts"] == committed["counts"]
    assert sum(d["counts"].values()) == 368
    assert d["counts"]["naive_into_FA_safe"] == 91
    assert d["counts"]["no_safe_route"] == 12


def test_uiseong_andong_states_that_the_responder_side_is_not_applicable():
    d = by_region()["uiseong_andong_2025"]
    r = d["responder"]
    assert r["n_depot_pois"] == 0 and r["available"] is False
    src = html(SCREENS / "uiseong_andong_2025" / "operator_screen.html")
    assert r["status_ko"] in src, "the statement must reach the status bar"


def test_the_depot_statement_never_says_the_region_has_no_fire_stations():
    """HANDOFF_ROUND3.md rule 11. The claim is about OSM mapping inside one
    bbox; the wider manifest bbox contains six."""
    for p in ALL:
        src = html(p)
        for banned in ("의성·안동에는 소방서가 없", "의성안동에는 소방서가 없",
                       "소방서가 없습니다."):
            assert banned not in src, banned
    r = by_region()["uiseong_andong_2025"]["responder"]
    assert "OSM에 매핑된" in r["status_ko"]
    assert "3,926" in r["status_ko"], "the wider bbox's six must be stated"


def test_yeongdeok_still_carries_the_coverage_limitation():
    """It is kept ON PURPOSE — the dashed walk bbox is how 32.6 % is shown."""
    d = by_region()["yeongdeok_2025"]
    assert d["coverage_pct"] == 32.6
    assert d["walk_box"] is not None
    assert "보행망 커버리지" in html(SCREENS / "yeongdeok_2025" / "operator_screen.html")


def test_no_responder_route_is_drawn_on_either_screen():
    """The 459 series is resident-side everywhere. Both lines are the
    resident's: fire-blind and future-aware."""
    for p in ALL:
        src = html(p)
        assert "주민 대피 경로" in src and "미래 인지 경로" in src
        for banned in ("구조자 경로", "출동 경로", "차량 경로"):
            assert banned not in src, banned


@pytest.mark.parametrize("screen", ALL, ids=lambda p: p.parent.name)
def test_the_row_cap_is_honest_about_what_it_hides(screen):
    d = payload(screen)
    assert d["max_rows"] == 45
    assert d["n_actionable_total"] == len(d["actionable"])
    if d["n_actionable_total"] > d["max_rows"]:
        # The overflow row is built at runtime, so the FILE carries the code
        # that builds it. Both halves of the promise must be there: how many
        # are hidden, and that the paper sheets carry all of them.
        src = html(screen)
        assert "D.n_actionable_total - cap" in src
        assert "A4 시트에는 전부 포함" in src


def test_uiseong_andong_has_more_points_than_fit_and_says_so():
    d = by_region()["uiseong_andong_2025"]
    assert d["n_actionable_total"] == 105 > d["max_rows"]
    src = html(SCREENS / "uiseong_andong_2025" / "operator_screen.html")
    assert "A4 시트에는 전부 포함" in src


def test_skip_preroll_variant_starts_at_detection():
    alt = SCREENS / "uiseong_andong_2025" / "operator_screen_nopreroll.html"
    if not alt.exists():
        pytest.skip("--skip-preroll variant not built")
    assert payload(alt)["preroll"] == 0
    assert by_region()["uiseong_andong_2025"]["preroll"] == 25


# ---------------------------------------------------------------------------
# 9. Demo window: --start-at, --paused-on-load, and exact state reconstruction
# ---------------------------------------------------------------------------

DEMO = SCREENS / "uiseong_andong_2025_demo.html"


def _run_json(region: str) -> dict:
    """The RUN.json the screen for `region` was built from."""
    runs = sorted((REPO / "outputs" / "live" / "replay" / region).glob("*/RUN.json"),
                  key=lambda p: p.stat().st_mtime)
    return json.loads(runs[-1].read_text(encoding="utf-8"))


@pytest.mark.parametrize("screen", ALL, ids=lambda p: p.parent.name)
def test_triggers_are_overpass_moments_not_first_hotspot_times(screen):
    """A trigger fires when an OVERPASS completes and its batch is diffed
    against the seen-set — not when the first hotspot of that batch was
    acquired. For Uiseong-Andong those are 77 minutes apart, and an earlier
    version showed 계산 중 at t=0 for a run that did not route until t+77."""
    from datetime import datetime

    d = payload(screen)
    run = _run_json(d["region"])
    poll = run["inputs"]["poll"]
    t0 = datetime.strptime(poll["archive_t0_utc"], "%Y-%m-%dT%H:%M:%SZ")
    expected = sorted(
        round((datetime.strptime(o["archive_time_utc"], "%Y-%m-%dT%H:%M:%SZ")
               - t0).total_seconds() / 60.0, 1)
        for o in poll["overpasses"])
    assert d["triggers"] == expected


def test_the_two_regions_trigger_at_the_known_moments():
    """These are the REPLAY screens; a manual screen triggers at t=0 by
    construction and is checked in tests/test_manual_trigger.py."""
    by = by_region()
    assert {d["trigger_source"] for d in by.values()} == {"replay"}
    assert by["uiseong_andong_2025"]["triggers"] == [77.0, 463.0]
    assert by["yeongdeok_2025"]["triggers"] == [0.0, 333.0]


@pytest.mark.parametrize("screen", ALL, ids=lambda p: p.parent.name)
def test_the_fill_is_a_fixed_duration_not_a_fixed_rate(screen):
    """So the beat is the same length for 44 rows and for 45-of-105, which is
    what makes a 60-second window around the trigger possible at all."""
    d = payload(screen)
    assert d["fill_span_min"] == 18 and d["calc_min"] == 12
    assert "D.fill_span_min / cap" in html(screen)


@pytest.mark.skipif(not DEMO.exists(), reason="demo screen not built")
def test_the_demo_screen_opens_thirty_seconds_before_the_trigger_and_paused():
    d = payload(DEMO)
    trigger = d["triggers"][0]
    assert trigger == 77.0
    # 30 s of wall clock at 60x is 30 field minutes.
    assert d["start_at"] == trigger - 30 == 47.0
    assert d["paused_on_load"] is True
    # trigger -> full list is calc + fill = 30 field minutes, so the window
    # from start to a complete list is exactly 60 s at 60x.
    assert d["calc_min"] + d["fill_span_min"] == 30
    assert (trigger + d["calc_min"] + d["fill_span_min"]) - d["start_at"] == 60


@pytest.mark.skipif(not DEMO.exists(), reason="demo screen not built")
def test_the_demo_screen_is_the_same_region_and_data_as_the_full_one():
    """A separate start point must not mean separate numbers."""
    a, b = payload(DEMO), by_region()["uiseong_andong_2025"]
    for k in ("region", "counts", "origins", "actionable", "routes", "bands",
              "hotspots", "triggers", "coverage_pct", "npz_sha256"):
        assert a[k] == b[k], k


@pytest.mark.parametrize("screen", ALL + ([DEMO] if DEMO.exists() else []),
                         ids=lambda p: p.stem if p.name != "operator_screen.html"
                         else p.parent.name)
def test_the_start_point_only_enters_through_the_clock(screen):
    """Reconstruction is exact because every drawn thing is a function of t.
    `T_START` may only initialise the clock and the reset target; if it leaked
    into the hazard, hotspot or row logic the two paths could diverge."""
    src = html(screen)
    assert "const T_START = (D.start_at !== null" in src
    assert "let t = T_START" in src
    assert "t = T_START; shown = -1; filled = 0; fillStart = null;" in src
    # T_START appears exactly three times: the definition and those two uses.
    assert src.count("T_START") == 3, src.count("T_START")


@pytest.mark.parametrize("screen", ALL + ([DEMO] if DEMO.exists() else []),
                         ids=lambda p: p.stem if p.name != "operator_screen.html"
                         else p.parent.name)
def test_paused_on_load_paints_before_the_first_frame(screen):
    """Otherwise a paused screen opens blank and stays blank."""
    src = html(screen)
    assert "render();" in src.split("requestAnimationFrame(tick);")[0][-400:]
