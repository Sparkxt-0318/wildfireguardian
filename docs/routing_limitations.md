# Routing-layer limitations — measured, recorded, deliberately not fixed

Round-4 review (2026-08-09/10) examined the routing mathematics against what
the documents say about it and found five places where they disagree, or where
the code's behaviour is narrower than its description. **None of these is
fixed, on purpose**: every committed count in this repository — the 459 series,
the three-region table, the budget sweep, the dispatch lists — was produced by
this code as it stands, and changing the logic would move all of them at once
(HANDOFF §5 rules 2 and 18). Paired contrasts are unaffected throughout: both
arms of every contrast run through the same code, so these limits divide out.

What changed instead: one A4 sheet sentence (§1), one docstring that stated a
direction backwards (`routing/hazard.py`, the past-horizon clamp), and one
docstring that called a row-weighted average a fold average (`spread_v2/model.py`).
Wording only; no classification, cost, or exposure computation moved.

---

## 1. `fa_exceeds_budget` names a cause the code does not establish

**The code condition** ([live/pipeline.py](../src/wildfireguardian/live/pipeline.py),
classification chain) is only:

    naive route does not enter the hazard  AND  future-aware search reached no refuge

Nothing in it distinguishes *why* the future-aware search failed. The budget is
one reason. Another is **time discretisation**: the router scores hazard at the
edge's arrival time rounded up to the next bin, so a node whose interpolated
risk crosses the cutoff *between* bins can block every detour while the budget
is nowhere near binding.

**Reproduced, not hypothesised**: a constructed field puts an origin in this
bucket at the full 600-minute budget — the naive route scores safe under
exact-time evaluation, every future-aware alternative is blocked by the
ceil-rounded bin's 0.6 ≥ 0.5 gate, and the budget never binds.

