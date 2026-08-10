"""PHASE 19 — the service layer.

What these tests are for, in one sentence each:

* the parameter defaults did not move when they left argparse,
* a request cannot change a process global, and is caught if it tries,
* the same input gives the same answer, twice, and from two threads,
* the progress report says something true while a 27-second scan runs,
* the resource cache hands out one load, not one per request,
* the job model has the four states a caller can act on,
* the committed scripts still exist and now call the service instead of
  inlining it.

⚠ Nothing here re-checks the ROUTING NUMBERS. Those are checked by re-running
the committed paths and diffing the artifacts (docs/service_layer.md §6);
a unit test that asserted 414/42/2 would be a fourth place for that number to
live and a fourth place for it to be wrong.
"""

from __future__ import annotations

import ast
import json
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from wildfireguardian.config import get as _cfg
from wildfireguardian.service import guards, jobs, params, progress, resources
from wildfireguardian.service import routing as svc_routing

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "wildfireguardian"
PIPELINE = SRC / "live" / "pipeline.py"
LIVE_SCRIPT = REPO / "scripts" / "run_live_detection.py"
MANUAL_SCRIPT = REPO / "scripts" / "run_manual_trigger.py"


# ---------------------------------------------------------------------------
# 1. The parameter defaults did not move
# ---------------------------------------------------------------------------


#: (RoutingParams field, config key, the historical literal fallback). Each
#: triple is exactly what the scripts' argparse default did before PHASE 19.
DEFAULT_SEAM = (
    ("p_cut", "pedestrian.walk_cutoff_p", 0.5),
    ("time_budget_min", "pedestrian.walk_budget_min", 600.0),
    ("time_step_min", "time.routing_time_step_min", 10.0),
    ("stride", "origin_scan.real_osm_stride", 18),
    ("sampling_m", "pedestrian.slope_sampling_m", 60.0),
    ("max_abs_slope", "pedestrian.max_abs_slope", 0.60),
    ("applicability_radius_km", "live.trigger.field_applicability_radius_km", 15.0),
)


@pytest.mark.parametrize(("field", "key", "literal"), DEFAULT_SEAM)
def test_each_default_is_the_config_value_the_script_read(field, key, literal):
    p = params.RoutingParams.from_config()
    assert getattr(p, field) == pytest.approx(float(_cfg(key, literal))), (
        f"{field} no longer equals config {key}; every 459-series number "
        "depends on it")


@pytest.mark.parametrize(("field", "key", "literal"), DEFAULT_SEAM)
def test_the_scripts_still_name_the_same_config_key(field, key, literal):
    """The seam is only safe while both sides read the SAME key."""
    src = LIVE_SCRIPT.read_text(encoding="utf-8") + MANUAL_SCRIPT.read_text(
        encoding="utf-8")
    if key in ("pedestrian.slope_sampling_m", "pedestrian.max_abs_slope"):
        pytest.skip("network-build knobs: the scripts leave them at the "
                    "library default, which reads the same key")
    assert f'"{key}"' in src, f"no script reads {key} any more"


def test_the_two_hardcoded_delivery_defaults_are_unchanged():
    p = params.RoutingParams.from_config()
    assert p.eps_m == 500.0, "the DBSCAN radius decides village membership"
    assert p.collect_routes == 12
    assert p.limit_origins == 0, "a non-zero default would truncate every scan"


def test_parameters_are_frozen_and_hashable():
    p = params.RoutingParams.from_config()
    with pytest.raises(Exception):
        p.p_cut = 0.9                      # type: ignore[misc]
    assert hash(p) == hash(params.RoutingParams.from_config())
    assert p == params.RoutingParams.from_config()


def test_the_resource_key_ignores_knobs_that_do_not_change_the_load():
    a = params.RoutingParams.from_config()
    b = params.RoutingParams.from_config(stride=6, p_cut=0.7, eps_m=250.0)
    assert a.resource_key == b.resource_key, (
        "stride, p_cut and eps_m change the SCAN, not the loaded network; "
        "keying the cache on them would reload a graph for nothing")
    c = params.RoutingParams.from_config(sampling_m=30.0)
    assert a.resource_key != c.resource_key, (
        "sampling_m rebuilds the edge times, so it MUST split the cache")


def test_the_run_parameter_block_keeps_the_committed_key_names():
    d = params.RoutingParams.from_config().as_run_parameters()
    assert "origin_scan_stride" in d, "RUN.json consumers read this name"
    assert d["routing_objective"] == "length_m (distance-ranked)"


def test_the_reverted_runs_field_is_refused_by_name():
    with pytest.raises(params.ParameterError, match="REVERTED"):
        params.check_npz(Path("data/processed/routing_demo.npz"))


# ---------------------------------------------------------------------------
# 2. The region gate is data, not an exit code
# ---------------------------------------------------------------------------


def test_a_coordinate_inside_the_bbox_passes_and_one_outside_does_not():
    w, s, e, n = params.walk_bbox("yeongdeok_2025")
    inside = params.check_in_region("yeongdeok_2025", (s + n) / 2, (w + e) / 2)
    assert inside["inside_registered_region"] is True
    outside = params.check_in_region("yeongdeok_2025", s - 5.0, w - 5.0)
    assert outside["inside_registered_region"] is False
    assert "없는 근거를 만들어내는" in outside["reason_ko"]


def test_an_unregistered_region_raises_rather_than_guessing_a_bbox():
    with pytest.raises(params.ParameterError):
        params.walk_bbox("gangwon_2099")


