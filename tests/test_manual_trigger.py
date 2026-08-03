"""Guards for the manual ignition-point trigger (Round-3 PHASE 12).

In real operation a fire's location arrives from a 119 call, a watch-tower or a
CCTV operator long before a satellite sees it. This path acts on that, and the
properties that matter are:

1. **Both triggers coexist.** The FIRMS path is untouched.
2. **The downstream is literally the same code**, so "identical to the FIRMS
   route" is a structural fact rather than a claim that has to be re-checked
   every time something changes.
3. **The source is recorded, and the trigger time means what it says.** For
   FIRMS it is a satellite overpass; for a manual report it is when a person
   entered a coordinate. Presenting one as the other would be a lie about
   provenance.
4. **A coordinate outside the registered region is refused**, because the
   network, refuges and hazard surface only exist inside it.
"""

from __future__ import annotations

import ast
import inspect
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from wildfireguardian.live import scope as scope_mod
from wildfireguardian.live.scope import Scope

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "run_manual_trigger.py"
LIVE = REPO / "scripts" / "run_live_detection.py"
MANUAL_RUNS = sorted((REPO / "outputs" / "live" / "manual").glob("*/*/RUN.json")) \
    if (REPO / "outputs" / "live" / "manual").exists() else []


def _calls(src: str) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        f, parts = node.func, []
        while isinstance(f, ast.Attribute):
            parts.append(f.attr)
            f = f.value
        if isinstance(f, ast.Name):
            parts.append(f.id)
        if parts:
            out.add(".".join(reversed(parts)))
    return out


# ---------------------------------------------------------------------------
# 1. Both triggers coexist
# ---------------------------------------------------------------------------


def test_the_firms_path_still_exists():
    assert LIVE.exists()
    src = LIVE.read_text(encoding="utf-8")
    assert "fetch_hotspots" in src, "the live FIRMS branch may not be removed"
    assert "--replay" in src, "the replay branch may not be removed"


def test_the_manual_script_exists_and_takes_a_coordinate():
    src = SCRIPT.read_text(encoding="utf-8")
    assert '"--lat"' in src and '"--lon"' in src


def test_address_lookup_is_explicitly_out_of_scope():
    """Stated, so nobody adds a geocoder later and quietly widens the claim."""
    src = SCRIPT.read_text(encoding="utf-8")
    assert "out of scope" in src
    for banned in ("geocode(", "nominatim", "kakao", "naver", "vworld"):
        assert banned.lower() not in src.lower(), banned


# ---------------------------------------------------------------------------
# 2. The downstream is the SAME code
# ---------------------------------------------------------------------------


def test_the_manual_script_reuses_run_trigger_rather_than_reimplementing():
    """This is what makes 'identical to the FIRMS route' structural."""
    src = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = {a.name for n in ast.walk(tree)
                if isinstance(n, ast.ImportFrom) and n.module == "run_live_detection"
                for a in n.names}
    assert "run_trigger" in imported, (
        "the manual path must call the same trigger function the FIRMS path "
        "does; a second implementation could drift")
    assert "run_trigger" in _calls(src)


def test_the_manual_script_does_not_reimplement_routing_or_delivery():
    calls = _calls(SCRIPT.read_text(encoding="utf-8"))
    for own in ("pipeline.route_region", "pipeline.deliver",
                "pipeline.write_viz", "pipeline.build_run_record"):
        assert own not in calls, (
            f"{own} is run_trigger's job; calling it here would fork the path")


def test_the_manual_script_never_sends_anything():
    calls = _calls(SCRIPT.read_text(encoding="utf-8"))
    assert not any(c.endswith(".send") or c == "send" for c in calls), calls


# ---------------------------------------------------------------------------
# 3. Source and trigger-time semantics
# ---------------------------------------------------------------------------


def test_the_three_trigger_sources_are_declared():
    assert scope_mod.TRIGGER_SOURCES == ("firms_nrt", "replay", "manual")


