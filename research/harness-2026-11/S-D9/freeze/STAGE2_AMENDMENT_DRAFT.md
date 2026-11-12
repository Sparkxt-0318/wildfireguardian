# A1 stage-2 amendment: DRAFT text (not frozen)

**Status: draft.** Nothing here is frozen until `make_freeze.py` writes the stage-2 record and Hannah verifies the text and the record. Part c stays closed until then (A1 §6.1, §9).

- Any item marked **PENDING** or **UNVERIFIED** is cited only after the named verifier's ledger row exists.
- Pins are collected in `STAGE2_PINS.md`.

## 1. Survey-timing exposure (declared; gate cleared)
- **Source:** `ledger/ACCESS_CONTROL.md`, PR #147, frozen at 1fc38266. Hannah's audit is ledger row 38 (PASS WITH NOTES) and her text check is row 41 (PASS).
- **Status wording for part c:** "Labels, perimeters and growth are sealed. Survey-timing metadata was exposed before the split, and the membership rules used it." Part c stays confirmatory, with these limitations. H is descriptive. Part d is exposed.
- **§1.2 reconciliation.** The five-field list in §1.2 describes what scorers may read. The membership filters are separate: §1.3, item 8 (timing-dependent), item 9 and item 10. These used discovery, first and last survey times to decide membership only. In total they changed membership for **18 b/c/d and 96 part-a** incidents. §1.1 uses no timing.
- **File list:** survey-timing files F1–F5, with their shas, are listed in the disclosure. This includes `GOFER_MATCH.csv` (451675c1).
- **Standing rule (added to A1).** No design choice, eligibility rule, constant or candidate may use a sealed incident's last survey time, survey days, or any cadence derived from them. Stratum G is defined from part a only.
- **Reporting rule.** Part-c results are also reported by tercile of survey span. This is descriptive and does not change the primary test.
- **Leak bound.** The plan is `derive/LEAK_BOUND_PLAN.md` (e8772880, PR #148), and constant provenance is in `CONSTANT_PROVENANCE.md` (0a89bee2).
  - Marcus runs the leak bound with the refits, and Owen verifies it.
  - A material leak is pre-defined as a 95% interval of ΔBrier lying entirely below 0. **PENDING** result.
- **Clean confirmation.** The clean confirmation is CR1 (`clean_replication/PREREGISTRATION_DRAFT.md`, PR #153), not part c. It is frozen separately.

## 2. d2_bracket_rebuilt protocol
- **Code (claude/s-d2-next):** `d2_bracket.py` 98d7d6c6, `run_d2_bracket.py` cc41cc33, `run_d2.py` e3c0843c, `time_estep.py` 0bebc764. **PENDING:** the final head and Owen's verification.
- **E-step:** discretised Gibbs on a 0.25 h grid.
  - 2 sweeps per epoch, with midpoint initialisation and a warm start.
  - Its own RNG: `SeedSequence([seed, 0x5D2B])`.
  - Order per epoch: kernel pass, then 2 detached sweeps, then the M-step on the same kernels, then the optimiser step.
  - The last epoch is used, with no validation selection.
  - Budget: 3 epochs (A1 budget line).
  - The protocol refuses burnout and spotting inputs.
- **Unscored burned cells.** Cells burned at the endpoint but not initially are latent.
  - Unscored latent cells get no own-event or exposure term; they act as sources only.
  - **Residual, recorded.** Unscored cells that are not endpoint-burned keep τ = ∞. Report their part-a share.
- **Grid step.** Elena's 0.25 h vs 0.05 h synthetic check (8b0fde65) finds differences ≤ 0.0024 in far share and ≤ 0.0010 in rate ratio. **UNVERIFIED** (Owen).
- **Timing.** About 2.6× d4 per pass, as an upper bound. Not a frozen quantity.
- **§5.2.** The native-marginal demo on R must exist before the code sha is frozen. **PENDING.**

## 3. far_share (descriptive, carries no weight)
- **Definition.** F is the set of offsets at Chebyshev distance ≥ 2 on the 9×9 stencil.
  - Mass is taken from `kernel_rates` after modulation.
  - It is averaged over part-a training scored cells, with equal weight.
  - The same stencil is used for d4_wind, d2_nll and d2_bracket.
- **Recovery tolerance.** Committed before the output was read, at 946f1e4e (`TOLERANCE_shape_recovery.md`).
- **Result.** Elena's 780cbabe: MCEM and mean-field NLL recover the far share in both kernels, while plug-in inflates it (0.388 vs 0.072). **UNVERIFIED** (Owen).
  - **Interpretive note:** the real part-a gap in NLL (about 0.64–0.68 vs MCEM about 0.07) is *not* explained by estimator bias under the synthetic model.

## 4. Crop property (A1 §3.1; item 22 declaration)
- **Finding.** 12,384 of 122,640 new-burn cells (10.1%), in 97 of 3,773 intervals, fall outside `crop_box(initial, 10)`. They are dropped in all arms. This is a property of the recipe, not a change to it.
  - Source: Elena b7cdc48f. **UNVERIFIED** (Owen).
- **Note:** spread beyond about 3.75 km is scored as unreachable and never trained.

## 5. Half-step scope
- "Half-step" in A1 §2.1 means Marcus's hourly CA (`half_step=True`) on H only.
- No mean-field half-step is added for d4_wind. Any such comparator needs its own synthetic check and is descriptive.

## 6. Pins (from `STAGE2_PINS.md`)

| item | state |
|---|---|
| refit train-events, final | **PENDING** (pre-weather list bbedca82 = fit-23 + 490, checked against allowlist 7db3cc0e) |
| part-a pool manifest | **PENDING** sha (daniel/data-fetch-3 982eb71c, 490/490) |
| weather input manifest | **PENDING** (Daniel, 13–14 Nov) |
| rebuild environment | **PENDING** |
| refit receipts: d4_wind_rebuilt, logistic_rebuilt, d4_wind_recal, d2_nll_rebuilt, d2_bracket_rebuilt | **PENDING** |
| rate-mixture form | **PENDING** |
| part-c manifests | **PENDING** |
| item 14 weather outcome (AlderCreek T/wind) | **PENDING** |

**Control-run evidence.** Owen verified Marcus's unmodified-rollout control on R (owen-smoke-2, rows 25 and 33).
- All 273 rebuilt cases are identical.
- d4_wind sits at the 4.17e-7 floor.
- c651_mc is bit-identical on 40 of 273 cases: a post-hoc subset of 34, disclosed, plus 6 chosen by a fixed rule.

## 7. Wording updates to A1
- **Line ~113:** "Open-Meteo, day 2" becomes "Open-Meteo, the 13 Nov 00:12 UTC fetch" for the AlderCreek weather.

## 9. Outcome-to-claim table (written before part c opens; changes no criterion)
Each row fixes the sentence the paper may write for one possible part-c result.
- "Superior" means **all six** §6.1 criteria pass for that candidate, on ≥ 20 analysable fires.
- The headline is `d2_bracket_rebuilt`. If it is not admitted, the headline is `d2_nll_rebuilt`. If neither is admitted, there is none (§6.1, revision 29).
- Every part-c sentence carries the survey-timing limitation (§1): "labels, perimeters and growth sealed; survey-timing metadata exposed before the split; membership rules used it".
- Any other admitted candidate is **secondary**, with its own verdict and **no multiplicity adjustment**. Any statement about it says so.

| # | part-c outcome (headline candidate) | what the paper may write | what it may not write |
|---|---|---|---|
| O1 | Superior: criteria 1–6 all pass | "On 30 reserved NIROPS fires (N analysable), the pre-registered headline candidate improved on persistence, 8 h dilation, the rebuilt logistic reference and the recalibrated rebuilt d4_wind in the 4 km band (paired Brier, 95% whole-fire interval below 0), with low-probability calibration no worse than the references." Plus the limitation. | "Confirmed" or "validated" without the limitation. Any claim outside the 4 km band, outside NIROPS survey horizons, or for other regions. |
| O2 | Beats persistence (1) and dilation (2); **not superior to `logistic_rebuilt`** (3 fails) | "The candidate improved on persistence but did not improve on a rebuilt logistic reference trained on the same fires. The pre-registered decision is NOT SUPERIOR." Also state: "Development power against the logistic reference was about zero at the effect seen on the development cohort (§6.3), so this outcome was the expected one." | That the candidate "matches" or is "equivalent to" logistic, since no equivalence test is registered. That it "beats the baseline", unqualified. |
| O3 | Beats persistence, logistic and dilation; **fails criterion 4** (vs `d4_wind_recal`) | "Improved on persistence and the logistic reference, but not on the recalibrated physical model, so the D1/D2 method change adds no demonstrated gain over recalibration. NOT SUPERIOR." | That the method change caused the gain over logistic. |
| O4 | Criteria 1–4 pass; **fails criterion 5** (low-bin calibration) | "Better on paired Brier, but worse calibrated in the lowest probability bin than a reference. NOT SUPERIOR under the pre-registered rule." | That it is superior. |
| O5 | **Not superior to persistence** (1 fails) | "The candidate did not improve on persistence in the 4 km band (NOT SUPERIOR)." Report the interval and the direction. If the interval includes 0, say "no detectable difference at this sample size", with the half-effect power of §6.3 (0.42 at 30 fires). | "Worse than persistence", unless the interval lies above 0. |
| O6 | **< 20 analysable fires** (criterion 6) | "INCONCLUSIVE: too few analysable fires; results descriptive." | Any verdict. |
| O7 | Headline `d2_bracket_rebuilt` **not admitted**; fallback `d2_nll_rebuilt` scored | The O1–O6 sentence for `d2_nll_rebuilt`, preceded by: "The pre-registered headline candidate was not admitted (reason); the pre-registered fallback is reported as the headline." | That the bracket model was tested on part c. |
| O8 | **No headline** (neither admitted) | "No candidate met the admission rules, so there is no headline part-c decision. Secondary candidates are reported individually, without multiplicity adjustment." | Promoting a secondary result to headline. |
| O9 | **Material leak bound** (§1; `LEAK_BOUND_PLAN.md`) | Whatever row applies, plus: "A part-a measurement found that survey-timing information could improve the reference model detectably. Criteria that depend on constants not shown independent of sealed survey timing are reported as descriptive." | Omitting the leak-bound result. |

For **secondary candidates and comparator rows** (d4_wind vs logistic on part c, `c651_fullvalid_rebuilt` and others), the same sentences apply with "secondary, no multiplicity adjustment" added. A secondary success never becomes the headline.

## 10. A1 closed to new change items after the stage-2 freeze
- A1 has **30 change items** in its revision log as of this draft. Once stage 2 is frozen and verified, **A1 accepts no new change items**.
- Allowed afterwards: errata that change no rule, number or membership, each logged as an erratum. Separate amendments already named in §8 (`c651_fullvalid_rebuilt`).
- **Later ideas go to:**
  - **part b**, by its own amendment naming a candidate by SHA before part b opens (A1 §1.2 item 4, §9 step 5); or
  - **CR1** (`clean_replication/`), before its freeze.
- A proposal that needs an A1 change after the freeze is recorded as "not adopted: A1 closed" and is redirected to one of these two places.

## 8. Out of scope
- **c651_fullvalid_rebuilt** goes in a separate, later amendment, developed first on part a and using the 44 events fetched on 14 Nov. It does not block stage 2. If part c opens first, c651_fullvalid is not scored on part c.
- **CR1** has its own preregistration.
