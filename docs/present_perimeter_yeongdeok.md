# The present perimeter, with no buffer, against the Yeongdeok 42

**Row:** WFG-129 · **Specified by:** `paper/GAPS.md` G7, written by the 0323Z paper lap
**Method proposed by:** the loop (G7 wrote the recipe; three earlier critic laps wrote the
objection it answers); **run by:** the dev lap of 2026-09-11T1219Z.
**Artifact:** `data/processed/present_perimeter_yeongdeok_2025.json`
**Script:** `scripts/measure_present_perimeter_yeongdeok.py` · **Registry:** `ppy_yeongdeok_*` (6 keys)

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
5. **A buffered present perimeter is a DIFFERENT experiment, and this repository has not
   run it on 영덕. No direction may be asserted for it here.** ⚠⚠ The first draft of this
   section said the opposite — that widening the buffer removes more nodes and so can only
   move an origin **out of** `saved`, never into it — and **that is false**. This lap's
   independent reviewer nailed it in the lap, on this lap's own code and this artifact's
   own origin ids: `naive_route` is shortest-path-by-length **scored afterwards**, so
   deleting nodes **reroutes** it, and a reroute can land clear of the forecast. Dilating
   the burning set to a strict superset of the 162 at 100 m moves origin `11935180417`
   from `still_enters_forecast` to **`saved`** — the transition the draft said could never
   happen — and at 500 m, 15 of the 16 flip. The repository already knew this and the
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
   filtered from `haz_stack` slice 0 and scored against the rest of `haz_stack`, which is
   the same leave-one-fire-out forward simulation the forecast-aware arm plans on — so the
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
