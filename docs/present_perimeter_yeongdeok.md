# The present perimeter, with no buffer, against the Yeongdeok 42

**Row:** WFG-129 · **Specified by:** `paper/GAPS.md` G7, written by the 0323Z paper lap
**Method proposed by:** the loop (G7 wrote the recipe; three earlier critic laps wrote the
objection it answers); **run by:** the dev lap of 2026-09-11T1219Z.
**Artifact:** `data/processed/present_perimeter_yeongdeok_2025.json`
**Script:** `scripts/measure_present_perimeter_yeongdeok.py` · **Registry:** the six
`ppy_yeongdeok_` outcome keys §4 names.
**§7 (WFG-259, 2026-09-11T2122Z) is a second run with its own script, artifact and
prefix** — `scripts/measure_present_perimeter_yeongdeok_buffer.py`,
`data/processed/present_perimeter_buffer_shape_yeongdeok_2025.json`,
`ppy_yeongdeok_buf_*` (15 keys). It changes nothing above it. **§2's slice-0 figures are a
third** (`ppy_yeongdeok_slice0_`, WFG-260).

---

## 1. The objection this answers

The number the booth says out loud, and the judged screen prints, is **42 of 458** on
영덕: origins that reach a refuge only when the router accounts for where the fire **will
be**. Its opponent is `naive_route`, and `naive_route` is **fire-blind** in this
repository's own words — `src/wildfireguardian/routing/evacuation.py:270`, 「Fire-blind
shortest path to the nearest shelter, then scored against the hazard」.

A fire-blind walker is not the status quo. The status quo is somebody who can see where
the fire is **now**. So the 42 credits the **forecast** with everything that merely
**looking out of the window** would already have bought, and until this run nothing in
the repository said how much of it that is. The fair opponent had been built once, on
의성·안동 (`docs/present_perimeter_arm.md`, WFG-114), and most of that region's contrast
did not survive it. On 영덕 — the region the headline is about — it had never been run.

## 2. What was run

| arm | what it knows when it plans | route choice |
|---|---|---|
| fire-blind (control, committed) | nothing | shortest path by `length_m` on the full network |
| **present perimeter, zero buffer (new)** | **where the fire is at slice 0** | the same, on the network minus the burning nodes |
| forecast-aware (committed) | the whole predicted hazard, in time | exposure-minimising on the time-expanded graph |

All three run on the **canonical arm**: `data/processed/routing_demo_canonical.npz`,
slope 60 m sampling, DiGraph, `|slope|` clipped at 0.6, distance-ranked, `p_cut` 0.5,
600-minute budget, stride-18 origin scan — the arm the headline's **42** comes from.

**Slice 0 is the observation, not a simulated slice, and that is why this opponent needs
no model** (WFG-260). ⚠ **The identity itself was already established and registered, one
lap earlier and elsewhere**: `docs/disc_null.md` §2's table and
`data/processed/disc_null_yeongdeok.json :: null_rule` record that `obs_stack[0] > 0` and
`haz_stack[0] >= 0.5` are the same **249** cells (`dn_yeongdeok_t0min_n_cells`,
`dn_yeongdeok_seed_cells_in_model`), and that script aborts if it ever stops being true.
What WFG-260 adds is this page saying it where the claim is made, and one figure nobody
had measured — the component count below. The evidence file is
`data/processed/present_perimeter_yeongdeok_slice0_2025.json`.
`scripts/build_canonical_hazard.py:88`
seeds `forward_simulate` from `snaps[0].cumulative_mask`, the first observed FIRMS cumulative
mask, so the model's first output is slice 1 at 180 min; `src/wildfireguardian/routing/hazard.py:97-100`
collapses the time bracket to `i0 == i1 == 0` at `t_min = 0.0`, so `prob_at(x, y, 0.0)` samples
that observed mask alone and mixes in no later slice; and `haz_stack[0] >= p_cut` is the same
set of cells as `obs_stack[0] > 0` — **249** cells (`dn_yeongdeok_t0min_n_cells`), compared
cell for cell and not by count. Slice 0 holds only `{0, 1}`; slice 1, the model's first
output, holds 3,961 distinct values. ⚠ The object is a **detection scatter**, not a mapped
fire line: those 249 cells of the **500 m** hazard grid, rasterised from VIIRS detections
whose own footprint is 375 m, fall into **226** 8-connected components
(`ppy_yeongdeok_slice0_components_8conn`; 236 at 4-connectivity), the largest **3** cells —
so 「present perimeter」 is a generous word for it, and the thing itself is more honest than
the word.

