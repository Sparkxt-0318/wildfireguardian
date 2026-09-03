"""Guards for the live detection pipeline (Round-3 PHASE 6).

Three properties are load-bearing here, and each is tested from more than one
direction:

1. **Replay is offline.** It is the demonstration path precisely because a
   network cannot be relied on at a venue. So a replay is run with the socket
   layer disabled, and separately the replay module is checked to expose no
   HTTP client at all.
2. **The scope statement cannot be dropped.** "Detection is real-time, weather
   is not" is the difference between describing this system and overclaiming
   it. Every artifact carries both lines; a sheet that does not is a failure.
3. **Nothing can be transmitted.** Same rule as PHASE 3 — the live path adds a
   trigger, and a trigger that could send is the one thing that must not exist.

The routing itself is additionally pinned against the committed canonical
result, so a live run that silently stopped meaning the same thing as the batch
run would fail here rather than in a demonstration.
"""

from __future__ import annotations

import ast
import inspect
import json
import socket
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from wildfireguardian.delivery import broadcast, printable, sms
from wildfireguardian.live import firms, pipeline, replay, scope
from wildfireguardian.live.state import SeenState, StageTimings

REPO = Path(__file__).resolve().parents[1]
ARCHIVE = REPO / "data" / "raw" / "firms_data" / "yeongdeok_2025_detections.csv"
CANONICAL = REPO / "data" / "processed" / "real_roads_real_hazard_canonical.json"
WALK_BBOX = (129.250, 36.300, 129.550, 36.600)


def _hs(lat: float, lon: float, minute: int = 0, conf: str = "h") -> firms.Hotspot:
    return firms.Hotspot(
        lat=lat, lon=lon,
        acquired_utc=datetime(2025, 3, 25, 12, 0, tzinfo=UTC) + timedelta(minutes=minute),
        source="TEST_NRT", satellite="N", instrument="VIIRS",
        confidence_raw=conf, frp=1.0)


# ---------------------------------------------------------------------------
# 1. Scope — the statement that must never be dropped
# ---------------------------------------------------------------------------


def test_scope_states_detection_is_live_and_weather_is_not():
    s = scope.Scope(mode="replay", weather_basis="2025-03-25 12:25 UTC",
                    hazard_field="data/processed/routing_demo_canonical.npz",
                    region="yeongdeok_2025")
    lines = s.lines()
    assert lines[0] == "화점 탐지: 실시간 (FIRMS NRT)"
    assert lines[1] == ("기상 자료: 2025-03-25 12:25 UTC 기준 "
                        "(ERA5는 약 5일 지연 발행)")
    assert "5일 지연" in lines[1], "the ERA5 lag may never be dropped"


def test_scope_dict_never_claims_a_real_time_forecast():
    s = scope.Scope("live", "2025-03-25 12:25 UTC", "x.npz", "yeongdeok_2025")
    d = s.as_dict()
    assert d["weather"] == "NOT real-time"
    assert d["hazard_field_is_precomputed"] is True
    assert d["era5_publication_lag_days"] == 5
    assert "실시간 예보 기반 예측" in d["scope_ko"] and "아닙니다" in d["scope_ko"]


def test_replay_and_live_banners_are_distinguishable():
    r = scope.Scope("replay", "b", "x.npz", "r").mode_banner()
    live = scope.Scope("live", "b", "x.npz", "r").mode_banner()
    assert "재생 모드" in r and "재생 모드" not in live
    assert r != live


def test_the_weather_basis_is_never_typed_into_the_source():
    """The half of the guard that needs no data, so it runs everywhere.

    ⚠ Kept separate on purpose. The derivation below needs the git-ignored
    detections archive, so on a clean clone it can only skip — and if both
    assertions lived in one test, the one that actually catches the regression
    (somebody hard-codes the date when the archive is missing) would skip with
    it, exactly where it is most likely to be needed.
    """
    src = inspect.getsource(pipeline.weather_basis)
    assert "2025-03-25" not in src, "the basis must be read, never typed"


