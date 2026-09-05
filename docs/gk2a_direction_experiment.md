# GK2A sub-daily direction experiment — preregistered plan (NO results)

Session 8, Phase 5. **This document is a preregistration and a feasibility
record. It contains no results, and the session that wrote it produced none:
the loader is a scaffold that raises `NotImplementedError`, and the primary
data arm is blocked on an API key (`docs/BLOCKERS.md`, Session 8).**

---

## 0. What the committed record actually says (the starting point)

⚠ **Revised 2026-08-29 (follow-up session, Task A).** An earlier draft of
this plan motivated the experiment as *explaining an anomaly* — a low
directional importance — and quoted the permutation-importance figures to do
it. That framing was wrong, and the numbers have been removed from this
document. What the tree actually holds:

- **There is no committed claim about wind-direction importance.** The
  section in `docs/MODEL_CARD.md` that once carried one is now headed
  「Permutation importance — what it measures, and what it does NOT
  establish」 and states: **「THIS SECTION WAS HEADED "Headline finding
  (severity ≫ wind direction)" AND THAT CLAIM IS WITHDRAWN AS NOT
  ESTABLISHED」** (withdrawn 2026-08-08, commits `9f40127` + `ce3ea64`).
  `docs/NUMBERS.json` registers **no** direction-importance entry —
  the project's own rule is that a reportable number lives in that registry,
  so a quantity absent from it is not a claim this project makes.
- **The withdrawal is methodological, not arithmetic.** The three recorded
  grounds: a six-feature *sum* set against a single variable; ERA5 at 0.25°
  (~28 km), which does not resolve the wind the comparison is about; and a
  single point estimate whose spread across seeds and folds was never
  measured. All three survive any re-measurement of the same shape, so no
  corrected ratio would repair the conclusion.
- **⚠ The card also states, and this plan repeats it: this does NOT mean
  wind direction is unimportant. It means that instrument, on that weather
  product, cannot see it.**

**Therefore the honest status is: the model's directional sensitivity is
currently UNCHARACTERISED in any committed artifact.** This experiment is
reframed accordingly — it **establishes a baseline**, it does not explain an
anomaly. No numeric ratio appears anywhere in this document, by design.

**Physics framing (unchanged, and valid in every case):** head-vs-flank
anisotropy is foundational — Rothermel (1972, INT-115); the Huygens
elliptical propagation used operationally in FARSITE (Finney 1998,
RMRS-RP-4, after Richards 1990, *IJNME* 30(6)). Fire spread is directional;
whether *this* model, on *these* labels, can express that is exactly what is
unmeasured.

## 1. Question and hypothesis (fixed in advance)

**Primary question (baseline-establishing, not anomaly-explaining):** at what
label time-resolution, if any, does this model's single `wind_alignment`
feature carry measurable importance — and is that importance distinguishable
from zero at all?

**H_res (label-resolution, the mechanism under test):** the committed labels
are *daily cumulative* FIRMS footprints. A day integrates over intra-day wind
shifts, so oppositely-directed spread episodes within one day cancel in the
label, and a directional feature computed against a daily transition cannot
correlate with what happened hour by hour. If labels are rebuilt at sub-daily
resolution from GK2A/AMI observations, directional signal — if it exists at
the modelled scale — becomes learnable.

- **H1:** under sub-daily labels, `wind_alignment` (same single feature, same
  definition, same code path) carries materially more importance than under
  daily labels on the *same fires* (criterion in §5).
- **H0:** it does not.

Either outcome is a *first* characterisation, and both will be reported with
equal prominence. ⚠ Neither outcome revives the withdrawn conclusion: a
larger directional importance would not make 「severity ≫ direction」
established, and a null would not make it true — the three grounds in §0 are
about the comparison's construction, not its value.

## 2. Data access — investigated 2026-08-29, with the gate that stopped it

**Why GK2A:** AMI observes the full disk every 10 minutes (Korean peninsula
every 2 minutes) at ~2 km IR resolution, and produced continuous fire-area
observation on the 2022 Uljin fire where MODIS-class polar orbiters managed
1–2 passes per day.

| arm | product | endpoint | key? | coverage of our six LOFO fires |
|---|---|---|---|---|
| **primary** | GK2A AMI **L2 FF (산불탐지)** — pixel-level fire detection, the label source that avoids in-house detection algorithms | KMA **API Hub**: https://apihub.kma.go.kr — product list 「위성GK2A 기상산출물」 https://apihub.kma.go.kr/apiList.do?seqApi=6 (HTTP GET with `authKey` parameter); NMSC datasvc (datasvc.nmsc.kma.go.kr) is the other portal | **YES — personal 인증키. STOP.** Filed as an action item for John in `docs/BLOCKERS.md` with the signup URL. No key was requested and no authentication was worked around. | full mission archive (2019-07→), i.e. all six fires incl. miryang_2022 / uljin_samcheok_2022 |
| fallback | GK2A AMI **L1B** radiances (FD 10-min, LA 2-min) | NOAA NODD open bucket `s3://noaa-gk2a-pds` (AWS us-east-1, `--no-sign-request`; verified listable 2026-08-29) | no | **2023-02 → present only** (verified against the bucket listing): covers gangneung_2023, hongseong_2023, uiseong_andong_2025, yeongdeok_2025; excludes miryang_2022 and uljin_samcheok_2022 |

