# The forecast track — what the field looks like when the weather is not known in advance

**Row:** Part B of `docs/auto/briefs/HINDCAST_CORRECTION.md` (the author's HQ brief,
2026-09-14). **Status:** the rule below is **declared before anything runs**, which is the
whole point of the page; §4 is empty until a run fills it.

## 1. Why this page exists

`docs/benchmark/results_v0.1.md` §2 measured that `forward_simulate` advances each step
with the **next step's real weather** — ERA5 reanalysis at times **after T0**
(`src/wildfireguardian/spread_v2/forward_sim.py`, steps 2 and 5). So every committed
spread field in this repository is a **hindcast**: a reconstruction of what the fire did
with the weather that actually occurred, not something anyone could have issued at
ignition. The protocol this project wrote put its own entrant in the hindcast track for
exactly that reason.

That is not a defect in the router and it does not void a routing result. It means the
routing headlines (42 of 458, 91 of 368, the 27 margin, the 주건물 fold) measure **what the
routing method gains from a good spread field**, and not the accuracy of a forecast. Part A
of the brief put that sentence on every judge surface beside every one of those numbers.

This page is the other half: **the field that would make the word 「forecast」 true**, and
what the same routes do on it.

## 2. Rule (declared 2026-09-14, before any run)

Two entrants. Both are **leave-one-complex-out** — 영덕 **and** 의성·안동 both held out of
training, the same fold `scripts/run_leakfree_yeongdeok_fold.py` fits — on the **canonical
영덕 canvas**, with the **canonical seed**, the **canonical steps**, and **new npz
filenames**. The canonical npz and every committed artifact are untouched and
digest-checked before and after.

- **F1 — frozen weather at T0 (no forecast at all).** Every step uses the ERA5 values at
  the **last time at or before T0** and holds them for the whole simulation. This is what
  an operator with no forecast would assume: that the weather at ignition is the weather
  they will get. It needs no new data.
  ⚠ **「last time at or before T0」 and not 「nearest time to T0」**, and the difference is
  the whole point: `WeatherSeries.at` picks the nearest index, which at a step boundary can
  be a **later** observation. An operator standing at T0 cannot see it, however close it
  is. F1 freezes the value arrays so that no lookup can reach past T0.
- **F2 — KMA 동네예보 issued before T0.** 초단기 where it covers, else 단기, mapped onto the
  model's weather features (10 m wind → u/v, T, RH → VPD, precipitation). This requires the
  archived forecast files from 기상자료개방포털 under `data/raw/kma_forecast/` with a
  `MANIFEST.json`. **If that manifest is absent the F2 script refuses to run and says why**;
  it does not fall back, and it does not substitute reanalysis for a forecast.

For each field that runs:

1. **Score it on the benchmark** with `scripts/benchmark/score_kspread.py`, as entrant
   **E4a** (F1) or **E4b** (F2), in the **forecast track** — the track the entrant belongs
   to because no input is an observation after T0. Protocol §3's separation holds: a
   forecast-track score is never reported beside a hindcast-track one as though they
   were comparable.
2. **Route the 458 canonical origins** and the **19,250 주건물 nodes** exactly as
   `scripts/run_leakfree_yeongdeok_fold.py` routes them — the same canonical origin set
   chosen at the canonical T0, the slope DiGraph, `p_cut` 0.5, a 600-minute budget and a
   10-minute step — and report the three-way partition beside the **canonical** and
   **leak-free** rows.
3. **Grade the routes on the observation** with the three-way rule of
   `docs/regrade_three_way.md` §2 (cell membership, A1–A6, miss allowance *m* = 0 as the
   headline). This is the number that does not depend on which field planned the route,
   which is why it is the one to carry forward.
4. **Last-safe-departure counts under the 5-hour rule**, with the cuts
   `docs/last_safe_departure.md` already fixed: `never`, `closes_before_5h`,
   `closes_after_5h`, `censored`.
5. **The four-way rescue split on the NH-057 scene** (`docs/rescue_routing_real_hazard.md`),
   recomputed on the forecast-track field.

New artifacts go under `data/processed/forecast_track/`; figures in the house style
(`paper/style.py`) go to **new filenames** under `docs/figures/finals/`. Nothing here is
registered in `docs/NUMBERS.json` and nothing here goes on a judge surface.

## 3. The reading rule, fixed now

**Whatever F1 and F2 say is the result.**

- If the forecast-track field **recovers most of the hindcast's routing advantage**, then
  the method's value is shown to **survive forecast error**, and the routing headlines mean
  more than they did before this page existed.
- If it **recovers little**, then the finding is that the router's value **depends on
  forecast quality** — quantified here for the first time — and the open benchmark is where
  that gets fixed.

**Neither outcome is edited into a better one.** No number on this page is moved, rounded,
re-cut or re-bucketed after it is seen, and no threshold below is chosen after the run.

⚠ **What a bad F1 result would NOT mean.** F1 is deliberately the *worst* honest
assumption — no forecast at all, the weather at ignition held flat for twelve hours — so it
is a **floor** and not an estimate of what a real forecast buys. A large gap between F1 and
the hindcast bounds how much of the routing advantage came from knowing the weather; only
F2, on a real issued forecast, says how much of that a forecaster could have recovered.
Reporting F1 alone as 「the forecast result」 would be the same error this whole correction
exists to fix, in the opposite direction.

⚠ **One fire, one ignition, one start time.** Everything here is 영덕 2025. Nothing on this
page is evidence about another fire, another region or another country.

## 4. Results

_Empty by construction: nothing has been run. §2 was written first and this section is
filled only by a run that obeys it._

## 5. What could not run, and why (2026-09-14)

The session that wrote this page was a **cloud container**, not the author's laptop.
`data/raw/**` is git-ignored, so the FIRMS/ERA5/DEM bundle never reaches a fresh clone
(CHARTER §4 「Sandbox facts」). Measured in that container rather than assumed:

- `data/raw/firms_data/` does not exist; `$WFG_FIRMS_DIR` is unset; a filesystem-wide
  search for `*_era5.nc`, `*_dem.tif`, `firms_data.zip` and `*_detections.csv` returned
  nothing.
- F1 needs all three: `{fire}_era5.nc` for the weather to freeze,
  `{fire}_dem.tif` for the slope walk network
  (`run_leakfree_yeongdeok_fold.py:165`), and `{leak}_detections.csv` for the overlap count
  (`:103`).
- `data/raw/kma_forecast/MANIFEST.json` does not exist either, so F2 refuses for the reason
  §2 says it should — which is the behaviour the brief asked for, not a failure.

⚠ **An empty `data/raw` in a fresh checkout is not evidence that the author has no data**
(the correction commit `4994f99` of 2026-09-14 exists because a previous session made
exactly that inference). The claim here is narrower and is the only one this container can
support: **this session cannot reach the bundle**, so F1 was written and not run.

Both scripts are committed and are the laptop's to run:

    python scripts/run_forecast_track_f1.py          # needs the raw bundle
    python scripts/run_forecast_track_f2_kma.py      # refuses unless data/raw/kma_forecast/MANIFEST.json exists

Until §4 is filled by such a run, **this page states no result**, and no surface anywhere in
the repository may cite one from it.