⚠ **And slice 0 is not neutral ground.** `obs_stack` is **cumulative**, so the `t = 0` seed
sits *inside* the footprint everything is later scored against; the model contains it by
construction and a null does not. `docs/disc_null.md` §3c is where that is paid for, and it
moved that page's headline ratio from 2.5360 to 2.2044 when it was. Reading slice 0 as
「the observation」 is correct about its provenance and says nothing about its innocence.
⚠ This is about the arm's **input** only; the **scoring** side is a different matter and §5
item 6 below is right about it.

The present-perimeter arm is a **node filter and nothing else**. A node is removed when
`hazard.prob_at(x, y, 0.0) >= p_cut`, which is character for character the predicate
`scripts/run_real_roads_real_hazard_slope.candidate_origins` already uses to refuse an
origin that is standing in the fire. No new rule, no new parameter. A refuge inside the
present perimeter is not a refuge and is dropped with the rest. The filtered graph is then
handed to the repository's own `naive_route`, and the result is **scored against the full
forecast** at the same departure time and the same `p_cut` as the other two arms.

So planning sees only the present; scoring sees the forecast. That single difference is
the whole contrast.

**Zero buffer, deliberately.** `docs/present_perimeter_arm.md` swept 250 m to 3 km on
의성·안동 and `docs/present_perimeter_buffer_shape.md` densified that grid; WFG-201
records what that costs — a width chosen after the results is a width chosen to win. Here
no width is swept, so none can be chosen. This is **not** WFG-033(b) and it does not
pre-empt NH-027.

## 3. The reproduction gate

The script writes nothing unless the committed partition re-derives first, in the same
process, from the committed snapshots (the WFG-114 pattern). It did:

| quantity | committed | recomputed here |
|---|---|---|
| origins scanned | 458 | 458 |
| `both_safe` | 414 | 414 |
| `naive_into_FA_safe` | 42 | 42 |
| `no_safe_route` | 2 | 2 |
| every other bucket | 0 | 0 |

A count measured on a tree that no longer reproduces its own baseline is not a measurement
of anything, which is why this table comes before the result rather than after it.

## 4. The result

The target set is `ppy_yeongdeok_target_origins` **44**: every origin whose fire-blind
route **reaches** a refuge and **enters** the forecast — the committed 42 plus the
committed 2. All 44 were reached fire-blind on the unfiltered graph, by the definition of
both buckets.

| outcome | key | count |
|---|---|---|
| the present perimeter alone already gets them out clear of the forecast | `ppy_yeongdeok_saved_by_present_perimeter` | **26** |
| they still walk into the forecast | `ppy_yeongdeok_still_enter_forecast` | **16** |
| they reach no refuge once the perimeter is removed | `ppy_yeongdeok_not_reached_under_filter` | **2** |

**Read in one sentence: of the 44 origins the headline is built on, a router that sees
only where the fire is right now already saves 26, and 16 are left for the forecast to
account for.**

The split is clean along the committed buckets, and that was not arranged:

- all **26** saved and all **16** still entering come out of the committed
  `naive_into_FA_safe` bucket (42 = 26 + 16);
- both origins in the committed `no_safe_route` bucket are the two `not_reached` — the
  same two the committed artifact already says have no safe route at all, now failing for
  the third time under a third router.

