# Overnight build session 7 — DIAGNOSTIC report

Date: 2026-05-29. Branch: `claude/dreamy-knuth-NlgfH`.

## 1. Headline verdict (first line)

**BUGGED → FRAGILE.** The Session-6 crown-fire result (9 % → 54 % area
capture) was an **artifact of a moisture-conflation bug**: the Van Wagner
crown-transition check was fed the *surface* live-fuel moisture (the
drought-cured-understory LFMC, 40 %) as the *tree-crown foliar moisture*.
Live conifer crowns do not desiccate to 40 % — the measured Korean value is
119 %. **Fixed** (decoupled crown foliar moisture from surface LFMC). With
the corrected/measured 119 %, **crown initiation collapses from 32 % of
cells to 0 %, and 24-h area-capture falls from 54 % back to ~9 %** — the
surface-only baseline. The 54 % does not survive.

This is a **success for the diagnostic**: we found a real bug, fixed it, and
report the corrected (worse) numbers honestly. No parameter was tuned to
preserve any result.

---

## 2. Concern 2 — why 32 % of cells crowned (the bug)

Instrumented the Session-6 config-c Yeongdeok run
(`scripts/diagnose_crown.py`, log in
`data/processed/crown_diagnostic_log.json`, 20,924 transition records).

**Trace of the wind paths (the suspected bug (d)):** NOT present. The
surface spread and the crown-trigger Byram intensity both use the *same*
WAF-corrected midflame wind (`wind.at()`); the Cruz crown ROS correctly uses
the 10-m wind (`wind.at_10m()`). Winds are consistent. So the answer is
**(e) — a different inconsistency: foliar-moisture conflation.**

Per-cell distributions, crowned vs not:

| quantity | CROWNED (n=6,796) median | NON-crowned (n=14,128) median |
|----------|-------------------------:|------------------------------:|
| I_o (critical) | **462.9** (pinned) | **462.9** (pinned) |
| I_B (surface) | 550 | 360 |
| slope (deg) | 16.6 | 10.0 |
| u10 (m/s, topo) | 17.4 | 13.9 |
| midflame (m/s) | 1.7 | 1.4 |
| foliar moisture | **40 %** | 40 % |

**The smoking gun:** every crowning cell's critical intensity is pinned at
**I_o = 462.9 kW/m** — the value for foliar moisture 40 % at CBH 4 m. At the
measured 119 %, I_o = 1,686 kW/m, which the surface intensity (max ~1,528
kW/m, even with slope + channel-wind boosts) **never reaches**. So:

- The bug (FMC = 40 %) lowered the threshold to 463 kW/m.
- Slope (steeper cells, median 16.6° vs 10°) and topographic channel winds
  (u10 17.4 vs 13.9) then pushed I_B over that lowered threshold.
- Both were necessary: at 40 % FMC, only 427/6,796 crowned cells were
  near-flat; 2,003 were steep (≥20°), 1,640 had topo-boosted midflame >2 m/s.

**Counterfactual (decisive):**

| crown foliar moisture | active-crown % | burned cells |
|-----------------------|---------------:|-------------:|
| 40 % (Session-6 bug) | 32 % | 20,941 |
| 90 % (drought-stressed) | **1 %** | 1,295 |
| 119 % (measured) | **0 %** | 1,264 |

**The fix:** `FireGrid.crown_foliar_moisture_pct` decouples the tree-crown
foliar moisture from the surface LFMC (`ModelConfig.crown_foliar_moisture_pct`
threads it through the harness). Default `None` reproduces the Session-6 bug
for provenance; the corrected runs set 119 %.

---

## 3. Concern 1 — sensitivity (the fragility, quantified)

`scripts/crown_sensitivity.py` swept CBH × surface load at the corrected
foliar moisture (119 %). 24-h area-capture:

| CBH \ load | 0.5 | 0.7 | 0.9 kg/m² |
|-----------:|----:|----:|----------:|
| 2 m | 11 % | 12 % | 27 % |
| 3 m | 10 % | 9 % | 8 % |
| 4 m (measured central) | 10 % | 9 % | 8 % |
| 5 m | 10 % | 9 % | 8 % |

- **Across the measured Korean CBH range (3.6–5.2 m): capture is a stable
  8–10 %** regardless of surface load — crown fire does not meaningfully
  trigger at realistic stand structure + foliar moisture.
- Capture only rises (to 27 %) at **CBH 2 m** (below the Korean range) with
  the heaviest load.
- **Dominant sensitivity parameter: canopy base height** — but only below
  the measured range. Surface load is secondary.

For contrast, the buggy 40 % FMC gives 54 % (CBH 4 m) to 96 % (CBH 2 m) — at
IoU ~0.09 (the fire over-runs the whole landscape).

