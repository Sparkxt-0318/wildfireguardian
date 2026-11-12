# F-C1b: see-before-leave for documented villages (definitions fixed before computing)

Orchestrator decision, 2026-11-12. This file fixes the village list, observer points, visibility settings and
interval arithmetic. It is committed before any F-C1b number is computed, and then sent to Nora and Iris.

**Quantity.** Per village: an interval for when the fire, or its smoke, first came into **line of sight of modelled
burning cells** from a documented location, against an interval for the leave-by time and the documented resident
timeline. The gap is an interval. **A sign is called only when the whole interval agrees.**

> Retrospective research on the 2025 event. Line of sight is necessary, not sufficient, for noticing. Not evidence
> of what any resident saw.

## Villages and observer points (OSM nodes from `planner/data/osm/*.overpass.json`; WGS84 lat, lon)

| Id | Village (account) | Observer point(s) | Documented anchors (KST, 25–26 Mar 2025; label) |
|---|---|---|---|
| V1 | Yeongdeok 지품면, at the 면사무소 | 지품면사무소, node 11835585365 (36.4484609, 129.2818195) | Black smoke from the north about 16:30, seen by the 면장 at the office; told fire was about 1 h away (VERIFIED, dgmbc 628364). 18:00 evacuation order and CBS (VERIFIED, county timeline). 20:25 power cut in 11 지품 villages (VERIFIED). |
| V2 | Yeongdeok 영덕읍 매정리 | 매정1리마을회관 11910567786 (36.4449605, 129.4209802); 매정2리 11933422134 (36.4550118, 129.4069928); 매정3리 11910567736 (36.4521412, 129.4219661) | 이장 knocks about 20:00; resident leaves about 20:30; "10 min later the fire swallowed the village", i.e. about 20:40 (VERIFIED, hankookilbo A2025032714350000238). Care-home car burns about 21:00 (VERIFIED). |
| V3 | Yeongdeok 축산면 경정리 | 경정1리 11779897800 (36.484571, 129.4350371); 경정2리 11777760668 (36.4919737, 129.4435679); 경정3리 11786328498 (36.4744058, 129.4335493) | Flames came over the ridge behind the village about 20:00 (SNIPPET). |
| V4 | Yeongdeok 노물리 | 노물리마을회관 11872367051 (36.445841, 129.4335354) | Residents aware only about midnight (SNIPPET). |
| V5 | Yeongdeok 강구면 | 강구2리 11994901953 (36.3669479, 129.385317); 강구4리 12000064607 (36.3612908, 129.3922726) | Text 00:07 on 26 Mar; fire about 30 min later (SNIPPET, Kyunghyang). |
| V6 | Andong 임하면 신덕1리 | OSM place node 신덕리 415158335 (36.51999, 128.83085). No hall is mapped, so this centroid is flagged and used with the ring (below). | Red flames came over about 17:30–18:00; fire reached the village about 10 min later (VERIFIED by Sofia, Nocut 6318424). |

- **Excluded until coordinates are sourced:** Cheongsong 파천면 (면사무소, 송강2리). No Cheongsong OSM data is in the
  repo, and no coordinate is guessed.
- **Excluded:** 지품 삼화1리 (no clock time).
- Where a village has several observer points, each point is reported separately. No village-level aggregate is
  formed.

## Visibility (verified F-C1 code: `seebefore/viewshed.py`, GLO-30 DSM, curvature k = 0.13, 15 m steps)

| Setting | Observer | Target point | Flame | Smoke column | Range cap |
|---|---|---|---|---|---|
| Optimistic | best of 9: point + 8 at 250 m, eye 2 m | any of the 3 x 3 cell sub-points | 10 m | 1,000 m | none |
| Pessimistic | the point, eye 2 m | cell centre | 2 m | 300 m | 15 km |

**Smoke at night.** The smoke column counts only before sunset: 18:50 KST on 25 Mar (09:50 UTC). After sunset only
flames count. Glow has no sourced distance and is not used.

## Fire timing per 375 m cell (whole event, KFS_01 grid; hours since t0 = 2025-03-22 02:24 UTC)

- **Detected cells** (≥1 FIRMS detection in the cell):
  - Arrival bracket [lo, hi]. hi = first detection, a hard upper bound.
  - lo = the last overpass with ≥1 grid detection before hi (`fdyn/variants.py` `firms_early`), a clear-sky lower
    bound.
  - Cloud and smoke can hide fire, so lo is labelled clear-sky.
