# AIR-EXTRACT: open-ground candidates near places with no road escape (design note; DRAFT, plan only; scope pending the orchestrator)

**Status.**
- This is a skeleton. Leo and Richard write it together; the split is agreed (Richard: A, C's checker use, E; Leo: B, C margins, D).
- **No code and no build** until Iris has assessed the finished note.
- Person-facing wording waits until Clara's pause lifts.
- Every threshold below is a **named parameter with no value** until a source is attached:
  - Sofia gives the landing-zone numbers;
  - Priya gives the radiant stand-off;
  - Daniel gives the layers.

**Iris's judgement (2026-11-12 22:36 UTC, on Sofia's note; the orchestrator decides).** DROP as a person-facing
output.
- **Why:**
  - The conditions that close roads in a wind-driven fire also ground helicopters.
  - There is no published numeric smoke limit.
  - There are 0 registered sites in 의성, and registered sites are operating bases, not pickup points.
  - A resident message mentioning a helicopter where there is no road route invites waiting.
- **At most, a staff-only research row** for no-route and unresolved origins:
  - distance to the nearest registered site;
  - whether daylight and the published wind limits allowed flight at that time;
  - "possible only if flyable";
  - never a route, and never counted as resolving an origin;
  - the smoke gate labelled unsourced;
  - it must not delay the multi-hour gate or the benchmark.

