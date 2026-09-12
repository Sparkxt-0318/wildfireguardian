# What a figure legend is allowed to claim

**Method proposed by the loop** (WFG-266, filed by critic #72 on 2026-09-12; the
underlying distinction is the author's, carried from `docs/routing_limitations.md`
§6 and the WFG-262 measurement). Built 2026-09-12 on the `auto/dev` lap that
redrew `F3b_regions.png` and `F8b_routing_map.png`.

## The distinction, in one sentence

A routing run returns what its two searches found; a legend that names the
outcome class **"no safe walking route"** asserts instead that no such route is
there, which is a stronger statement about the world than any search result can
support.

## Method

The `no_safe_route` bucket is not produced once. **The command is the authority
here, not this prose**, because two drafts of this very section got the count
wrong before it shipped. Run it and compare:

```
$ grep -rn "enters_hazard and not fa.reached" --include=*.py . | grep -v "\.auto/venv"
19
```

Nineteen lines, 2026-09-12, at `a9bc4ab` plus this lap's tree. They are not
nineteen producers, and the breakdown is the point:

| what | count | where |
|---|---|---|
| **producers of `no_safe_route`** | **7** | below |
| producers of `fa_exceeds_budget` (`not nv.enters_hazard and not fa.reached`) | 3 | `run_real_roads_real_hazard_slope.py:138`, `run_multi_region_routing.py:316`, `live/pipeline.py:480` |
| prose: docstrings and comments quoting the condition | 9 | `paper/make_figures.py` ×7, `tests/test_figure_legend_claims.py` ×2 |

The seven producers:

| producer | line | spelling |
|---|---|---|
| `scripts/run_real_roads_real_hazard_slope.py` | `:131` | `elif nv.enters_hazard and not fa.reached:` |
| `scripts/run_real_roads_real_hazard.py` | `:151` | identical |
| `scripts/run_routing_integration.py` | `:256` | identical |
| `scripts/run_multi_region_routing.py` | `:310` | identical |
| `src/wildfireguardian/live/pipeline.py` | `:474` | identical |
| `scripts/measure_present_perimeter_yeongdeok.py` | `:164` | `elif nv.reached and nv.enters_hazard and not fa.reached:` |
| **`paper/make_figures.py`** | **`:649`** | `elif nv.reached and nv.enters_hazard and not fa.reached:` |

The first five are character-identical including indentation. The last two add the
`nv.reached` conjunct explicitly rather than inheriting it from a preceding
`if not nv.reached:` guard, which all five of the others do have.

⚠⚠ **The seventh is inside this repair's own file, and missing it is the finding
of this lap.** `paper/make_figures.py:649` sits inside `F8b_routing_map`, about a
hundred lines above the legend this lap rewrote, and the set it builds is exactly
what `:710` plots as the x-markers that `:755` labels. So F8b does **not** read
this bucket out of a committed artifact at all: it recomputes the partition with
the repository's router and then asserts equality with the committed one
(`counts_ok`, true at the render that shipped — the legend prints the counts).

That matters for what this document may claim. It is **not** true that every
figure drawing this bucket draws the same artifact's predicate. F3b and F5b read
committed counts; F8b recomputes them from a seventh copy that happens to agree.
The agreement is a fact about today's source and today's render, not a property
the repository enforces.

⚠ **Three drafts of this section, three wrong counts, and the third was caught by
the independent reviewer rather than by the lap.** The first named three producers
and called them "repeated verbatim in three scripts", line numbers each off by
one. The second — written *as the correction*, with the anti-pattern freshly named
in `docs/auto/MEMO.md` — said five, and pasted the grep above beside the answer
"five sites" without re-reading what the grep returns. The reviewer ran that one
line, got nineteen, and found the seventh producer inside the file being edited.
The lap had pre-registered, in `a9bc4ab`, that it would not paste a phrase across
figures until it had read the producer behind each. It had not.

`scripts/build_multi_region_comparison.py:145-179` re-runs nothing: it carries
each region's `counts` out of the committed per-region files unchanged.

Read it in two halves. `nv.enters_hazard` says the fire-blind shortest route
**did reach** a refuge but passed through the predicted hazard to do so.
`not fa.reached` says the forecast-aware search terminated without reaching one.
Together they establish what two specific searches returned under one budget, one
`p_cut` and one walk network. They establish nothing about routes neither search
examined, and the walk network is itself partial — the canonical Yeongdeok field
covers about a third of the predicted fire core, and the direction of that bias
is unmeasured (`paper/manuscript.md` §4.3, third caveat).

## Result

Three legends in `paper/make_figures.py` drew this bucket. All three now report
the search rather than assert the world:

