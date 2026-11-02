"""Full-data tests: committed outputs reproduce exactly, the independent path B reproduces every number, and the
published numbers satisfy the invariants the text relies on."""
import json
import re
import tempfile
from pathlib import Path

import pytest

from conftest import PACKAGE_ROOT, graphs_available
from wfg_impact import numbers as numbers_mod, sentences, sources

NUMBERS = json.loads((PACKAGE_ROOT / 'NUMBERS.json').read_text(encoding='utf-8'))
N = NUMBERS['numbers']


def test_committed_text_outputs_reproduce_exactly(built):
    _, texts = built
    for name, body in texts.items():
        assert (PACKAGE_ROOT / name).read_text(encoding='utf-8') == body, f'{name} is out of date: run compute.py'


def test_figure_table_twins_reproduce_exactly(path_a_result, built):
    from wfg_impact import figures
    nums, _ = built
    with tempfile.TemporaryDirectory() as td:
        figures.draw_all(path_a_result, nums, Path(td), Path(td))
        for p in sorted(Path(td).glob('*.csv')):
            assert (PACKAGE_ROOT / 'tables' / p.name).read_text(encoding='utf-8') == p.read_text(encoding='utf-8')
        for stem in ('fig1_checked_share_by_offset', 'fig2_deadline_by_origin_type', 'fig3_travel_only_vs_checked'):
            for ext in ('png', 'svg'):
                assert (PACKAGE_ROOT / 'figures' / f'{stem}.{ext}').is_file()


@pytest.mark.skipif(not graphs_available(), reason='road graphs missing: run python tools/fetch_routing_inputs.py')
def test_independent_path_b_reproduces_every_number():
    import verify
    from wfg_impact import path_b
    recomputed, _ = path_b.compute()
    problems = verify.compare(NUMBERS, recomputed)
    assert not problems, '\n'.join(problems[:50])


def test_headline_numbers_are_self_contained():
    assert list(NUMBERS['headline']) == list(numbers_mod.HEADLINE_KEYS)
    for key, h in NUMBERS['headline'].items():
        for field in ('value', 'definition', 'scope', 'scope_text', 'script', 'inputs', 'input_sha256', 'unit'):
            assert field in h, (key, field)
        assert set(h['input_sha256']) == set(h['inputs'])
        assert all(NUMBERS['inputs'][p]['sha256'] == d for p, d in h['input_sha256'].items())
        assert (h.get('numerator') is None) == (h.get('denominator') is None)
        assert h['script'] == 'research/solve2027-impact/compute.py'


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
            if graphs_available():
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
        # no origin has a gap: the figure-1 subtitle and "share checked at t = share with deadline >= t" rely on it
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


def test_hand_written_readme_facts_match_numbers():
    readme = (PACKAGE_ROOT / 'README.md').read_text(encoding='utf-8')
    assert N['places@all/places#care_facility']['value'] == 5 and 'care_facility' not in \
        ''.join(k for k in N if k.startswith('places@yeongdeok_2025/places#'))
    assert '5 care facilities are mapped in OSM (all in Uiseong-Andong), none in Yeongdeok' in readme
    assert N['osm_origins_not_checkable@all/places']['value'] == 3 and 'the 3 not-checkable villages' in readme
    assert N['research_origins@all/places']['value'] == 8 and 'the 8 research' in readme
    assert N['destinations_used.shelter@yeongdeok_2025/places']['value'] == 1 and 'one OSM-mapped' in readme
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
