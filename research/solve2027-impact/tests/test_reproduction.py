"""Full-data tests: committed outputs reproduce exactly, the independent path B reproduces every number, and the
published numbers satisfy the invariants the text relies on."""
import json
import re
import tempfile
from pathlib import Path

import pytest

from conftest import PACKAGE_ROOT, ROUTING_SKIP, routing_inputs_available
from wfg_impact import numbers as numbers_mod, sentences, sources

NUMBERS = json.loads((PACKAGE_ROOT / 'NUMBERS.json').read_text(encoding='utf-8'))
N = NUMBERS['numbers']


def test_committed_text_outputs_reproduce_exactly(built):
    _, texts = built
    for name, body in texts.items():
        assert (PACKAGE_ROOT / name).read_text(encoding='utf-8') == body, f'{name} is out of date: run compute.py'


def test_figures_and_table_twins_reproduce_exactly_whatever_the_matplotlib_config(path_a_result, built):
    """Drawn under a deliberately different ambient matplotlib configuration (as a matplotlibrc or MATPLOTLIBRC would
    set it), the figures still equal the committed ones: SVG byte for byte, PNG pixel for pixel; the ambient settings
    are restored afterwards."""
    import matplotlib
    from wfg_impact import figures
    nums, _ = built
    hostile = {  # settings figures._style() pins ...
               'text.hinting': 'no_hinting', 'font.family': ['serif'], 'font.size': 14.0, 'figure.dpi': 72.0,
               'svg.fonttype': 'path', 'svg.hashsalt': 'ambient', 'hatch.linewidth': 3.0, 'axes.facecolor': '#eeeeee',
               'figure.facecolor': '#dddddd', 'savefig.dpi': 300.0,
               # ... and settings only the reset to matplotlib's defaults protects against
               'xtick.labelsize': 20.0, 'ytick.labelsize': 20.0, 'axes.labelsize': 20.0, 'axes.xmargin': 0.3,
               'axes.ymargin': 0.3, 'legend.handlelength': 5.0, 'patch.antialiased': False, 'lines.antialiased': False,
               'lines.linewidth': 3.0, 'grid.alpha': 0.1}
    with tempfile.TemporaryDirectory() as td, matplotlib.rc_context(hostile):
        drawn = figures.draw_all(path_a_result, nums, Path(td), Path(td))
        assert matplotlib.rcParams['text.hinting'] == 'no_hinting' and matplotlib.rcParams['font.size'] == 14.0
        for p in sorted(Path(td).glob('*.csv')):
            assert (PACKAGE_ROOT / 'tables' / p.name).read_text(encoding='utf-8') == p.read_text(encoding='utf-8')
        assert sorted(p.name for p in drawn) == sorted(f'{stem}.{ext}' for ext in ('png', 'svg') for stem in (
            'fig1_checked_share_by_offset', 'fig2_deadline_by_origin_type', 'fig3_travel_only_vs_checked'))
        for p in drawn:
            assert figures.same_figure(p, PACKAGE_ROOT / 'figures' / p.name), f'{p.name} is out of date: run compute.py'


@pytest.mark.skipif(not routing_inputs_available(), reason=ROUTING_SKIP)
def test_independent_path_b_reproduces_every_number():
    import verify
    from wfg_impact import path_b
    recomputed, _ = path_b.compute()
    problems = verify.compare(NUMBERS, recomputed)
    assert not problems, '\n'.join(problems[:50])


