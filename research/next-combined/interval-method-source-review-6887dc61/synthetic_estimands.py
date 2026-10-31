"""Tiny invented-fire estimand controls, no repository imports or actual data."""
from fractions import Fraction as Q
from itertools import permutations
import json
from pathlib import Path


def ap(rows):
    positives = sum(y for y, _ in rows)
    if positives == 0:
        return None
    grouped = {}
    for y, p in rows:
        count, hit = grouped.get(p, (0, 0))
        grouped[p] = count + 1, hit + y
    total = hit = 0
    value = Q(0)
    for p in sorted(grouped, reverse=True):
        count, added = grouped[p]
        total += count
        hit += added
        value += Q(added, positives) * Q(hit, total)
    return value


def need(name, condition, evidence):
    if not condition:
        raise AssertionError(name)
    checks.append(dict(name=name, status="PASS", evidence=evidence))


checks = []
# Different fire sizes force the macro and pooled targets apart.
n, candidate_sse, reference_sse = [1, 3], [Q(1), Q(0)], [Q(1), Q(3)]
pooled = sum(candidate_sse) / sum(n)
macro = sum(s / k for s, k in zip(candidate_sse, n)) / 2
need("pooled_brier_is_not_equal_fire_mean", pooled == Q(1, 4) and macro == Q(1, 2),
     dict(pooled=str(pooled), equal_fire=str(macro)))
# One whole-fire draw includes every entry of the sampled fire, with multiplicity.
selection = [1, 1]
draw_value = sum(candidate_sse[i] for i in selection) / sum(n[i] for i in selection)
need("whole_fire_multiplicity_changes_denominator", draw_value == 0 and sum(n[i] for i in selection) == 6,
     dict(sampled_fires=selection, draw_entries=6))
paired = (sum(candidate_sse) - sum(reference_sse)) / sum(n)
macro_difference = sum((s-r)/k for s, r, k in zip(candidate_sse, reference_sse, n)) / 2
need("paired_pooled_brier_difference_is_not_macro_difference", paired == -Q(3,4) and macro_difference == -Q(1,2),
     dict(pooled_difference=str(paired), macro_difference=str(macro_difference)))
bss = 1 - sum(candidate_sse) / sum(reference_sse)
macro_bss = sum(1-s/r for s,r in zip(candidate_sse,reference_sse)) / 2
need("bss_ratio_of_sums_is_not_mean_fire_bss", bss == Q(3,4) and macro_bss == Q(1,2),
     dict(pooled_bss=str(bss), mean_fire_bss=str(macro_bss)))
# Pooled AP must rerank all selected entries; it cannot be made from per-fire AP scalars.
a = [(1,Q(1,10)), (0,Q(2,10))]
b = [(1,Q(9,10)), (0,Q(8,10)), (0,Q(7,10)), (0,Q(6,10))]
need("pooled_ap_is_not_macro_ap", ap(a+b) == Q(2,3) and (ap(a)+ap(b))/2 == Q(3,4),
     dict(pooled_ap=str(ap(a+b)), macro_ap=str((ap(a)+ap(b))/2)))
need("duplicate_fire_ap_recomputed_as_multiset", ap(a+a+b) == Q(7,12) and ap(a+a+b) != (2*ap(a)+ap(b))/3,
     dict(pooled_duplicate_ap=str(ap(a+a+b))))
tie_rows = [(1,Q(1,2)), (0,Q(1,2)), (1,Q(1,2))]
need("tie_group_ap_is_order_invariant", all(ap(list(order)) == Q(2,3) for order in permutations(tie_rows)),
     dict(expected_ap="2/3", permutations=6))
need("all_positive_ap_remains_defined", ap([(1,Q(1,10)),(1,Q(9,10))]) == 1,
     dict(expected_ap="1"))
zero = [(0,Q(1,5)),(0,Q(1,3))]
need("no_positive_ap_is_unavailable_not_zero", ap(zero) is None, dict(expected_ap=None))
fire_rows = [a,zero]
values = [ap(fire_rows[i]+fire_rows[j]) for i in range(2) for j in range(2)]
need("undefined_ap_draw_count_retained", sum(v is None for v in values) == 1 and len(values)==4,
     dict(total_draws=4, defined_draws=3, undefined_no_positive_draws=1, interval_target="conditional_on_defined_draws"))
reference_sse = [Q(1),Q(0)]
need("zero_reference_sse_draw_is_undefined", sum(reference_sse[i] for i in [1,1]) == 0,
     dict(zero_reference_draw_must_not_be_zero_bss=True))
# Pairing means the same fire index draw, never separately selected model populations.
paired_same = sum((candidate_sse[i]-candidate_sse[i]) for i in selection) / sum(n[i] for i in selection)
need("identical_models_have_exact_zero_paired_effect", paired_same == 0,
     dict(expected_difference="0", common_index_draw=selection))
result = dict(status="PASS", controls=len(checks), checks=checks,
              scope="Invented arithmetic only; no actual source arrays, models, predictions or metrics opened or executed")
Path(__file__).with_name("SYNTHETIC_ESTIMAND_CONTROLS.json").write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps(dict(status=result["status"], controls=len(checks))))