def test_a_manual_scope_does_not_claim_a_firms_detection():
    s = Scope(mode="manual", weather_basis="2025-03-25 12:25 UTC",
              hazard_field="x.npz", region="yeongdeok_2025",
              trigger_source="manual", trigger_at="2026-08-03 04:53 UTC")
    line = s.detection_line()
    assert line == "발화점: 수동 입력 · 2026-08-03 04:53 UTC"
    assert "FIRMS" not in line, (
        "a coordinate someone phoned in was not detected by an instrument")
    assert s.is_manual and "수동 입력" in s.mode_banner()


def test_the_default_scope_wording_is_unchanged():
    """Every pre-PHASE-12 caller must keep its exact strings."""
    s = Scope(mode="replay", weather_basis="2025-03-25 12:25 UTC",
              hazard_field="x.npz", region="yeongdeok_2025")
    assert s.trigger_source == "firms_nrt"
    assert s.lines()[0] == "화점 탐지: 실시간 (FIRMS NRT)"


def test_a_manual_scope_records_what_its_trigger_time_means():
    s = Scope(mode="manual", weather_basis="b", hazard_field="x", region="r",
              trigger_source="manual", trigger_at="2026-08-03 04:53 UTC")
    d = s.as_dict()
    assert d["trigger_source"] == "manual"
    assert d["trigger_at"] == "2026-08-03 04:53 UTC"
    assert "NOT a satellite overpass" in d["trigger_at_meaning"]
    assert "no satellite involved" in d["detection"]


def test_a_firms_scope_says_its_trigger_time_is_an_overpass():
    s = Scope(mode="live", weather_basis="b", hazard_field="x", region="r")
    assert "overpass" in s.as_dict()["trigger_at_meaning"]


# ---------------------------------------------------------------------------
# 4. The region gate
# ---------------------------------------------------------------------------


def test_an_out_of_region_coordinate_is_refused_before_any_routing():
    src = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(src)
    main = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    body = ast.unparse(main)
    gate = body.index("EXIT_OUT_OF_REGION")
    route = body.index("run_trigger(")
    assert gate < route, "the bbox check must precede the routing"
    assert "inside_registered_region" in src