- **Undetected cells:** the kriged mean with sd of about 17 h. These cells contribute only to a separate
  **"kriged-inclusive"** row, never to the bracket-only result.
- **Burning interval:** [arrival, arrival + T), with T = 3,970 s, the same law as the packets.
- **Himawari AHI** is not used here until its detection rule is fixed and reviewed (pending orchestrator, Iris and
  Elena).

## Intervals per observer point and setting

- **First-visible interval** [V_lo, V_hi]: over all detected cells visible under the setting (flame: h_req < flame
  height; smoke: h_req < column height and the time is before sunset):
  - V_lo = min(lo)
  - V_hi = min(hi)
  - Fire cells burn from arrival, so the first visible time is within [min lo, min hi] over the visible cells.
- **Village arrival interval** [A_lo, A_hi]: over detected cells within 500 m of the observer point:
  - A_lo = min(lo)
  - A_hi = min(hi)
  - If no cell within 500 m is detected, the interval is "not bracketed".
- **Leave-by interval** [L_lo, L_hi]:
  - **Preliminary** (until the F-DYN deadline field passes Nora): L_hi = A_hi − trip_min and L_lo = A_lo − trip_min.
    trip_min is the fastest fire-free trip from the nearest planner place's road entry node to its quickest
    destination (`research/solve2027-impact` trips). It is labelled "fire-arrival-based, not a routing deadline".
  - **Final:** the F-DYN leave-by interval from Richard's exact field on the bracket variants.
- **Gap interval** = [L_lo − V_hi, L_hi − V_lo] (minutes):
  - **negative** (waiting to see is too late) only if L_hi − V_lo < 0;
  - **non-negative** only if L_lo − V_hi ≥ 0;
  - otherwise **indeterminate**.
  - A sign is robust only when the optimistic and pessimistic settings agree.

## Reported beside each result

The documented timeline from the table, with its label. **Accounts are a labelled third source, not truth.**

## Amendment 1 (Iris's assessment, adopted; committed before any F-C1b computation is reported)

A run started under the unamended text was stopped and nothing from it is reported.

1. **Village footprint.** Cells within 500 m of the observer point, **plus the cell containing the nearest planner
   place's road entry node**. Sensitivity rows at 250 m and 1,000 m. More cells can only make arrival earlier.
2. **Sign must hold with undetected cells too.** A sign is called only if it holds in **both** rows:
   - `bracket_detected_only`;
   - `wide_bracket_all_burned`: undetected burned cells get the bracket [last overpass with no detection anywhere in
     their own cell before their kriged mean − 2 sd, kriged mean + 2 sd]. That is wide on purpose.

   Otherwise the result is **indeterminate**. Reason: satellites miss burning cells, which makes V late and biases
   the gap toward negative.
3. **Direction of the preliminary leave-by.** "Arrival minus fastest fire-free trip" ignores roads cut before the
   village is reached, so it is an **upper bound** on the true deadline. A negative gap under it is robust to that
   simplification; a non-negative one is **not**, and is labelled "not robust to the leave-by simplification" until
   the F-DYN deadline field replaces it.
4. **Selection.** The six villages are **case studies chosen because accounts exist, not a sample**. No rate or
   share is quoted from them. The same intervals are computed for **all 174 planner places** (observer = OSM place
   point, the unselected set). The six are presented as the subset with outside evidence.
5. **Account check** (accounts are never substituted for missing detections).
   - For each village: is the documented time inside the satellite arrival bracket? Reported as k of 6, labelled
     with read-in-full or snippet.
   - **V1 test of the visibility model:** does the model have smoke (both settings) visible from 지품면사무소 by
     16:30 KST, 25 Mar?
6. **Time zones.** Every time is written with its zone. Accounts are in KST (UTC+9); detections are stored in
   hours since t0 = 2025-03-22 02:24 UTC.
7. **Timing source.** FIRMS brackets as above. When the AHI rule (`AHI_RULE.md`, owner Leo) is committed and
   validated, an `ahi_bounded` row is added: AHI first-fire in the containing 2 km pixel is used as an **upper bound
   on arrival within about 2 km**, never as the cell's own arrival.
