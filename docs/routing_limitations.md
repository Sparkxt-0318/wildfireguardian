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

⚠ **§7 was added on 2026-09-12 and is not one of the five either.** WFG-262's
independent reviewer pointed out that both repairs, and the whole review that
produced §1 to §5, had stayed on the **459 resident** series, while the sheet
the booth physically hands a judge is the **439 responder** series. Same defect,
third arm, and the only one that had never been audited at all. It changed a
third A4 sheet sentence, on the same wording-only terms.

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
classifier branches only on `reached` and `enters_hazard`, and **until this row
nothing in the tree read that note** — critic #70 measured one grep hit, the
definition itself. So such an origin landed in `no_safe_route` and printed that
bucket's line, and for a rural elderly resident 「we searched and found nothing」
and 「the fire is already at your house」 are opposite dispatch decisions.

**What changed.** The note is now the named constant `ORIGIN_REFUSED_NOTE`,
`live/pipeline.py` reads it, and an origin refused this way gets its own sheet
line — 「출발 지점이 이미 통행 불가 기준 이상, 경로 탐색 없음」 — **inside**
`no_safe_route`. No bucket is added, the partition assertion is untouched, and
every committed count holds.

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
artifact — the origin counts are the registered `mr_yeongdeok_n_origins`,
`mr_uiseong_n_origins` and `mr_uljin_n_origins`, and both numbers per region are
recorded in the artifact's `identity_controls` block — and for the two regions whose
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

## 7. The sheet the booth hands over: `no_surviving_vehicle_ingress` named a cause too

**Found by WFG-262's independent reviewer (2026-09-12) as that lap's root
objection, measured and repaired here (WFG-264).** <!-- forbidden-ok: 264, this is the BACKLOG ROW ID WFG-264 and not the gangneung_donghae_2022 Build-A positive count the gate anchors that value to. Same false-positive class as ba437f5, where the gate read a lap stamp as a camera count. No figure is asserted on this line. --> §1 and §6 are this same audit
on the two walk-side buckets. They are the only two sheet-sentence audits above
this one — the other four sections are about other things — and **both are on
the 459 resident series**, which prints to
`outputs/live/replay/`. The sheet a judge is physically handed at the booth is
the **439 responder series**: `docs/auto/JUDGE_QA.md` sends the student to
`outputs/dispatch/`, and `scripts/generate_dispatch_outputs.py` is the script
that builds it. Nobody had read its unreachable condition.

**The code condition.** `rescue.build_dispatch_list` puts a home in the
unreachable set iff `rescue.rescuer_reachable` returns False, and that function
is a loop over every depot which keeps a depot only when its survival-aware
responder route satisfies `reached and not enters_hazard`:

    the resident cannot self-evacuate on foot
      AND for every depot, the survival-aware responder route either did not
          reach the home or was marked as entering the hazard

That is all of it. Nothing in it distinguishes *why*.

### Three return sites, one sentence

`rescuer_route` is `evacuation.future_aware_route` called with the **depot** as
`start` and the home as the only shelter. So three distinct returns collapse into
this class:

| # | return site | what actually happened |
|---|---|---|
| A | the pre-search refusal | the **depot's own node** is already at or above the vehicle cutoff at dispatch time, and the function returns before one edge is relaxed |
| B | Dijkstra exhausted | merges three worlds: the 75-minute responder budget ran out, the ceil-rounded hazard gate closed every edge, **or the drive graph has no depot→home path at all** |
| C | reached but `enters_hazard` | a route was found and reached the home, and exact-time evaluation marked it as crossing the cutoff |

⚠ **(A) is not (B) with a different flavour, and it is not the branch WFG-262
measured at zero.** §6's zero is structural because all three copies of
`candidate_origins` filter *origins* by the same predicate the branch tests.
**Nothing in this repository filters depots that way.** The 439 arm's start node
is a depot, so §6's argument does not transfer, which is why this row was
forbidden to repair the sentence by analogy.

### What the sentence asserted, and the three ways it can be wrong

The sheet printed 「예산 내 차량 진입로가 화재로 차단됨(우회 포함)」 — 「the
vehicle access road within budget is blocked by fire, detours included」. It
asserts a cause (fire), a resource (a budget consumed) and a procedure (detours
tried). Each is reproduced false below, on a constructed field, deterministically
(`tests/test_vehicle_unreachable_split.py`; no clock, no network, no file outside
the repository):

⚠ **Every row below is a CONSTRUCTED field, not a committed 영덕 household.**
They show these return sites are reachable by this code and that the sentence is
false when they fire. Which of them fired on the committed run is **not
measured** and is not measurable from the committed artifacts — see the end of
this section.

| constructed case | fire in the field | what the sheet said | what happened |
|---|---|---|---|
| depot inside the cutoff at dispatch | yes, on the depot | detours included | site (A): the router returned before relaxing an edge; **no detour was tried** |
| home on a disconnected road component | **none anywhere** | blocked by fire | site (B): there is no road, and no fire |
| only path longer than the responder budget | **none anywhere** | blocked by fire | site (B): the budget bound, and no fire |

### What the committed 영덕 fields say

⚠ **Read the provenance before the counts.** Both artifacts are the 영덕
**PARTIAL REAL FLIP**: the drive network, refuges and depots are real OSM
geometry, and the fire **hazard and terrain are SYNTHETIC**, in the artifacts'
own words 「absolute magnitudes stay illustrative until the real hazard is
flipped in」. These counts are therefore statements about **what this committed
run recorded**, which is exactly what they are used for here — the question is
what the sheet asserted about its own run — and they are not measurements of how
often a real 영덕 fire strands a real household.