**What the documents say**: `budget_sweep.md` ("fa_exceeds_budget is 0 at 600
minutes on the canonical field too", §"the sixth category") and
`tests/test_partition_categories.py`'s docstring treat the bucket as
budget-caused by definition. `multi_region.md` §3.1 describes the non-Yeongdeok
600-minute entries (2 and 3) as "FA cannot finish in time"; HANDOFF §2 records
"9 and 4" for a different arm of the same comparison. Both readings are
reported here as written; neither is adjudicated, because adjudicating would
mean re-running committed scans.

**What is safe to say**: the committed Yeongdeok canonical count for this
bucket is 0, so nothing Yeongdeok reports rests on the ambiguity. For the two
regions where the bucket is non-empty, say "the future-aware search did not
complete within the scan's constraints", not "the budget was exceeded".

**The one change made**: the A4 route-note for this bucket used to print
「보행 경로는 있으나 대피 시간 예산 초과」 — a cause assertion. It now prints
「직행 경로는 화재를 지나지 않으나 예산 내 안전 도달은 확인되지 않음」, which
is exactly the code condition and nothing more. No byte-identity test pins the
old sentence (checked before changing: the delivery-layer identity tests cover
the 439-series defaults, and `test_every_actionable_bucket_has_operator_readable_korean_text`
checks only that the text is non-empty Korean). Committed run directories keep
the sentence they were generated with, as records.

## 2. The objective the router minimises is not the number the report prints

Two Riemann approximations of the same integral:

| | risk sampled at | time point | where |
|---|---|---|---|
| **optimisation objective** | the edge's **head** (arrival node) | arrival time **rounded up** to the next bin | `routing/evacuation.py`, future-aware relaxation (`nexp = exp_u + hv·tt`) |
| **reported exposure** | the edge's **tail** (departure node) | **exact** departure time | `routing/evacuation.py::_evaluate_path` |

Right-endpoint-on-rounded-bins versus left-endpoint-on-exact-times. On a field
where risk rises over an edge's traversal, the two orderings can disagree: a
constructed two-route example (equal travel times) has the optimiser choose the
path whose *reported* exposure is **2.22×** the alternative's.

**What this bounds, and what it does not**:

- The headline **72.0 % exposure reduction** and every fire-blind-vs-future-aware
  contrast are **valid as contrasts** — both arms are scored by the same
  `_evaluate_path`, so the scoring convention divides out.
- An **absolute** exposure value ("the evacuee's exposure was X prob·min")
  inherits the convention and should not be quoted as if the route provably
  minimised that exact quantity. Quote contrasts.
- Documents that say `future_aware_route` "minimises cumulative exposure"
  (`slope_integration.md`, `budget_sweep.md`) are describing the design intent;
  the minimised functional is the right-endpoint rounded-bin approximation
  above.

## 3. 「남은 시간」 is quantised to the field's slice grid

`_time_to_cutoff` ([live/pipeline.py](../src/wildfireguardian/live/pipeline.py))
and its structural twins (`evacuation.py`, `rescue.py::corridor_survival_time`)
check **only the field's stored slice times**, so the returned "time until this
point's risk crosses the cutoff" is always a slice timestamp — an **upper**
bound, late by up to one slice against the interpolated crossing.

On the canonical Yeongdeok field the slices are 0/180/360/540/720 min, and the
candidate rule excludes points already over the cutoff at t=0, so the A4
「남은 시간」 column can only read **180 / 360 / 540 / 720 / 확인 불가**:

- the printable layer's urgency tag (`< 30 min` → 긴급) and the "already
  elapsed" state are **structurally unreachable on this field** — not broken,
  but dead until a field with finer slices exists;
- the dispatch sort (closing window ascending) ties in blocks; order within a
  tie is the stable scan order, which is deterministic but not meaningful;
- `rescue.py`'s reachability margin (12 min) is smaller than every slice
  spacing in use (15–180 min), so the margin can be swallowed by the same
  quantisation on the rescue side.

Note the asymmetry: the **router's** hazard gate rounds arrival times **up**
into 10-minute bins (conservative), while the **display's** remaining-time
reads slices only (optimistic). Two layers, two conventions, both recorded
here. The sheets' figures are what the committed pipeline has always printed.

## 4. The time-expanded search is not provably optimal (and is deterministic)

The Dijkstra state is `(node, time_bin)` but the exact clock rides along in the
priority-queue tuple, so it is **path-dependent within a bin**: if a
lower-exposure-but-later-clock path is settled first for a state, downstream
bin lookups and budget checks use that later clock, and the strict-improvement
update (`nexp < dist − 1e-12`) discards an equal-exposure earlier-clock path
that arrives afterwards. Consequences:

- "minimises cumulative exposure" holds under the state abstraction, not as a
  proven property over exact-clock paths; the docstring's exposure-tie →
  earlier-arrival preference operates only through heap ordering;
- **no counterexample has been constructed** at the 10-minute bins in use —
  the window for one is narrow — so this is recorded as a theoretical limit,
  not an observed defect;
- determinism is unaffected: heap order is total and the committed results
  reproduce.

## 5. Permutation importance is a row-weighted average, not a fold mean

`model.py` aggregates each feature's per-fold AUC drop with
`np.average(drops, weights=held_out_row_counts)`. The uiseong_andong fold holds
~54 % of all rows, so the committed importance ranking is dominated by the
largest fire, and "averaged over folds" (the docstring's old wording, now
corrected) overstated the symmetry. The committed values are what they are —
this changes their *reading*: an importance rank is mostly the big fold's rank.
`weather_dependency.md` §1 group sums inherit the same weighting.

---

*Cross-references: `budget_sweep.md` (§1's bucket), `slope_integration.md` and
`budget_sweep.md` (§2's minimisation phrasing), `operator_screen.md` /
`live_pipeline.md` (§3's sheets), `service_layer.md` §5 (determinism
guarantees §4 leans on), `MODEL_CARD.md` (§5's committed ranking).*