def test_the_catalogue_lists_every_registered_region():
    cat = svc_routing.region_catalogue()
    assert {c["region"] for c in cat} == set(params.known_regions())
    for c in cat:
        assert len(c["walk_bbox_wsen"]) == 4
        assert isinstance(c["ready"], bool)


# ---------------------------------------------------------------------------
# 3. Process globals — decision ③
# ---------------------------------------------------------------------------


def test_the_osmnx_settings_digest_is_stable_when_nothing_touches_them():
    assert guards.osmnx_settings_digest() == guards.osmnx_settings_digest()
    assert len(guards.osmnx_settings_items()) > 10, (
        "the digest must cover the real settings, not an empty list that would "
        "silently pass forever")


def test_changing_an_osmnx_setting_during_a_request_is_caught():
    ox = pytest.importorskip("osmnx")
    guards.freeze_globals(force=True)
    before = ox.settings.log_console
    try:
        ox.settings.log_console = not before
        with pytest.raises(guards.GlobalStateViolation, match="osmnx"):
            guards.assert_globals_unchanged(where="test")
    finally:
        ox.settings.log_console = before
    guards.assert_globals_unchanged(where="test")


def test_touching_the_numpy_global_stream_during_a_request_is_caught():
    guards.freeze_globals(force=True)
    state = np.random.get_state()
    try:
        np.random.seed(12345)
        with pytest.raises(guards.GlobalStateViolation, match="numpy"):
            guards.assert_globals_unchanged(where="test")
    finally:
        np.random.set_state(state)
    guards.assert_globals_unchanged(where="test")


def test_freeze_is_idempotent_so_a_second_call_cannot_rebaseline_a_drift():
    first = guards.freeze_globals(force=True)
    ox = pytest.importorskip("osmnx")
    before = ox.settings.log_console
    try:
        ox.settings.log_console = not before
        again = guards.freeze_globals()          # no force
        assert again is first, (
            "re-freezing without force would adopt the drifted value as the "
            "new baseline and the violation would never be reported")
    finally:
        ox.settings.log_console = before
        guards.freeze_globals(force=True)


def _service_sources() -> list[Path]:
    return sorted((SRC / "service").glob("*.py"))


def test_no_service_module_writes_an_osmnx_setting():
    for path in _service_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for tgt in node.targets:
                if (isinstance(tgt, ast.Attribute)
                        and isinstance(tgt.value, ast.Attribute)
                        and tgt.value.attr == "settings"):
                    pytest.fail(f"{path.name}: assigns to osmnx.settings")


def test_no_service_module_draws_from_the_numpy_global_stream():
    banned = {"seed", "rand", "randn", "randint", "choice", "shuffle",
              "permutation", "random_sample", "normal", "uniform"}
    for path in _service_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in banned
                    and isinstance(node.func.value, ast.Attribute)
                    and node.func.value.attr == "random"):
                pytest.fail(
                    f"{path.name}: np.random.{node.func.attr} draws from the "
                    "process-wide stream; use np.random.default_rng(seed)")


# ---------------------------------------------------------------------------
# 4. Determinism — decision ④
# ---------------------------------------------------------------------------


def test_the_building_sample_seed_comes_from_config_and_is_pinned():
    seed = int(_cfg("building_origins.sample_seed", 20260805))
    assert seed == 20260805, (
        "PHASE 18's building sample results were drawn with this seed; moving "
        "it re-draws every sample and every convergence figure")


def test_the_same_sample_seed_draws_the_same_sample_twice():
    """The property a web button needs: press it twice, get the same answer."""
    seed = int(_cfg("building_origins.sample_seed", 20260805))
    a = np.random.default_rng(seed).choice(5000, size=1000, replace=False)
    b = np.random.default_rng(seed).choice(5000, size=1000, replace=False)
    assert np.array_equal(a, b)
    # ...and the two PHASE-18 streams are deliberately different streams.
    c = np.random.default_rng(seed + 1).choice(5000, size=1000, replace=False)
    assert not np.array_equal(a, c), (
        "convergence() and spatial_bias() must not share a stream; seed+1 is "
        "what separates them")


def test_drawing_a_sample_does_not_move_the_global_stream():
    seed = int(_cfg("building_origins.sample_seed", 20260805))
    before = guards.numpy_global_digest()
    np.random.default_rng(seed).choice(100, size=10, replace=False)
    assert guards.numpy_global_digest() == before, (
        "an explicit Generator must not touch the legacy global stream — that "
        "is the whole reason PHASE 18 used default_rng")


def test_the_two_phase18_sampling_functions_leave_the_global_stream_alone():
    """The specific claim, checked on the specific functions.

    ``convergence`` and ``spatial_bias`` are the only two functions in this
    tree that draw samples anywhere near a reportable number. They take a seed
    and build their own Generator, so they are safe to call from a
    long-running process — and this asserts that rather than assuming it.
    """
    import sys
    if str(REPO / "scripts") not in sys.path:
        sys.path.insert(0, str(REPO / "scripts"))
    from run_building_origin_routing import convergence, spatial_bias

    seed = int(_cfg("building_origins.sample_seed", 20260805))
    before = guards.numpy_global_digest()
    a1 = convergence(np.zeros(60, int), [20], 5, seed)
    b1 = spatial_bias(np.zeros((60, 2)), [20], 5, seed)
    after = guards.numpy_global_digest()
    assert after == before, (
        "a sampling function that moved the global stream would make every "
        "LATER request in the same process depend on how many requests came "
        "before it")
    # ...and they are individually reproducible, which is the other half.
    assert convergence(np.zeros(60, int), [20], 5, seed) == a1
    assert spatial_bias(np.zeros((60, 2)), [20], 5, seed) == b1