def test_headline_numbers_are_self_contained():
    assert list(NUMBERS['headline']) == list(numbers_mod.HEADLINE_KEYS)
    for key, h in NUMBERS['headline'].items():
        for field in ('value', 'definition', 'scope', 'scope_text', 'script', 'inputs', 'input_sha256', 'unit',
                      'uses_graph', 'uses_hazard'):
            assert field in h, (key, field)
        assert set(h['input_sha256']) == set(h['inputs'])
        assert all(NUMBERS['inputs'][p]['sha256'] == d for p, d in h['input_sha256'].items())
        assert (h.get('numerator') is None) == (h.get('denominator') is None)
        assert h['script'] == 'research/solve2027-impact/compute.py'
        # the road graph and the HAZARD packets are listed (with SHA-256) exactly when the number needs them
        assert any(p.endswith('/graph.json') for p in h['input_sha256']) == h['uses_graph'] == N[key]['uses_graph'], key
        assert any(p.endswith('/HAZARD.json') for p in h['input_sha256']) == h['uses_hazard'] == N[key]['uses_hazard'], key
    window = [k for k in NUMBERS['headline'] if k.split('@')[0].startswith(
        ('not_checked_although_fits.', 'window_limited_among_not_checked.', 'deadline_set_by.',
         'places.not_checked_although_fits', 'no_checked_route_any_offset.trip_fits', 'fastest_trip_s.', 'trip_model.'))]
    assert len(window) == 18          # 13 window classification + 4 fire-free trip time + 1 trip-model validation keys
    assert all(NUMBERS['headline'][k]['uses_graph'] and NUMBERS['headline'][k]['uses_hazard'] for k in window)


def test_every_number_has_a_definition_and_a_known_scope():
    for key, e in N.items():
        assert e['definition'] and e['scope'] in NUMBERS['scopes'], key
        if e['numerator'] is not None:
            assert 0 <= e['numerator'] <= e['denominator'] and e['value'] == e['numerator'], key


def test_input_hashes_match_the_files_and_index():
    index = json.loads((sources.CACHE_DIR / 'INDEX.json').read_text(encoding='utf-8'))
    by_path = {f'planner/cache/{e["path"]}': e['sha256'] for e in index}
    for path, row in NUMBERS['inputs'].items():
        if path in by_path:
            assert row['sha256'] == by_path[path]
        if path.startswith('data/routing/'):
            if routing_inputs_available():
                assert sources.sha256_file(sources.routing_data_root() / path[len('data/routing/'):]) == row['sha256']
        else:
            assert sources.sha256_file(sources.REPO / path) == row['sha256']
    for scope, s in NUMBERS['scopes'].items():
        if 'graph_sha256' in s:        # the API's recorded graph identity is the file the redundancy used
            region = s['region']
            assert NUMBERS['inputs'][f'data/routing/graphs/{region}/graph.json']['sha256'] == s['graph_sha256']
            assert s['tie_breaks'] == 0 and s['purpose'] == 'booth'
            assert all(h['platform'].startswith('macOS') and h['machine'] == 'arm64' for h in s['host'])


def test_invariants_the_text_relies_on():
    scopes = [s for s in NUMBERS['scopes'] if s.endswith('Z')] + ['uiseong_andong_2025/pooled', 'yeongdeok_2025/pooled', 'all/pooled']
    for sc in scopes:
        n = N[f'cases@{sc}']['value']
        for t in sources.GRID_OFFSETS_S:
            assert sum(N[f'cell.{v}.offset_{t:04d}s@{sc}']['value'] for v in
                       ('checked_route', 'model_no_route', 'unresolved', 'window_unsatisfiable')) == n
            assert N[f'cell.window_unsatisfiable.offset_{t:04d}s@{sc}']['value'] == 0
        assert sum(N[f'deadline.{c}@{sc}']['value'] for c in numbers_mod.DEADLINE_CATS) == n
        assert sum(N[f'best_verdict.{v}@{sc}']['value'] for v in ('checked_route', 'model_no_route', 'unresolved')) == n
        # no origin has a gap: "share checked at t = share with deadline >= t" relies on it
        assert N[f'contiguous_differs_from_latest@{sc}']['value'] == 0
        assert N[f'no_checked_route_any_offset@{sc}']['value'] == \
            N[f'deadline.none_model_no_route@{sc}']['value'] + N[f'deadline.none_unresolved@{sc}']['value']
        assert N[f'attempts@{sc}']['value'] == 18 * n            # 3 candidate destinations x 6 departure offsets
    a = 'all/pooled'
    assert N[f'records.route_checks@{a}']['value'] == (N[f'records.dispatch_attempts@{a}']['value'] +
                                                       N[f'records.rechecks@{a}']['value'] +
                                                       N[f'records.research_route_checks@{a}']['value'])
    assert N[f'records.dispatch_attempts@{a}']['value'] == N[f'attempts@{a}']['value']
    assert N[f'api_check.recorded_equals_api_rule_on_original@{a}']['share'] == 1.0
    assert N[f'api_check.recorded_equals_planner_rule_on_original@{a}']['share'] == 1.0
    assert N[f'api_check.displayed_differs_explained_by_recheck@{a}']['share'] == 1.0
    assert N[f'travel_only.pairs@{a}']['share'] == 1.0
    assert N[f'travel_only.clear_pairs_equal_arrival@{a}']['share'] == 1.0
    assert N['travel_only.fastest_meets_flames@yeongdeok_2025/pooled']['value'] == 0   # "all in Uiseong-Andong"


