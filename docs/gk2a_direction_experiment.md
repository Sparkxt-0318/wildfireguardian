# GK2A sub-daily direction experiment — preregistered plan (NO results)

Session 8, Phase 5. **This document is a preregistration and a feasibility
record. It contains no results, and the session that wrote it produced none:
the loader is a scaffold that raises `NotImplementedError`, and the primary
data arm is blocked on an API key (`docs/BLOCKERS.md`, Session 8).**

---

## 0. What the committed record actually says (the starting point)

`docs/MODEL_CARD.md`: the *measurement* is real — permutation importance of
the six-feature fire-weather severity group 0.102 vs the single
`wind_alignment` feature 0.0023 — but the *conclusion* once drawn from it
(「severity ≫ wind direction」) is **withdrawn as not established**, for
recorded reasons: a six-feature sum against one variable; a 0.25° weather
product that cannot resolve local wind; and an unmeasured spread. This plan
does not resurrect the withdrawn conclusion and does not re-quote the ratio
as a finding; it tests one *candidate explanation* for the low single-feature
importance.

**Tension motivating the test:** head-vs-flank anisotropy is foundational in
fire-behaviour physics — Rothermel (1972, INT-115); the Huygens elliptical
propagation used operationally in FARSITE (Finney 1998, RMRS-RP-4, after
Richards 1990, *IJNME* 30(6)). A model in which the directional term carries
almost nothing is in tension with that physics, and one mundane candidate
cause is the **label**, not the atmosphere.

## 1. Hypothesis (fixed in advance)

**H_res (label-resolution artefact):** the committed labels are *daily
cumulative* FIRMS footprints. A day integrates over intra-day wind shifts, so
oppositely-directed spread episodes within one day cancel in the label, and a
directional feature computed against a daily transition cannot correlate with
what actually happened hour by hour. If labels are rebuilt at sub-daily
resolution from GK2A/AMI observations, the directional signal — if it exists
at the modelled scale — becomes learnable.

- **H1:** under sub-daily labels, `wind_alignment` (same single feature, same
  definition, same code path as Build B) carries materially more importance
  than under daily labels on the *same fires* (criterion in §5).
- **H0:** it does not; the low directional importance is not (mainly) a
  label-resolution artefact.

Either outcome is informative and both will be reported; H0 would strengthen
the MODEL_CARD's other recorded explanations (weather-product resolution).

## 2. Data access — investigated 2026-08-29, with the gate that stopped it

**Why GK2A:** AMI observes the full disk every 10 minutes (Korean peninsula
every 2 minutes) at ~2 km IR resolution, and produced continuous fire-area
observation on the 2022 Uljin fire where MODIS-class polar orbiters managed
1–2 passes per day.

| arm | product | endpoint | key? | coverage of our six LOFO fires |
|---|---|---|---|---|
| **primary** | GK2A AMI **L2 FF (산불탐지)** — pixel-level fire detection, the label source that avoids in-house detection algorithms | KMA **API Hub**: https://apihub.kma.go.kr — product list 「위성GK2A 기상산출물」 https://apihub.kma.go.kr/apiList.do?seqApi=6 (HTTP GET with `authKey` parameter); NMSC datasvc (datasvc.nmsc.kma.go.kr) is the other portal | **YES — personal 인증키. STOP.** Filed as an action item for John in `docs/BLOCKERS.md` with the signup URL. No key was requested and no authentication was worked around. | full mission archive (2019-07→), i.e. all six fires incl. miryang_2022 / uljin_samcheok_2022 |
| fallback | GK2A AMI **L1B** radiances (FD 10-min, LA 2-min) | NOAA NODD open bucket `s3://noaa-gk2a-pds` (AWS us-east-1, `--no-sign-request`; verified listable 2026-08-29) | no | **2023-02 → present only** (verified against the bucket listing): covers gangneung_2023, hongseong_2023, uiseong_andong_2025, yeongdeok_2025; excludes miryang_2022 and uljin_samcheok_2022 |

