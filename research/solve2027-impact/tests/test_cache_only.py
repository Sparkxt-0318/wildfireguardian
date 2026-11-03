"""Checks that need only the committed inputs (planner cache, INDEX.json, places files), never data/routing/: they
run, and never skip, whether or not the road graphs and HAZARD packets are present.

* both independent paths recompute every cache-only number (uses_graph = false) with data/routing/ made unreachable,
  and the result equals NUMBERS.json, so those numbers truly need nothing else;
* planner/cache/INDEX.json totals reconcile with the published counts;
* every travel_only record is accounted for; check-level and per-type counts add up.
"""
import json

from conftest import PACKAGE_ROOT, no_routing_data
from wfg_impact import numbers as numbers_mod, planner_rules as pr, sources

NUMBERS = json.loads((PACKAGE_ROOT / 'NUMBERS.json').read_text(encoding='utf-8'))
N = NUMBERS['numbers']
CACHE_ONLY = {k: e for k, e in N.items() if not e['uses_graph']}
FILE_SCOPES = [s for s in NUMBERS['scopes'] if s.endswith('Z')]
CASE_SCOPES = FILE_SCOPES + [f'{r}/pooled' for r in sources.REGIONS] + ['all/pooled']


def test_path_a_recomputes_every_cache_only_number_without_routing_data(cache_only_result, tmp_path):
    assert cache_only_result['with_graphs'] is False and cache_only_result['redundancy'] == []
    with no_routing_data(tmp_path):
        nums = numbers_mod.build(cache_only_result)
    # exactly the numbers flagged uses_graph = false can be built without the road graph and HAZARD packets
    assert set(nums) == set(CACHE_ONLY)
    assert len(CACHE_ONLY) > 500 and len(CACHE_ONLY) < len(N)       # not vacuous
    for key, e in CACHE_ONLY.items():
        a = nums[key]
        for field in ('value', 'numerator', 'denominator', 'share', 'n', 'unit', 'scope', 'subset', 'definition',
                      'uses_graph', 'uses_hazard'):
            assert a.get(field) == e.get(field) and type(a.get(field)) is type(e.get(field)), (key, field)


def test_path_b_recomputes_every_cache_only_number_without_routing_data(tmp_path):
    import verify
    from wfg_impact import path_b
    with no_routing_data(tmp_path):
        recomputed, _ = path_b.compute(with_graphs=False)
        problems = verify.compare(NUMBERS, recomputed, cache_only=True)
    assert set(recomputed) == set(CACHE_ONLY)
    assert not problems, '\n'.join(problems[:50])


def test_index_json_totals_reconcile_with_the_published_counts():
    index = [e for e in json.loads((sources.CACHE_DIR / 'INDEX.json').read_text(encoding='utf-8'))
             if e['region_id'] in sources.REGIONS]
    assert len(index) == 6
    pairs = {'checked_route': ('attempts.verdict.checked_route', 'research_checks.verdict.checked_route'),
             'model_no_route': ('attempts.verdict.model_no_route', 'research_checks.verdict.model_no_route'),
             'unresolved/AT_ISSUE_FAILURE': ('attempts.unresolved.AT_ISSUE_FAILURE', 'research_checks.unresolved.AT_ISSUE_FAILURE'),
             'unresolved/TIMEOUT': ('attempts.unresolved.TIMEOUT', 'research_checks.unresolved.TIMEOUT')}
    for e in index:
        sc = sources.scope_id(e['region_id'], e['input_time'])
        g = lambda k: N[f'{k}@{sc}']['value']  # noqa: E731
        # origins = the OSM origins of the dispatch plans + the recorded research-mission origins
        assert e['origins'] == g('cases') + g('research_origins')
        # checks = every stored route-check record (travel_only comparisons are not counted)
        assert e['checks'] == g('records.route_checks') == g('records.dispatch_attempts') + g('records.rechecks') + \
            g('records.research_route_checks')
        assert g('records.dispatch_attempts') == g('attempts')
        assert N[f'research_checks.verdict.checked_route@{sc}']['denominator'] == g('records.research_route_checks')
        # verdicts = displayed dispatch attempts (re-checks substituted) + research checks, by verdict and reason code
        assert set(e['verdicts']) <= set(pairs)
        for name, (displayed, research) in pairs.items():
            assert e['verdicts'].get(name, 0) == g(displayed) + g(research), (sc, name)
        assert g('attempts.unresolved.other') == g('research_checks.unresolved.other') == 0
        assert sum(e['verdicts'].values()) == e['checks'] - g('records.rechecks')
    readme = (PACKAGE_ROOT / 'README.md').read_text(encoding='utf-8')
    assert '## Reconciliation with planner/cache/INDEX.json' in readme
    assert '| **all six** | 530 = 522 + 8 | 9,722 = 9,396 + 279 + 47 |' in readme


def test_every_travel_only_record_is_accounted_for():
    a = 'all/pooled'
    records = N[f'records.travel_only@{a}']['value']
    assert records == sum(N[f'records.travel_only@{s}']['value'] for s in FILE_SCOPES)
    paired, unpaired = N[f'travel_only.pairs@{a}'], N[f'travel_only.records_not_paired@{a}']
    assert unpaired['denominator'] == records == paired['numerator'] + unpaired['numerator']
    assert paired['numerator'] == paired['denominator']           # every case with a checked route has its comparison
    research = N[f'travel_only.records_not_paired.research_origin@{a}']
    assert research['numerator'] == research['denominator'] == unpaired['numerator']   # all unpaired: research origins
    assert unpaired['numerator'] <= N[f'research_origins@{a}']['value']
    flame = N[f'travel_only.records_not_paired.fastest_meets_flames@{a}']
    assert flame['denominator'] == unpaired['numerator']
    readme = (PACKAGE_ROOT / 'README.md').read_text(encoding='utf-8')
    assert (f'store {records} travel_only comparison checks (`records.travel_only@all/pooled`): the '
            f'{paired["numerator"]} comparisons paired with village/care-facility cases') in readme