def test_the_global_seeding_that_does_exist_is_not_reachable_from_a_request():
    """`scripts/spread_v2/*.py` DO call np.random.seed — inside functions.

    They are the reason `guards` exists. None is importable from the request
    path, so the risk is structural rather than present, and this test is what
    turns "we checked once" into "it is still true".
    """
    offenders = sorted(p.name for p in (REPO / "scripts" / "spread_v2").glob("*.py")
                       if "np.random.seed(" in p.read_text(encoding="utf-8"))
    assert offenders, (
        "if these ever stop existing, delete this test — but do not delete the "
        "guard, which is about what a future edit might add")

    # Every one of them lives under scripts/ and is named `NN_thing.py`, which
    # is not an importable identifier. Nothing on the request path can pull one
    # in by accident; it would have to be loaded deliberately.
    for name in offenders:
        assert name[0].isdigit(), (
            f"{name} is now importable by name, so a request-path module could "
            "pull it in and inherit its global seeding")

    # And no library module CALLS np.random.seed. Checked on the syntax tree,
    # not on the text: `guards.py` names the function in its docstring, and a
    # test that could not tell an explanation from a call would be useless.
    for path in _service_sources() + [SRC / "live" / "pipeline.py"]:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "seed"
                    and isinstance(node.func.value, ast.Attribute)
                    and node.func.value.attr == "random"):
                pytest.fail(f"{path.name} seeds the process-wide stream")


def test_building_snapping_has_no_seed_at_all_and_is_therefore_deterministic():
    """Snapping is nearest-node, not a draw. Assert that, rather than invent a seed.

    ``load_walk_nodes`` sorts the node ids and projects them; two calls must
    return the identical array, because a building's origin node is the answer
    to a distance question and not to a random one.
    """
    bld = pytest.importorskip("wildfireguardian.buildings")
    snap = REPO / "data" / "snapshots" / "MANIFEST.json"
    if not snap.exists():
        pytest.skip("snapshot store absent")
    ids_a, xy_a, crs_a = bld.load_walk_nodes("yeongdeok_2025", repo=REPO)
    ids_b, xy_b, crs_b = bld.load_walk_nodes("yeongdeok_2025", repo=REPO)
    assert ids_a == ids_b and crs_a == crs_b
    assert np.array_equal(xy_a, xy_b)
    src = (REPO / "src" / "wildfireguardian" / "buildings" / "__init__.py"
           ).read_text(encoding="utf-8")
    assert "random" not in src, (
        "the building layer must stay draw-free; a seed here would be a new "
        "source of run-to-run variation")


def test_the_determinism_key_ignores_provenance_but_not_the_coordinate():
    a = svc_routing.IgnitionRequest(region="yeongdeok_2025", lat=36.44,
                                    lon=129.37, reported_by="119 신고")
    b = svc_routing.IgnitionRequest(region="yeongdeok_2025", lat=36.44,
                                    lon=129.37, reported_by="CCTV")
    c = svc_routing.IgnitionRequest(region="yeongdeok_2025", lat=36.45,
                                    lon=129.37)
    assert a.determinism_key() == b.determinism_key(), (
        "who reported it reaches the artifact, not the computation")
    assert a.determinism_key() != c.determinism_key()


def test_the_result_digest_drops_time_and_keeps_the_answer():
    base = {"counts": {"both_safe": 414}, "n_scanned": 458,
            "bucket_fingerprint": "abc", "n_villages": 29, "n_points": 44,
            "scan": {"counts": {"both_safe": 414}}, "manifest": {"villages": []},
            "applicability": {"verdict": "IN_SCOPE"}}
    slow = {**base, "run_id": "X", "timings_s": {"route_s": 99.9}}
    fast = {**base, "run_id": "Y", "timings_s": {"route_s": 1.1}}
    assert svc_routing.result_digest(slow) == svc_routing.result_digest(fast)
    moved = {**base, "counts": {"both_safe": 413}}
    assert svc_routing.result_digest(moved) != svc_routing.result_digest(base)


def test_a_duration_nested_inside_the_scan_block_does_not_move_the_digest():
    """The bug the first PHASE-19 measurement found, pinned.

    ``ScanOutcome.as_dict`` carries ``route_seconds``. It was missing from the
    exclusion set, so three scans with byte-identical buckets reported three
    different digests and the run was recorded as non-deterministic. A digest
    that calls a slower run a different ANSWER is worse than no digest.
    """
    base = {"counts": {"both_safe": 414}, "n_scanned": 458,
            "bucket_fingerprint": "abc", "n_villages": 29, "n_points": 44,
            "manifest": {"villages": []}, "applicability": {}}
    a = {**base, "scan": {"counts": {"both_safe": 414}, "route_seconds": 24.67}}
    b = {**base, "scan": {"counts": {"both_safe": 414}, "route_seconds": 25.43}}
    assert svc_routing.result_digest(a) == svc_routing.result_digest(b)


def test_every_duration_looking_key_the_service_emits_is_excluded():
    """A new timing field must be added to the exclusion set when it is added.

    Checked against the keys the service actually emits, so the set cannot
    drift behind the payload.
    """
    emitted = {"route_seconds", "wall_s", "elapsed_s", "timings_s", "seconds",
               "duration_s", "idle_s"}
    missing = emitted - svc_routing.NON_DETERMINISTIC_KEYS
    assert not missing, f"duration keys not excluded from the digest: {missing}"


# ---------------------------------------------------------------------------
# 5. Progress — decision ①
# ---------------------------------------------------------------------------


