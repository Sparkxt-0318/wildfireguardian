# Issuer jurisdiction — design and pre-registered pass rule

Status: DESIGN, accepted by the orchestrator (2026-11-12); Iris's reading pending. Committed BEFORE the labelling
build runs, so that the pass rule cannot be fitted to the result. No code yet.

## Problem (Mira N1 on the owner-decision cut)
The issuer registry checks the issuer's name, not its jurisdiction. A registered issuer renders "문의: <시·군> …" at
any place: 영덕군 on all 258 의성–안동 place-scenarios, 의성군 on all 273 영덕 place-scenarios. If staff supply the
wrong issuer, a resident message could name another county as its contact.

## Data (option B, orchestrator decision)
- Source: 국토교통부_(센서스경계)시군구경계_20250120, data.go.kr dataset 15125064, 이용허락범위 "제한 없음". Named by
  Sofia from the source page; the file is fetched by Daniel.
- The SHP is not committed. The build script records the sha256 of every file it reads.
- Each real origin in planner/public/data/regions/{uiseong_andong_2025,yeongdeok_2025}/places.geojson gets
  `sigungu: { ko, status, reason, source }`, with source "행정구역: 국토교통부 (센서스경계)시군구경계 2025-01-20,
  공공데이터포털".
- Coordinates: the polygons stay in their own CRS (from the .prj, expected EPSG:5179); WGS84 points are transformed into
  it. Never snapped.
- Sanity checks that stop the build: polygons for 의성군, 안동시, 청송군, 영양군 and 영덕군 exist; 군위군 is not in 경북
  (moved to 대구 in 2023-07).

## Labelling rule (tolerance, stated before any run)
A place's 시·군 is ESTABLISHED only if all of these hold:
1. its OSM point lies inside exactly one 시군구 polygon;
2. the point's distance to that polygon's boundary is ≥ 50 m;
3. its road-entry node lies inside the same polygon.

Otherwise it is NOT ESTABLISHED, with exactly one reason, checked in this order:
- outside_all — in no polygon (coast or water);
- multiple — in more than one polygon;
- near_boundary — the point is within 50 m of the boundary;
- entry_differs — the road-entry node is in a different 시·군.

The 50 m margin is a stated, conservative guard, not a measured accuracy: the census boundary is a statistical
version, and its line precision is not stated. Counts are reported at 0 / 25 / 50 / 100 m; 50 m is the value that
ships unless the orchestrator or Iris change it before the cut.

entry_differs is conservative (orchestrator): the issuing county is the place's own county, and an entry node in
another county only withholds the contact line. It never assigns the place to the entry node's county. It is reported
separately.

## Rule in the message kit
The resident contact line renders only if sigungu.status = established AND sigungu.ko = the registered issuer's 시·군.
Otherwise there is no line, and the staff report names the field to fix (EN/KO, wording with Iris and Sofia):
- mismatch: the issuer does not match this place's county (names both);
- not established: the reason in plain words.

## PRE-REGISTERED PASS RULE (acceptance numbers)
The cut passes only if ALL of the following hold on the 531 real place-scenarios:
1. Cross-county lines removed: 영덕군 on 의성–안동 place-scenarios = 0 (from 258); 의성군 on 영덕 place-scenarios = 0
   (from 273). More generally, for every registered issuer, 0 place-scenarios render a contact line where
   sigungu.ko ≠ the issuer's 시·군.
2. No line where not established: 0 place-scenarios render any contact line when sigungu.status ≠ established.
3. Every withheld line has a staff warning: every place-scenario that loses its line under the rule shows the
   mismatch or not-established warning in BOTH languages.
4. Nothing else changes: every resident output other than the contact line, and every violation, is byte-identical
   to Main for all 531 real + 600 synthetic place-scenarios. The synthetic cases carry no sigungu, so they are not
   established, and their only change is the absent contact line.
5. Labels are complete and explained: every real origin has exactly one status, and every not-established one has
   exactly one reason. The counts by region and reason are reported at 0 / 25 / 50 / 100 m.
6. Sanity: the five county polygons exist; 군위군 is not in 경북; the sha256 of the source files is recorded.
7. Mutations each make at least one test fail: (a) the jurisdiction rule disabled; (b) two place labels swapped across
   counties; (c) the margin set to 0 m with a fixture point 10 m inside a boundary.

Correct-county coverage is REPORTED, not gated: the number of place-scenarios where the matching county's issuer
renders a line. It can only fall relative to today, through not-established places, and is reported exactly by
region and reason. If it falls below 50 % of today's for any registered county, the cut is not shipped; it goes back
to the orchestrator and Iris with the numbers, since such a large loss would need a decision.

## Build tooling (ready before the real file; 2026-11-12)
- `export_places.py` (standard library) writes `places_input.json`: one row per real origin, 177 in total
  (86 의성–안동 + 91 영덕), with the id, the OSM point and the road-entry node, all WGS84. The 531 place-scenarios are
  these origins across the six caches.
- `label_sigungu.py` applies the rule above and writes `labels.json`. It records the sha256 of every source file and
  reports counts at 0 / 25 / 50 / 100 m. It stops (exit 2) on a failed sanity check. A `--fixture` run skips the
  sanity checks and is marked FIXTURE.
- `test_label_sigungu.py` uses SYNTHETIC UTM-K boundary files (two adjacent 10 km squares) and covers:
  - every reason, in order;
  - margin sensitivity;
  - margin 0 m on a point 10 m inside a boundary (mutation c);
  - overlap;
  - cp949 and utf-8 .dbf names;
  - a geographic CRS refused;
  - the 군위군 vintage check;
  - the CLI exit codes;
  - completeness of the real input list.
  9 passed. Mutations: the entry check removed → 1 failed; the margin check removed → 3 failed.
- Not yet run on real data: the 국토교통부 SHP is hosted on V-World, which these containers cannot reach. The owner
  is downloading it.