Measured by `scripts/measure_vehicle_unreachable_split.py`, which opens two
committed artifacts and nothing else — no re-run, no refit, no committed count
moved. `build_dispatch_list` stores `best_closing_window_min` for context: the
best **direct-corridor** closing window over all depots, from `assess_ingress`,
with an infinity mapped to `null`. Since `reachable` is
`survival >= eta + margin` and `assess_ingress` returns a feasible corridor when
one exists and the largest window otherwise, two things are readable off the
committed file:

| | committed dispatch slice | full-coverage re-run |
|---|---:|---:|
| homes in the class | 24 | 32 |
| no finite best closing window | **0** | **0** |
| direct corridor survives to or past the responder's ETA (window ≥ 0) | **4** | **8** |
| direct corridor reachable by the screening test itself (window ≥ 12 min) | **1** | **4** |

⚠ **The second row was nearly published as something it is not, and the
reproduction above is what stopped it.** The draft of this section read a `null`
window as 「no drive path from any depot at all」, because `ingress_corridor`'s
`NetworkXNoPath` branch stores `-inf`. It is an infinity of **either** sign: a
corridor the fire never crosses has infinite survival and stores `+inf`. The
over-budget case in `tests/test_vehicle_unreachable_split.py` is exactly that —
a road, no fire, a null window — and it failed the assertion the draft had
written. So the zero rules out **both** worlds together and neither separately,
which is a weaker claim than the draft made and the one the field supports: every
home in the class had at least one depot with a road, on a corridor the fire
does cross.

Registered as the eight `vus_` keys. Identity controls, required before any count
above was written: `len(unreachable_homes)` re-derives against **both**
`four_way_counts` and `responder_exposure` on each arm, `four_way_sums_to_n` is
true, and the 12-minute threshold is **read out of each artifact's own
`provenance.assumed`** rather than typed into the script — a margin the script
had to supply would be a parameter of the measurement instead of a property of
the run.

**The sub-case is empty on both fields, and an empty sub-case is published as an
empty sub-case** (the WFG-262 discipline). The row's pre-registration said the
count would probably be zero, before the number existed; what it did not
anticipate is that the zero would turn out to answer a broader question than the
one it was asked.

**The last row is the one that mattered.** A stored window at or above the
margin can only have come from `assess_ingress`'s *feasible* branch: for that
home the direct-corridor screening returned `reachable=True` — a corridor whose
earliest fire-cutoff crossing is a full safety margin after the responder's ETA
— while the survival-aware router returned no route. The sheet told a dispatcher
the access road was blocked by fire.

⚠ **What this does NOT show, said plainly.** It is **not** a misclassification
count and no home is claimed to be reachable. `rescuer_reachable` is the decider
by design, it is the more conservative of the two tests, and a rescue tool that
errs conservatively about sending a vehicle into a fire is erring the right way.
It is also **not** a split by return site: the committed artifacts do not record
which of (A), (B), (C) fired for each home, and recovering that would mean
re-running the scan, which this row is forbidden to do. The finding is about the
**sentence**: a class whose condition is 「no survival-aware ingress route was
confirmed」 was printing 「fire blocked the road, and we tried detours」.

**The one change made.** `scripts/generate_dispatch_outputs.py` now names the
line as a constant, `UNREACHABLE_REASON_KO`, and prints
「어느 거점에서도 생존 인지 차량 진입 경로가 확인되지 않음」 — every depot was
tried and no survival-aware ingress route was confirmed, which is the code
condition and nothing more. Checked before changing, and this is the whole of
`Done when` (c): **no test pinned the old string** — one grep over `tests/` for
it returns nothing, and the delivery layer's byte-identity defaults
(`printable.UNREACHABLE_REASON_FALLBACK` and the two headings) are untouched,
because the 439 sheets always supply their own `reason_ko` and never reach that
fallback. The superseded sentence is kept in the same module as
`SUPERSEDED_UNREACHABLE_REASON_KO` and in `live_pipeline.md`'s record table.
**Committed run directories under `outputs/dispatch*` keep the sentence they
were generated with, as records, exactly as §1 and §6 left theirs** — 44 files
under `outputs/` carry it and not one is rewritten. They are a record of what was
generated on 2026-08-01, not a statement this repository makes today.

⚠ **One cost, named rather than discovered later.** The new line is longer than
the old one — **32 characters against 27**, counting every code point including
spaces, which is the convention stated here because no other one was used to
produce it — and the 사유 column is on a page-budget gate
(`tests/test_sparsity_and_page_budget.py`). The committed sheets are not
regenerated, so nothing committed moves; a student who reprints the kit with
`--split-unreachable` has the overflow escape the script already ships.
`tests/test_vehicle_unreachable_split.py` re-derives both lengths from the two
constants, so this pair cannot drift from the strings it describes.

⚠ **The first draft of that parenthesis said 「29 against 26」, which is not the
length of either string under any convention, and this lap's independent reviewer
found it.** It was typed from an impression rather than measured, in the one
section of this repository whose whole subject is a sentence that asserted more
than it had established. Recorded rather than quietly corrected, because that is
the failure mode §7 exists to name.

---

*Cross-references: `budget_sweep.md` (§1's bucket), `slope_integration.md` and
`budget_sweep.md` (§2's minimisation phrasing), `operator_screen.md` /
`live_pipeline.md` (§3's sheets), `service_layer.md` §5 (determinism
guarantees §4 leans on), `MODEL_CARD.md` (§5's committed ranking),
`multi_region.md` §3.1 and `present_perimeter_yeongdeok.md` §4 (§6's three
committed bucket counts).*
