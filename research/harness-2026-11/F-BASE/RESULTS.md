# F-BASE results: 20 frozen panel missions (rules: DESIGN.md, frozen at 85747d3c)

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
- Hypothesis, not checked: the FW missions are the ones whose instance carries acceptance windows and wait blocks that bind.

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