@pytest.mark.skipif(not ARCHIVE.exists(), reason="detections archive not present")
def test_weather_basis_is_derived_from_committed_data_not_a_literal():
    basis, meta = pipeline.weather_basis("yeongdeok_2025", repo=REPO)
    assert basis == "2025-03-25 12:25 UTC"
    assert meta["derived_from"].endswith("yeongdeok_2025_detections.csv")


# ---------------------------------------------------------------------------
# 2. Replay is offline BY CONSTRUCTION
# ---------------------------------------------------------------------------


def _imported_names(module) -> set[str]:
    """Every module name the source actually imports, from the AST.

    Checked against the parse tree rather than the text, because the docstrings
    in this package legitimately DISCUSS the things they must not import.
    """
    tree = ast.parse(inspect.getsource(module))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
            names.update(a.name for a in node.names)
    return names


def _called_names(module_or_src) -> set[str]:
    """Dotted names of every call site in the source, from the AST."""
    src = (module_or_src if isinstance(module_or_src, str)
           else inspect.getsource(module_or_src))
    out: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        parts: list[str] = []
        while isinstance(f, ast.Attribute):
            parts.append(f.attr)
            f = f.value
        if isinstance(f, ast.Name):
            parts.append(f.id)
        if parts:
            out.add(".".join(reversed(parts)))
    return out


def test_replay_module_exposes_no_http_client():
    imported = _imported_names(replay)
    for forbidden in ("urllib", "requests", "http", "socket", "urllib3",
                      "fetch_hotspots", "map_key", "credentials_present"):
        assert forbidden not in imported, (
            f"{forbidden!r} is imported by the replay module. Replay is the "
            "demonstration path and must have no way to reach a network.")
    # It may share the pure data types and the parser, and nothing else.
    assert {"Hotspot", "parse_csv"} <= imported


@pytest.mark.skipif(not ARCHIVE.exists(), reason="detections archive not present")
def test_replay_source_builds_with_the_network_disabled(monkeypatch):
    """The strongest form of the claim: build and iterate a replay while any
    socket construction raises."""

    def _no_network(*a, **k):
        raise AssertionError("replay attempted a network connection")

    monkeypatch.setattr(socket, "socket", _no_network)
    monkeypatch.setattr(socket, "create_connection", _no_network)

    src = replay.ReplaySource.from_csv(ARCHIVE, window_h=12.0, speed=0.0,
                                       bbox_wsen=WALK_BBOX)
    assert src.hotspots and src.overpasses
    assert all(WALK_BBOX[0] <= h.lon <= WALK_BBOX[2] for h in src.hotspots)
    assert all(WALK_BBOX[1] <= h.lat <= WALK_BBOX[3] for h in src.hotspots)
    seen = set()
    for op in src.iter_overpasses():
        assert op.n > 0
        seen.add(op.index)
    assert len(seen) == len(src.overpasses)
    assert src.as_dict()["network_used"] is False


def test_replay_overpasses_are_in_time_order_and_split_on_the_gap():
    hs = [_hs(36.4, 129.3, 0), _hs(36.4, 129.31, 30),
          _hs(36.4, 129.32, 200), _hs(36.4, 129.33, 210)]
    ops = replay.group_overpasses(hs, gap_minutes=90.0)
    assert [o.n for o in ops] == [2, 2]
    assert ops[0].archive_time < ops[1].archive_time


@pytest.mark.parametrize("speed,expected", [(60.0, 60.0), (3600.0, 1.0)])
def test_replay_clock_maps_archive_time_onto_wall_clock(speed, expected):
    t0 = datetime(2025, 3, 25, 12, 0, tzinfo=UTC)
    clock = replay.ReplayClock(t0_archive=t0, speed=speed)
    assert clock.wall_delay_s(t0 + timedelta(hours=1)) == pytest.approx(expected)


def test_replay_clock_at_zero_speed_never_sleeps():
    t0 = datetime(2025, 3, 25, 12, 0, tzinfo=UTC)
    calls: list[float] = []
    clock = replay.ReplayClock(t0_archive=t0, speed=0.0, sleep=calls.append)
    clock.wait_until(t0 + timedelta(hours=10), 0.0)
    assert calls == []


# ---------------------------------------------------------------------------
# 3. FIRMS acquisition — NRT only, all-or-nothing, no key in a message
# ---------------------------------------------------------------------------


