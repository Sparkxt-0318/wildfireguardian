# F-BASE results: 20 frozen panel missions (rules: DESIGN.md, frozen at 85747d3c)

**Scope (applies to every count below):** contact relaxation (O2) only. Equality with the router's full-policy
verdicts holds only under the dose and peak precondition that Richard checks per request.

Command (host: this container, py3.12, single thread):

    python research/harness-2026-11/F-BASE/run_panel_fbase.py --bundles <F-3.2 run_panel output at a03f218> \
        --f32 <F-3.2 dir at a03f218> --summary <F-3.2 results/panel_summary_py312.json>

Raw output: `RESULTS_panel.json`. Bundles were regenerated with F-3.2's frozen `run_panel.py` at a03f218; all 20
instance sha256 values equal F-3.2's recorded `instance_sha256`.

## Agreement with recorded SIPP (rule 3: exact verdict, T to the second)

| solver | agree | disagreements |
|---|---|---|
| exact (F-BASE-X) | **20/20** | none |
| N1 earliest label, waiting everywhere | 20/20 | none on this panel (its unsound case exists, see tests) |
| N2 earliest label, waiting rules | 15/20 | 4 false NO_ROUTE, 1 late T (1294 vs 1270) |
| N3 no acceptance windows | 14/20 | 5 early T, 1 unsound ROUTE (T=2921 on a recorded NO_ROUTE) |

- N2 failures are all `FW*` missions: 2023-04-02 FW2, 2022-06-01 FW1 (late), 2025-03-25 FW1, 2022-03-04 FW2, 2025-03-26 FW1.
- N3 failures: the same five FW missions (early T: 968, 1032, 573, 1400, 776) plus 2025-03-25T19 FD1 (claims 2921).

### Which rule each failure trips (`mechanism.py`, `RESULTS_mechanism.json`)

Ablation, comparing each naive solver with the exact solver on the same ablated instance: remove all blocked
wait starts (`no_WB`), make every node waitable (`all_wait`), or widen acceptance windows to `[dep, H]` (`no_AC`).

| failures | fixed by no_WB | fixed by all_wait | fixed by no_AC |
|---|---|---|---|
| N2, 5 missions | 0/5 | 0/5 | **5/5** |
| N3, 6 missions | 0/6 | 0/6 | **6/6** |

All 11 failures trip **one rule: the destination acceptance window.** Non-waitable nodes and blocked wait starts
trip none of them on this panel.
- In the five FW missions, the window opens later than the earliest possible arrival, at exactly the exact T
  (`[1459, 3480]`, `[1270, …]`, `[1064, …]`, `[1655, …]`, `[896, …]`).
  - N2 extends only the earliest departure of each state, so it misses the later admitted arrival into the window:
    four false NO_ROUTE and one late T.
  - N3 reports the earliest arrival, before the window opens.
- 2025-03-25T19 FD1: the window `[0, 2861]` closes before N3's arrival at 2921, so N3 claims an unsound route.
- N1 agrees 20/20 only because it lets an arrival wait at the destination until the window opens, which the
  admission rule does not allow. Its agreement on this panel is not evidence that it is sound.

## Frozen published independent rows (Main 2a751631, `research/routing/INDEPENDENT_ROWS.csv`)

`compare_independent.py`, `RESULTS_independent.json`. Column meanings are as stated in INDEPENDENT_REPORT.v1.md.
- RDA_CAND: 40/40 rows agree in verdict and arrival second (both repetitions of 15 routes and 5 refusals).
- RDA_BASE: 26/26 resolved rows agree. The 14 unresolved rows (8 TIMEOUT, 6 centre-only refusals) have nothing to compare.

## Witnesses

All 15 exact ROUTE witnesses replay in `fbase.replay`. Spliced into the bundle in place of F-3.2's witness, each is
`ACCEPT ROUTE T` under F-3.2's `check_py.py` (15/15). The C checker was not built; not run.

## Cost (rule 4, this host only; median of 3 fresh processes; peak RSS = max over the 3)

Exact search 0.00–3.26 s, peak RSS 20–227 MiB; parse 0.00–0.19 s. Largest: 2025-03-25T19 FD1 (NO_ROUTE) 3.26 s / 227 MiB.
Per-mission figures are in `RESULTS_panel.json`. Verdict and T were identical across the 3 repeats for every solver.

## Not done yet

- Router (`run_panel.py` SIPP) and Richard's F-3.1 field timings under the same harness: no comparison claimed.
- 140-request departure sweep; delta-debug smallest failing panel-derived instances (hand-built 2–3 node cases are in tests).
- Second published baseline (Sofia).
