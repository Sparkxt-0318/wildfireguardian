# Overnight build session 6 — report (FIRE-TYPE PHYSICS)

Date: 2026-05-29. Branch: `claude/dreamy-knuth-NlgfH`.

Session 5 showed surface-only Rothermel misses ~90 % of the observed 2025
Yeongdeok area because Korean pine spring fires are crown/spotting/Föhn
driven. This session added those three physics modules + a rule-based
regime classifier, each **independently validated then ablated**.

**Headline (honest):** 24 h area capture rose from **9 % → 54 %** (crown
fire) and IoU from **0.086 → 0.295**. This is the real improvement the
brief predicted (~40-60 %). **The model still does not "work":** it misses
the first 3 h almost entirely, over-predicts total area, and IoU peaks at
~0.30. Crown fire is the breakthrough; topographic wind is foundational
but inert on its own; spotting trades capture for precision.

---

## 0. Test count vs baseline

| | tests |
|---|---|
| Session 5 baseline | 258 |
| **Session 6** | **297** (+39; 0 regressions) |

New test files: `test_topo_wind.py` (7), `test_crown_fire.py` (12),
`test_spotting.py` (9), `test_regime.py` (7), + 4 smoke-tree imports.

```
$ python -m pytest tests/ -q
297 passed in ~27 s
```

---

## 1. The ablation table (the core result)

Yeongdeok 2025, real SRTM terrain, 50 m cells, 24 h, dead 1-h 8 %, LFMC
40 %, ambient 10-m wind 13.9 m/s (WAF 0.10 → uniform midflame 1.39 m/s).
Each row adds **one** module. Observed-approx 24 h ≈ **3,800 ha**.
"capture" = fraction of observed area captured; "front" = mean front-position
error (m).

| Config | 6 h cap | 12 h cap | **24 h cap** | **24 h IoU** | 24 h pred ha | active-crown % |
|--------|--------:|---------:|-------------:|-------------:|-------------:|---------------:|
| (a) uniform + surface (S5 baseline) | 1 % | 2 % | **9 %** | **0.086** | 326 | — |
| (b) topo wind + surface | 1 % | 2 % | **8 %** | **0.083** | 316 | — |
| (c) topo + **crown** | 7 % | 36 % | **54 %** | **0.295** | 5,235 | **32 %** |
| (d) topo + crown + **spotting** | 20 % | 40 % | **59 %** | **0.243** | 7,740 | 27 % |

Per-horizon detail for the best configs is in
`data/processed/yeongdeok_2025_ablation.json`.

---

## 2. Per-module findings (honest, attributed)

### D1 — Topographic wind: foundational but **~zero recovery alone**

`topo_wind.py` (Föhn slope acceleration k=0.4, channel funnelling ≤2×, lee
0.6×; all cited). On real Yeongdeok SRTM it turns the uniform 13.9 m/s into
an **8.3–34.7 m/s** field (valleys 2.5×, lee 0.6×) —
`docs/figures/topo_wind_yeongdeok.png`.

**Ablation (a)→(b): ΔIoU = −0.003, Δcapture = −1 pt.** Topographic wind
**alone recovered none of the 90 % miss**, and was marginally worse. Why:
with the correct WAF (×0.10), even 2.5× channel acceleration gives only
~3.5 m/s midflame — still a slow *surface* fire. Faster channel winds do
nothing until there is a crown-fire mechanism to convert them into fast
spread. This is an honest negative result; topo wind is retained because it
is the prerequisite that *feeds* the crown module the high 10-m winds it
needs (the crown ROS uses U₁₀, not midflame).

### D2 — Crown fire: **the dominant missing physics**

`crown_fire.py` — Van Wagner (1977) transition + Cruz/Alexander (2005)
active crown ROS. Reproduces Van Wagner's canonical I_o (CBH 6 m, FMC 100 %
→ **2,476 kW/m**, tested) and Korean-pine crown ROS of 20–80 m/min at
10–30 m/s. Implementation note: used the **published** Cruz 2005 form
(`U₁₀^0.7`, EFFM) rather than the brief's truncated `U^0.9/CFC` text — flagged
in the module docstring.

**Ablation (b)→(c): ΔIoU = +0.212 (0.083 → 0.295), Δcapture = +46 pts
(8 % → 54 %).** **32 % of burned cells reached active crown** — far above
the brief's 5 % diagnostic gate, so no investigation needed: the
topo-accelerated channel winds push surface intensity past Van Wagner's
threshold (I_o = 463 kW/m at drought FMC), the fire climbs into the canopy
and runs at 20–50 m/min. `docs/figures/crown_transition_diagram.png` shows
the surface ROS (crushed flat by the WAF) vs the crown ROS that bypasses it.

This is the session's breakthrough and matches the brief's ~40-60 %
expectation.

### D3 — Spotting: **mixed — more capture, worse precision**