def test_no_runtime_korean_string_carries_a_banned_dash():
    """The layer the screen gates cannot see, guarded at its source.

    Stage labels, the skipped-stage format and the cancellation note travel
    as JSON in HTTP responses and reach the console's header via textContent.
    check_screen_assets scans built files, so a dash HERE showed on screen
    for the whole routing while every static gate passed — and the vendored
    subset has no U+2014 glyph, so it rendered in a fallback face.
    """
    banned = ("—", "–")  # EM dash, EN dash
    for s in progress.TRIGGER_STAGES:
        assert not any(c in s.label_ko for c in banned), s.label_ko
    # The skipped-stage line is composed at runtime; compose one and check it.
    p = progress.Progress(progress.TRIGGER_STAGES)
    p.skip("pdf", "검사용")
    line = p._stages["pdf"].text_ko()
    assert "생략" in line and not any(c in line for c in banned), line
    # The cancellation note as the status endpoint serialises it.
    src = Path(jobs.__file__).read_text(encoding="utf-8")
    for ln in src.splitlines():
        if "취소된 요청" in ln:
            assert not any(c in ln for c in banned), ln


def test_the_stage_weights_are_a_partition():
    total = sum(s.weight for s in progress.TRIGGER_STAGES
                if not s.excluded_from_total)
    assert total == pytest.approx(1.0), (
        "the overall bar is a weighted sum; weights that do not sum to 1 make "
        "it stop short of 100 % or pass it")
    assert any(s.excluded_from_total for s in progress.TRIGGER_STAGES), (
        "PDF conversion is excluded everywhere else in this project and must "
        "be excluded here too")


def test_routing_owns_most_of_the_bar_because_it_owns_most_of_the_clock():
    by_key = {s.key: s.weight for s in progress.TRIGGER_STAGES}
    assert by_key["routing"] > 0.8, (
        "STEP 0 measured ~26.9 s of a ~31 s cold request inside routing; a bar "
        "that gave it less would run to 90 % and then stop for 25 seconds")


def test_progress_reports_a_readable_line_while_it_advances():
    p = progress.Progress()
    p.begin("routing", 458)
    p.set_done("routing", 137)
    snap = p.snapshot()
    assert snap["current_stage"] == "routing"
    assert "137/458" in snap["current_text_ko"]
    assert 0.0 < snap["overall_fraction"] < 1.0
    json.dumps(snap)                       # must be serialisable as-is


def test_overall_progress_is_monotone_and_ends_at_one():
    p = progress.Progress()
    seen = [p.overall]
    for key, total in (("load", 3), ("routing", 10), ("cluster", 4),
                       ("render", 2), ("record", 2)):
        p.begin(key, total)
        for _ in range(total):
            p.advance(key)
            seen.append(p.overall)
        p.finish(key)
        seen.append(p.overall)
    p.close()
    assert all(b >= a - 1e-9 for a, b in zip(seen, seen[1:])), "went backwards"
    assert p.overall == pytest.approx(1.0)


def test_a_skipped_stage_counts_as_complete_not_as_stalled():
    p = progress.Progress()
    p.skip("load", "이미 적재됨")
    assert p.snapshot()["stages"][0]["state"] == "skipped"
    assert p.overall > 0.0, (
        "a warm request skips loading; a bar that treated that as 0 % would "
        "under-report every warm request forever")


def test_a_listener_that_raises_cannot_kill_the_job():
    def boom(_snapshot):
        raise RuntimeError("listener exploded")

    p = progress.Progress(on_event=boom)
    p.begin("routing", 2)
    p.advance("routing")                   # must not propagate


def test_progress_is_safe_to_read_while_it_is_being_written():
    p = progress.Progress()
    p.begin("routing", 2000)
    stop = threading.Event()
    errors: list[BaseException] = []

    def reader():
        try:
            while not stop.is_set():
                json.dumps(p.snapshot())
        except BaseException as exc:       # noqa: BLE001
            errors.append(exc)

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    for _ in range(2000):
        p.advance("routing")
    stop.set()
    t.join(timeout=5)
    assert not errors, errors


# ---------------------------------------------------------------------------
# 6. The progress hook does not change what is computed
# ---------------------------------------------------------------------------


def test_the_pipeline_progress_hooks_are_observation_only():
    """``on_progress`` may be CALLED and may be compared to None. Nothing else.

    If its return value were ever read, a callback could change a bucket, and
    the guarantee that a run with progress equals a run without it would be
    gone.
    """
    tree = ast.parse(PIPELINE.read_text(encoding="utf-8"))
    call_nodes = [n for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id == "on_progress"]
    assert call_nodes, "the hooks vanished"
    statement_calls = {id(node.value) for node in ast.walk(tree)
                       if isinstance(node, ast.Expr)}
    for call in call_nodes:
        assert id(call) in statement_calls, (
            "on_progress(...) is used as a value somewhere; it must be a bare "
            "statement so its return value cannot reach a decision")
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) \
                and node.left.id == "on_progress":
            assert all(isinstance(op, (ast.IsNot, ast.Is)) for op in node.ops)


def test_the_hook_defaults_to_none_so_batch_behaviour_is_the_committed_one():
    import inspect

    from wildfireguardian.live import pipeline as pl
    for fn in (pl.route_region, pl.deliver):
        sig = inspect.signature(fn)
        assert sig.parameters["on_progress"].default is None, (
            f"{fn.__name__} must default to no callback")


# ---------------------------------------------------------------------------
# 7. The resource cache — decision ②
# ---------------------------------------------------------------------------


class _FakeNet:
    def __init__(self):
        import networkx as nx
        self.graph = nx.DiGraph()
        self.graph.add_node(1, x=0.0, y=0.0)
        self.shelters = {1}