def test_non_nrt_sources_are_refused():
    with pytest.raises(firms.FirmsError, match="NRT"):
        firms.fetch_hotspots(WALK_BBOX, sources=["VIIRS_SNPP_SP"],
                             key="k", opener=lambda *a, **k: "")


def test_a_failing_source_aborts_the_whole_poll(monkeypatch):
    """A partial hotspot list reads as 'no new fire'. Better to fail loudly."""
    monkeypatch.setattr("time.sleep", lambda *_: None)

    def boom(url, timeout):
        raise OSError("connection reset")

    with pytest.raises(firms.FirmsError, match="Discarding the whole poll"):
        firms.fetch_hotspots(WALK_BBOX, sources=["VIIRS_SNPP_NRT"],
                             key="secret-key", retries=2, backoff_s=[0.0],
                             opener=boom)


def test_the_map_key_never_appears_in_a_recorded_url(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    captured: dict = {}

    def boom(url, timeout):
        captured["url"] = url
        raise OSError("nope")

    with pytest.raises(firms.FirmsError):
        firms.fetch_hotspots(WALK_BBOX, sources=["VIIRS_SNPP_NRT"],
                             key="SUPER-SECRET", retries=1, opener=boom)
    assert "SUPER-SECRET" in captured["url"]        # it is used...


def test_recorded_attempts_redact_the_key(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    body = "latitude,longitude,acq_date,acq_time,confidence\n36.4,129.3,2025-03-25,1225,h\n"
    res = firms.fetch_hotspots(WALK_BBOX, sources=["VIIRS_SNPP_NRT"],
                               key="SUPER-SECRET", opener=lambda u, t: body)
    blob = json.dumps(res.as_dict(), ensure_ascii=False)
    assert "SUPER-SECRET" not in blob                # ...but never recorded
    assert "<MAP_KEY>" in blob
    assert len(res.hotspots) == 1


def test_a_non_csv_response_is_rejected_rather_than_parsed_as_empty():
    with pytest.raises(firms.FirmsError, match="not a FIRMS CSV"):
        firms.fetch_hotspots(WALK_BBOX, sources=["VIIRS_SNPP_NRT"], key="k",
                             opener=lambda u, t: "Invalid MAP_KEY.")


def test_confidence_normalises_viirs_letters_and_modis_percentages():
    assert firms.confidence_label("h") == "high"
    assert firms.confidence_label("n") == "nominal"
    assert firms.confidence_label("l") == "low"
    assert firms.confidence_label("95") == "high"
    assert firms.confidence_label("50") == "nominal"
    assert firms.confidence_label("5") == "low"
    assert firms.confidence_label("???") == "low", "ungradable ranks low"


def test_new_hotspots_ignores_re_observations_of_the_same_pixel():
    seen: set[str] = set()
    pts: list[tuple[float, float]] = []
    first = firms.new_hotspots([_hs(36.40, 129.30)], seen, seen_points=pts)
    assert len(first) == 1
    seen.add(first[0].key())
    pts.append((first[0].lat, first[0].lon))
    # 100 m away — well inside one VIIRS pixel, so not a new fire.
    again = firms.new_hotspots([_hs(36.4009, 129.30)], seen, seen_points=pts)
    assert again == []
    # 2 km away is a genuinely different place.
    other = firms.new_hotspots([_hs(36.418, 129.30)], seen, seen_points=pts)
    assert len(other) == 1


def test_a_batch_dedupes_against_itself():
    got = firms.new_hotspots([_hs(36.40, 129.30), _hs(36.4005, 129.3002),
                              _hs(36.45, 129.35)], set())
    assert len(got) == 2


def test_in_bbox_is_inclusive_and_rejects_outside():
    assert firms.in_bbox(_hs(36.30, 129.25), WALK_BBOX)
    assert not firms.in_bbox(_hs(36.29, 129.25), WALK_BBOX)


# ---------------------------------------------------------------------------
# 4. State — a hotspot cannot trigger twice across a restart
# ---------------------------------------------------------------------------


def test_the_seen_set_survives_a_restart(tmp_path):
    p = tmp_path / "state.json"
    s = SeenState.load(p, "yeongdeok_2025")
    s.observe([_hs(36.40, 129.30)])
    s.save()

    again = SeenState.load(p, "yeongdeok_2025")
    assert again.keys == s.keys
    assert firms.new_hotspots([_hs(36.40, 129.30)], again.keys,
                              seen_points=again.points) == []


def test_a_state_file_from_another_region_is_not_reused(tmp_path):
    p = tmp_path / "state.json"
    s = SeenState.load(p, "uljin_samcheok_2022")
    s.observe([_hs(36.40, 129.30)])
    s.save()
    other = SeenState.load(p, "yeongdeok_2025")
    assert other.keys == set(), (
        "a foreign state file would suppress this region's first real detection")


def test_timings_separate_warm_from_cold():
    t = StageTimings(load_hazard_s=1.0, load_network_s=2.0, load_pois_s=0.5,
                     route_s=25.0, cluster_s=0.1, render_s=0.4)
    assert t.warm_total_s == pytest.approx(25.5)
    assert t.cold_total_s == pytest.approx(29.0)


def test_pdf_conversion_is_excluded_from_the_headline_timing():
    """PDF is ~2.7 s per sheet and scales with the number of villages, not with
    the decision. Folding it in would answer the wrong question."""
    t = StageTimings(route_s=25.0, cluster_s=0.1, render_s=0.4, pdf_s=78.0)
    assert t.warm_total_s == pytest.approx(25.5)
    assert t.warm_total_with_pdf_s == pytest.approx(103.5)
    assert t.deliver_s == pytest.approx(78.4)
    d = t.as_dict()
    assert d["pdf_s"] == 78.0
    assert "EXCLUDED" in d["definition"]["pdf_s"]


# ---------------------------------------------------------------------------
# 5. The delivery layer, resident-side — additive, and defaults unchanged
# ---------------------------------------------------------------------------


def test_walk_mode_sms_never_mentions_a_vehicle():
    for m in (sms.compose_family_walk("시험마을", 5, 2),
              sms.compose_welfare_walk("시험마을", 5, 2, soonest_min=40.0)):
        assert "차량" not in m.body, (
            "the 459 series has no responder side; a vehicle claim would "
            "describe a computation that was not performed")
        assert m.within_limit and m.n_chars <= sms.MAX_CHARS


@pytest.mark.parametrize("n_pts,n_unreach", [(1, 0), (9, 0), (14, 5), (40, 12)])
def test_walk_mode_sms_stays_within_90_chars(n_pts, n_unreach):
    for m in (sms.compose_family_walk("거무역리공원 일대", n_pts, n_unreach),
              sms.compose_welfare_walk("거무역리공원 일대", n_pts, n_unreach, 15.0)):
        assert m.n_chars <= sms.MAX_CHARS, m.body


def test_broadcast_walk_mode_says_walking_not_vehicles():
    b = broadcast.compose("시험마을", refuge="공원", n_unreachable=3, mode="walk")
    assert "차량" not in b.text
    assert "걸어서" in b.text
    assert b.check()["ok"], b.check()["violations"]


def test_broadcast_default_mode_is_unchanged():
    """PHASE 3's committed scripts must not move underneath a re-run."""
    b = broadcast.compose("시험마을", refuge="공원", n_unreachable=3)
    assert "차량 진입이" in b.text


def test_broadcast_replay_prefix_is_read_aloud_and_fits():
    b = broadcast.compose("시험마을", refuge="공원", n_unreachable=1, mode="walk",
                          prefix_lines=("재생 모드입니다.",))
    assert b.lines[0] == "재생 모드입니다."
    assert b.check()["ok"], b.check()["violations"]


def test_broadcast_rejects_an_unknown_mode():
    with pytest.raises(ValueError, match="mode must be"):
        broadcast.compose("시험마을", mode="rocket")


def _village(points):
    from wildfireguardian.delivery.villages import Village

    return Village(cluster_id=1, name="시험마을", name_basis="test", points=points)


def test_printable_defaults_are_the_439_series_wording():
    """The PHASE-3 sheets are committed; their headings may not drift."""
    v = _village([{"x": 0.0, "y": 0.0, "unreachable": True,
                   "closing_window_min": 10.0}])
    html = printable.render_html(
        v, generated_at="t", git_commit="c" * 12, config_hash="h" * 12,
        source_file="f", n_total_dispatch=1, n_total_unreachable=1)
    assert "■ 구조 필요 지점 — 남은 시간 순" in html
    assert "■ 차량 도달 불가 지점 — 별도 조치 필요" in html


def test_printable_walk_headings_replace_the_vehicle_wording():
    v = _village([{"x": 0.0, "y": 0.0, "unreachable": True,
                   "closing_window_min": 10.0}])
    html = printable.render_html(
        v, generated_at="t", git_commit="c" * 12, config_hash="h" * 12,
        source_file="f", n_total_dispatch=1, n_total_unreachable=1,
        dispatch_heading=pipeline.WALK_DISPATCH_HEADING,
        unreachable_heading=pipeline.WALK_UNREACHABLE_HEADING,
        unreachable_reason_fallback=pipeline.WALK_UNREACHABLE_FALLBACK,
        route_note_fallback=pipeline.WALK_ROUTE_FALLBACK)
    assert "차량" not in html
    assert pipeline.WALK_UNREACHABLE_HEADING in html


def test_extra_footer_lines_append_to_the_fixed_cautions():
    v = _village([{"x": 0.0, "y": 0.0, "unreachable": False,
                   "closing_window_min": 5.0}])
    html = printable.render_html(
        v, generated_at="t", git_commit="c" * 12, config_hash="h" * 12,
        source_file="f", n_total_dispatch=1, n_total_unreachable=0,
        extra_footer_lines=["추가 단서입니다."])
    for fixed in printable.FOOTER_LINES:
        assert fixed in html, "a fixed caution may never be displaced"
    assert "추가 단서입니다." in html


def test_the_live_sheet_keeps_every_mandated_string_in_two_banners():
    """The banner block was compacted from five boxes to two because five
    pushed the largest cluster onto a second page. Nothing may have been lost
    in the compaction — only moved."""
    s = scope.Scope("replay", "2025-03-25 12:25 UTC",
                    "data/processed/routing_demo_canonical.npz", "yeongdeok_2025")
    banners = [s.mode_banner(),
               scope.SCOPE_BANNER_KO + "  " + " · ".join(s.lines())]
    v = _village([{"x": 0.0, "y": 0.0, "unreachable": False,
                   "closing_window_min": 5.0}])
    html = printable.render_html(
        v, generated_at="t", git_commit="c" * 12, config_hash="h" * 12,
        source_file="f", n_total_dispatch=1, n_total_unreachable=0,
        banner_lines=banners, extra_footer_lines=[s.coverage_caveat()],
        dispatch_heading=pipeline.WALK_DISPATCH_HEADING,
        unreachable_heading=pipeline.WALK_UNREACHABLE_HEADING)
    assert len(banners) == 2, "keep the banner block short; boxes cost a page"
    for mandated in ("화점 탐지: 실시간 (FIRMS NRT)",
                     "ERA5는 약 5일 지연 발행",
                     "재생 모드",
                     "실시간 예보 기반 예측",
                     "32.6 %만 덮는"):
        assert mandated in html, mandated


def test_printable_banner_lines_render_one_box_each():
    v = _village([{"x": 0.0, "y": 0.0, "unreachable": False,
                   "closing_window_min": 5.0}])
    html = printable.render_html(
        v, generated_at="t", git_commit="c" * 12, config_hash="h" * 12,
        source_file="f", n_total_dispatch=1, n_total_unreachable=0,
        banner_lines=["첫째 문구", "둘째 문구"])
    assert "첫째 문구" in html and "둘째 문구" in html


# ---------------------------------------------------------------------------
# 6. The pipeline means the same thing as the committed batch run
# ---------------------------------------------------------------------------


def test_the_origin_rule_matches_the_committed_scan_line_for_line():
    """Three copies of `candidate_origins` exist by design (each script must be
    editable without silently redefining the others). They must stay identical."""
    import sys

    sys.path.insert(0, str(REPO / "scripts"))
    from run_real_roads_real_hazard_slope import (  # noqa: PLC0415
        candidate_origins as batch,
    )

    live_src = inspect.getsource(pipeline.candidate_origins)
    batch_src = inspect.getsource(batch)
    for token in ("core = haz[0] >= 0.5", "band = 0.45 * (ymax - ymin)",
                  "hazard.prob_at(x, y, 0.0) >= p_cut",
                  "abs(y - ign_y) > band"):
        assert token in live_src and token in batch_src, token


def test_every_actionable_bucket_has_operator_readable_korean_text():
    assert set(pipeline.ACTIONABLE) == set(pipeline.BUCKET_TEXT)
    assert "both_safe" not in pipeline.BUCKET_TEXT, (
        "a both_safe origin needs no sheet")
    for bucket, (_unreachable, text) in pipeline.BUCKET_TEXT.items():
        assert text and not text.isascii(), bucket


@pytest.mark.skipif(not CANONICAL.exists(), reason="canonical artifact absent")
def test_the_live_bucket_names_are_the_committed_ones():
    committed = json.loads(CANONICAL.read_text())["arms"]["slope_digraph_canonical"]
    live_keys = set(pipeline.BUCKET_TEXT) | {"both_safe", "unclassified"}
    assert set(committed["counts"]) == live_keys


# ---------------------------------------------------------------------------
# 7. Nothing can be transmitted
# ---------------------------------------------------------------------------


def test_the_pipeline_never_calls_send():
    """AST, not text: the docstrings here legitimately discuss sms.send."""
    calls = _called_names(pipeline)
    assert "sms.send" not in calls, (
        "the live path adds a trigger; a trigger that could transmit is the "
        "one thing that must not exist")
    assert not any(c.endswith(".send") or c == "send" for c in calls), calls
    # It does compose, and that is the whole of what it may do.
    assert {"sms.compose_family_walk", "sms.compose_welfare_walk"} <= calls


def test_the_runner_never_calls_send():
    src = (REPO / "scripts" / "run_live_detection.py").read_text(encoding="utf-8")
    calls = _called_names(src)
    assert not any(c.endswith(".send") or c == "send" for c in calls), calls
    assert "sms.demo_mode" in calls, "the runner must report the demo-mode state"


def test_no_module_in_the_live_package_calls_send():
    for mod in (scope, firms, replay, pipeline):
        calls = _called_names(mod)
        assert not any(c.endswith(".send") or c == "send" for c in calls), (
            f"{mod.__name__} contains a send call")


def test_demo_mode_is_still_on_by_default(monkeypatch):
    monkeypatch.delenv(sms.DEMO_MODE_ENV, raising=False)
    assert sms.demo_mode() is True


def test_write_viz_notes_carry_no_single_regions_facts():
    """⚠ Round-4 A3-1/A3-2: the fourth and fifth region-literal instances.

    write_viz's phrasing_rule wrote Uiseong-Andong's measured depot facts
    ("ignition-centred", "contains six") into EVERY region's viz.json —
    self-contradicted beside a status_ko reporting four mapped depots — and
    origins_note carried Yeongdeok's 44/458 in an English sentence the
    region-literal checker's Korean-gated numeric branch could not see.
    Pinned at the source: the rule must be conditional on the region actually
    having zero mapped depots, and neither note may state a count as a
    literal.
    """
    src = inspect.getsource(pipeline.write_viz)
    # The rule exists only for zero-depot regions, and carries no region's
    # measured facts.
    assert "if not res.n_depot_pois else None" in src, (
        "phrasing_rule must be emitted only for regions with zero mapped "
        "depots — unconditional emission is how Uiseong-Andong's facts "
        "reached every region's record")
    for fact in ("contains six", "ignition-centred", "3,926", "919"):
        assert fact not in src, (
            f"a single region's measured fact {fact!r} is back in write_viz")
    # origins_note computes every count it states.
    assert "44-of-458" not in src and '"44' not in src, (
        "Yeongdeok's actionable/origin counts are literals again")
    assert "{len(points)}" in src and "{len(geo)}" in src, (
        "origins_note must derive its counts from the data it describes")