The fallback arm requires deriving hotspots from L1B ourselves (3.9 µm /
11 µm brightness-temperature differencing) — an **added confounder** (our
detector's validity becomes part of the result), which is why it is the
fallback and not the primary.

## 3. Label construction (fixed in advance)

1. Aggregate GK2A fire-pixel detections into **3-hour windows** (primary
   resolution; 1-hour as a sensitivity check). 3 h is chosen in advance as a
   compromise between cloud-gap robustness and shift resolution.
2. A model cell (500 m grid, unchanged) is labelled *newly ignited in window
   w* iff a GK2A fire pixel's footprint intersects it in w and none did in
   any earlier window. This mirrors the committed daily transition labels
   with the day replaced by the window.
3. GK2A's ~2 km IR pixel is 4× the model cell: each detection is mapped to
   the cells its footprint covers (label dilation), and this coarseness is
   carried as a stated limitation, not hidden by pretending point precision.
4. Weather features join at the window midpoint (same ERA5 product; its
   0.25° resolution limitation is unchanged and stated).

## 4. Comparison (fixed in advance)

- Features: the committed 16, unchanged, including `wind_alignment` computed
  against the window's wind.
- Model/seed/folds: `HistGradientBoostingClassifier`, seed 20250603,
  leave-one-fire-out, **restricted to the fires the chosen arm covers** —
  and the daily-label baseline is **re-run on that same fire subset**, so
  the contrast is label resolution and nothing else.
- Readouts, both arms: permutation importance of `wind_alignment`
  (single-feature, never a group sum — the MODEL_CARD's recorded lesson) and
  its leave-one-feature-out ablation delta per fold.

## 5. Success / failure criterion (decided now, before any data)

H1 is **supported** iff BOTH:

1. `wind_alignment` permutation importance under sub-daily labels is at
   least **5×** its daily-label value on the same subset, and
2. the per-fold LOFO ablation delta for `wind_alignment` has a
   fold-bootstrap 95 % interval that **excludes zero** under sub-daily
   labels while including zero under daily labels.

Anything less is reported as **H1 unsupported** — including "importance rose
but less than 5×". The threshold does not move after data arrives. A
negative result will be committed with the same prominence as a positive
one.

## 6. Confounders (recorded in advance)

1. **2 km detection vs 500 m model grid** — label dilation injects spatial
   uncertainty exactly at the scale where direction is expressed.
2. **Cloud masking** — IR detection fails under cloud; missing windows are
   not "no fire". Windows with FF-product cloud flags are excluded, and the
   exclusion count reported.
3. **Geostationary viewing geometry at ~36–37° N** — off-nadir pixel growth
   and terrain parallax on Korean slopes shift apparent hotspot positions.
4. **ERA5 0.25° wind is unchanged** — if local wind is the binding
   limitation (a MODEL_CARD-recorded candidate), sub-daily labels alone will
   not rescue direction; that outcome supports H0 and is informative.
5. **Fallback arm only**: our own L1B hotspot algorithm's validity.
6. **Subset non-representativeness**: the fallback arm drops the two 2022
   fires, including the one (Uljin) with the best-documented GK2A fire
   observation record.

## 7. What exists in the tree after this session

- This plan.
- `src/wildfireguardian/fire_detection/gk2a.py` — loader scaffold, raises
  `NotImplementedError`, docstring points here. **No stub data, no
  placeholder arrays.**
- The blocker entry with the exact signup URL (`docs/BLOCKERS.md`).
- **No GK2A data, no labels, no importance numbers.** Generating synthetic
  GK2A-like data and reporting any direction-importance number from it was
  explicitly forbidden and was not done.

## References

- Rothermel, R. C. (1972). USDA Forest Service INT-115.
- Finney, M. A. (1998). FARSITE. USDA Forest Service RMRS-RP-4.
- Richards, G. D. (1990). *IJNME*, 30(6).
- Kang, Y., Lee, S., Cho, D. & Im, J. (2026). *Communications Earth &
  Environment*, 7:684 — cited **only** for Layer-0 readiness framing and its
  own statement that its outputs should feed localized fire activity models
  (1° / daily FWI / 31-day horizon; **not** a spread-direction input).