**This note follows that ruling once the orchestrator gives it.** Until then, sections B–D are kept staff-only, and the
smallest version (Iris's row) is listed first in D.

**Owner direction (via the orchestrator, 2026-11-12 22:25 UTC).** Produce "air-extraction candidates" for places
with no road escape. It comes after current work and must not displace `no_reentry/2`.

**What this is not.**
- A candidate is "open-ground candidate", never "safe to land" and never "landing zone".
- Every table carries this line: "Whether a flight is feasible is the pilot's and the agency's decision; this table
  lists open ground only."

## A. Which places have "no road escape" (Richard; Leo supplies the packets)

**Draft definition.** A place is in the labelled set **NO_CHECKED_ROUTE** when it has no checked route under each of
the three timing variants: kriged_mean, firms_early and envelope. envelope_burnset is reported as its own row
(Richard, position 1 below).
- Packets: `no_reentry/2` (MANIFEST_v3_7, once Nora passes it).
- Router: Richard's full checker.
- It is never reported as a bare "no route".

**Split by cause.** Each place in the set gets exactly one label, in Richard's precedence (position 3 below):
1. **at-issue.** The origin is in flame at the departure.
2. **fire-limited.** Inside the loaded graph, every exit is blocked by fire under every variant.
3. **road-limited.** The only exits leave the loaded graph. The graph is clipped: the c651 window, or the export grid
   + 5 km under Daniel's rebuild. So the result says nothing about roads outside it, and these places are listed
   separately, not as air candidates.

**Sensitivity to waiting.**
- Waiting is allowed only at graph dead-end nodes, as supplied in graph.json; the rule is undocumented and the owner
  has been asked.
- The set is also reported under "waiting nowhere" and under "waiting anywhere". Membership that changes between them
  is flagged.

**Departure grid.** As in Richard's headline: the 30-min grid, per region, start and horizon.

**Richard's positions (2026-11-12 22:31 UTC; his full A and E text to follow, committed with credit).**
1. **Quantifier.**
   - NO_CHECKED_ROUTE needs **all three timing variants** to give no route: kriged_mean, firms_early and envelope. It
     is their intersection.
   - A per-variant table is always shown alongside.
   - envelope_burnset is its own row and does not enter the intersection.
2. **Place to origin.** A place maps to its start node(s) as the caches record them. A place with several nodes
   qualifies only if all of them have no route.
3. **Cause precedence:**
   1. at-issue: the origin point is in flame at departure;
   2. fire-limited within the loaded graph;
   3. otherwise possibly road-limited. A route off the clipped graph is not excluded, so these places are **not air
      candidates by default**. They are listed separately as "graph window too small to decide".
4. **Waiting.**
   - The headline uses the supplied rule: waiting only at dead ends.
   - "Waiting anywhere" can only remove places, and "waiting nowhere" can only add them. Both are reported as counts.
5. **E.** Without a sourced incident list, the note states that nothing is validated.

## B. Candidate-site rule (Leo; layers from Daniel; values from Sofia)

**Sources.** Sofia's note to Leo, Richard, Iris and the orchestrator (2026-11-12 22:35 UTC). Her research agents opened
every source, and she re-checked the key figures herself. Unit conversions are her arithmetic.

**B1. Registered sites first.** 산림청 산림항공본부_이착륙장 정보 (data.go.kr 15069465):
- CSV, 627 rows, updated 2026-09-17, "이용허락범위 제한 없음";
- coordinates, surface, obstacles, approach directions and safety area;
- 경북 has 48 rows: 영덕 4, 청송 2, 영양 1, 안동 2-3 (string match), **의성 0**.

These are forest-aviation operating sites, not resident pickup points. Each one carries that label.

**B2. Open-ground candidates** (only if the orchestrator keeps more than Iris's row). An open polygon or patch qualifies
when it passes all three tests below. The values are sourced, but the choice of reference is not yet adopted.

| Parameter | Value | Source |
|---|---|---|
| `CLEAR_MIN_M` (safety-circle diameter) | 27.4 m (Type 2) / 33.5 m (Type 1); "at least 1.5 × rotor diameter" | NWCG PMS 510 (May 2023), Exhibit 8.3 |
| `SLOPE_MAX` | 6° (11%, "9:1"); Korean and ICAO heliport standards: 2% | PMS 510; 국토교통부고시 제2022-350호 제80조; ICAO Annex 14 Vol II |
| Approach path | at least the safety-circle width, ideally about 91 m long, with no obstacle above about 1:8 | PMS 510 |
| Improvised sites (Korea) | no size or slope given; "안전하다고 판단되는 장소" | 119항공대 운영 규정 (소방청훈령 제478호) |

**Not published anywhere Sofia opened:**
- a numeric smoke or visibility-in-smoke limit for landing;
- canopy or "open enough" criteria beyond obstacle clearance;
- capacity (people per trip).

`TREE_MAX` therefore stays a named parameter with no value.

**B3. Layers.** Daniel, 22:32 UTC. Design input only: nothing is fetched until the orchestrator approves a fetch plan.
- **Slope: Copernicus GLO-30**, 2021 release.
  - Public S3, no key; the host has been verified from our network.
  - Tiles N36_E128 and N36_E129 are already fetched and hashed in data-fetch.
  - Still needed: N36_E126, N35_E128 and possibly N37_E129.
  - It is the owner's own terrain product.
  - **GLO-30 is a DSM.** Slope over forest edges and small clearings is biased, so the threshold is stated as "slope
    from a DSM".
  - SRTM and NGII need accounts, so they are excluded.
- **Tree cover: ESA WorldCover v200**, 2021.
  - 10 m class map, class 10 = tree; CC BY 4.0. The host is not yet tested.
  - It is the only product fine enough for a pitch-sized clearing.
  - Optional cross-check: GLAD GEDI–Landsat canopy height 2019, for which a mirror is already found.
  - LC100 (100 m) is too coarse for a site test.
- **OSM polygons.**
  - They come from the same osmium pass as the roads, so there are no extra requests.
  - **The snapshot date is the issue.** The dated path is not working yet, and the fallback is a labelled **CURRENT
    (2026)** Geofabrik extract, not the fire date.
  - Completeness will be measured, not assumed. Example: OSM school polygons per 시군구 against an official count.
  - "Unmapped ≠ absent."

**Output of B.** A static candidate set per region, with the source layer and vintage for each site. Nothing in B
depends on fire.

## C. Time condition (Leo: arrival margins from packets; Priya: stand-off)

At departure time t, under a timing variant v, a candidate site is **open at t under v** when all three hold:
1. no cell within `BUFFER_M` of the site is burning, or has burned, at t;
2. the forecast arrival in that buffer is later than t + `MARGIN_MIN` under v;
3. no cell burning at t is within the radiant stand-off `STANDOFF_M` (Priya's table, cited as is).

**Burned buffer cells.** Under `no_reentry/2`, "has burned" uses C0 ∪ born cells. That is the same closure as the
routing packets, so a burned-out buffer cell counts as not open.

**Ranges.** Results are reported per variant: the window over t is a **range across variants, not a point**.
envelope_burnset is static, so it gives the most restrictive reading.

**Flight gate (Sofia's sources; applies to the whole option, before any site).**
- **Daylight only.** Night needs NVG and lit sites (119항공대 운영 규정 제22조). PMS 510 prohibits carrying
  passengers at night in a single-engine helicopter.
- **Wind** under the type limit: 40 kt (≈20.6 m/s) for Type 1-2, 30 kt for Type 3, with a 15 kt gust spread (PMS 510
  Exhibit 6.2). The 119 rule refers wind to "기종별 교범".
- **Visibility** at least 3,200 m over land (119항공대 운영 규정 제21조).
- **Smoke: no published threshold.** It is a named, unsourced input.

**March 2025 record (Sofia; press sources as cited in her note).** It is reported as context, not as a model input:
- gusts of about 27 m/s on 25 Mar forced 4 helicopters down;
- haze and smoke stopped flights on 23 and 25 Mar, and there were no night operations;
- after the S-76 crash in 의성 at 12:51 on 26 Mar, all fire helicopters were grounded until about 15:30;
- **no report of residents airlifted.** 104 residents were taken off 영덕 breakwaters by 해경 vessels.

**NOT modelled, listed in every table:**
- smoke and visibility (no published threshold);
- wind at the site (only the published type limits, applied as a gate);
- wires and obstacles (beyond the stated layers);
- aircraft availability, range and turnaround, and the grounding after an accident;
- crew procedures;
- ground conditions (soft field, dust);
- people's ability to reach the site;
- capacity per trip.

## D. Output: a planning table for staff and agencies (Leo)

**D0. Minimal form (Iris's row; listed first).** Staff-only, one research row per no-route or unresolved origin:
- the distance to the nearest **registered** 산림청 site (B1);
- whether daylight and the published wind limit allowed flight at that time (C gate);
- the smoke gate, labelled unsourced;
- the label "possible only if flyable".

It is never a route, and it is never counted as resolving an origin.

**D1. Full form** (only if the orchestrator keeps it). One row per place in the A set:
- the cause label;
- the **nearest k open-ground candidates**, k to be fixed;
- for each candidate:
  - the distance from the place on foot (straight line and along roads/paths if the graph has them, both labelled);
  - the source layer;
  - the **time window per variant** in which C holds.

Header line: "Open-ground candidates only. Whether a flight is feasible is the pilot's and the agency's decision."

## E. What the March 2025 replay could check (Richard and Leo)

- **Air extraction itself cannot be validated.** Sofia found no report of residents airlifted in March 2025.
- **One check of the A set (Richard).** 영덕 residents taken off breakwaters by boat (경정3리, 석리 etc.; about
  104 people; YTN 2025-03-26). Are those places in NO_CHECKED_ROUTE on the matching Yeongdeok starts, and with which
  cause label?
  - It needs a sourced mapping from each village to its origin node(s), and the incident time from the source.
  - Without both, nothing is validated.
- **The C flight gate against the record.** Wind, haze and night closures and the 26 Mar grounding, at the reported
  times.

These are checks against reported events, not proof that a site is usable.

## Inputs pending

| Who | What | Status |
|---|---|---|
| Richard | Split agreed (he: A, C's checker use, E; Leo: B, C margins, D); positions recorded in A; full A/E text | to follow, after his /1 batch and waiting runs |
| Daniel | Korea tree-cover/DEM products, OSM open-ground polygons in the extracts | received 22:32 (B3); fetch plan only after approval |
| Sofia | Sourced LZ size, slope, obstacle values, flight limits, registers, 2025 record | received 22:35 (B1, B2, C gate, E) |
| Orchestrator | Keep, reduce to Iris's staff-only row (D0), or drop | pending |
| Priya (via orchestrator) | Radiant stand-off table and its assumptions | asked |
| Iris | Assessment of the finished note before any build | after the draft |
