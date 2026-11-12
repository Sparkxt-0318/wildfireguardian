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

## 8. Out of scope
- **c651_fullvalid_rebuilt** goes in a separate, later amendment, developed first on part a and using the 44 events fetched on 14 Nov. It does not block stage 2. If part c opens first, c651_fullvalid is not scored on part c.
- **CR1** has its own preregistration.