**The filter is small, and this is the check that makes the 26 readable.** It removes
`ppy_yeongdeok_filter_nodes_removed` **162** of the walk graph's nodes and
`ppy_yeongdeok_filter_shelters_removed` **1** of its refuges. The objection this run was
pre-registered against — that a node filter can cut a village off from every refuge for
reasons that have nothing to do with the fire, and that 「the present perimeter does not
save them」 would then be indistinguishable from 「my filter cut the graph」 — is answered
by measurement rather than by assertion: the only origins that lose their refuge are the
two that had no safe route under any arm. Where the present perimeter fails on the other
42, it fails by **walking into the forecast**, not by having nowhere to walk.

For the 26 it saves, the detour is real but modest: the median present-perimeter route is
about 800 m longer than the fire-blind one and the longest is about 5.1 km longer
(computed from `per_origin` in the artifact; these two are descriptive and are not
registered, because no page quotes them).

## 5. What this does **not** show

1. **No committed number moves.** The canonical partition is still 414 / 42 / 2, this run
   reproduced it before writing anything, and no route in the committed artifacts was
   re-run. These six keys sit **beside** the 42; they do not replace it.
2. **It is not a margin**, and must not be spoken as one. NH-032, NH-034 and NH-052 are
   open and `docs/auto/DIRECTION.md` bars every margin from every judge-facing surface.
   What this is, is a partition of 44 origins into three named outcomes.
3. **It says nothing about the 91.** 의성·안동 is a different region, measured with a
   different arm and a 1 km buffer (`docs/present_perimeter_arm.md`). Nothing here
   transfers to it in either direction.
4. **One fire, one region, one horizon, one opponent.** The canonical field's own
   envelope-coverage caveat (32.6 % of the final-slice core inside the routing extent)
   applies to this run unchanged, and a second fire could split the 44 any other way.
5. **A buffered present perimeter, swept and scored as the project's opponent of record,
   is a DIFFERENT experiment and this repository has not run it on 영덕. No direction may
   be asserted for that arm here.** ⚠ **Narrowed 2026-09-11T2122Z (WFG-259, `WC-020`):**
   §7 below runs the two widths **this item itself names**, to make this item's own
   figures re-derivable. It sweeps nothing, chooses nothing and nominates no opponent, and
   the un-run experiment above is still un-run. ⚠⚠ The first draft of this
   section said the opposite — that widening the buffer removes more nodes and so can only
   move an origin **out of** `saved`, never into it — and **that is false**. This lap's
   independent reviewer nailed it in the lap, on this lap's own code and this artifact's
   own origin ids: `naive_route` is shortest-path-by-length **scored afterwards**, so
   deleting nodes **reroutes** it, and a reroute can land clear of the forecast. ⚠ **That
   correction was right, and until 2026-09-11T2122Z the two numbers it rests on came from
   a reviewer probe inside a session that had ended and were in no artifact (WFG-259).
   They have now been run, and they reproduce exactly, origin id included: §7 below.**
   Dilating the burning set to a strict superset of the 162 at 100 m moves origin
   `11935180417` from `still_enters_forecast` to **`saved`** — the transition the draft
   said could never happen — and at 500 m, `ppy_yeongdeok_buf_w500m_flipped_to_saved`
   **15** of the 16 flip. ⚠⚠ **Read §7 before quoting either figure.** What the run also
   measured, and what nobody could have read off this sentence, is that the dilated arm
   **saves fewer origins overall at both widths**, so 「15 of the 16 flip」 does **not**
   mean a buffered opponent recovers all but one of the 42. The repository already knew the
   first half and the
   draft cited the row that says so while contradicting it: WFG-201 records that a width
   **added** to the grid can only tie or beat the incumbent, so the opponent's best score
   is **non-decreasing** in how finely anyone searches, and
   `data/processed/present_perimeter_buffer_shape_uiseong_andong_2025.json`'s
   `buffer_sensitivity` shows exactly that on the other region. So: a buffered opponent
   can be **stronger**, this run does not measure it, and whether it should be run on 영덕
   is **NH-027**. The bound-shaped word for the project's headline is **NH-053** and is
   the author's.