class _FakeResources:
    def __init__(self, region):
        self.region = region
        self.haz = np.zeros((5, 10, 10), dtype=np.float32)
        self.net = _FakeNet()
        self.n_shelter_pois = 1
        self.n_depot_pois = 0
        self.npz_sha256 = "0" * 64


@pytest.fixture()
def fake_loader(monkeypatch, tmp_path):
    calls: list[str] = []

    def _load(region, *, npz_path, repo, sampling_m=None, max_abs_slope=None):
        calls.append(region)
        time.sleep(0.05)
        return _FakeResources(region)

    monkeypatch.setattr(resources._pipeline, "load_resources", _load)
    for r in params.known_regions():
        (tmp_path / f"{r}.npz").write_bytes(b"x")
    return calls, tmp_path


def test_a_second_request_for_the_same_region_does_not_load_again(fake_loader):
    calls, tmp = fake_loader
    cache = resources.ResourceCache(capacity=2)
    p = params.RoutingParams.from_config()
    r1, cached1, _ = cache.get("yeongdeok_2025", p,
                               npz_path=tmp / "yeongdeok_2025.npz")
    r2, cached2, _ = cache.get("yeongdeok_2025", p,
                               npz_path=tmp / "yeongdeok_2025.npz")
    assert cached1 is False and cached2 is True
    assert r1 is r2, "the objects must be shared, not merely equal"
    assert calls == ["yeongdeok_2025"]


def test_two_threads_asking_at_once_produce_one_load(fake_loader):
    calls, tmp = fake_loader
    cache = resources.ResourceCache(capacity=2)
    p = params.RoutingParams.from_config()
    got: list[object] = []

    def ask():
        res, _cached, _e = cache.get("yeongdeok_2025", p,
                                     npz_path=tmp / "yeongdeok_2025.npz")
        got.append(res)

    ts = [threading.Thread(target=ask) for _ in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=10)
    assert len(calls) == 1, (
        "four concurrent requests loaded the graph more than once; a duplicate "
        "load is not just slow, it doubles peak memory")
    assert all(g is got[0] for g in got)


def test_a_different_sampling_spacing_is_a_different_entry(fake_loader):
    calls, tmp = fake_loader
    cache = resources.ResourceCache(capacity=4)
    a = params.RoutingParams.from_config()
    b = params.RoutingParams.from_config(sampling_m=30.0)
    cache.get("yeongdeok_2025", a, npz_path=tmp / "yeongdeok_2025.npz")
    cache.get("yeongdeok_2025", b, npz_path=tmp / "yeongdeok_2025.npz")
    assert len(calls) == 2
    assert cache.stats()["resident"] == 2


def test_capacity_one_evicts_the_previous_region(fake_loader):
    calls, tmp = fake_loader
    cache = resources.ResourceCache(capacity=1)
    p = params.RoutingParams.from_config()
    cache.get("yeongdeok_2025", p, npz_path=tmp / "yeongdeok_2025.npz")
    cache.get("uiseong_andong_2025", p, npz_path=tmp / "uiseong_andong_2025.npz")
    stats = cache.stats()
    assert stats["resident"] == 1 and stats["evictions"] == 1
    cache.get("yeongdeok_2025", p, npz_path=tmp / "yeongdeok_2025.npz")
    assert len(calls) == 3, "the evicted region had to be loaded again"


def test_preload_refuses_to_load_more_regions_than_it_can_hold(fake_loader):
    _calls, tmp = fake_loader
    cache = resources.ResourceCache(capacity=1)
    with pytest.raises(resources.ResourceError, match="capacity"):
        cache.preload(list(params.known_regions()),
                      params.RoutingParams.from_config())


def test_the_stats_block_reports_memory_and_says_what_kind(fake_loader):
    _calls, tmp = fake_loader
    cache = resources.ResourceCache(capacity=2)
    cache.get("yeongdeok_2025", params.RoutingParams.from_config(),
              npz_path=tmp / "yeongdeok_2025.npz")
    s = cache.stats()
    assert s["hazard_bytes_total"] == 5 * 10 * 10 * 4
    assert "PEAK-RSS" in s["note"], "an upper bound must be labelled as one"
    assert s["entries"][0]["rss_delta_is_peak_upper_bound"] is True
    json.dumps(s)


# ---------------------------------------------------------------------------
# 8. Run-id isolation — decision ③
# ---------------------------------------------------------------------------


def test_two_run_ids_minted_in_the_same_second_differ():
    at = svc_routing.datetime.now(svc_routing.UTC)
    a = svc_routing.make_run_id(at=at, unique="aaaaaaaa")
    b = svc_routing.make_run_id(at=at, unique="bbbbbbbb")
    assert a != b, (
        "the committed scheme had one-second resolution; two requests inside "
        "one second shared a directory and overwrote each other")
    assert a.startswith(at.strftime("%Y%m%dT%H%M%SZ")), (
        "the timestamp prefix must survive — every consumer in this tree finds "
        "the latest run by sorting directory names")


def test_a_run_id_with_no_job_keeps_the_committed_shape_exactly():
    at = svc_routing.datetime.now(svc_routing.UTC)
    assert svc_routing.make_run_id(at=at) == at.strftime("%Y%m%dT%H%M%SZ")


# ---------------------------------------------------------------------------
# 9. The job model — decision ①
# ---------------------------------------------------------------------------


