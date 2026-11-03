"""Cross-check against the Route-Check API's own per-origin fields.

The API's aggregation code, ``api/dispatch.py`` (unmodified; it imports only ``statistics``), is loaded by file path
so that its ``origin_plan`` (lines 34-44: ``best_verdict`` 9-17, ``latest_checked_depart_offset_s`` 37,
``contiguous_latest`` 20-31) can be re-applied to the ORIGINAL attempts recorded in each cached dispatch plan. Line
numbers in this module refer to repository commit 0cd95db2.

Three comparisons are reported per origin:
1. recorded API fields  vs  ``api/dispatch.py`` re-applied to the recorded attempts (data integrity);
2. recorded API fields  vs  the planner rules (path A) applied to the original attempts (rule equivalence);
3. recorded API fields  vs  the planner's displayed values, which replace re-checked attempts with their re-check
   (``planner/src/api/cache.ts`` lines 120-145). Differences in (3) are explained only if (1) and (2) agree and the
   origin has at least one re-checked attempt.
"""
from __future__ import annotations

import importlib.util

from .sources import REPO

_DISPATCH = None


def dispatch_module():
    global _DISPATCH
    if _DISPATCH is None:
        path = REPO / 'api' / 'dispatch.py'
        spec = importlib.util.spec_from_file_location('wfg_api_dispatch_readonly', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _DISPATCH = mod
    return _DISPATCH


def recorded_fields(wire_plan: dict) -> dict:
    return {'best_verdict': wire_plan.get('best_verdict'),
            'latest_s': wire_plan.get('latest_checked_depart_offset_s'),
            'contiguous_s': wire_plan.get('latest_contiguous_checked_depart_offset_s')}


def api_rule_fields(wire_plan: dict, destination_ids: list[str]) -> dict:
    """``api/dispatch.py origin_plan`` applied to the recorded (original) attempts."""
    d = dispatch_module()
    order = {k: i for i, k in enumerate(destination_ids)}
    p = d.origin_plan(wire_plan['origin_id'], wire_plan.get('snap'), list(wire_plan.get('attempts') or []), order)
    return {'best_verdict': p['best_verdict'], 'latest_s': p['latest_checked_depart_offset_s'],
            'contiguous_s': p['latest_contiguous_checked_depart_offset_s']}
