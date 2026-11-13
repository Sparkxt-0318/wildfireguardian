# AIR-EXTRACT: early action and air options for places with no road escape (design note; DRAFT, plan only)

**Status.**
- Plan only. **No build** until Iris has read this note.
- Wording stays draft until Clara's pause lifts.
- Leo and Richard write the note together:
  - Richard: §1, §2's latest-departure field, and §5;
  - Leo: §2's table form, §3 and §4.
- Every threshold is either sourced, with the source named, or a **named parameter with no value**.

**Owner decision (option a, relayed by the orchestrator, 2026-11-12 22:39 UTC).**
- **STAFF/AGENCY-ONLY.** Nothing in this note is person-facing, and nothing goes into any resident channel.
- **Build order:**
  1. the early-action list (§2), the main output, which needs no new data;
  2. Iris's air row D0 (§3.1);
  3. open-ground candidates D1 (§3.2), only as a later, labelled extension, if the owner asks again after seeing D0.
- Boats are noted descriptively for coastal places (§4).

**Iris's judgement (2026-11-12 22:36 UTC, verbatim):**

> DROP as a person-facing output; at most a staff-only descriptive count, if the orchestrator wants it.
>
> Reasons: the conditions that close roads in a wind-driven fire are those that ground helicopters (Sofia's sources:
> wind, smoke, night, the grounding after 26 March, and no report of residents evacuated by helicopter in March
> 2025); no published numeric smoke limit, so the "flyable" gate has no source; 0 registered sites in 의성, and the
> sites are operating bases, not pickup points; and a resident message mentioning a helicopter where there is no road
> route invites waiting.
>
> If kept: a staff-only research row for no-route and unresolved origins giving distance to the nearest registered
> site and whether daylight and the published wind limits allowed flight at that time. "Possible only if flyable",
> never a route, never counted as resolving an origin, smoke gate labelled unsourced. It shouldn't delay the
> multi-hour gate or the benchmark.

## 1. The "no road escape" set (Richard)

