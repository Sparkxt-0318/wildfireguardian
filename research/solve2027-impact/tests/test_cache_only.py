"""Checks that need only the committed inputs (planner cache, INDEX.json, places files), never data/routing/: they
run, and never skip, whether or not the road graphs and HAZARD packets are present. Both independent paths recompute
every cache-only number (uses_graph = false) with data/routing/ made unreachable, and the result equals NUMBERS.json,
so those numbers truly need nothing else.
"""
import json

from conftest import PACKAGE_ROOT, no_routing_data
from wfg_impact import numbers as numbers_mod

NUMBERS = json.loads((PACKAGE_ROOT / 'NUMBERS.json').read_text(encoding='utf-8'))
N = NUMBERS['numbers']
CACHE_ONLY = {k: e for k, e in N.items() if not e['uses_graph']}


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