def test_check_level_counts_and_per_type_survival_add_up():
    for sc in CASE_SCOPES:
        for sub in ('', '#village', '#care_facility'):
            if f'cases@{sc}{sub}' not in N:
                assert sub == '#care_facility' and sc.startswith('yeongdeok')      # no care facility in Yeongdeok
                continue
            g = lambda k: N[f'{k}@{sc}{sub}']['value']  # noqa: E731
            n_att = g('attempts')
            assert n_att == 18 * g('cases')                      # 3 candidate destinations x 6 departure offsets
            assert sum(g(f'attempts.verdict.{v}') for v in pr.VERDICTS) == n_att
            assert g('attempts.verdict.unresolved') == sum(g(f'attempts.unresolved.{c}')
                                                           for c in ('AT_ISSUE_FAILURE', 'TIMEOUT', 'other'))
            # the documented equivalence: no case has a gap, so "checked at +t" = "leave-by deadline at or after +t"
            assert g('contiguous_differs_from_latest') == 0
            for t in sources.GRID_OFFSETS_S:
                assert sum(g(f'cell.{c}.offset_{t:04d}s') for c in numbers_mod.CELL_CATS) == g('cases')
                assert g(f'cell.checked_route.offset_{t:04d}s') == sum(
                    g(f'deadline.latest_{u:04d}s') for u in sources.GRID_OFFSETS_S if u >= t)
        # village + care facility = all, for every per-type family
        for fam in (['attempts', 'contiguous_differs_from_latest'] + [f'attempts.verdict.{v}' for v in pr.VERDICTS] +
                    [f'attempts.unresolved.{c}' for c in ('AT_ISSUE_FAILURE', 'TIMEOUT', 'other')] +
                    [f'cell.{c}.offset_{t:04d}s' for c in numbers_mod.CELL_CATS for t in sources.GRID_OFFSETS_S]):
            parts = [N[k]['value'] for k in (f'{fam}@{sc}#village', f'{fam}@{sc}#care_facility') if k in N]
            assert sum(parts) == N[f'{fam}@{sc}']['value'], (fam, sc)
    for sc in FILE_SCOPES + ['all/pooled']:
        g = lambda k: N[f'{k}@{sc}']['value']  # noqa: E731
        assert sum(g(f'research_checks.verdict.{v}') for v in pr.VERDICTS) == g('records.research_route_checks')


def test_entry_points_stop_with_a_hint_without_routing_data(tmp_path):
    """compute.py (write and --check) and a full verify.py exit with status 2 and a hint, not a traceback, when the
    road graphs and HAZARD packets are missing; verify.py --cache-only is what runs without them (tested above)."""
    import os
    import subprocess
    import sys
    env = {**os.environ, 'WFG_ROUTING_DATA': str(tmp_path / 'no-routing-data'), 'PYTHONDONTWRITEBYTECODE': '1'}
    for script, args in (('compute.py', ['--check']), ('compute.py', []), ('verify.py', [])):
        r = subprocess.run([sys.executable, str(PACKAGE_ROOT / script), *args], env=env, capture_output=True,
                           text=True, timeout=300)
        assert r.returncode == 2, (script, args, r.stdout, r.stderr[-2000:])
        assert r.stdout == '' and 'Traceback' not in r.stderr
        assert r.stderr.startswith('MISSING INPUTS: ') and 'tools/fetch_routing_inputs.py' in r.stderr
        assert 'verify.py --cache-only' in r.stderr and str(tmp_path / 'no-routing-data') in r.stderr


def test_routing_inputs_are_recorded_under_repository_paths():
    """Wherever WFG_ROUTING_DATA points, graph and HAZARD files are recorded as data/routing/... paths."""
    graphs = sorted(g['graph_file'] for g in NUMBERS['graphs'])
    assert graphs == sorted(sources.graph_rel(r) for r in sources.REGIONS) == \
        sorted(f'data/routing/graphs/{r}/graph.json' for r in sources.REGIONS)
    meta = NUMBERS['scopes']
    hazards = sorted(meta[s]['hazard_file'] for s in FILE_SCOPES)
    assert len(hazards) == 6 and hazards == sorted(sources.hazard_rel(meta[s]['region'], meta[s]['input_time'])
                                                   for s in FILE_SCOPES)
    assert sorted(p for p in NUMBERS['inputs'] if p.startswith('data/routing/')) == sorted(graphs + hazards)


def test_entry_distances_cover_every_checked_place():
    for reg in list(sources.REGIONS) + ['all']:
        e = N[f'entry_distance_m.max@{reg}/places']
        assert e['n'] == N[f'places@{reg}/places']['value']
        assert e['value'] <= 2000.0                           # checkable = an entry point within 2 km
        assert N[f'entry_distance_m.min@{reg}/places']['value'] <= N[f'entry_distance_m.median@{reg}/places']['value'] \
            <= e['value']
        assert N[f'entry_distance_over_1000m@{reg}/places']['numerator'] <= N[f'entry_distance_over_500m@{reg}/places']['numerator']