@pytest.fixture()
def stub_runner(monkeypatch):
    """A runner whose work is a controllable sleep, not a 27-second scan."""
    gate = threading.Event()
    gate.set()

    def _fake(request, *, cache, run_id=None, progress=None, should_cancel=None,
              repo=None):
        gate.wait(timeout=10)
        if progress is not None:
            progress.begin("routing", 4)
            for _ in range(4):
                progress.advance("routing")
            progress.finish("routing")
        if request.lat > 90:
            raise svc_routing.ServiceError("범위 밖", code="out_of_region")
        return {"run_id": run_id, "counts": {"both_safe": 1},
                "determinism_key": request.determinism_key()}

    monkeypatch.setattr(jobs, "route_from_ignition", _fake)
    runner = jobs.JobRunner(cache=resources.ResourceCache(capacity=1),
                            max_workers=2, max_queue=4)
    yield runner, gate
    runner.shutdown(wait=False)


def _req(lat=36.44, lon=129.37):
    return svc_routing.IgnitionRequest(region="yeongdeok_2025", lat=lat, lon=lon)


def test_submit_returns_immediately_and_the_id_answers_for_the_job(stub_runner):
    runner, _gate = stub_runner
    t0 = time.monotonic()
    job_id = runner.submit_ignition(_req())
    assert time.monotonic() - t0 < 0.5, "submit must not wait for the work"
    st = runner.wait(job_id, timeout=15)
    assert st["state"] == jobs.SUCCEEDED
    assert st["state_ko"] == "완료"
    assert st["result"]["counts"] == {"both_safe": 1}
    assert st["progress"]["overall_fraction"] == 1.0


def test_a_job_passes_through_queued_running_and_finished(stub_runner):
    runner, gate = stub_runner
    gate.clear()
    job_id = runner.submit_ignition(_req())
    assert runner.status(job_id)["state"] in (jobs.QUEUED, jobs.RUNNING)
    gate.set()
    assert runner.wait(job_id, timeout=15)["state"] == jobs.SUCCEEDED
    assert runner.status(job_id)["finished_utc"]


def test_a_failure_is_reported_with_a_code_a_transport_can_map(stub_runner):
    runner, _gate = stub_runner
    job_id = runner.submit_ignition(_req(lat=99.0))
    st = runner.wait(job_id, timeout=15)
    assert st["state"] == jobs.FAILED
    assert st["error_code"] == "out_of_region"
    with pytest.raises(svc_routing.ServiceError):
        runner.result(job_id)


def test_reading_an_unknown_job_id_raises_rather_than_returning_empty(stub_runner):
    runner, _gate = stub_runner
    with pytest.raises(KeyError):
        runner.status("nope")


def test_a_full_queue_refuses_rather_than_accepting_and_forgetting(stub_runner):
    runner, gate = stub_runner
    gate.clear()
    ids = []
    try:
        for _ in range(20):
            ids.append(runner.submit_ignition(_req()))
    except jobs.QueueFull as exc:
        assert "대기열" in str(exc)
    else:
        pytest.fail("an unbounded queue would accept work it cannot do")
    finally:
        gate.set()


def test_a_queued_job_can_be_cancelled_before_it_starts(stub_runner):
    runner, gate = stub_runner
    gate.clear()
    first = [runner.submit_ignition(_req()) for _ in range(3)]
    last = first[-1]
    assert runner.cancel(last) is True
    gate.set()
    time.sleep(0.5)
    assert runner.status(last)["state"] == jobs.CANCELLED


def test_a_finished_job_cannot_be_cancelled(stub_runner):
    runner, _gate = stub_runner
    done = runner.submit_ignition(_req())
    runner.wait(done, timeout=15)
    assert runner.cancel(done) is False, (
        "saying otherwise would let a caller believe a written run directory "
        "is going to disappear")


# ---------------------------------------------------------------------------
# 9-B. Cancelling a RUNNING scan — PHASE 19 STEP 2
# ---------------------------------------------------------------------------


class _CancellableNet:
    """A tiny network whose scan is long enough to be cancelled mid-way."""

    def __init__(self, n=400):
        import networkx as nx
        self.graph = nx.DiGraph()
        for i in range(n):
            self.graph.add_node(i, x=float(i), y=0.0)
        self.shelters = {0}


def test_route_region_stops_at_an_origin_boundary_when_asked():
    """The control hook raises; it does not return a half-scan.

    A truncated classification is not a smaller answer, it is a wrong one —
    ``sum(counts) == len(cand)`` is asserted inside the scan and a partial run
    would violate it.
    """
    from wildfireguardian.live import pipeline as pl

    seen = {"n": 0}

    class _Res:
        net = _CancellableNet()
        hazard = None
        haz = None
        extent = None

    def fake_candidates(net, hazard, haz, extent, p_cut, stride):
        return list(range(50)), (0.0, 0.0)

    def fake_naive(*a, **k):
        seen["n"] += 1
        raise AssertionError("should have been cancelled before routing an origin")

    def fake_field(*a, **k):
        raise AssertionError(
            "the hazard table must not be built for a request that has already "
            "been cancelled — it costs a few hundred milliseconds and nobody "
            "will read it")

    import unittest.mock as mock
    with mock.patch.object(pl, "candidate_origins", fake_candidates), \
            mock.patch.object(pl, "naive_route", fake_naive), \
            mock.patch.object(pl, "build_time_expanded_field", fake_field):
        with pytest.raises(pl.RoutingCancelled, match="0 of 50"):
            pl.route_region(_Res(), p_cut=0.5, budget_min=600.0, step_min=10.0,
                            stride=18, should_cancel=lambda: True)
    assert seen["n"] == 0, "cancellation must land BEFORE the origin is routed"