### 2a. Plan B — the keyless L1B arm, and the burden it carries

**The access split, stated once and plainly:** the **L2 산불탐지 (FF)**
product — the one that would hand us fire pixels somebody else validated —
**requires a KMA API Hub 인증키, and that key is the primary blocker**
(`docs/BLOCKERS.md`; the session stopped there rather than working around
authentication). The **L1B radiances are keyless** on NOAA NODD
(`aws s3 ls --no-sign-request s3://noaa-gk2a-pds/AMI/L1B/FD/`, listing
verified 2026-08-29), and their archive begins **2023-02**, which **does
cover the March 2025 경북 fires** (uiseong_andong_2025, yeongdeok_2025) as
well as gangneung_2023 and hongseong_2023. So plan B is *runnable today*
without asking anyone for anything.

⚠ **What plan B costs, so it is never mistaken for a free substitute.** L1B
is radiance, not detection. Deriving hotspots means building a mid-infrared
(~3.8 µm, AMI's SW038 fire channel) versus window-channel (~11 µm)
brightness-temperature-difference detector ourselves, and that detector
becomes **part of the result**:

1. **It needs its own validation before any label built from it is usable** —
   at minimum, agreement against FIRMS/VIIRS detections over the same fires
   and hours, reported as its own numbers. An unvalidated detector would make
   a null result uninterpretable (did direction not matter, or did we simply
   fail to see the fire?).
2. **Its thresholds are a researcher degree of freedom.** They must be fixed
   *before* the direction analysis and stated in this document, or the
   experiment stops being preregistered.
3. **Two of the six LOFO fires drop out** (miryang_2022, uljin_samcheok_2022
   predate 2023-02), so the daily-label baseline must be re-run on the
   reduced subset for the comparison to mean anything (§4).

Consequently plan B is **a fallback with an added confounder, not the
primary arm**: it converts an access problem into a measurement problem. If
the key arrives, the L2 arm supersedes it and the detector work is
unnecessary.

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
5. **Fallback (plan B) arm only**: our own 3.8 µm/11 µm hotspot detector's
   validity — which must be established against FIRMS/VIIRS *before* any
   label built from it is used, with its thresholds fixed in advance (§2a).
6. **Subset non-representativeness**: the fallback arm drops the two 2022
   fires, including the one (Uljin) with the best-documented GK2A fire
   observation record.
7. **Baseline fragility of the comparison itself.** The daily-label side of
   the comparison must be re-run in the *same* session as the sub-daily side.
   The tree already contains two LOFO lineages that differ by a corrected DEM
   (`spread_v2_lofo.json` vs `spread_v2_lofo_dem_corrected.json`,
   `docs/dem_defect_2026-08-02.md`), and today's inputs reproduce the
   corrected one — so quoting a stored daily-label number against a freshly
   computed sub-daily one would compare two things that differ by more than
   the label.

## 7. What exists in the tree after this session

- This plan.
- `src/wildfireguardian/fire_detection/gk2a.py` — loader scaffold, raises
  `NotImplementedError`, docstring points here. **No stub data, no
  placeholder arrays.**
- The blocker entry with the exact signup URL (`docs/BLOCKERS.md`) — the
  **L2 key remains the primary blocker**; plan B (§2a) is documented as
  runnable-but-costly, not as a reason to close it.
- **No GK2A data, no labels, no importance numbers.** Generating synthetic
  GK2A-like data and reporting any direction-importance number from it was
  explicitly forbidden and was not done.
- **No numeric importance ratio anywhere in this document** (revised
  2026-08-29): there is no committed claim about direction importance to
  quote, so quoting one here would manufacture the very anomaly the plan is
  supposed to be establishing a baseline for.

## References

- Rothermel, R. C. (1972). USDA Forest Service INT-115.
- Finney, M. A. (1998). FARSITE. USDA Forest Service RMRS-RP-4.
- Richards, G. D. (1990). *IJNME*, 30(6).
- Kang, Y., Lee, S., Cho, D. & Im, J. (2026). *Communications Earth &
  Environment*, 7:684 — cited **only** for Layer-0 readiness framing and its
  own statement that its outputs should feed localized fire activity models
  (1° / daily FWI / 31-day horizon; **not** a spread-direction input).