# ---------------------------------------------------------------------------
# 5. The recorded run
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not MANUAL_RUNS, reason="no manual run recorded yet")
def test_the_manual_run_records_everything_the_phase_asks_for():
    rec = json.loads(MANUAL_RUNS[-1].read_text(encoding="utf-8"))
    m = rec["manual_trigger"]
    assert rec["trigger_source"] == "manual"
    # input coordinate, input time, processing duration
    assert isinstance(m["input_lat"], float) and isinstance(m["input_lon"], float)
    datetime.strptime(m["entered_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    assert m["input_to_dispatch_list_s"] > 0
    # which hazard field, and ITS weather basis
    assert m["hazard_field"].endswith(".npz")
    assert len(m["hazard_field_sha256"]) == 64
    assert m["hazard_weather_basis"] == rec["scope"]["weather_basis"]
    assert m["inside_registered_region"] is True
    assert "NOT a satellite overpass" in m["entered_utc_meaning"]


@pytest.mark.skipif(not MANUAL_RUNS, reason="no manual run recorded yet")
def test_the_manual_run_used_a_precomputed_surface_and_says_so():
    rec = json.loads(MANUAL_RUNS[-1].read_text(encoding="utf-8"))
    assert rec["scope"]["hazard_field_is_precomputed"] is True
    assert "5일 지연" in rec["scope"]["weather_line_ko"]
    assert any("not re-simulated" in n for n in rec["notes"])


@pytest.mark.skipif(not MANUAL_RUNS, reason="no manual run recorded yet")
def test_the_manual_run_matches_the_firms_run_on_everything_but_provenance():
    """Same routing, same field, same parameters -> same answer. If this ever
    fails, the two paths have diverged and one of them is wrong."""
    replay = sorted((REPO / "outputs" / "live" / "replay" / "yeongdeok_2025")
                    .glob("*/RUN.json"))
    if not replay:
        pytest.skip("no Yeongdeok replay run to compare against")
    M = json.loads(MANUAL_RUNS[-1].read_text(encoding="utf-8"))
    F = json.loads(replay[-1].read_text(encoding="utf-8"))
    if M["region"] != F["region"]:
        pytest.skip("runs are for different regions")

    assert M["counts"] == F["counts"]
    assert M["inputs"]["hazard_npz_sha256"] == F["inputs"]["hazard_npz_sha256"]
    assert M["scope"]["weather_basis"] == F["scope"]["weather_basis"]
    assert M["inputs"]["parameters"]["origin_scan_stride"] == \
        F["inputs"]["parameters"]["origin_scan_stride"]
    assert M["outputs"]["n_villages"] == F["outputs"]["n_villages"]
    assert M["outputs"]["n_points"] == F["outputs"]["n_points"]
    # ...and the provenance is exactly what differs.
    assert M["trigger_source"] == "manual"
    assert F["trigger_source"] in ("replay", "firms_nrt")


@pytest.mark.skipif(not MANUAL_RUNS, reason="no manual run recorded yet")
def test_the_manual_run_produced_all_three_delivery_formats():
    run_dir = MANUAL_RUNS[-1].parent
    man = json.loads((run_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    assert man["all_three_formats_per_village"] is True
    assert man["nothing_was_sent"] is True
    v = run_dir / man["villages"][0]["directory"]
    for f in ("dispatch_a4.html", "broadcast_script.txt", "sms_drafts.json",
              "sms_drafts.txt"):
        assert (v / f).exists(), f


# ---------------------------------------------------------------------------
# 6. The operator screen built from a manual trigger
# ---------------------------------------------------------------------------


MANUAL_SCREEN = REPO / "outputs" / "live" / "screens" / "yeongdeok_2025_manual.html"


def _payload(p: Path) -> dict:
    import re

    m = re.search(r"^const D = (\{.*\});$", p.read_text(encoding="utf-8"), flags=re.M)
    assert m
    return json.loads(m.group(1))


@pytest.mark.skipif(not MANUAL_SCREEN.exists(), reason="manual screen not built")
def test_the_manual_screen_states_the_source_on_its_status_bar():
    d = _payload(MANUAL_SCREEN)
    assert d["trigger_source"] == "manual"
    assert d["scope"]["detection"].startswith("발화점: 수동 입력 · ")
    assert "FIRMS NRT" not in d["scope"]["detection"]


@pytest.mark.skipif(not MANUAL_SCREEN.exists(), reason="manual screen not built")
def test_the_manual_screen_distinguishes_input_time_from_overpass_time():
    src = MANUAL_SCREEN.read_text(encoding="utf-8")
    assert "트리거 시각 = 좌표 입력 시각 (위성 통과 시각 아님)" in src
    assert "NOT a satellite overpass" in _payload(MANUAL_SCREEN)["trigger_at_meaning"]


@pytest.mark.skipif(not MANUAL_SCREEN.exists(), reason="manual screen not built")
def test_the_manual_screen_triggers_at_zero_because_there_is_no_overpass():
    d = _payload(MANUAL_SCREEN)
    assert d["triggers"] == [0.0]
    assert len(d["hotspots"]) == 1, "one reported coordinate, not a batch"
    assert d["preroll"] == 0, "nothing preceded the report to lead in from"


@pytest.mark.skipif(not MANUAL_SCREEN.exists(), reason="manual screen not built")
def test_the_manual_screen_shows_the_committed_counts():
    d = _payload(MANUAL_SCREEN)
    assert sum(d["counts"].values()) == 458
    assert d["counts"]["naive_into_FA_safe"] == 42
    assert d["counts"]["no_safe_route"] == 2


@pytest.mark.skipif(not MANUAL_SCREEN.exists(), reason="manual screen not built")
def test_the_manual_screen_is_still_self_contained():
    src = MANUAL_SCREEN.read_text(encoding="utf-8")
    import re

    urls = set(re.findall(r"https?://[^\s\"'<>)]+", src))
    urls.discard("http://www.w3.org/2000/svg")
    assert urls == set()
    body = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    for api in ("fetch(", "XMLHttpRequest", "localStorage", "setInterval("):
        assert api not in body, api