`spotting.py` — Albini-1979-calibrated ember transport (flame length → loft
→ ballistic drift; stochastic, seeded). Honest note: the brief's Albini
one-liner was truncated, so the standard published transport chain is
implemented and documented. Crown-fire flames (~5–6 m) at 10–30 m/s give
spot distances of **hundreds of m to ~1.5 km** (tested), the right
magnitude for the observed jumps.

**Ablation (c)→(d): Δcapture = +5 pts (54 % → 59 %), 6 h capture 7 % → 20 %
(much faster mid-game front), BUT ΔIoU = −0.052 (0.295 → 0.243) and area
over-prediction worsens (5,235 → 7,740 ha, +104 % of observed).** Spotting
helps the fire reach distant observed area faster, but with no containment /
fuel-break / suppression mechanism the stochastic embers spread it too
widely, lowering overlap precision. **Reported, not hidden.** Best IoU is
config (c) topo+crown (0.295); best capture is (d).

### D4 — Regime classifier: rule-based, FARSITE-style (no ML)

`regime.py` — a standalone, independently-tested classifier
(SURFACE / PASSIVE_CROWN / ACTIVE_CROWN + spotting gate) built over the
validated Van Wagner / Cruz-Alexander criteria. Tested to agree
bit-for-bit with the CA's in-line `crown_fire.classify_crown_regime`, so the
regime logic is inspectable in isolation. No ML, per the brief — the
ML type-conditional predictor is Round-2 work pending real Korean fire data.

---

## 3. What this does and does NOT mean

**Does:** the three regimes together raise 24 h area capture from 9 % to
54–59 % and IoU from 0.086 to ~0.30. The physics behaves as its papers say
(crown transition at the right intensity, crown ROS magnitudes, spot
distances). Each module's contribution is attributed by ablation.

**Does NOT:** the model still **misses the first 3 h almost entirely**
(1–3 h capture ≤ 1 % in every config — the CA needs time to develop
crowning, and the real fire's early explosive run isn't captured),
**over-predicts 24 h area** by +38 % (crown) to +104 % (spotting), and
**peaks at IoU ~0.30** against an *approximate* observed perimeter. This is
a real, honest improvement — **not** a working operational forecast.

The single most defensible statement for the writeup: *"Adding crown-fire
physics raises 24-hour burned-area capture from 9 % to 54 %, confirming that
Korean pine spring fires are crown-driven; the surface-only model's failure
was diagnostic, not incidental."*

---

## 4. Remaining gaps / next-session priorities

1. **Early-front under-prediction (1–3 h).** The dominant remaining miss.
   Likely needs faster crown onset + the real (gusty) wind time series.
2. **Over-prediction control.** No suppression / fuel-break / containment
   model; spotting especially runs away. A containment or burn-probability
   (Monte-Carlo) framing would restore precision.
3. **Real ground truth.** All numbers are vs the *approximate* perimeter;
   real KFS shapefile (needs access) would make IoU meaningful.
4. **Real wind incl. gusts** (KMA key) — the WAF-corrected mean 1.39 m/s
   midflame is what crushes the surface fire; gusts drive the real run.
5. **Korean surface-litter fuel data** — the surface bed is still provisional.

---

## 5. Data provenance (Session 6 additions)

| Input | Status | Source |
|-------|--------|--------|
| Topographic wind coefficients | HEURISTIC (cited) | Föhn studies; Whiteman 2000 |
| Van Wagner transition | ✅ PUBLISHED | Van Wagner 1977 CJFR 7 |
| Cruz/Alexander crown ROS | ✅ PUBLISHED | Cruz et al. 2005 CJFR 35 |
| Korean canopy CBH/CBD/FMC | ✅ MEASURED | Lee et al. 2018 |
| Albini spotting constants | HEURISTIC (calibrated) | Albini 1979 GTR INT-56 |
| Regime thresholds | ✅ PUBLISHED | Van Wagner; Scott & Reinhardt 2001 |
| Everything from S1–S5 | unchanged | (DEM real; wind/fuel/perimeter synthetic/approx) |

## 6. Files

**Created:** `spread_model/{topo_wind,crown_fire,spotting,regime}.py`;
`scripts/{run_ablation,make_topo_wind_figure,make_crown_diagram}.py`;
`docs/figures/{topo_wind_yeongdeok,crown_transition_diagram}.png`;
`data/processed/yeongdeok_2025_ablation.json`;
`tests/test_{topo_wind,crown_fire,spotting,regime}.py`;
this report.

**Modified:** `spread_model/cellular_automaton.py` (GriddedWindField, regime
array, crown switch in `_spread_from`, spotting pass in `step`);
`spread_model/rothermel/fuel_model.py` (canopy params, `fine_fuel_load_kg_m2`,
`can_crown`); `validation/harness.py` (topo/crown/spotting flags, regime
fractions); `tests/test_smoke.py`.

## 7. API keys this session

**None present.** All Session-6 physics needs no keys; real KFS/KMA/Sentinel
ingestion remains Round-2.