**Inputs** (the routing author's text, 13 Nov ~09:20; figures verified in verification ledger rows 72, 73 and 77).
- **Field:** the HEADLINE deadline field on `no_reentry/2` (MANIFEST_v3_7, sha256 7c178267…; 819bcb91), as verified
  in ledger row 72. The runner is `deadline_field/headline.py` at 54bcb96e (claude/f31-deadline-field). Environment:
  numpy 1.26.4, Python 3.13.18.
- **Checking:** every reported latest departure has a witness that passes the full checker (4,842 / 4,842 on the
  headline).
- **CERT and ROUTER:** "No checked route" is read from CERT (router OR closed footprint). Refusal claims come only from
  ROUTER. On the headline, CERT and ROUTER agree on every place.
- **Departures:** the field is exact to the second over [0, H]. The list reports it on the 30-min grid only (§2).

**Definition.** A place is in **NO_CHECKED_ROUTE** at a departure time when **all three timing variants** give no
checked route: kriged_mean, firms_early and envelope.
- That is the intersection, with a per-variant table always shown alongside.
- envelope_burnset is its own row and does not enter the intersection.
- A place maps to its start node(s) as the caches record them. With several nodes, it qualifies only if none of them
  has a route.
- It is **never** reported as a bare "no route".

**Not evaluated: start point on ground burned before the start** (Iris, 13 Nov, on the `/2` headline at 54bcb96e).
These places come first and are kept separate from the set.
- **Label:** "start point on ground the model shows as burned before this start time: not evaluated", with the
  line "Under the no-re-entry rule nothing is computed from this point. This says nothing about whether people are
  there or whether roads are passable."
- **Why.** Under `no_reentry/2` the origin's own cell is closed, so nothing was searched. These are 1,074 of the 1,322
  rows that lost their route going from `/1` to `/2`.
- **Excluded from:** the no-road-escape set, the early-action list (§2) and the air candidates (§3).
- **Their own count,** per timing variant, with "inside" and "touches" reported separately.
- **Measured on the `/2` headline** (routing author, rule NOT_EVALUATED_LABEL_RULE.md @ da167134, tables @ 50535521).
  - **1,114 not-evaluated rows over 48 packets, all "inside" and 0 "touches".** That is the 1,074 that lost their
    route, plus 40 with no route on `/1` either.
  - Every one is a CERT origin-in-flame at t = 0. 8 h is identical to 5 h.
  - B0 there equals the plan meta on all 48 packets.
  - **248 rows "depend on the no-re-entry rule"** (fire-limited 88, possibly road-limited 160).
  - **Per start** (kriged_mean, 5 h; 8 h identical): not evaluated / depends on the no-re-entry rule / other no route,
    out of 84 UA or 90 YD places:

    | Start | Not evaluated | Depends on no-re-entry | Other no route |
    |---|---|---|---|
    | UA 23T01Z | 8 | 19 | 1 |
    | UA 24T09Z | 20 | 13 | 0 |
    | UA 25T17Z | 42 | 4 | 9 |
    | YD 25T19Z | 33 | 0 | 5 |
    | YD 25T23Z | 39 | 1 | 0 |
    | YD 26T08Z | 39 | 1 | 2 |

    The firms_early and envelope rows are in F-3.1 RESULTS (split table). **Unsplit no-route counts are never quoted.**

**Cause label**, exactly one per place, in this precedence: 0 → 1 → 1b → 2 → 3. Agency wording is Iris's, and every
label says "modelled" because these are statements about a fire reconstruction, not observations.
0. **"start point on ground the model shows as burned before this start time: not evaluated"**. Not part of the set
   (above).
1. **"origin already inside the modelled fire area at that departure time"** (internally: at-issue).
1b. **"every road exit crosses ground the model shows as already burned"**, flagged **"depends on the no-re-entry
    rule"**. These places stay in the set (Iris).
2. **"every road exit in the mapped area is blocked by modelled fire"** (internally: fire-limited).
3. **"undetermined: map window too small"** (internally: road-limited). There is no checked route inside the loaded
   graph, but a route off the clipped graph is not excluded. These places are **kept out of every count of
   no-escape places**, and they are not air candidates.

**Dependence on the waiting rule.**
- **Decided, 13 Nov** (the orchestrator, on the owner's delegation, relayed by Richard):
  - The documented default stays: waiting is allowed only at graph dead-end nodes.
  - A labelled sensitivity row, **"waiting allowed everywhere"**, is ALWAYS reported. That includes Marcus's finding
    that all 14 NO_ROUTE results flip under it.
  - No verified result changes.
- **Plain-language wording: FINAL** (the orchestrator, 13 Nov 00:13 UTC, verbatim; recorded in F-3.1
  WAITING_SENSITIVITY_RULE.md @ 1b792c77).
  - **(S) Single-departure results:** "The trip starts at the stated time. Once moving, a stop is allowed only at a
    road dead end (a graph dead-end node), which may be a short detour off the route; waiting is not allowed at any
    other node, including the start unless it is itself a dead end. Other departure times are separate results."
  - **(R) Range results** (the deadline field and departure sweeps; the range and step are named): "Each departure
    time in [range, step named] is a separate trip. Leaving later is how waiting at the start place is represented.
    Once moving, a stop is allowed only at a road dead end (a graph dead-end node), which may be a short detour off
    the route; waiting is not allowed at any other node."
- **Not monotone in departure time.** A later departure can have a route when an earlier one has none.

## 2. EARLY-ACTION LIST (main output; no new data)

**What it gives.** For each place that is in the §1 set at some departure, the last computed departure time with a
checked road route, per timing variant.
- **Shown as a range across variants, with the earliest edge first.** The earliest edge is labelled: "earliest of the
  three variants computed; the fire may close roads earlier than any of them." All three variants treat cells with no
  fire information as not burning, so the earliest variant is **not** a safe bound (Iris).
- **Grid times, not deadlines.** The checker runs on a 30-min departure grid, so the route may have closed at any time
  in the following 30 minutes. Each value is shown as a pair: **"last computed time with a route / next computed
  time, none"**. It is never shown as a single clock time, and never called a deadline.
- **Prefix check.** "Last computed time with a route" does **not** mean every earlier time had one, because results
  are not monotone in departure time. Each list states, per place and variant, **whether the feasible departure set
  is a prefix** of the grid. This is checked per run, not assumed. In Richard's `/1` run it was a prefix everywhere (0
  non-prefix sets over 48 pairs). A non-prefix place lists its feasible departures explicitly.
- **Waiting wording.** The list carries the (R) wording above, with the range and step named.
- **Origin already inside the modelled fire area.** Such a place has no latest departure. It is shown as "none at any
  computed time", never as a blank or a time.
- **Header of every list:**
  - the checker (Richard's full checker, with its commit);
  - the packet version (MANIFEST_v3_7 `no_reentry/2`, with its sha256).
- **Not built until Nora passes `no_reentry/2`.**
- **Purpose.** Staff can prioritise early warning and assisted transport *before* the roads close.
- **Scope.** The list is for places still ahead of the fire. "Not evaluated" places (start point on ground burned
  before the start) are never on it. Without this split it would be led by places the modelled fire has already
  passed (Iris).

**Columns:**
- the place;
- the cause label (§1);
- the (last computed time with a route / next computed time, none) pair under kriged_mean, firms_early and envelope;
- the earliest of those pairs, with the label above;
- the envelope_burnset row, which is static;
- whether the result depends on the waiting rule;
- the departure grid step.

**Source** (the routing author's text, 13 Nov ~09:20). The per-place CERT leave-by of the HEADLINE `/2` run
(results/HEADLINE_NR2_summary.json, ledger row 72) and the per-place issue sets in its raw outputs. No new data is
needed.
- **Grid pair:** "last computed time with a route" = the largest multiple of 1,800 s in the place's feasible departure
  set; "next computed time, none" = that + 1,800 s. If that time is ≥ H, it is written "none up to the horizon (H)".
- **Prefix:** measured, not assumed. On the `/2` headline, 0 of 48 pairs have a non-prefix feasible set, so every
  place's set is [0, leave-by]. The list still carries the per-place prefix flag, and any future non-prefix place
  lists its feasible grid times explicitly.
- **Horizon-censored places** (route at every grid time up to H): "route at every computed time to H". Never a time.
- **Header of every list:**
  - checker: `deadline_field/headline.py` @ 54bcb96e + the kit's `check_route`;
  - packets: MANIFEST_v3_7 `no_reentry/2`, sha256 7c178267…;
  - numpy 1.26.4.
- **Spotting:** under a clamped isotropic spotting dilation of 500–2,000 m (ledger row 77), no place's leave-by gets
  later. That is a research check, not a list column.
- **Map-edge limit:** the border-touch count (an upper bound on witnesses that touch the edge of the fire-data grid)
  will be stated beside the list. It is in its final run: so far 0 witnesses touch in the 47 of 48 packets done.

**Pre-season version.** The same list from the March 2025 replay, per region:
- which places lost their last checked route;
- how long before they were reached **by the modelled fire**.

It is a planning list for next season, labelled: "replay of March 2025; not a forecast. One fire, March 2025, that
day's wind. A place not on this list has not been shown to have a road escape." Without the last sentence it reads as
a list of the villages at risk, and absence reads as safe (Iris).

**Official link: HELD.** 행정안전부 고립예상지역대책 (data.go.kr 15139647; field 헬기구조가능여부). Sofia, 22:44 UTC,
from the dataset page and its catalog record only.
- **Not usable from here.**
  - It needs an account and a service key: "API 유형 LINK" to safetydata.go.kr, with a project or personal service
    key. Our rule is no accounts.
  - Coverage is not stated ("공간범위 --").
  - It is updated in real time.
  - It gives addresses (상세주소), not coordinates.
  - **헬기구조가능여부 has no published definition**: its values, who assesses it, and landing vs hoist are all
    unknown.
  - 고립위험사유 suggests the isolation scenario may be flood or landslide rather than wildfire. That is Sofia's
    inference, to be checked in a sample.
- **No column is added.** The owner, as key-holder, would have to pull one 경북 sample and confirm four things:
  - coverage and year;
  - the hazard type in 고립위험사유;
  - the value set of 헬기구조가능여부;
  - whether the addresses geocode cleanly.
- **If it is added later,** the field is quoted verbatim and labelled "행안부 고립예상지역 목록(위험 유형:
  <고립위험사유>), 헬기구조가능여부 정의 미공개", with its source and date in the same cell.
- **Sibling datasets.** Same provider and key terms; recorded, not used:
  - 15139708 지역고립예상지점 (village name and 행정동코드);
  - 15139648 교통두절예상지역: road segments expected to be cut, with designated detours. That one may matter for
    routing; it would be a separate question for the owner.

## 3. AIR TABLE (secondary; staff-only)

### 3.1 D0: registered-site row (Iris's row; built second)

One research row per place in the §1 set, and per unresolved origin.

**Distance to the nearest 산림청 registered landing site.**
- Source: 산림청 산림항공본부_이착륙장 정보, data.go.kr 15069465.
  - CSV, 627 rows, modified 2026-09-17, "이용허락범위 제한 없음".
  - It is the only fetch item (Daniel's FETCH_PLAN, cca4e27a).
  - The API variant 15134224 needs a service key, so it is excluded.
- 경북 has 48 rows. **의성 has 0 registered sites**, and every 의성 row says so.
- **Fetched** by Daniel at ca7133d8 (`air_extract/KFS_HELIPAD_MANIFEST.md`); the CSV stays out of git until Hannah has
  reviewed it.
  - sha256 `55f66625…`, 116,211 bytes; CP949; 627 rows × 32 columns.
  - Served as "…_20251022.csv"; 점검일 runs from 2014-07-07 to 2025-10-22.
  - **Coordinates.** DMS split over six integer columns, and **no datum is stated**.
    - 538 rows are valid.
    - 24 rows are blank.
    - **65 rows are invalid** (minutes or seconds ≥ 60). They are not repaired or guessed.
- **D0 rule for unusable rows, fixed before any build.**
  - Sites with blank or invalid coordinates are excluded from the distance computation.
  - Every row states how many registered sites in its 시군구 were excluded for this reason, because **an excluded
    site could be nearer** than the reported one.
  - The datum is stated as "not given by the source; read as WGS84/GRS80 geographic". At these distances that
    choice is immaterial.
- **경북 breakdown** (Daniel, 13 Nov; rows assigned to a 시군구 from the address text, not by point-in-polygon).
  - All 48 경북 rows: 42 valid, 2 blank, 4 invalid.

  | 시군구 | Rows | Usable |
  |---|---|---|
  | 의성 | 0 | — |
  | 안동 | 2 | 2 |
  | 청송 | 2 | 2 |
  | 영양 | 1 | 1 |
  | 영덕 | 4 | 4 |
  | **울진** | 1 | **0 (its only site has invalid coordinates)** |

  - So **울진 rows say "1 registered site in 울진 excluded: coordinates invalid in the source"**, and the nearest
    usable site lies outside 울진.
  - Whether any coordinate falls outside its stated 시군구 is not yet checked. A point-in-polygon check is done before
    D0 is built.
- These are forest-aviation operating sites, **not pickup points**, and every row is labelled that way.

**Flight gate at that time.** It is stated per row, from Sofia's sources. Only daylight and wind can be evaluated:
there is no source for smoke, and none yet for visibility at the time.
- **Daylight.** Night needs NVG and lit sites (119항공대 운영 규정, 소방청훈령 제478호, 제22조). PMS 510 prohibits
  carrying passengers at night in a single-engine helicopter.
- **Wind** under the published type limits. These are labelled **"US interagency reference (NWCG PMS 510)"**. The
  Korean rule (119항공대 운영 규정) defers to each aircraft's manual ("기종별 교범").
  - 40 kt (≈20.6 m/s) for Type 1-2;
  - 30 kt for Type 3;
  - with a 15 kt gust spread (NWCG PMS 510, May 2023, Exhibit 6.2).
  - **The wind source is named before anything is computed, with whether it carries gusts.** Hourly mean wind from a
    reanalysis understates gusts, and the limits are gust-sensitive, so a mean-wind gate errs towards "not
    excluded". If only mean wind is available, every row says so.
- **Visibility** at least 3,200 m over land (119항공대 운영 규정 제21조). **Not evaluated:** no source for visibility
  at the time.
- **Smoke: UNSOURCED.** No published numeric limit was found. **Not evaluated.**

**Two statuses only.** A row may never say "flyable" or "possible":
- **"excluded (night, or wind over the published limit)"**;
- **"not excluded by the gates evaluated (smoke and visibility not evaluated)"**.

Every row also carries "flight feasibility is the pilot's and agency's decision". A row **never counts as resolving a
place**.

**Summary count, reported with the table.** Of the rows, how many are excluded by daylight or by wind alone. Iris
expects most of them, as a hypothesis; that count is the finding.

### 3.2 D1: open-ground candidates (later extension; only if the owner asks again after D0)

Recorded so the design exists. **Nothing here is fetched or built.**

**Site criteria.** Sourced values, the choice of reference not adopted:

| Parameter | Value | Source |
|---|---|---|
| Safety circle | 27.4 m (Type 2) / 33.5 m (Type 1); "at least 1.5 × rotor diameter" | PMS 510 Exhibit 8.3 |
| Slope | ≤ 6° (11%). Korean and ICAO heliport standards: 2% | PMS 510; 국토교통부고시 제2022-350호 제80조; ICAO Annex 14 Vol II |
| Approach path | ≥ safety-circle width, ideally about 91 m long, no obstacle above about 1:8 | PMS 510 |
| Improvised sites (Korea) | no size or slope given | 119항공대 운영 규정 |
| Canopy, "open enough" | **not published**: `TREE_MAX` stays a named parameter with no value | — |

**Layers** (Daniel; not in any fetch plan):
- Copernicus GLO-30. It is a DSM, so slope over clearings is biased.
- ESA WorldCover v200, 10 m.
- OSM open-ground polygons, from a CURRENT-2026 snapshot only. "Unmapped ≠ absent", and completeness is to be
  measured.

**Time condition**, per variant:
- the site and a `BUFFER_M` buffer are neither burning nor burned at the time (the `/2` closure);
- the forecast arrival is later than the time plus `MARGIN_MIN`;
- the site is outside Priya's radiant stand-off: no cell burning at that time within the stand-off distance. The
  distance is measured from the edge of the burning cell rectangle, which is how her rows are defined.

**Radiant stand-off rows (Priya, 22:45 UTC; cited as is).**
- **Source.** F-4.2 `results/RADIANT_S7.json` key `standoff`, branch `claude/priya-f34-f42` @ eecfb0b. Plan:
  RADIANT_PLAN.md §7a (e33256b), committed before the results; §7b fix at 5022ad1.
- **Main rows.** Flame width 100 m, window 1.0. Each cell is the distance to 1.0 / to 2.5 kW/m², in metres.

  | Flame | E (kW/m²) | H 1 m | H 2 m | H 5 m | H 10 m | H 20 m | H 30 m | H 40 m | H 50 m |
  |---|---|---|---|---|---|---|---|---|---|
  | surface | 76 (AS 3959) | 34.7 / 15.0 | 58.2 / 28.7 | 102.5 / 58.2 | 150.2 / 90.0 | | | | |
  | crown | 112 (1200 K) | | | | 184.4 / 112.5 | 263.8 / 163.8 | 324.3 / 202.4 | 375.1 / 234.8 | 419.7 / 263.1 |
  | crown | 118 | | | | 189.5 / 115.8 | 270.9 / 168.4 | 333.0 / 208.0 | 385.1 / 241.2 | 431.0 / 270.3 |

- **Sensitivity rows** (measured-crown E 150 and 200, window 0.5, a 3,750 m front; up to about 2.7 km). These are
  cited only as labelled sensitivities, never as main rows.
- **What each row assumes:**
  - a solid vertical planar flame;
  - the receiver at flame-centre height;
  - τ = 1, i.e. no smoke or air attenuation;
  - radiation only, with no convection allowance;
  - thresholds for an unprotected person from Purser / SFPE.
- **Caveats that go with every citation** (Sofia's reading):
  - measured fluxes exist only to about 15 m;
  - the 50–400 m distances, the 1.0–2.5 kW/m² range and flames above about 25 m have not been validated;
  - the model over-predicts with distance (back-test 2–3× high);
  - it can under-predict with convection on slopes or in wind, with hotter flames, or with wider fronts;
  - embers and smoke are not covered.
- **Which row applies.** Which E/H row applies to a site is a fire-type choice the table does not make. It stays a
  named parameter `STANDOFF_ROW` with no value until it is sourced.

The same gates and label apply as in 3.1.

## 4. Boats (descriptive only)

- **For coastal places in the §1 set, one note.** In March 2025, 울진해경 took 104 residents off 영덕 breakwaters
  (경정3리, 석리 and others) by vessels and boats.
  - Source: YTN 2025-03-26, via Sofia.
  - Residents reported that 해경 arrived about 2 h after the call (kbmaeil 202503260913624).
- Recorded as what worked in 2025. It is not modelled and is not a route.

## 5. What the March 2025 replay can and cannot validate (Richard and Leo)

**Can be checked:**
- **The §1 set against the breakwater rescues.** Are 경정3리, 석리 etc. in NO_CHECKED_ROUTE on the matching
  Yeongdeok starts, and with which cause label?
  - **This is fixed in this note BEFORE it is run** (Iris). The villages are already known, so the comparison could
    otherwise be fitted. The three parts follow (the routing author's text, 13 Nov ~09:20).
  - **Village → node mapping source:** INSTANCE.json (F-DYN _data, 819bcb91), Yeongdeok origins by OSM place name.
    The nodes it gives:

    | Village | Origin | Entry node | Entry distance |
    |---|---|---|---|
    | 경정리 | osm:node/415160201 | osm:11779897864 | 71.9 m |
    | 석리 | osm:node/415160200 | osm:11872197463 | 474.4 m |
    | 남석리 | osm:node/415160162 | osm:4778527797 | 12.9 m |
    | 노물리 | osm:node/415160193 | osm:11872368163 | 73.7 m |
    | 오보리 | osm:node/415160194 | osm:11897956630 | 328.8 m |
    | 축산리 | osm:node/415158213 | osm:12144230037 | 154.3 m |

    **Stated approximation:** "경정3리" maps to the OSM place node for 경정리, the parent village. The node is not the
    breakwater; the entry distance is the place node → road node distance. A reported village not in the list is "not
    in the place list", never "no route".
  - **Incident times:** from the sources only, written here before the run.
    - YTN 2025-03-26 (found by the source researcher): 104 residents taken off 영덕 breakwaters by 울진해경.
    - kbmaeil 202503260913624: 해경 arrived about 2 h after the call.
    - The exact clock times are **not yet sourced**. The source researcher is to supply call and pickup times, each
      with a source, before the run. **Until then the check is not run.**
  - **Agreement criterion** (fixed now):
    - **The start used:** the latest recorded Yeongdeok start at or before the earliest sourced call time.
      - The recorded starts are 25T19Z, 25T23Z and 26T08Z UTC (= 26 Mar 04:00, 08:00 and 17:00 KST).
      - If every sourced call time is earlier than 25T19Z, the check **cannot be run on recorded starts**, and it is
        reported as "not checkable: no recorded start before the incident".
    - **Agree:** the village is in the §1 NO_CHECKED_ROUTE set (all three timing variants) at the grid departure
      nearest the call time, with cause label 1, 1b or 2.
    - **Disagree:** it has a checked route at that departure under any timing variant.
    - **Other cases are their own class:**
      - "not evaluated", as start point on burned ground (rule 0);
      - "undetermined: map window too small" (label 3);
      - the place node > 500 m from the breakwater named in the source.
    - "Reached" means reached by the modelled fire.
    - **What it can show:** six villages, one fire. Agreement does not validate the set, and disagreement is reported
      with the route's witness.
- **The §2 early-action times against reported evacuation-order and road-closure times,** where a source gives them.
- **The §3.1 flight gate against the record:**
  - 25 Mar: gusts about 27 m/s, 4 helicopters landed;
  - 23 and 25 Mar: haze stopped flights;
  - no night operations;
  - 26 Mar 12:51 to about 15:30: national grounding after the 의성 crash.

**Cannot be validated:**
- **Air extraction itself.** Sofia found no report of residents airlifted in March 2025.
- Any landing-site suitability.
- Smoke limits.

## Iris's reading (2026-11-12, at 860aebea; applied in this revision)

**Verdict.** The restructure is right. Go ahead with §2 after the changes, and with D0 after its own.

**Applied:**
- §2: the earliest edge is not a safe bound; grid-time pairs, never deadlines; "none at any computed time"; the
  absence line on the replay list; checker and packet version named; not built until Nora passes `/2`.
- D0: two statuses only, never "flyable" or "possible"; the wind source named, with gusts or the mean-wind caveat;
  the US interagency label on the limits; the summary count of rows excluded by daylight or wind.
- §1: agency wording with "modelled"; "undetermined: map window too small" kept out of all counts.
- §5: the breakwater check fixed in the note before it is run.

**Priority unchanged.** Plan and staff-only. This must not delay the multi-hour gate, the benchmark, or Richard's
16.4 km/h runs.

## Inputs

| Who | What | Status |
|---|---|---|
| Richard | §1 text, §2 latest-departure field, §5 breakwater check | §1/§2 from the verified `/2` headline (rows 72/73), sent 13 Nov ~09:20; §5 criteria fixed; incident clock times pending from Sofia |
| Sofia | 행안부 고립예상지역 (15139647) | answered 22:44: needs a service key, coverage unstated, addresses only, field undefined; column HELD pending an owner sample |
| Daniel | 산림청 CSV (15069465), one file, after the road extract | in fetch plan (cca4e27a) |
| Priya | radiant stand-off rows (D1 only) | received 22:45; cited in §3.2 |
| Iris | reading of this note before any build | read 860aebea; changes applied; §2 may proceed after Nora's /2 pass, D0 after these changes |