def test_window_classification_partitions_and_never_hides_a_checked_route():
    scopes = [s for s in NUMBERS['scopes'] if s.endswith('Z')] + ['uiseong_andong_2025/pooled', 'yeongdeok_2025/pooled', 'all/pooled']
    for sc in scopes:
        n = N[f'cases@{sc}']['value']
        for t in sources.GRID_OFFSETS_S:
            o = f'offset_{t:04d}s@{sc}'
            lim, fit = N[f'window_limited.{o}'], N[f'not_checked_although_fits.{o}']
            assert lim['denominator'] == n and fit['denominator'] == n - lim['numerator']
            for v in ('model_no_route', 'unresolved'):     # fits + limited = the planner's own cell count
                assert N[f'cell_window.{v}.fits.{o}']['value'] + N[f'cell_window.{v}.limited.{o}']['value'] == \
                    N[f'cell.{v}.{o}']['value']
            assert fit['numerator'] == N[f'cell_window.model_no_route.fits.{o}']['value'] + \
                N[f'cell_window.unresolved.fits.{o}']['value']
            # every checked cell fits: window-limited cells are all among the unchecked ones
            assert lim['numerator'] == N[f'cell_window.model_no_route.limited.{o}']['value'] + \
                N[f'cell_window.unresolved.limited.{o}']['value']
            wl = N[f'window_limited_among_not_checked.{o}']
            assert wl['numerator'] == lim['numerator'] and wl['denominator'] == n - N[f'cell.checked_route.{o}']['value']
        closes = N[f'window_closes_within_hour@{sc}']['value']
        assert N[f'deadline_set_by.window@{sc}']['denominator'] == closes
        assert N[f'deadline_set_by.window@{sc}']['value'] + N[f'deadline_set_by.fire_or_limits@{sc}']['value'] == closes
        for t in sources.GRID_OFFSETS_S[:-1]:
            assert N[f'deadline.latest_{t:04d}s.set_by_window@{sc}']['value'] + \
                N[f'deadline.latest_{t:04d}s.set_by_fire_or_limits@{sc}']['value'] == N[f'deadline.latest_{t:04d}s@{sc}']['value']
        assert N[f'window_limited.offset_0000s@{sc}']['value'] == 0       # at the forecast time everything fits
    # the fire-free trip model is the API's own travel-time-only route time
    assert N['trip_model.equals_travel_only@all/pooled']['share'] == 1.0
    a, b = N['travel_only.fastest_meets_flames@all/pooled#leave_by_3000s'], N['travel_only.fastest_meets_flames@all/pooled#leave_by_before_3000s']
    tot = N['travel_only.fastest_meets_flames@all/pooled']
    assert (a['numerator'] + b['numerator'], a['denominator'] + b['denominator']) == (tot['numerator'], tot['denominator'])