`docs/methodology/crown_initiation_sensitivity.md` frames this as the
physical/policy finding: stand structure (CBH), raisable by thinning/
pruning, governs crown-initiation potential; the Yeongdeok number carries an
**uncertainty band (~9 % central, up to ~27 % at low CBH)**, not a single
value. `docs/figures/crown_initiation_vs_cbh.png`.

---

## 4. Concern 3 — cross-partial reporting wind (fixed)

The interaction module's `REPRESENTATIVE_MIDFLAME_U` is now anchored to the
**actual WAF-corrected Yeongdeok midflame wind, 1.39 m/s** (was 1.5 m/s,
already realistic; the brief's worry was a 4 m/s value). At 1.39 m/s:

| | ∂R/∂U (m/min per m/s) |
|---|---|
| dry (dead 6 %) | **0.97** |
| moist (dead 20 %) | **0.59** |
| ratio | **1.64** (constant across U — Rothermel is separable) |

(At 4 m/s the absolute values inflate to 1.53 / 0.93; the ratio is
unchanged.) The qualitative finding — dry fuel → ~1.6× larger marginal wind
effect — is intact; the absolute numbers are now anchored to the wind the
fire truly feels. `docs/figures/dRdU_vs_wind.png`,
`docs/methodology/interaction.md`.

---

## 5. The honest area-capture statement going forward

**Do not cite "54 %".** The defensible statement:

> Adding crown-fire physics with the **measured** Korean canopy parameters
> (CBH 3.6–5.2 m, foliar moisture 119 %) leaves 24-h area-capture at **~9 %**,
> the surface-only baseline — the modelled surface fire is not intense enough
> to cross the Van Wagner threshold at realistic foliar moisture. Crown
> initiation is **acutely sensitive to canopy base height**: capture reaches
> ~27 % only if CBH drops to ~2 m (below the measured range). The earlier
> 54 % was an artifact of an unrealistically low (40 %) foliar-moisture input.

---

## 6. Net effect on the project story

**It strengthens the project's credibility while weakening its
"prediction-works" claim** — exactly the honest trade the diagnostic exists
to surface:

- **Strength:** we caught and fixed our own headline result before the
  writeup, and turned the failure into a real finding (crown initiation is
  CBH-governed; stand management is a mitigation lever).
- **Weakness:** crown fire did **not** actually solve the Session-5 problem.
  The apparent solution was a parameter artifact; the deeper bottleneck
  remains that the WAF-corrected surface fire under-predicts intensity, so it
  cannot legitimately trigger crowning. The real 2025 fire *did* crown — our
  model failing to (at realistic parameters) means the surface→crown trigger
  alone is insufficient; the missing intensity (gusts, lower fuel moisture,
  finer-scale wind) is the open problem.
- **The routing spine (Session 5) is unaffected** — it consumes whatever
  front it is given and remains the project's defensible core contribution.

---

## 7. Test count

| | tests |
|---|---|
| Session 6 baseline | 297 |
| **Session 7** | **302** (+5 `test_crown_foliar_moisture.py`; 0 regressions) |

The new tests pin the bug (steep windy stand crowns at 40 %) and the fix
(decoupling to 119 % collapses crowning).

---

## 8. What to do next

1. **Adopt the corrected default.** `ModelConfig.crown_foliar_moisture_pct`
   should be set to the measured 119 % (or a documented drought value) in all
   production runs; `None` is retained only to reproduce the S6 bug.
2. **Re-attack the real bottleneck** (Session-5 / S7§6): the surface fire is
   too weak to crown at realistic foliar moisture. Needs the real gusty KMA
   wind and/or a re-examination of the WAF and provisional surface fuel —
   the surface intensity, not the crown threshold, is the limiting factor.
3. **Report the uncertainty band**, not a point estimate, anywhere the
   Yeongdeok capture is cited.
4. Real KFS perimeter / KMA wind / Korean surface-litter data remain the
   Round-2 unlocks (need API/data access).

## 9. Files

**Created:** `scripts/{diagnose_crown,crown_sensitivity,make_dRdU_figure,make_crown_sens_figure}.py`;
`docs/methodology/crown_initiation_sensitivity.md`;
`docs/figures/{crown_initiation_vs_cbh,dRdU_vs_wind}.png`;
`data/processed/crown_diagnostic_log.json`;
`tests/test_crown_foliar_moisture.py`; this report.

**Modified:** `spread_model/cellular_automaton.py` (crown_foliar_moisture
decoupling + diagnostic log hook); `spread_model/interaction.py` (anchor
wind to 1.39 m/s); `validation/harness.py` (thread crown_foliar_moisture_pct);
`scripts/run_ablation.py` (corrected FMC default);
`docs/methodology/interaction.md`.

## 10. API keys

None present. All Session-7 work is forensic on existing code + literature.