6. **The scoring array is the model's own forecast, not where the fire went.** ⚠ 「Saved」
   here means 「clear of the model's own predicted hazard」. The present-perimeter arm is
   filtered from `haz_stack` slice 0 — which is the **observed** FIRMS mask and not a
   simulated slice, §2 above and WFG-260 — and scored against `haz_stack` **as a whole**,
   which from 180 min on is the same leave-one-fire-out forward simulation the
   forecast-aware arm plans on. ⚠ **Scoring is not slices 1-4 either**, and a draft of this
   correction said so and was wrong: `_evaluate_path` scores every node at its arrival time
   starting from `departure_min = 0.0`, so slice 0 is in the scoring field too and every
   node reached before 180 min is scored on a slice-0 ↔ slice-1 blend. That does not soften
   this item — the model's field is still what 「saved」 is measured against — so the
   oracle in this comparison is on the **scoring** side, exactly as `docs/oracle_gap.md`
   §2 and Q36 already say for the headline itself. This run inherits that caveat whole and
   does not reduce it: the 26 / 16 / 2 is a contrast between three routers over one
   predicted field, not a count of people who would have lived. Re-scoring against real
   forecast error is **WFG-213**, `blocked(NH-052)`. This item was added by the lap's
   independent reviewer under `mandela`; the first draft of this section gave only the
   envelope-coverage caveat.
7. **`not_reached` is the filter's doing and not the fire's.** It is reported separately
   and is never folded into either other count. Here it happens to coincide with the two
   origins the committed artifact already calls unsaveable, which is concordance and not
   proof.
8. **Nothing here has been on a judge-facing surface.** The row's own constraint: no
   number from this run reaches the README, the finals screen, the Q&A bank, the booth
   script or the manuscript until the critic or the author has read it. ⚠ The three counts
   ARE written into `paper/GAPS.md` G7, which is the ledger that specified the run and
   records what closed it; that is a loop surface and not the manuscript, and this list is
   not exhaustive without it.

   ⚠ **정정 (2026-09-11T1520Z, WFG-258(a); caught by that lap's independent reviewer, not
   by the lap).** The sentence above is now true only of the **counts**. The **existence
   and the date** of this run are on judge-facing surfaces as of that lap, and deliberately
   so: `README.md`'s TL;DR and its Round-4 item 1, and `docs/auto/JUDGE_QA.md` Q19's spoken
   draft and its prescribed booth sentence, all now say the comparison **has** been run on
   영덕 and link here — because until that lap they said it never had, one window after
   this page disproved them (WFG-258, `WC-019`). ⚠ **No count moved**: not the 26, not the
   16, not the 2, not the 44, on any of them, and
   `tests/test_judge_qa_bank.py::test_no_ppy_count_reaches_a_spoken_draft` is the gate that
   now holds them off a spoken draft. **NH-059** is the author's decision on whether they
   may be spoken, and §6 below stays empty until it is answered. This note exists because
   README links a judge straight to this page, so a reader arrives here from a surface this
   item said did not exist.

## 6. What a judge should hear, once this has been read

Not yet. This section is deliberately empty until the critic lap or the author has read
§4 and §5, which is the constraint WFG-129 was filed with. The sentence it will hold, when
it is licensed, is about the 44 and the three outcomes — never a margin, and never the
bare 26 without the 16 and the 2 beside it.

## 7. The dilation, measured (WFG-259)

**Why this section exists.** §5 item 5 above asserted two figures — one origin flipping at
100 m, and 「at 500 m, 15 of the 16 flip」 — that came from an independent reviewer's probe
inside a session that has ended. They were in no artifact, no registry key was either of
them, and the script that produced the committed 26 / 16 / 2 took no buffer argument. They
were also the most consequential integers on this page, because this page is one click from
`README.md`'s TL;DR and because 「15 of the 16」 reads, at a glance, as 「a router that sees
only where the fire is now, plus half a kilometre, reaches all but one of the origins the
headline **42** credits to the forecast」. CHARTER §3.3: 「A number you cannot register, you
do not write.」 This section is the run.

