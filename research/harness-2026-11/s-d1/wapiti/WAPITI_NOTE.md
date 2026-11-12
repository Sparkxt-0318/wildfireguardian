# Wapiti reconciliation note: why c651 beats no-new-burn in the preprint but not in the six-fire evaluation

**DEVELOPMENT-ONLY, exposed fire (Wapiti, cohort R). Existing outputs only, no new fits. Verifier: Owen.**
The step list was committed before any number (`WAPITI_PLAN.md`, 117932f2), and so was the script
(`wapiti_reconcile.py`). Results: `RESULTS_wapiti.json`. The preprint numbers are Victor's exact reproduction
(`S-D9/derive/M548_REPRO.*`, PR #125 at 86550a33; Hannah PASS WITH NOTES, ledger row 32).

**Inputs.**
- (S) The six-fire stored entries (heldout dir at 6a3265a0, Wapiti per-fire file).
- (M) The 25 owner-archive cases. All 100 input files equal Victor's recorded sha256. Nothing from the archive is
  committed.
- (M) reproduces Victor exactly: 275,961 entries, 2,525 positives, BSS vs always-zero 8.17%.

## Result: the sign change is entirely the interval set

| step | intervals | cells | positives | Brier c651 | Brier zero | c651 − zero | BSS vs zero |
|---|---|---|---|---|---|---|---|
| A0 (S) as stored | 52 | 494,121 | 3,744 | 0.010949 | 0.007577 | **+0.003372** | −44.5% |
| A1 interval set: (S) restricted to the 24 intervals matched to (M) | 24 | 264,307 | 2,520 | 0.008757 | 0.009534 | **−0.000778** | +8.16% |
| A2 mask: (M) mask | 24 | 264,307 | 2,520 | identical to A1 | | | |
| A3 labels: (M) labels | 24 | 264,307 | 2,520 | identical to A1 | | | |
| A4 predictions: (M) probability | 24 | 264,307 | 2,520 | identical to A1 | | | |
| A5 full (M) mask on matched intervals | 24 | 264,307 | 2,520 | identical to A1 | | | |
| A6 full (M) set (adds 1 interval) | 25 | 275,961 | 2,525 | 0.008402 | 0.009150 | −0.000747 | +8.17% |

- **The sign flips at A1 and nowhere else.** Every single-factor effect applied alone to A1 (mask, labels,
  predictions) changes nothing.
- On the 24 matched intervals the two evaluations hold the **same cells, the same labels and bit-identical
  predictions**. The grids are cell-aligned with offset (0, 0), and 0 (S) cells lie outside the (M) mask.
- Post-plan, descriptive (`wapiti_addendum.py`): 264,307 of 264,307 predictions and labels are equal, with max |Δp| = 0.
- On these cells the S-D9 "persistence" forecast equals always-zero, which was checked: the mask excludes cells
  burned at the cutoff.
- So the mask (band versus full rectangle), the label source, the crop and the prediction run are **not** the cause
  here. All four coincide on the common intervals.

## Which intervals (post-plan, descriptive)

- **The preprint's 25 intervals** have cutoffs from 2 to 30 August 2024 and lengths of 12.8–35.7 h.
  - One of them, 2–5 August (73 h), is not in (S), because the frozen six-fire rule takes only intervals of 48 h or
    less.
- **The 28 intervals only in (S)** have cutoffs from 24 August to 15 October 2024 and lengths of 19.1–47.7 h.
  - They hold 229,814 cells with only 1,224 positives (base rate 0.53%).
  - c651 is worse than no-new-burn on **26 of 28**.
  - Pooled excess Brier is +0.0081 per cell.
  - Five late-season intervals carry 55% of that excess, led by 28 September (47.7 h, 3 positives on 7,968 cells),
    2 September (44.6 h, 70 positives) and 5 September.
- **Reading, a hypothesis that was not tested:** the six-fire set adds the later, slower, longer intervals of the
  fire. There c651's spread probabilities over-predict against very few new burns. The preprint window (the August
  growth phase) is where c651 helps.

## Consequence for wording

- The preprint's "8.17% better than no-new-burn" is **specific to the preprint's 25-interval August cohort**.
- It is not a property of Wapiti as scored by the six-fire protocol. Over all 52 eligible intervals of 48 h or less,
  c651 is 44.5% worse than no-new-burn on Wapiti.
- Neither number is a test result: Wapiti is exposed, and it is c651's SELECTED_ON fire.