def test_wording_that_depends_on_numbers():
    # S2 "(Yeongdeok: ..., at both)"
    y0, y30 = N['not_checked_although_fits.offset_0000s@yeongdeok_2025/pooled'], N['not_checked_although_fits.offset_1800s@yeongdeok_2025/pooled']
    assert (y0['numerator'], y0['denominator']) == (y30['numerator'], y30['denominator'])
    # S5 "in none of the ... at +50 minutes", "all in Uiseong-Andong"
    assert N['travel_only.fastest_meets_flames@all/pooled#leave_by_3000s']['numerator'] == 0
    assert N['travel_only.fastest_meets_flames@yeongdeok_2025/pooled']['numerator'] == 0
    # S3 caution "for all ... of them the fastest fire-free trip fits"
    assert N['no_checked_route_any_offset.trip_fits_at_offset_0000s@all/pooled']['share'] == 1.0
    # S4 caution "Of these places, ... had no checked route at any departure time" (a subset of the S4 count)
    assert N['places.no_checked_route_any_offset_any_input@all/places']['numerator'] <= \
        N['places.not_checked_although_fits_any_offset_any_input@all/places']['numerator']
    # README "Read this first" 2: "most of the drop toward +50 min in Uiseong-Andong is window-limited",
    # "most deadlines before +50 min are window-set"
    assert N['window_limited_among_not_checked.offset_3000s@uiseong_andong_2025/pooled']['share'] > 0.5
    assert N['deadline_set_by.window@all/pooled']['share'] > 0.5
    # "the 1-hour scenario window" and the 480 s / 1,080 s trip limits: valid_until 3600 s, 120 s stay, every file
    for sc, s in NUMBERS['scopes'].items():
        if 'graph_sha256' in s:
            assert s['valid_until_s'] == 3600 and s['valid_from_s'] == 0 and s['dt_s'] == 1
    # README "the shared road usually extends well beyond the entry node itself"
    assert N['redundancy.shared_stretch_within_100m@all/places']['share'] < 0.5
    # S6 shared stretch statistic covers exactly the single-path places
    assert N['redundancy.shared_stretch_m.median@all/places']['n'] == N['redundancy.turn_aware_paths_1@all/places']['numerator']


def test_hand_written_readme_facts_match_numbers():
    readme = (PACKAGE_ROOT / 'README.md').read_text(encoding='utf-8')
    assert N['places@all/places#care_facility']['value'] == 5 and 'care_facility' not in \
        ''.join(k for k in N if k.startswith('places@yeongdeok_2025/places#'))
    assert '5 care facilities are mapped in OSM (all in Uiseong-Andong), none in Yeongdeok' in readme
    assert N['osm_origins_not_checkable@all/places']['value'] == 3 and 'the 3 not-checkable villages' in readme
    assert N['research_origins@all/places']['value'] == 8 and 'the 8 research' in readme
    assert N['destinations_used.shelter@yeongdeok_2025/places']['value'] == 1
    assert 'an unnamed OSM point tagged `amenity=shelter` without `shelter_type`' in readme
    lo, hi = N['fastest_trip_s.min@all/places#care_facility']['value'], N['fastest_trip_s.max@all/places#care_facility']['value']
    assert f'They are {lo}-{hi} s fire-free drive' in readme and hi <= 480       # "the window never limits them"
    assert N['places.window_limited_at_offset_3000s@all/places#care_facility']['numerator'] == 0
    assert 'takes at most 480 s (8 min); at +40 min, at most 1,080 s' in readme
    assert N['destinations_used.shelter@uiseong_andong_2025/places']['value'] == 0
    assert N['redundancy.turn_aware_equals_plain@all/places']['share'] == 1.0 and 'equal for every place' in readme
    for marker in ('사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다.', 'Planning aid only — not for live evacuation operations.'):
        assert marker in readme


FORBIDDEN = [r'\bsafe route', r'\bsafely\b', r'\bsaved\b', r'\blives\b', r'casualt(y|ies) (were )?avoided',
             r'simulations? of the actual fire(?! spread)', r'\bevacuated\b', r'\bguarantee']


def test_application_sentences_never_state_outcomes():
    for s in sentences.SENTENCES:
        text, caution, keys = sentences.render(s, N)
        assert keys and all(k in N for k in keys)
        for pat in FORBIDDEN:
            assert not re.search(pat, text, flags=re.I), (s['id'], pat)
        # "safe" may only appear negated
        for m in re.finditer(r'safe', text, flags=re.I):
            assert re.search(r'never (presents? as |described as |be read as )?"?safe', text[max(0, m.start() - 40):m.end() + 1], re.I), s['id']
    assert 5 <= len(sentences.SENTENCES) <= 8