**Method, pre-registered before the run** in this lap's claim commit `031214b`, because the
word 「dilating」 does not pin the operation. The dilation is in **node space**: a walk-graph
node is refused when its Euclidean distance in projected metres to **any** node of the
committed base burning set — the 162 — is at most `d`. A refuge inside the dilated set is
removed with the rest. The other reading, dilating the burning **raster** cells and
re-thresholding `prob_at`, is a different operation; it was not run, and it was not run
afterwards to see whether it matched this page better. Widths are **0, 100 and 500 m**: the
two already written above, so none could be chosen after the answer, plus `d = 0` as an
identity control. Everything downstream is unchanged — same `naive_route`, same
`departure_min`, same `p_cut`, same scoring against the full forecast, same three outcomes
reported separately.

`scripts/measure_present_perimeter_yeongdeok_buffer.py` writes nothing unless three gates
pass in the same process: the committed 414 / 42 / 2 partition re-derives; the `d = 0` arm
reproduces the committed 26 / 16 / 2 **exactly**; and the 100 m node set is a **strict
superset** of the 162, which is what §5 item 5 itself asserts. All three passed.
Artifact: `data/processed/present_perimeter_buffer_shape_yeongdeok_2025.json`.

### 7.1 The result

| dilation | nodes refused | of the same 44 origins: saved | still entering | not reached | origin refused outright |
|---|---|---|---|---|---|
| 0 m (committed) | 162 | 26 | 16 | 2 | 0 |
| 100 m | `ppy_yeongdeok_buf_w100m_nodes_refused` 227 | `ppy_yeongdeok_buf_w100m_saved` 12 | `ppy_yeongdeok_buf_w100m_still_entering` 26 | `ppy_yeongdeok_buf_w100m_not_reached` 3 | `ppy_yeongdeok_buf_w100m_origins_refused` 3 |
| 500 m | `ppy_yeongdeok_buf_w500m_nodes_refused` 890 | `ppy_yeongdeok_buf_w500m_saved` 18 | `ppy_yeongdeok_buf_w500m_still_entering` 0 | `ppy_yeongdeok_buf_w500m_not_reached` 3 | `ppy_yeongdeok_buf_w500m_origins_refused` 23 |

