"""Invented small examples only, no repository or actual study imports/data."""
from fractions import Fraction as Q
from math import comb, isclose
from pathlib import Path
import json
import platform
import numpy as np
import sklearn
from sklearn.metrics import average_precision_score
from synthetic_estimands import ap


def vectors(total, length):
    if length == 1:
        yield (total,)
    else:
        for first in range(total + 1):
            for tail in vectors(total - first, length - 1):
                yield (first, *tail)


def group_once(fires):
    groups = {}
    for f, rows in enumerate(fires):
        for y, p in rows:
            counts, positives = groups.setdefault(p, ([0] * len(fires), [0] * len(fires)))
            counts[f] += 1
            positives[f] += y
    return [(p, *groups[p]) for p in sorted(groups, reverse=True)]


def cached_ap(groups, multiplicity):
    positive_total = sum(sum(m * a for m, a in zip(multiplicity, positives))
                         for _, _, positives in groups)
    if positive_total == 0:
        return None
    seen = hit = 0
    result = Q(0)
    for _, counts, positives in groups:
        n = sum(m * count for m, count in zip(multiplicity, counts))
        added = sum(m * count for m, count in zip(multiplicity, positives))
        if n == 0:
            continue
        seen += n
        hit += added
        result += Q(added, positive_total) * Q(hit, seen)
    return result


# Unequal fire sizes, cross-fire ties, two no-positive fires, and an all-positive fire.
labels = [[1, 0], [0, 0, 0], [1, 1], [1, 0, 0], [0], [1, 0, 1]]
scores = [
    [[Q(1, 2), Q(1, 2)], [Q(9, 10), Q(1, 2), Q(1, 10)], [Q(1, 2), Q(1, 10)],
     [Q(9, 10), Q(9, 10), Q(1, 10)], [Q(9, 10)], [Q(1, 10), Q(1, 2), Q(9, 10)]],
    [[Q(1, 10), Q(9, 10)], [Q(1, 2), Q(1, 2), Q(1, 2)], [Q(9, 10), Q(9, 10)],
     [Q(1, 2), Q(1, 10), Q(9, 10)], [Q(1, 10)], [Q(9, 10), Q(1, 10), Q(1, 2)]]
]
results = []
paired_checks = paired_defined = paired_null = wrong_draw_detected = 0
for f_count in (4, 6):
    multiplicities = list(vectors(f_count, f_count))
    assert len(multiplicities) == comb(2 * f_count - 1, f_count - 1)
    for model, model_scores in enumerate(scores):
        fires = [list(zip(labels[f], model_scores[f])) for f in range(f_count)]
        grouped = group_once(fires)
        flat = [row for fire in fires for row in fire]
        y, p = zip(*flat)
        defined = undefined = 0
        cache = {}
        for m in multiplicities:
            literal = [row for f, fire in enumerate(fires) for _ in range(m[f]) for row in fire]
            value = cached_ap(grouped, m)
            assert value == ap(literal)
            cache[m] = value
            weights = [m[f] for f, fire in enumerate(fires) for _ in fire]
            if value is None:
                assert sum(yi * w for yi, w in zip(y, weights)) == 0
                undefined += 1
            else:
                weighted = average_precision_score(np.array(y), np.array(p, dtype=float),
                                                   sample_weight=np.array(weights))
                assert isclose(float(value), weighted, rel_tol=0, abs_tol=2e-15)
                defined += 1
        # Repeated request is an identical cache lookup, never an extra effective draw.
        assert cache[multiplicities[0]] == cached_ap(grouped, multiplicities[0])
        assert cached_ap(grouped, (1,) * f_count) == ap(flat)
        results.append(dict(status="PASS", fires=f_count, model=model, multiplicity_vectors=len(multiplicities),
                            exact_literal_concat_matches=len(multiplicities), sklearn_weighted_matches=defined,
                            undefined_no_positive_vectors=undefined, cached_repeated_request="identical"))
        for reference in ("persistence", "dilation_best"):
            reference_fires = [[(yi, Q(0) if reference == "persistence" else Q((j + f) % 2))
                                for j, yi in enumerate(labels[f])] for f in range(f_count)]
            reference_groups = group_once(reference_fires)
            for m in multiplicities:
                c, r = cache[m], cached_ap(reference_groups, m)
                literal_reference = [row for f, fire in enumerate(reference_fires)
                                     for _ in range(m[f]) for row in fire]
                assert r == ap(literal_reference)
                paired_checks += 1
                if c is None or r is None:
                    assert c is None and r is None
                    paired_null += 1
                    continue
                literal_candidate = [row for f, fire in enumerate(fires)
                                     for _ in range(m[f]) for row in fire]
                assert c-r == ap(literal_candidate)-ap(literal_reference)
                paired_defined += 1
                wrong_reference = cached_ap(reference_groups, tuple(reversed(m)))
                if wrong_reference is not None and wrong_reference != r:
                    wrong_draw_detected += 1
assert wrong_draw_detected > 0

# The real study would use the canonical 10,000 sampled draws, not uniform vectors.
# Multiplicity-vector probabilities differ, so quantiles must retain draw frequencies.
ordered_draws = [(0, 0, 0), (0, 0, 1), (0, 1, 0), (1, 0, 0)]
cache_keys = [tuple(draw.count(f) for f in range(3)) for draw in ordered_draws]
assert len(set(cache_keys)) == 2 and cache_keys.count((2, 1, 0)) == 3
small_fires = [list(zip(labels[f], scores[0][f])) for f in range(3)]
small_groups = group_once(small_fires)
expanded_cache = [cached_ap(small_groups, m) for m in cache_keys]
literal_draws = [ap([row for f in draw for row in small_fires[f]]) for draw in ordered_draws]
assert expanded_cache == literal_draws
assert sum(expanded_cache) / len(expanded_cache) != sum(set(expanded_cache)) / len(set(expanded_cache))
policy = dict(whole_fire_draws=10000, seed=20261030,
              cache_only=True, quantiles_weight_actual_draw_frequencies=True,
              any_undefined_draw_full_95_interval=None,
              conditional_interval_if_reported="separate and explicitly conditioned on a positive-label draw",
              missing_expected_fire="complete-cohort supplement unavailable, no available-fire-only resampling")
out = dict(status="PASS", model_cohort_checks=len(results), results=results,
           frequency_control="PASS", policy=policy,
           paired_ap_controls=dict(comparisons=paired_checks, defined=paired_defined, null=paired_null,
                                   exact_literal_differences="PASS", unpaired_reference_draw_detected=wrong_draw_detected,
                                   references=["persistence", "dilation_best"], sign="positive favours candidate"),
           runtime=dict(python=platform.python_version(), numpy=np.__version__, sklearn=sklearn.__version__),
           scope="Only invented data: 497 multiplicity vectors per model, exact rational literal-concatenation agreement; no actual arrays/models/metrics")
Path(__file__).with_name("SYNTHETIC_CACHED_AP_CONTROLS.json").write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(dict(status=out["status"], cohort_model_checks=len(results),
                      literal_comparisons=sum(r["exact_literal_concat_matches"] for r in results),
                      sklearn_comparisons=sum(r["sklearn_weighted_matches"] for r in results),
                      paired_ap_comparisons=paired_checks)))