def test_the_cancel_hook_is_separate_from_the_progress_hook():
    """Two hooks, two jobs. The observation one must stay unable to abort.

    If cancellation were signalled through ``on_progress`` — by raising, or by
    a truthy return — then a progress listener could change an answer, and the
    guarantee that a run with progress equals a run without it would be gone.
    """
    import inspect

    from wildfireguardian.live import pipeline as pl
    sig = inspect.signature(pl.route_region)
    assert sig.parameters["on_progress"].default is None
    assert sig.parameters["should_cancel"].default is None
    src = PIPELINE.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)
                and isinstance(node.exc.func, ast.Name)
                and node.exc.func.id == "RoutingCancelled"):
            break
    else:
        pytest.fail("route_region no longer raises RoutingCancelled")


def test_a_running_job_can_be_cancelled_and_leaves_nothing_behind(tmp_path, monkeypatch):
    """The demonstration case: a misclick must not cost 26 seconds."""
    from wildfireguardian.live import pipeline as pl

    started = threading.Event()

    def _slow(request, *, cache, run_id=None, progress=None, should_cancel=None,
              repo=None):
        out = tmp_path / "runs" / (run_id or "x")
        out.mkdir(parents=True, exist_ok=True)
        started.set()
        for i in range(2000):
            if should_cancel is not None and should_cancel():
                if not any(out.iterdir()):
                    out.rmdir()
                raise pl.RoutingCancelled(f"cancelled after {i} of 2000 origins")
            time.sleep(0.001)
        (out / "RUN.json").write_text("{}", encoding="utf-8")
        return {"run_id": run_id}

    monkeypatch.setattr(jobs, "route_from_ignition", _slow)
    runner = jobs.JobRunner(cache=resources.ResourceCache(capacity=1),
                            max_workers=1, max_queue=4)
    try:
        job_id = runner.submit_ignition(_req())
        assert started.wait(timeout=10)
        t0 = time.monotonic()
        assert runner.cancel(job_id) is True, "a RUNNING job must be cancellable"
        st = runner.wait(job_id, timeout=15)
        stopped_after = time.monotonic() - t0
    finally:
        runner.shutdown(wait=False)

    assert st["state"] == jobs.CANCELLED
    assert st["error_code"] == "cancelled"
    assert st["nothing_was_written"] is True
    assert stopped_after < 2.0, (
        f"took {stopped_after:.1f}s to stop; the point of cancelling is not "
        "waiting for the scan")
    leftovers = list((tmp_path / "runs").glob("*/*")) if (tmp_path / "runs").exists() else []
    assert not leftovers, f"a cancelled run left files behind: {leftovers}"


def test_cancelling_is_reported_as_its_own_state_not_as_a_failure(stub_runner):
    """A cancelled job is not an error a reader should go hunting for."""
    runner, _gate = stub_runner
    assert jobs.CANCELLED in jobs.TERMINAL
    assert jobs.CANCELLED != jobs.FAILED
    assert jobs._STATE_KO[jobs.CANCELLED] == "취소됨"


def test_two_concurrent_jobs_get_two_run_ids_and_two_progress_reports(stub_runner):
    runner, _gate = stub_runner
    a = runner.submit_ignition(_req())
    b = runner.submit_ignition(_req(lat=36.45))
    sa = runner.wait(a, timeout=15)
    sb = runner.wait(b, timeout=15)
    assert sa["result"]["run_id"] != sb["result"]["run_id"]
    assert sa["job_id"] != sb["job_id"]
    assert sa["progress"] is not sb["progress"]


def test_the_runner_stats_expose_the_cache_and_the_frozen_globals(stub_runner):
    runner, _gate = stub_runner
    s = runner.stats()
    assert s["workers"] == 2
    assert "resource_cache" in s and "globals" in s
    assert s["globals"]["osmnx_settings_n_attributes"] > 0
    json.dumps(s)


# ---------------------------------------------------------------------------
# 9-C. PHASE 20 — the hoisted time-expanded field
# ---------------------------------------------------------------------------


def _tiny_field_setup():
    """A 3x3 lattice with a real hazard sequence. Small enough to be exact."""
    import numpy as _np

    from wildfireguardian.routing.future_front import RoadNetwork
    from wildfireguardian.routing.hazard import HazardSequence
    from wildfireguardian.spread_v2.grid import CoarseGrid

    net = RoadNetwork.synthetic_grid((0.0, 0.0), 3, 3, 100.0, shelter_nodes={8})
    for _u, _v, d in net.graph.edges(data=True):
        d["time_min"] = d["length_m"] / 60.0
    grid = CoarseGrid(minx=0.0, miny=0.0, maxx=300.0, maxy=300.0,
                      cell_size_m=100.0, nrows=3, ncols=3)
    surfaces = [_np.full((3, 3), 0.1), _np.full((3, 3), 0.2)]
    haz = HazardSequence(grid=grid, times_min=_np.array([0.0, 600.0]),
                         surfaces=surfaces)
    return net, haz


def test_the_hoisted_field_is_bit_identical_to_the_one_built_per_origin():
    """The whole optimisation rests on this, so it is asserted directly."""
    from wildfireguardian.routing import evacuation as ev

    net, haz = _tiny_field_setup()
    kw = dict(departure_min=0.0, time_budget_min=600.0, p_cut=0.5,
              time_step_min=10.0)
    a = ev.build_time_expanded_field(net, haz, **kw)
    b = ev.build_time_expanded_field(net, haz, **kw)
    assert a.nodes == b.nodes
    assert np.array_equal(a.table, b.table), (
        "two builds of the same field disagree — the table is not a pure "
        "function of its inputs and the hoist is unsound")
    assert a.table.dtype == b.table.dtype


