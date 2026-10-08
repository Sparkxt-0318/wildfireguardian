"""Observer instrumentation of the isolated exact router; no pruning changes.

The instrumented source is derived from the adjacent repaired core using exact
anchors. Every anchor count is checked. Observers collect evidence but never
change geometry, doses, ordering, dominance, caps, or destination admission.
Use a fixed maintained max_expansions for paired semantic comparisons. Wall
timings from profiled runs include observer overhead and are not production
latency estimates.
"""
from collections import Counter
from fractions import Fraction
from functools import wraps
import hashlib
import math
from pathlib import Path
import resource
import sys
import time
import types

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "routing-package"))
from routing import core


def _deep_bytes(roots):
    """Owned Python object approximation; excludes graph/hazard and allocator overhead."""
    seen, stack, total = set(), list(roots), 0
    while stack:
        item = stack.pop()
        identity = id(item)
        if identity in seen:
            continue
        seen.add(identity); total += sys.getsizeof(item)
        if isinstance(item, dict):
            stack.extend(item.keys()); stack.extend(item.values())
        elif isinstance(item, (tuple, list, set, frozenset)):
            stack.extend(item)
        elif isinstance(item, Fraction):
            stack.extend((item.numerator, item.denominator))
    return total


class Recorder:
    def __init__(self, request):
        self.request = request
        self.counts, self.timings = Counter(), Counter()
        self.records, self.front, self.heap, self.cache = [], {}, [], {}
        self.pending_live = set()
        self.geometry_states, self.geometry_chords = set(), set()
        self.expanded_keys, self.expanded_nodes = set(), set()
        self.wait_departures = Counter()
        self.retained = self.peak_retained = self.peak_heap = self.peak_pending = 0
        self.peak_key_width = 0
        self.pop_min = self.pop_max = None
        self.max_retained_dose_ratios = {}
        self.max_candidate_peak_ratio = 0.0
        self.checked_incumbent = None
        self.started = time.perf_counter()

    def timed(self, function, category):
        @wraps(function)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                self.timings[category] += time.perf_counter() - start
                self.counts[category + "_calls"] += 1
        return wrapper

    def bind(self, records, front, heap, cache, member_ids, budgets, peak_budget):
        self.records, self.front, self.heap, self.cache = records, front, heap, cache
        self.member_ids, self.budgets, self.peak_budget = member_ids, budgets, peak_budget

    def dominates(self, a, b, phase):
        start = time.perf_counter()
        self.counts["dominance_vector_comparisons"] += 1
        self.counts["dominance_" + phase + "_comparisons"] += 1
        try:
            for x, y in zip(a, b):
                self.counts["dominance_component_comparisons"] += 1
                if x > y:
                    return False
            return True
        finally:
            self.timings["dominance"] += time.perf_counter() - start

    def add_wrapper(self, function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            self.counts["add_attempts"] += 1
            start = time.perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                self.timings["add_inclusive"] += time.perf_counter() - start
        return wrapped

    def cost_wrapper(self, function):
        @wraps(function)
        def wrapped(key, occupancy):
            hit = key in self.cache
            self.counts["cost_calls"] += 1
            self.counts["cost_cache_hits" if hit else "cost_cache_misses"] += 1
            result = function(key, occupancy)
            self.counts["cost_" + key[0].lower() + "_calls"] += 1
            if not result["admissible"]:
                self.counts["cost_rejected"] += 1
                for code in result["codes"]:
                    self.counts["cost_reject_" + code] += 1
                if any(row["peak"] > self.peak_budget for row in result["per_member"].values()):
                    self.counts["cost_reject_PEAK_BUDGET"] += 1
            else:
                self.counts["cost_admissible"] += 1
            peak = max((v["peak"] for v in result["per_member"].values()), default=0)
            if self.peak_budget > 0:
                self.max_candidate_peak_ratio = max(self.max_candidate_peak_ratio, peak / self.peak_budget)
            return result
        return wrapped

    def geometry_wrapper(self, function):
        @wraps(function)
        def wrapped(edge, start, end, from_fraction=0, to_fraction=1, graph=None, node_lookup=None):
            self.counts["edge_geometry_calls"] += 1
            self.geometry_states.add((edge["id"], start, end, from_fraction, to_fraction))
            self.geometry_chords.add((edge["id"], from_fraction, to_fraction))
            before = time.perf_counter()
            try:
                return function(edge, start, end, from_fraction, to_fraction, graph, node_lookup)
            finally:
                self.timings["geometry"] += time.perf_counter() - before
        return wrapped

    def rejected(self, category):
        self.counts["rejected_" + category] += 1

    def added(self, key, old, keep, idx, dose):
        evicted = set(old) - set(keep)
        self.counts["labels_retained_cumulative"] += 1
        self.counts["labels_evicted_from_front"] += len(evicted)
        self.retained += 1 - len(evicted)
        self.pending_live.difference_update(evicted); self.pending_live.add(idx)
        self.peak_retained = max(self.peak_retained, self.retained)
        self.peak_heap = max(self.peak_heap, len(self.heap))
        self.peak_pending = max(self.peak_pending, len(self.pending_live))
        self.peak_key_width = max(self.peak_key_width, len(keep) + 1)
        for mid, value, budget in zip(self.member_ids, dose, self.budgets):
            ratio = float(value / budget) if budget > 0 else (0.0 if value == 0 else None)
            if ratio is not None:
                self.max_retained_dose_ratios[mid] = max(self.max_retained_dose_ratios.get(mid, 0.), ratio)

    def popped(self, idx, node, incoming, t, admission, *, stale=False):
        self.counts["heap_pops"] += 1
        self.counts["heap_stale_pops" if stale else "heap_live_pops"] += 1
        self.pending_live.discard(idx)
        if not stale:
            self.pop_min = t if self.pop_min is None else min(self.pop_min, t)
            self.pop_max = t if self.pop_max is None else max(self.pop_max, t)

    def expanded(self, node, incoming, t, admission):
        self.counts["expanded"] += 1
        self.expanded_keys.add((node, incoming, t, admission)); self.expanded_nodes.add(node)

    def waiting(self, node, t):
        self.wait_departures[(node, t)] += 1

    def destination(self, node, t):
        self.counts["destination_admissions"] += 1
        self.counts["destination_admission_node_" + node] += 1

    def checked(self, checked, legs, arrival, destination):
        self.counts["route_checks"] += 1
        if checked["ok"]:
            self.counts["route_checks_passed"] += 1
            self.checked_incumbent = {"legs": legs, "arrival": arrival,
                                      "destination": destination, "checker": checked,
                                      "proof_level": "independent supplied-field witness only; no optimum claim"}

    def report(self, result):
        widths = Counter(len(v) for v in self.front.values())
        widest = sorted(self.front.items(), key=lambda kv: (-len(kv[1]), str(kv[0])))[:3]
        snapshots = []
        for key, indices in widest:
            doses = [[str(x) for x in self.records[i][4]] for i in indices[:4]]
            snapshots.append({"key": list(key), "width": len(indices), "first_four_exact_dose_vectors": doses})
        return {"schema": "wfg.routing.diagnostic/1", "counts": dict(self.counts),
                "timing_s": dict(self.timings), "instrumented_wall_s": time.perf_counter() - self.started,
                "timing_scope": "inclusive category timers; add_inclusive overlaps dominance; node_geometry overlaps edge geometry; observer bookkeeping is included in wall time",
                "frontier": {"records_ever_retained": len(self.records), "current_front_keys": len(self.front),
                             "current_retained_front_labels_including_expanded": self.retained,
                             "peak_retained_front_labels_including_expanded": self.peak_retained,
                             "current_heap_entries_including_stale": len(self.heap), "peak_heap_entries_including_stale": self.peak_heap,
                             "current_pending_live_labels": len(self.pending_live), "peak_pending_live_labels": self.peak_pending,
                             "maximum_labels_per_exact_key": self.peak_key_width,
                             "final_width_histogram": dict(sorted(widths.items())), "widest_final_keys": snapshots},
                "geometry": {"calls": self.counts["edge_geometry_calls"], "distinct_edge_time_fraction_geometries": len(self.geometry_states),
                             "distinct_static_edge_fraction_chords": len(self.geometry_chords),
                             "repeated_edge_time_fraction_geometries": self.counts["edge_geometry_calls"] - len(self.geometry_states)},
                "cache": {"entries": len(self.cache), "hits": self.counts["cost_cache_hits"], "misses": self.counts["cost_cache_misses"]},
                "search_time": {"live_pop_min_s": self.pop_min, "live_pop_max_s": self.pop_max,
                                "heap_min_priority_and_time": list(self.heap[0][:2]) if self.heap else None,
                                "expanded_unique_nodes": len(self.expanded_nodes), "expanded_unique_exact_keys": len(self.expanded_keys),
                                "distinct_wait_departure_node_times": len(self.wait_departures),
                                "repeated_wait_candidates_same_node_time": sum(v - 1 for v in self.wait_departures.values())},
                "budget_usage": {"maximum_retained_dose_fraction_by_member": self.max_retained_dose_ratios,
                                 "maximum_evaluated_candidate_peak_fraction": self.max_candidate_peak_ratio},
                "memory": {"search_objects_deep_approx_bytes": _deep_bytes((self.records, self.front, self.heap, self.cache)),
                           "scope": "approximate final records/front/heap/cost-cache Python objects only; includes shared scalar references once, excludes graph/hazard, allocator overhead and observer sets",
                           "process_peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1048576 if sys.platform == "darwin" else 1024)},
                "checked_incumbent_observed": self.checked_incumbent,
                "primary_status": result["status"], "primary_reason": result["reason"]}


def _instrumented_module(recorder):
    path = ROOT / "routing-package/routing/core.py"
    source = path.read_text()
    replacements = [
        ('    def cost(key, occupancy):', '    @_DIAG.cost_wrapper\n    def cost(key, occupancy):'),
        ('    cap = None\n\n    def add(', '    cap = None\n    _DIAG.bind(records, front, heap, cost_cache, member_ids, budgets, peak_budget)\n\n    @_DIAG.add_wrapper\n    def add('),
        ('        if any(v > b for v, b in zip(dose, budgets)):\n            return', '        if any(v > b for v, b in zip(dose, budgets)):\n            _DIAG.rejected("CUMULATIVE_DOSE")\n            return'),
        ('if any(all(a <= b for a, b in zip(records[j][4], dose)) for j in old):', 'if any(_DIAG.dominates(records[j][4], dose, "old_bounds_new") for j in old):'),
        ('keep = [j for j in old if not all(a <= b for a, b in zip(dose, records[j][4]))]', 'keep = [j for j in old if not _DIAG.dominates(dose, records[j][4], "new_bounds_old")]'),
        ('            metrics["dominated"] += 1\n            return', '            metrics["dominated"] += 1\n            _DIAG.rejected("DOMINATED")\n            return'),
        ('        heapq.heappush(heap, (t + distance[node], t, idx))', '        heapq.heappush(heap, (t + distance[node], t, idx))\n        _DIAG.added(key, old, keep, idx, dose)'),
        ('        if idx not in front.get((node, incoming, t, admission), []):\n            continue', '        if idx not in front.get((node, incoming, t, admission), []):\n            _DIAG.popped(idx, node, incoming, t, admission, stale=True)\n            continue\n        _DIAG.popped(idx, node, incoming, t, admission)'),
        ('            for d in destinations.get(node, []):\n                end =', '            for d in destinations.get(node, []):\n                _DIAG.destination(node, t)\n                end ='),
        ('                ):\n                    continue\n                c = cost(\n                    ("DWELL"', '                ):\n                    _DIAG.rejected("DESTINATION_OPENING_OR_HORIZON")\n                    continue\n                c = cost(\n                    ("DWELL"'),
        ('                if any(v > b for v, b in zip(final_dose, budgets)):\n                    continue', '                if any(v > b for v, b in zip(final_dose, budgets)):\n                    _DIAG.rejected("DESTINATION_CUMULATIVE_DOSE")\n                    continue'),
        ('                checked = check_route(graph, hazard, request, legs, node)', '                checked = check_route(graph, hazard, request, legs, node)\n                _DIAG.checked(checked, legs, t, node)'),
        ('        metrics["expansions"] += 1\n        if t >= horizon:', '        metrics["expansions"] += 1\n        _DIAG.expanded(node, incoming, t, admission)\n        if t >= horizon:'),
        ('            if (incoming, e["id"]) in forbidden:\n                continue', '            if (incoming, e["id"]) in forbidden:\n                _DIAG.rejected("FORBIDDEN_TURN")\n                continue'),
        ('            end = t + e["travel_ticks"] * dt\n            if end > horizon:\n                continue', '            end = t + e["travel_ticks"] * dt\n            if end > horizon:\n                _DIAG.rejected("EDGE_HORIZON")\n                continue'),
        ('            metrics["wait_candidates"] += 1\n            c = cost(', '            metrics["wait_candidates"] += 1\n            _DIAG.waiting(node, t)\n            c = cost('),
    ]
    for old, new in replacements:
        if source.count(old) != 1:
            raise RuntimeError("Diagnostic source anchor count differs: " + repr(old))
        source = source.replace(old, new, 1)
    module = types.ModuleType("routing._diagnostic_core")
    module.__package__ = "routing"
    module.__dict__["_DIAG"] = recorder
    exec(compile(source, str(path) + ":diagnostic", "exec"), module.__dict__)
    module.edge_occupancies = recorder.geometry_wrapper(module.edge_occupancies)
    module.node_cell = recorder.timed(module.node_cell, "node_geometry")
    module.evaluate_occupancy = recorder.timed(module.evaluate_occupancy, "exposure")
    module._lower_bounds = recorder.timed(module._lower_bounds, "heuristic")
    module.check_route = recorder.timed(module.check_route, "checking")
    return module, hashlib.sha256(path.read_bytes()).hexdigest(), hashlib.sha256(source.encode()).hexdigest()


def solve_profiled(graph, hazard, request, *, prepared=None):
    recorder = Recorder(request)
    module, source_hash, instrumented_hash = _instrumented_module(recorder)
    before = time.perf_counter()
    result = module.solve(graph, hazard, request, prepared=prepared)
    elapsed = time.perf_counter() - before
    report = recorder.report(result)
    report["solve_call_wall_s"] = elapsed
    report["source_sha256"] = source_hash
    report["instrumented_source_sha256"] = instrumented_hash
    return result, report
