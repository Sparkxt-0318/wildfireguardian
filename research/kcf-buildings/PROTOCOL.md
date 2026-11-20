# kcf-buildings: real household, resident, vehicle and building numbers for the 174 places (frozen before any result)

Frozen 2026-11-20, Main at `7c9fa18c` (PR #230). Working branch `research/kcf-buildings`. No hard stop; the work is
pushed at least once a day. Nothing in §1–§8 changes after the first result is computed. A mistake found later is
corrected by a dated **amendment** at the bottom with its reason, never by editing this text. A test that fails is
reported as failed.

**Every number here is a count taken from a public register or statistic, or an estimate built from one, used as
input to a model of reconstructed fire and road data. It is not what happened to people. It is not an order or advice
to any official.**

## 0 What had been looked at before freezing

* The data folder `~/Desktop/wildfire 3 (1)` (the same as "wildfire 3" in the Google Drive folder "wildfireguardian"):
  it holds one file, `DATA_INDEX.md`, written 2026-11-19. That file says the folder holds **no population,
  household, vehicle or building data and no key** (the finals forecast and the heat data are committed in the repo,
  under `research/`). The Google Drive copy cannot be reached from here. So **no key was read from the folder**. The
  environment variable `DATA_GO_KR_KEY` is not set (checked: set / not set only, no value printed). No key was
  searched for anywhere else on this machine. Consequence: the national building register (건축물대장, data.go.kr)
  and VWorld (both need a key) are **not used**. The fallback of the task text is used: open building footprints.
* Reachability only (HTTP status, no data read): `jumin.mois.go.kr` 200, `stat.molit.go.kr` 200, `www.data.go.kr`
  200, `api.vworld.kr` 200, `kosis.kr` 302, Geofabrik `south-korea-250321.osm.pbf` 301 (exists), Microsoft building
  footprints index 200. In the Microsoft index (`dataset-links.csv`, 1.47 MB) no location name contains "Korea";
  Google Open Buildings does not cover Korea. So the open footprint source is **OpenStreetMap, snapshot 2025-03-21**,
  the same snapshot as the road graph of `wfg-roadlayer`.
* The form of the MOIS monthly download (`downloadCsv.do`, option "all 읍면동") and its header line and the first
  four lines (Seoul). **No row of any of the 174 places' 읍면동 had been read.**
* The structure (columns, counts) of the existing inputs: `product/wfg-roadlayer/data/households/*.csv` (equal split
  of a 시군 or 읍면 total over 법정리), `data/traffic_sources.json` (1.198 vehicles per household, Gyeongbuk
  province), `research/kcf-queue/PROTOCOL.md`, `RESULTS.md` (headline: 55 of 1,119 place-hours cannot clear), the
  runner `kq/run_real.py`. **No new household, vehicle or building number, and no rerun of the queue model, existed.**

## 1 What is computed

For each of the **174 places** of `research/kcf-replay/per_place.csv` (169 villages and hamlets, 5 care facilities;
two regions, Yeongdeok and Uiseong-Andong), a table with: households, residents, residents aged 65 or over,
registered vehicles, buildings by use (house, apartment or multi-unit, care facility, school, other, unknown) and the
names of care facilities and schools. Then the queue model of `research/kcf-queue` is rerun with these numbers
instead of the assumed ones, and the village cards and fragility table of `product/wfg-roadlayer` are updated.

## 2 Sources, in the order tried (each dataset's date is recorded in the output)

| id | quantity | first choice | fallback | date wanted |
|---|---|---|---|---|
| a1 | households, population, by 읍·면·동 | MOIS 주민등록 인구통계 (`jumin.mois.go.kr`, monthly, "all 읍면동" CSV) | the published county tables already cited in `traffic_sources.json` | 2025-02 (last month-end before the fire of 21–28 March 2025) |
| a2 | residents aged 65 or over, by 읍·면·동 | MOIS 연령별 인구통계 (same site, same month) | none: reported as "not available" | 2025-02 |
| a3 | per 리 (행정리 or 법정리) households | none is published by MOIS or KOSIS for a 리; the task asks for it, so it is **ESTIMATED** from §3 | equal split (the old rule) | — |
| b | registered vehicles by 시·군·구 | MOLIT 자동차 등록현황 (`stat.molit.go.kr`) | KOSIS table; else the province ratio already in `traffic_sources.json` (then labelled "province ratio, not district") | 2025-02 or the closest earlier month |
| c1 | building footprints and use, care facilities, schools | national building register (건축물대장, `DATA_GO_KR_KEY`) | road-name address building database; VWorld | not used: no key |
| c2 | (same) | **OpenStreetMap, Geofabrik `south-korea-250321.osm.pbf`**, read with GDAL (`ogr2ogr`) | — | 2025-03-21 |

Each fetched file is stored under `research/kcf-buildings/data/` with its URL, fetch time and SHA-256. A source that
cannot be fetched is recorded in `SOURCES.md` with the error, and the next one is used.

## 3 How buildings and households are assigned to a village (frozen rule)

1. **Residential building.** An OSM `building` is a *dwelling* if its tag is `house`, `detached`, `semidetached_house`,
   `terrace`, `residential`, `bungalow`, `farm`, `cabin`, or an untagged `building=yes` with footprint 20–400 m² that
   is not tagged as anything else (`amenity`, `shop`, `tourism`, `man_made`, `landuse` of a non-residential kind).
   Dwelling *weight* `w = 1`. An *apartment or multi-unit* building (`apartments`, `dormitory`) has `w = max(1,
   footprint area × levels / 80 m²)`, `levels` = `building:levels` or 1 (the 80 m² per dwelling is ASSUMED).
   Other uses (care facility, school, other, unknown) have `w = 0`.
2. **Use classes.** Care facility = `amenity` in `social_facility`, `nursing_home`, `hospice`; `healthcare` of the same
   kind; or a name containing 요양, 경로당(excluded: senior hall), 노인복지, 양로, 복지시설 (경로당 is reported
   separately, not as care facility). School = `amenity` in `school`, `kindergarten`, `college`. Their names are kept.
3. **Village cell.** The anchors are all OSM `place` nodes of kind village, hamlet, neighbourhood or isolated_dwelling,
   plus the 174 places themselves, that lie inside the same 읍·면·동. A building is given to the **nearest anchor
   inside the same 읍·면·동** (a Voronoi cell clipped to the 읍·면·동; if OSM has an admin boundary for the 리 that
   contains the building, that boundary is used instead and the anchor of that 리 receives it). The 읍·면·동 polygon
   is the OSM boundary (`admin_level` 8 or 9 relation) containing the place; the MOIS row is found by the Korean name
   and the 시·군; if the name and the polygon disagree the polygon wins and the place is flagged.
4. **Households.** Village households `H_v = H_eupmyeondong × W_v / ΣW`, `W_v` the dwelling weight sum in the
   village cell, `ΣW` the sum over all cells of that 읍·면·동 (MOIS, 2025-02). Residents `P_v = P_eupmyeondong ×
   W_v / ΣW`. Residents aged 65 or over `A_v = P_v × (65+ share of the 읍·면·동)`. All three are **ESTIMATED** at
   village level and **MEASURED** at 읍·면·동 level. The 읍·면·동 totals are reproduced exactly by construction (checked).
   Where a 읍·면·동 has no dwelling in OSM, or the place cannot be matched, the old equal split is kept for that place
   and it is listed in the limits as "not matched".
5. **Vehicles.** `V_v = H_v × (registered vehicles of the 시·군·구 / households of the 시·군·구)` (b above and a1), an
   **ESTIMATE** (district rate, not a count per village). "Registered vehicles" = all registered vehicles of the table,
   the same definition as the 1.198 per household of the old arm; passenger cars alone is a sensitivity row.
6. **Buildings at risk.** For a card for issue hour `T`, the number of the village's buildings (by use) that stand in
   a 375 m cell which the MEASURED-arm closure field of `research/kcf-replay` reaches within the 8 h horizon (closure
   second `<= H`). It is a count of buildings in cells the reconstructed fire reaches, from the same field the queue
   model uses. **No fire is spread from building to building**; no building is ignited, shielded or burned in any
   computation.
7. **Checks reported, none used to filter:** per 읍·면·동, OSM dwellings per household (a completeness proxy; the
   MOIS totals anchor the level, OSM only decides the split inside a 읍·면·동); number of anchors per 읍·면·동; share
   of households given to the 174 places; the spread of the new `H_v` against the old equal split.

## 4 The rerun of the queue model

Same code (`research/kcf-queue/kq`), same fire arm (MEASURED, 8 h), same 13 issue hours (12:00–24:00 KST, 25 March
2025), same capacities, spread, smoke factor, shelters, neighbour rule and the same place-hours (1,119 at 137 places).
**Only the demand changes.** Assumed arm = `N_v = round(H_equal-split × 1.0 × 1.198)`, as before. Real arm = `N_v =
round(V_v)`, `V_v` of §3.5, from the registered households and the district vehicle rate. The neighbours' vehicles
also change. The headline is MIDDLE parameters, CONTESTED. LOW and HIGH (spread, smoke, road capacity ends; the
household and vehicle multipliers are **not** applied to the real counts, since those multipliers stood in for the
missing data) are run as a second table. The queue model's own tests (T0–T5, certificates, checker) are rerun
unchanged on the real arm and their verdicts reported.

## 5 What is compared (side by side, same place-hours)

1. Clearance time per village: (i) the card's no-queue clearance line `N_v / 800 veh/h`, assumed vs real; (ii) the
   queue model's leave-by start `s*` (and the shift `L0 − s*`), assumed vs real. Median, quartiles, maximum.
2. **How many leave-by times change**: place-hours where `|s*_real − s*_assumed| >= 60 s`, `>= 10 min`, and where the
   state changes (clears / cannot clear).
3. How many place-hours cannot clear: **55 of 1,119** with assumed numbers against the real-arm count (MIDDLE,
   CONTESTED), and which places move in or out.
4. Which villages change most, by demand (`N_real / N_assumed`), by `s*` shift, and by minutes of queue delay;
   top 10 each, with the reason where the data show it (a large village that the equal split gave too few
   households; a small one given too many).
5. A one-row-per-measure before-and-after table in `RESULTS.md`.

## 6 The village cards and the fragility table

`product/wfg-roadlayer` cards and fragility sheet show, for the place: households, residents, residents aged 65 or
over, and buildings at risk, each marked **MEASURED** (a register count for exactly that place), **MEASURED (읍·면·동)**
(a register count for the 읍·면·동, shown with the village estimate) or **ESTIMATED**. The card's old assumed numbers
are not deleted from the data folder; the card reads the new file. Cards and tests are rebuilt and the golden files
updated with the reason in the commit.

## 7 Limits stated now

No 리-level register was reachable, so the per-village numbers are estimates inside measured 읍·면·동 totals. OSM is
incomplete and uneven in rural Korea; the split inside a 읍·면·동 inherits that. OSM `building` tags often carry no
use; "unknown" is large and is shown, not hidden. Registered vehicles are where a vehicle is registered, not where it
is parked or driven from. Residents 65 or over use the 읍·면·동 share, which understates old villages and overstates
villages with young families. The MOIS counts are of 2025-02, a month before the fire; the fire destroyed homes and
later counts differ. Care facility resident counts are not in any source tried (kept at the old assumed 30, labelled
ASSUMED). Households are registered households: second homes and non-registered residents are not counted.

## 8 Outputs

`RESULTS.md` (one before-and-after table, limits with register dates and the villages that could not be matched, and
five lines for `research/kcf-evidence/TALK_NUMBERS.md`), `SOURCES.md`, `data/` (fetched files with hashes),
`per_place_real.csv` (174 rows, every figure with a status column), the rerun outputs under
`research/kcf-queue/results_real/`, and the updated `product/wfg-roadlayer` files.

## 9 Amendments

(none yet)
