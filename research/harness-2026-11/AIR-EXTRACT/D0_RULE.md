# D0 air row: build rule and pass criteria (written 13 Nov, before any build)

> **Staff and agency use only. Not resident-facing.** Research rows about the distance to registered forest-aviation
> operating sites. These are **not pickup points**. Flight feasibility is the pilot's and the agency's decision. A row
> **never** counts as resolving a place.

This file implements DESIGN.md §3.1 (D0; the assessor's row). It fixes how D0 is built and what must hold. The
assessor reads this rule before the build, and the independent verifier checks the output.

## 1. Preconditions (each must hold before the build; otherwise D0 is not built)

- **P-a, register.** The 산림청 CSV (data.go.kr 15069465) has been reviewed for provenance by the provenance verifier.
  - The file is the one the data-fetch author fetched: sha256 55f666251b5e803ad2fd92eaaf1a8518200045038dc03838b0d76f73b6137931,
    116,211 bytes, CP949 (manifest @ ca7133d8).
  - It stays out of git. A copy is obtained only from the data-fetch author's scratch, or by re-fetching through the
    same public flow, and must match that sha256.
  - **Status at writing:** the review is not yet recorded. D0 waits for it.
- **P-b, boundaries for the point-in-polygon check.** 시군구 boundaries come from the OSM snapshot already used for the
  road graphs: south-korea-250101.osm.pbf, sha 9b67fc95…, `boundary=administrative`, `admin_level=6`.
  - **Label:** "OSM administrative boundaries as of 2025-01-01".
  - Extraction is done with pyosmium in the existing venv, and the extract's sha256 is recorded.
  - Only sites that could be a nearest site are checked: those within 100 km of any listed place.
- **P-c, wind source.** A wind source must be named **before** the wind gate is computed, stating whether it carries
  gusts (DESIGN §3.1).
  - **None is named at writing.** Until one is, the wind gate is **not evaluated**, and every row says so (§4).
  - Daylight is computed regardless (§4).

## 2. Rows

- **One row per unit on the early-action main list** (EARLY_ACTION_LIST.json @ 2f6275f7, 166 units).
  - Units with label 3 and the unclassified-closing units get rows too. They keep their list labels and are never
    counted as resolved.
- **The time of the row** is the unit's first computed departure in the set (`first_grid_departure_in_set`). It is
  written as "YYYY-MM-DD HH:MM KST (replay)".
- **Place location:** the origin point from the planner's `places.geojson` for the region (the source INSTANCE names).
  It is the place node, not a building.

## 3. Nearest registered site

- **Parse rule** (the data-fetch author's, unchanged): a site is **usable** only if its DMS minutes and seconds are both
  below 60 and the point lies inside 33–39°N, 124–132°E. That gives 538 sites. Blank (24) and invalid (65) sites are
  never repaired or guessed.
- **Datum:** "not given by the source; read as WGS84/GRS80 geographic". At these distances the choice is immaterial,
  and the text says so.
- **Distance:** geodesic on the WGS84 ellipsoid (`pyproj.Geod`), from the place point to each usable site. The row
  gives the nearest site's name (이착륙장명), its 관할기관명, the distance to 0.1 km, and its 시군구.
- **Unusable sites in the place's 시군구:** every row gives, verbatim, "N registered site(s) in <시군구> excluded:
  coordinates blank or invalid in the source; an excluded site could be nearer". N may be 0.
  - The 시군구 is taken from the place point (P-b polygon). The register's 시군구 is taken from its address text.
- **Point-in-polygon result per usable site within 100 km:** "inside the 시군구 named in its address" or "outside it".
  A site found outside is **kept, and flagged**. Its coordinates are not changed. The count of such sites is reported.
- **의성:** every 의성 row says "의성 has 0 registered sites in the source".
- **울진:** every 울진 row says "1 registered site in 울진 excluded: coordinates invalid in the source".

## 4. Flight gate at the row's time

- **Daylight:** the sun's elevation at the place point and the row's time, from the NOAA solar-position algorithm,
  implemented and unit-tested against published sunrise and sunset for one date and place.
  - **Night** = the sun's centre below −0.833° (the standard sunrise/sunset refraction convention). The convention is
    stated.
  - **Source of the rule:** night needs NVG and lit sites (119항공대 운영 규정, 소방청훈령 제478호, 제22조). PMS 510
    prohibits carrying passengers at night in a single-engine helicopter.
- **Wind:** not evaluated until P-c holds.
  - Once it does, the limits are 40 kt (Type 1–2) and 30 kt (Type 3), with a 15 kt gust spread. They are labelled "US
    interagency reference (NWCG PMS 510)".
  - The Korean rule defers to each aircraft's manual.
  - If the source gives mean wind only, every row says "hourly mean wind; gusts not represented; the gate errs toward
    'not excluded'".
- **Visibility and smoke:** not evaluated. There is no source for visibility at the time, and smoke is UNSOURCED.

**Status, one of exactly two strings:**
- **"excluded (night, or wind over the published limit)"**, with the reason named (night / wind);
- **"not excluded by the gates evaluated (X not evaluated)"**, where X lists every gate not evaluated. Until P-c holds,
  X is "wind, smoke and visibility". Afterwards it is "smoke and visibility".

Every row also carries:
- "flight feasibility is the pilot's and agency's decision";
- "forest-aviation operating site, not a pickup point";
- "this row does not resolve the place".

## 5. Summary count (reported with the table)

- Of the rows: how many are excluded by daylight alone, by wind alone, and by either.
- How many are not excluded by the gates evaluated.
- Which gates were evaluated.

The assessor's hypothesis (most excluded) is stated as a hypothesis, and the count is the finding.

## 6. Outputs

- `AIR-EXTRACT/results/D0_AIR_ROW.json` and `.md`.
- Header: the staff/agency label, the absence line ("one fire, March 2025, that day's wind. A place not on this list
  has not been shown to have a road escape."), the datum statement, the register sha256, the boundary extract sha256,
  the gates evaluated, and the input sha256s.
- Builder: `AIR-EXTRACT/build_d0.py`, committed before it is run.

## 7. Pass criteria (fixed now)

- **D1, rows.** There is one row per main-list unit (166), and no others.
- **D2, register.** The CSV sha256 equals the pin. Usable / blank / invalid = 538 / 24 / 65 under the parse rule. No
  unusable site contributes a distance.
- **D3, nearest.** For each row, no usable site is nearer than the reported one. This is checked by a second,
  independent distance routine (haversine on a sphere of radius 6,371.0088 km), which must agree on the identity of the
  nearest site, or be within 0.5% where two sites tie.
- **D4, exclusion text.** Every row carries its 시군구's excluded count. 의성 rows carry the 0-sites text and 울진
  rows the invalid-site text.
- **D5, point-in-polygon.** Every usable site within 100 km has an inside/outside result. Every site outside is
  flagged on the rows where it is the nearest.
- **D6, daylight.** The solar routine reproduces the published sunrise and sunset for the test date and place within 2
  minutes. Every row has a daylight result.
- **D7, statuses.** Every status is one of the two strings in §4, and X is complete. The words "flyable", "possible",
  "safe", "rescue" and "evacuate by air" appear nowhere.
- **D8, labels.** Every row carries the three fixed strings (§4), and every file carries the header lines (§6).

## 8. Amendment 1: preconditions settled by the orchestrator (13 Nov, ~12:43Z; before any build)

- **P-a, register.**
  - I re-fetch the CSV through the same public data.go.kr flow (manifest @ ca7133d8), into its own empty directory,
    and require sha256 55f66625…. **If the sha differs, D0 stops and reports. The file is not used.**
  - The provenance verifier is asked for a ledger row on the file. **D0 results are not cited until that row
    exists.**
- **P-b, boundaries.** The OSM `admin_level=6` boundaries from the 2025-01-01 pbf are confirmed, labelled
  "OpenStreetMap administrative boundaries, snapshot 2025-01-01".
  - **Cross-check:** for every place used, the place → 시군구 assignment from the polygons must agree with the merged
    jurisdiction labels (labels.json, 177 places).
  - **Any disagreement is reported, not resolved.** The row then carries both assignments.
- **P-c, wind.**
  - **Source:** the Open-Meteo historical archive (no key; the same service as the weather stream), 10 m wind speed
    **and** gusts at each site and place for the replay hours.
  - **Label:** "reanalysis-based, not observed; grid scale kilometres; not a flight-safety assessment".
  - **Quota:** the calls are agreed with the data-fetch author before any is sent, because the daily quota is shared.
    A few hundred weighted calls at most, sent today before 23:30Z or after his 00:12Z day-2 run.
  - **If gusts cannot be served for those dates,** D0 evaluates daylight only and says so.
  - **Gate:** with gusts, the wind gate excludes when the mean is above the limit or the gust spread (gust − mean) is
    above 15 kt, under the Type 1–2 limit (40 kt). The Type 3 limit (30 kt) is reported beside it.
  - **Location and hour:** the wind is read at the place point and at the nearest site, at the row's hour. Either one
    over the limit excludes. The values used are shown.
- **Smoke and visibility:** not evaluated.
- **KMA station data:** only if the assessor rules the reanalysis insufficient for a staff-only planning row.
- **Status text once wind is evaluated:** "not excluded by the gates evaluated (smoke and visibility not evaluated)".

**P-b done (13 Nov).**
- **Boundaries.** `extract_sigungu_osm.py` on the 2025-01-01 pbf (sha 9b67fc95…) gives 230 `admin_level=6` polygons,
  0 failed rings. The extract's sha256 is 3427c103c465f8f6…; it is kept outside the repository.
- **Cross-check.** `check_place_sigungu.py` → `results/PLACE_SIGUNGU_CHECK.json`: all **59 of 59** distinct places on
  the early-action main list get the same 시군구 from the OSM polygons as from labels.json (V-World BND_SIGUNGU_PG,
  2025-06-30). There are **0 disagreements**.
