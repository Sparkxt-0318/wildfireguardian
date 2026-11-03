"""Provenance: which numbers depend on this package's own road-graph computation, and which inputs every headline
number records.

The source flags are checked from both sides: test_cache_only.py proves that every uses_graph = false number is
reproduced with data/routing/ unreachable; here, perturbing only the road-graph-derived values must change nothing but
numbers flagged uses_graph (and uses_hazard where trip times or the window are involved).
"""
import copy
import json
import re

from conftest import PACKAGE_ROOT
from wfg_impact import analysis, numbers as numbers_mod

NUMBERS = json.loads((PACKAGE_ROOT / 'NUMBERS.json').read_text(encoding='utf-8'))
N = NUMBERS['numbers']
README = (PACKAGE_ROOT / 'README.md').read_text(encoding='utf-8')

# families written out here independently of numbers.py: the 1-hour window classification and fire-free trip times
# (graph.json travel_ticks x HAZARD.json dt, window from HAZARD.json) and the graph-only road metrics
WINDOW_FAMILIES = ('window_limited.', 'window_limited_among_not_checked.', 'not_checked_although_fits.',
                   'deadline_set_by.', 'cell_window.', 'places.not_checked_although_fits_', 'places.window_limited_at_',
                   'no_checked_route_any_offset.trip_fits_', 'fastest_trip_s.', 'trip_model.')
GRAPH_ONLY_FAMILIES = ('redundancy.', 'redundancy_x.', 'travel_only.extra_length_m.')


def _metric(key: str) -> str:
    return key.split('@')[0]


def _is_window(key: str) -> bool:
    m = _metric(key)
    return m.startswith(WINDOW_FAMILIES) or re.fullmatch(r'deadline\.latest_\d{4}s\.set_by_(window|fire_or_limits)', m)


def test_every_number_records_its_sources():
    counts = {'window': 0, 'graph': 0, 'cache': 0}
    for key, e in N.items():
        if _is_window(key):
            assert e['uses_graph'] is True and e['uses_hazard'] is True, key
            counts['window'] += 1
        elif _metric(key).startswith(GRAPH_ONLY_FAMILIES):
            assert e['uses_graph'] is True and e['uses_hazard'] is False, key
            counts['graph'] += 1
        else:                                   # aggregates of the recorded cache and place files only
            assert e['uses_graph'] is False and e['uses_hazard'] is False, key
            counts['cache'] += 1
    assert min(counts.values()) > 100, counts


def test_headline_inputs_include_graph_and_hazard_packets_where_used():
    for key, h in NUMBERS['headline'].items():
        e = N[key]
        assert (h['uses_graph'], h['uses_hazard']) == (e['uses_graph'], e['uses_hazard'])
        caches = [p for p in h['inputs'] if p.startswith('planner/cache/') and p.endswith('Z.json')]
        graphs = sorted(p for p in h['inputs'] if p.endswith('/graph.json'))
        hazards = sorted(p for p in h['inputs'] if p.endswith('/HAZARD.json'))
        regions = sorted({p.split('/')[2] for p in caches})
        assert graphs == ([f'data/routing/graphs/{r}/graph.json' for r in regions] if e['uses_graph'] else []), key
        # the HAZARD packet of exactly the cache files (input times) the number is computed from
        expect = sorted(f'data/routing/latest_inputs_try02/packets/{p.split("/")[2]}/{p.split("/")[3][:-5]}/HAZARD.json'
                        for p in caches)
        assert hazards == (expect if e['uses_hazard'] else []), key
        for p in graphs + hazards:
            assert h['input_sha256'][p] == NUMBERS['inputs'][p]['sha256'], (key, p)
    # S2's window-corrected headline numbers cannot be computed from the cache alone: their inputs say so
    for t in ('0000', '1800'):
        h = NUMBERS['headline'][f'not_checked_although_fits.offset_{t}s@uiseong_andong_2025/pooled']
        assert 'data/routing/graphs/uiseong_andong_2025/graph.json' in h['input_sha256']
        assert sum(p.endswith('HAZARD.json') for p in h['input_sha256']) == 3
    note = NUMBERS['inputs']['data/routing/latest_inputs_try02/packets/yeongdeok_2025/20250325T190000Z/HAZARD.json']['note']
    assert note.endswith('only valid_from, valid_until and dt are read')


def _rebuild(result, mutate):
    r = copy.deepcopy(result)
    mutate(r)
    analysis.classify_window(r['records'], r['metas'], r['redundancy'])     # fits and deadline_set_by again
    return numbers_mod.build(r)


def _changed(a: dict, b: dict) -> set:
    assert set(a) == set(b)
    return {k for k in a if any(a[k].get(f) != b[k].get(f) for f in ('value', 'numerator', 'denominator'))}


def _faster_trips(r):
    """As if graph.json travel_ticks or HAZARD.json dt were different: every fire-free trip takes half as long."""
    for x in r['redundancy']:
        x['trip_by_dest_s'] = {k: (None if v is None else v // 2) for k, v in x['trip_by_dest_s'].items()}
    for p in r['pairs']:
        if p.get('trip_model_s') is not None:
            p['trip_model_s'] //= 2


def _other_roads(r):
    """As if graph.json's roads were different: other redundancy values, shared stretches and route lengths."""
    for x in r['redundancy']:
        x['turn_aware_paths'] = {2: 3, 3: 4}.get(x['turn_aware_paths'], x['turn_aware_paths'])
    for x in [x for x in r['redundancy'] if x['turn_aware_paths'] == 1][::2]:
        x['turn_aware_paths'] = 2
    for x in r['redundancy']:
        x['entry_out_degree'] += 1
        x['cut_at_entry_node'] = not x['cut_at_entry_node']
        if x['shared_stretch_m'] is not None:
            x['shared_stretch_m'] *= 2
    for p in r['pairs']:
        for k in ('checked_length_m', 'fastest_length_m', 'extra_length_m'):
            if p.get(k) is not None:
                p[k] *= 2


def test_source_flags_follow_the_real_dependencies(path_a_result):
    base = numbers_mod.build(path_a_result)
    assert _changed(base, numbers_mod.build(copy.deepcopy(path_a_result))) == set()
    for mutate, hazard, must in ((_faster_trips, True, ('fastest_trip_s.median@all/places', 'trip_model.equals_travel_only@all/pooled',
                                                        'window_limited.offset_3000s@all/pooled',
                                                        'not_checked_although_fits.offset_3000s@uiseong_andong_2025/pooled')),
                                 (_other_roads, False, ('redundancy.turn_aware_paths_1@all/places',
                                                        'redundancy.shared_stretch_m.median@all/places',
                                                        'redundancy_x.cases@all/pooled#rc1',
                                                        'travel_only.extra_length_m.median@all/pooled'))):
        changed = _changed(base, _rebuild(path_a_result, mutate))
        assert set(must) <= changed, (mutate.__name__, set(must) - changed)
        wrong = sorted(k for k in changed if not N[k]['uses_graph'] or (hazard and not N[k]['uses_hazard']))
        assert not wrong, (mutate.__name__, wrong[:20])


def test_readme_counts_of_cache_only_numbers_match():
    cache_only = sum(1 for e in N.values() if not e['uses_graph'])
    assert f'(`uses_graph` = false, {cache_only:,} of the {len(N):,} numbers)' in ' '.join(README.split())