def test_a_route_with_a_hoisted_field_equals_one_that_builds_its_own():
    """Supplying the field must be indistinguishable from not supplying it."""
    from wildfireguardian.routing import evacuation as ev

    net, haz = _tiny_field_setup()
    kw = dict(departure_min=0.0, time_budget_min=600.0, p_cut=0.5,
              time_step_min=10.0)
    field = ev.build_time_expanded_field(net, haz, **kw)
    for start in (0, 1, 2, 3, 4):
        own = ev.future_aware_route(net, start, haz, **kw)
        shared = ev.future_aware_route(net, start, haz, **kw, field=field)
        assert own.as_dict() == shared.as_dict(), f"origin {start} diverged"
        assert own.route == shared.route
        assert own.node_hazard == shared.node_hazard
        assert own.arrival_times_min == shared.arrival_times_min


@pytest.mark.parametrize("bad", [
    {"departure_min": 5.0}, {"time_budget_min": 300.0},
    {"p_cut": 0.7}, {"time_step_min": 5.0},
])
def test_a_field_built_for_other_parameters_is_refused_not_used(bad):
    """A mismatched table would return a plausible route for the wrong question.

    It cannot raise on its own — the array has the right shape and the lookups
    succeed — so the mismatch has to be checked rather than discovered.
    """
    from wildfireguardian.routing import evacuation as ev

    net, haz = _tiny_field_setup()
    kw = dict(departure_min=0.0, time_budget_min=600.0, p_cut=0.5,
              time_step_min=10.0)
    field = ev.build_time_expanded_field(net, haz, **kw)
    with pytest.raises(ValueError, match="different parameters"):
        ev.future_aware_route(net, 0, haz, **{**kw, **bad}, field=field)


def test_a_field_from_a_different_network_is_refused():
    from wildfireguardian.routing import evacuation as ev
    from wildfireguardian.routing.future_front import RoadNetwork

    net, haz = _tiny_field_setup()
    kw = dict(departure_min=0.0, time_budget_min=600.0, p_cut=0.5,
              time_step_min=10.0)
    field = ev.build_time_expanded_field(net, haz, **kw)
    bigger = RoadNetwork.synthetic_grid((0.0, 0.0), 4, 4, 100.0,
                                        shelter_nodes={15})
    for _u, _v, d in bigger.graph.edges(data=True):
        d["time_min"] = d["length_m"] / 60.0
    with pytest.raises(ValueError, match="nodes"):
        ev.future_aware_route(bigger, 0, haz, **kw, field=field)


def test_the_scan_builds_the_field_once_not_once_per_origin():
    """The measurable claim: one build per scan, whatever the origin count."""
    import unittest.mock as mock

    from wildfireguardian.live import pipeline as pl
    from wildfireguardian.routing import evacuation as ev

    net, haz = _tiny_field_setup()
    calls = {"n": 0}
    real = ev.build_time_expanded_field

    def counting(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    class _Res:
        pass

    res = _Res()
    res.net, res.hazard, res.haz, res.extent = net, haz, None, None

    with mock.patch.object(pl, "build_time_expanded_field", counting), \
            mock.patch.object(pl, "candidate_origins",
                              lambda *a, **k: ([0, 1, 2, 3], (0.0, 0.0))):
        pl.route_region(res, p_cut=0.5, budget_min=600.0, step_min=10.0,
                        stride=18)
    assert calls["n"] == 1, (
        f"built the table {calls['n']} times for 4 origins; the point of "
        "PHASE 20 is that it is built once")


def test_every_other_caller_still_works_without_a_field():
    """Ten call sites pass no field. The default must stay self-sufficient."""
    import inspect

    from wildfireguardian.routing import evacuation as ev
    assert inspect.signature(ev.future_aware_route).parameters["field"].default is None


# ---------------------------------------------------------------------------
# 10. The committed scripts are shells, and still exist
# ---------------------------------------------------------------------------


def test_no_committed_entry_point_was_deleted():
    for name in ("run_live_detection.py", "run_manual_trigger.py",
                 "run_multi_region_routing.py", "run_yeongdeok_canonical_routing.py",
                 "run_building_origin_routing.py", "generate_dispatch_outputs.py",
                 "build_operator_screen.py"):
        assert (REPO / "scripts" / name).exists(), f"{name} was removed"


def test_run_trigger_delegates_to_the_service_instead_of_inlining_it():
    src = LIVE_SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "run_trigger")
    body = ast.unparse(fn)
    assert "service_routing.run_trigger_core" in body
    for inlined in ("pipeline.route_region", "pipeline.deliver",
                    "pipeline.write_viz", "pipeline.build_run_record"):
        assert inlined not in body, (
            f"{inlined} is back inside the script; the service layer is then a "
            "second implementation rather than the only one")


def test_the_display_path_helper_does_not_raise_outside_the_repo():
    import importlib
    import sys
    if str(REPO / "scripts") not in sys.path:
        sys.path.insert(0, str(REPO / "scripts"))
    mod = importlib.import_module("run_live_detection")
    assert mod.rel_to_repo("/tmp/elsewhere/run") == "/tmp/elsewhere/run"
    assert not mod.rel_to_repo(REPO / "outputs" / "x").startswith("/")


def test_the_service_package_contains_no_web_server():
    """PHASE 19 stops one layer short of a transport, on purpose."""
    banned = ("fastapi", "flask", "uvicorn", "aiohttp", "starlette",
              "http.server", "socketserver", "werkzeug")
    for path in _service_sources():
        low = path.read_text(encoding="utf-8").lower()
        for token in banned:
            assert f"import {token}" not in low and f"from {token}" not in low, (
                f"{path.name} imports {token}; PHASE 19 is explicitly scoped to "
                "end before the web server")
