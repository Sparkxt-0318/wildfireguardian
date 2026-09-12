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

⚠ **§6 was added on 2026-09-12 and is not one of the five.** The Round-4 review
found five; critic #70 found a sixth on 2026-09-11 — the *same* defect as §1, in
the bucket defined one line above §1's in the same dict, which the Round-4 sweep
did not carry across. It is recorded here rather than renumbered into the
original five, because 「the review found five and missed the neighbour of one of
them」 is the finding. It changed a second A4 sheet sentence, on the same
wording-only terms.

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

## 6. `no_safe_route` named a cause too, and the audit §1 ran was never run on it

**Found by critic #70 (2026-09-11), measured and repaired by the WFG-262 lap
(2026-09-12).** §1 is this same audit on `fa_exceeds_budget`, the bucket defined
one line above `no_safe_route` in the same dict. It was never run on the
neighbour, and the neighbour is the bucket that is non-empty on all three
regions.

**The code condition** ([live/pipeline.py](../src/wildfireguardian/live/pipeline.py),
classification chain) is only:

    naive route enters the hazard  AND  future-aware search reached no refuge

**The sentence it used to print** on the A4 sheet was 「예산 내 안전한 보행
경로가 없음(우회 포함)」 — 「no safe walking route within budget, detours
included」. That asserts two things the condition does not establish: that a
budget was consumed, and that detours were tried and exhausted. `reached=False`
is also produced by the ceil-rounded hazard gate closing every alternative with
the budget nowhere near binding, which is §1's mechanism unchanged. **The one
change made**: the sheet now prints 「직행 경로는 화재를 지나고 안전한 우회
도달은 확인되지 않음」, which is the code condition and nothing more. Committed
run directories under `outputs/live/replay/` keep the sentence they were
generated with, as records, exactly as §1 left them.

### The member that would have made it worse, and how many there are

`routing/evacuation.py` (future-aware search, the pre-search guard) returns
`reached=False, enters_hazard=True` **before any search runs**, when the
origin's own node is already at or above `p_cut` at departure, carrying
`note="origin already at/above the impassable cutoff at departure"`. The
classifier branches only on `reached` and `enters_hazard` and **never reads
`note`**, so such an origin would land in `no_safe_route` — and for a rural
elderly resident 「we searched and found nothing」 and 「the fire is already at
your house」 are opposite dispatch decisions.

**The row that filed this assumed at least one such member existed. It was
measured instead, and there are none.**
`scripts/measure_no_safe_route_origin_split.py` rebuilds each region's node set
from the committed walk snapshot, imports the committed origin rule rather than
restating it, and reads the branch predicate off `build_time_expanded_field`'s
own table at column 0:

| region | committed `no_safe_route` | refused before any search |
|---|---|---|
| 영덕 2025 (canonical) | 2 | **0** |
| 의성·안동 2025 | 12 | **0** |
| 울진·삼척 2022 | 10 | **0** |

Identity controls, all three required before any count above is believed:
`n_nodes` and `n_origins_scanned` re-derive exactly against each committed
artifact (8443 / 458, 6678 / 368, 7300 / 393), and for the two regions whose
artifact recorded `origin_nodes_by_bucket`, every listed member was checked
individually rather than inferred from the aggregate. Registered as the four
`nsr_` keys. **No committed count moved and no arm was refit**; the interpretation
was written into the claim commit before the numbers existed, both ways.

### Why the zero is structural, and why it still needs a test

All three copies of `candidate_origins`
(`run_real_roads_real_hazard_slope.py`, `run_multi_region_routing.py`,
`live/pipeline.py`) skip a node with `hazard.prob_at(x, y, 0.0) >= p_cut`, and
`build_time_expanded_field` fills `table[:, 0]` with
`prob_at_points(nx, ny, departure_min + 0)`. At `departure_min = 0` those are
**the same predicate on the same node**, so every origin that could trigger the
guard was removed before the scan began.

**What this does NOT show.** It does not license the old sheet sentence: §1's
mechanism needs no unsearched member, which is why the wording changed anyway.
It says nothing about a scan called with `departure_min > 0`, where the two
predicates read different columns and the guard becomes reachable. And the
protection is unnamed: it lives three files from the branch it protects, in
three duplicated copies, and until this row nothing tied the two predicates
together. **The margin is also thin** — 영덕's largest departure-time
probability over scanned origins is `nsr_max_departure_prob_yeongdeok`, which
clears the 0.5 cutoff by under half a hundredth. The invariant holds by
arithmetic, not by design intent, and `tests/test_no_safe_route_origin_split.py`
is what will notice when it stops holding.

⚠ **What the tests do not cover, said plainly.** They pin the guard's behaviour,
that its note has a reader, that both sheet lines assert no cause, and that all
three origin rules still carry the filter. They do **not** exercise
`route_region`'s refused-origin branch end to end, because that branch fires for
zero origins on every committed field and the classification loop is inline
rather than extracted. Pulling it out to make it testable would be a refactor,
and this row is a label and a sentence. So the branch is reasoned and reviewed,
not executed: if it ever fires in a real run, that run is the first execution of
those three lines.

---

*Cross-references: `budget_sweep.md` (§1's bucket), `slope_integration.md` and
`budget_sweep.md` (§2's minimisation phrasing), `operator_screen.md` /
`live_pipeline.md` (§3's sheets), `service_layer.md` §5 (determinism
guarantees §4 leans on), `MODEL_CARD.md` (§5's committed ranking),
`multi_region.md` §3.1 and `present_perimeter_yeongdeok.md` §4 (§6's three
committed bucket counts).*