*(Every cell of the two dilated rows carries a key. The first draft of this table left
the middle two columns as bare integers, which is the same gate hole this row was filed
against, one column over; WFG-259's independent reviewer named it.)*

**§5 item 5's two figures reproduce, exactly.** At 100 m,
`ppy_yeongdeok_buf_w100m_flipped_to_saved` **1** of the 16 origins that still entered the
forecast under the zero-buffer arm moves into `saved`, and it is origin `11935180417` —
the same id the sentence names. At 500 m,
`ppy_yeongdeok_buf_w500m_flipped_to_saved` **15** of those 16 flip. The sentence is true and
is now re-derivable from a committed artifact.

### 7.2 And the inference drawn from it is false

**The buffered arm does not save more. It saves fewer, at both widths.** 26 at zero buffer;
**12** at 100 m; **18** at 500 m. On these three widths the best-scoring opponent is the
**zero-buffer one this page already committed**.

**Where the loss comes from, read off the cross-tabulation** — `transition_matrix_from_zero`
in the artifact, which exists because the first draft of this paragraph inferred it from two
marginal counts that both happen to read 23 and got it wrong (WFG-259's independent reviewer
blocked the lap for it). Of the **26** the zero-buffer arm saved, the 500 m dilation:

- refuses `ppy_yeongdeok_buf_w500m_refused_from_saved` **20** of them **outright** — the
  origin's own node is inside the dilated set, so no route is attempted at all;
- leaves `ppy_yeongdeok_buf_w500m_cut_off_from_saved` **3** more with a plannable origin and
  **no route to any refuge**, which is a different harm and is counted separately;
- still saves `ppy_yeongdeok_buf_w500m_still_saved_from_saved` **3**.

3 + the 15 that flip out of the still-entering group = the **18** above. ⚠ The 23 refused in
total is **not** that 20: it also takes 2 origins from `not_reached` and 1 from
`still_enters_forecast`. **Marginal counts do not compose, and two of them being equal does
not make them the same set of origins.**

**The flip count and the loss count are two halves of one geometric fact, and quoting the
first alone inverts the conclusion.** ⚠ Why the loss falls where it does — whether the
origins a present-perimeter filter helps are the ones nearest the fire — is a plausible
reading of these cells and **is not measured here**: the artifact holds outcome labels and
no distance field, so this page does not assert it.

So the reading that threatened the headline — 「500 m recovers all but one of the 42」 — is
**not what the experiment says**, and it is registered as a forbidden phrasing on every key
above. What 500 m buys is the elimination of `still_enters_forecast`, paid for by refusing
to plan for a quarter of the origins. An operator cannot spend that currency.

⚠ This is **not** a claim that a buffered opponent is weak in general, and **not** a
nomination of any width. A buffered present-perimeter arm scored as the project's opponent
of record is **WFG-033(b)** and **NH-027**, and is the author's. Three widths, two of them
lifted verbatim from prose written before the run, is not a sweep; a later lap that adds a
width to find a better one has crossed into WFG-033(b).

### 7.3 What this does **not** show, and one sentence it refuses to license

1. **No committed number moves.** 414 / 42 / 2 and 26 / 16 / 2 both re-derived here before
   anything was written, and neither was re-run in anger.
2. **The oracle is still on the scoring side.** §5 item 6 applies to every number in this
   section word for word: the arm is scored against the model's own forecast field, so
   「saved」 means 「clear of the model's own predicted hazard」 and not 「would have lived」.
3. **One fire, one region, one horizon.** The canonical field's 32.6 % envelope-coverage
   caveat applies unchanged, and a second fire could split the 44 any other way.
4. **`origin refused outright` is the filter's doing, not the fire's**, and is reported in
   its own column for exactly the reason the zero-buffer run reports `not_reached`
   separately. Whether a county office would call such a household 「already inside the
   danger zone」 rather than 「unplannable」 is a question about policy that this run does
   not answer and must not be quietly answered for it. ⚠⚠ **The alternative accounting is
   written out here rather than left to be computed at a booth, because it is not
   symmetric and it flips one row.** Count a refused origin as a non-loss instead of a
   loss — that is, credit the arm with every origin it did not walk into the forecast —
   and 100 m is **still** worse than zero buffer (12 + 3 against 26) while 500 m turns into
   18 + 23 against 26, which reads the opposite way. **This page does not adopt that
   accounting**, for the reason item 4 opens with: an origin the filter refuses has been
   given no plan, and 「we did not route you into the fire because we did not route you」
   is not a rescue. But a judge can do that arithmetic in ten seconds from the table above,
   so the number is stated here with the objection attached rather than discovered at the
   booth. ⚠ Under either accounting, the three origins the 500 m dilation cuts off from
   every refuge are a loss, and neither reading makes the buffered arm the better opponent
   at 100 m.
5. ⚠⚠ **It does not license the sentence it was partly filed to license, and this is
   recorded rather than quietly dropped.** WFG-259's second half asked for a sentence saying
   that the fair opponent is systematically weakened by the coarseness of this project's own
   input — a 226-component detection scatter rather than a mapped fire line (§2, WFG-260) —
   **and that the direction of that bias runs in this project's favour.** The argument for
   the direction was that dilation moves origins **into** `saved`, so a sparser burning set
   must save fewer. Measured here, growing the refused set **lowers** the net saved count at
   both widths. So the only evidence in this repository bearing on that direction runs
   **against** the convenient reading, and the premise the argument rested on is not what
   the run shows. Dilation is in any case a weak proxy for coarseness: it grows one
   observation's burning set outward, while a finer sensor would change **which** cells burn
   and would not blanket-buffer around detections. **No sentence asserting the direction of
   that bias may be written on any surface, in either direction, on this evidence.** That
   the object is a detection scatter and not a fire line is measured and stays (§2); what
   it does to the comparison is not.