| figure | file written | label |
|---|---|---|
| F3b | `paper/figures/F3b_regions.png` | `no safe walking route found` |
| F5b | `paper/figures/F5b_decision_shift.png` | `no safe walking route found` |
| F8b | `paper/figures/F8b_routing_map.png` | `origin: no safe walking route found` |

F5b was repaired one lap earlier, from `no safe walking route exists`. F3b and
F8b were repaired here. Their predecessors `F3_regions.png`, `F5_decision_shift.png`
and `F8_routing_map.png` stay committed and byte-unchanged as the record
(CHARTER §3 rule 2 and §3.7; NH-042, the author's decision on regenerating a
committed figure, is still open). `paper/manuscript.md` points at the repaired
files.

`tests/test_figure_legend_claims.py` binds this: every string literal in
`paper/make_figures.py` that is not a docstring and that names this bucket must
carry `found` and must not carry `exists` or `at all`. It was graded red against
five mutations — a reverted legend, an `exists` legend, a legend deleted rather
than repaired, a figure regenerating its committed predecessor in place, and a
manuscript pointing back at a superseded file — and green once each was undone.

### Why a test and not the grep the row asked for

WFG-266's done-when (d) asked that one grep of `paper/make_figures.py` for
`no safe walking route` return only supersession docstrings. **That clause cannot
be satisfied while the repository is correct**, and the lap that closed the row
did not satisfy it.

The measurement, which is what the claim commit pre-registered would be given
before the clause was amended:

```
$ grep -c "no safe walking route" paper/make_figures.py
9
```

Nine, at lines 133, 146, 173, 252, 283, 574, 581, 586 and 755. Six are
supersession docstrings and comments, which the clause permits. **The other three
are the three repaired legends themselves** (`:173` F3b, `:283` F5b, `:755` F8b),
because `no safe walking route found` contains `no safe walking route`. The
clause's own exemplar F5b — repaired one lap earlier and correct — fails it. A
substring cannot distinguish a claim from a report of a search, which is the whole
of the distinction being repaired, and satisfying the clause literally would mean
breaking three correct legends to turn a grep green. The done-when is amended
here, in writing, with that count as the reason, and the predicate moved onto the
claim instead.

## Caveats

- **A rewording is not a measurement.** Nothing here re-ran a router, changed a
  count, or made any origin more or less reachable. The committed partitions are
  untouched.
- **The gate is line-based and label-shaped.** It reads string literals in one
  file. A legend built by string concatenation at draw time, or a claim made in
  a figure's caption rather than its legend, escapes it. The caption side is held
  by review, not by this gate.
- **`fa_exceeds_budget` carries the same family of over-claim and is NOT repaired
  here.** `not fa.reached` merges budget exhaustion (`evacuation.py:511`),
  hazard-forbidden edges (`:517`) and an exhausted search with no path at all
  (`:528-532`); the band's label names only the first. Left standing deliberately
  rather than widened into this row, and filed as WFG-269 so it is a debt with a
  name.
- **The strongest live instance of this class is not in a figure.** `README.md`
  says, in the project's own voice, that two origins have no safe walking route
  **at all** — stronger than any legend repaired here, on the most-read surface
  in the repository. It is filed as WFG-270 and deliberately not edited here:
  CHARTER §3.5c requires a withdrawal to be registered in
  `docs/auto/withdrawn_claims.json` in the same lap, and this spelling appears in
  several non-record documents, so it is a row rather than a nit.

## What this does NOT show

- It does **not** show that a safe walking route exists for those origins. The
  repair removes a claim; it does not replace it with the opposite claim. What is
  known is only what the two searches returned.
- It does **not** show that the figures are now free of over-claim. One bucket's
  label was audited across three figures. The other bands were read for
  discrimination against this one and otherwise left alone, and the caveat above
  names the one known survivor.
- It does **not** establish that the seven producers will stay in agreement. They
  are seven hand-copies of one condition, not one shared function; nothing in this
  repository fails if a lap edits one of them, and three drafts of the Method
  section above demonstrate how easily a careful reader counts them wrong. That is
  a real fragility, it is not fixed here, and it is filed as **WFG-271**.
- It does **not** bind a committed PNG to the source that drew it. The gate reads
  string literals; a lap could repair a legend in code, ship a stale render, and
  stay green. Both figures here were opened and read by eye instead, which is
  review and not a gate.
- The gate keys on the literal substring `no safe walking route`, so a **reworded**
  over-claim escapes it — "no safe route", "no walkable route", "cannot reach
  safety". This is the same measured limit `docs/withdrawn_claims.md` §4 records
  for registered spellings: a copy-paste ratchet, not a claim detector.
