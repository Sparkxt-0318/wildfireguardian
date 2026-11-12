# Issuer jurisdiction: results against the pre-registered pass rule (DESIGN.md, baadd81)

Status: built and tested; **waiting for Mira's verification and for Iris and Sofia on the staff wording.** No PR yet.

## Labels (delivered by Daniel; Hannah verifies)

- **Run.** Daniel's run 3 of `label_sigungu.py` @ 92757b2e (sha256 534fee03…5d06), on the owner's BND_SIGUNGU_PG.
  - Archive sha256: bafb7ef2…5b41.
  - BASE_DATE: 2025-06-30.
  - CRS: EPSG:5186.
- **The file.** `labels.json`, committed byte for byte as delivered: sha256 0896957b…be52c, 71,746 bytes.
- **Source line.** Sofia's wording, the same on every label:
  "행정구역: BND_SIGUNGU_PG (BASE_DATE 2025-06-30). 2026-11-12 프로젝트 책임자 제공. 프로젝트 책임자에 따르면 data.go.kr 15125064(센서스경계 시군구경계)에 연결된 V-World 페이지에서 내려받음(출처 확인 중)."
- **Applied.** `apply_sigungu.py` writes the labels into the two `places.geojson` files.
  - Only the `sigungu` property is added to the 177 origins; everything else is unchanged.
  - `--check` passes, and a pytest pins it.

Counts are identical at 0, 25, 50 and 100 m. There are no outside_all, multiple, near_boundary or entry_differs cases. The smallest boundary distance is 189.1 m.

| Region | 시·군 | Origins | Place-scenarios |
|---|---|---|---|
| uiseong_andong_2025 | 의성군 | 48 | 144 |
| uiseong_andong_2025 | 안동시 | 38 | 114 |
| yeongdeok_2025 | 영덕군 | 82 | 246 |
| yeongdeok_2025 | 청송군 | 4 | 12 |
| yeongdeok_2025 | 영양군 | 5 | 15 |

**Verified by Hannah (ledger row 65): PASS.**
- Archive leg: her own script, run unmodified by Daniel.
  - The archive and all 5 member hashes match.
  - EPSG:5186, 252 features, BASE_DATE 20250630.
  - All 177 places lie in exactly one polygon, with the entry node in the same polygon: 0 mismatches.
  - The smallest boundary distance is 189.1 m, so the 50 m margin never binds.
  - All 9 청송/영양 places agree.
  - The margin logic was read and found sound.
- Independent leg: OSM admin_level-6 boundaries agree on 177/177.
- **Not verified:** the archive's portal of origin. The source line keeps "출처 확인 중" until the owner confirms it.

## Kit rule

`buildChannels` renders a registered issuer's contact line only when the place's `sigungu` is established **and** names the issuer's own 시·군.
- Otherwise there is no line.
- A staff line in both languages says what happened. Substance is Iris's (2026-11-12); the final Korean is Sofia's.
  - **mismatch:** "문의처 없음 — 입력한 기관(X)은 행정구역 경계 자료(2025-06-30 기준)상 이 장소의 시·군(Y)과 다릅니다. 이 장소의 문의처는 Y에서 정합니다. 기관명을 잘못 입력한 경우에만 고치십시오. 주민에게는 문의처 줄만 빠지고 나머지는 그대로인 안내가 나갑니다." / "No contact line — the issuer entered (X) is not the 시·군 this place lies in (Y), by the boundary file dated 2025-06-30. The contact for this place is for Y to set. Correct the issuer name only if it was entered wrongly. Residents get the same message without the contact line."
  - **not established:** "문의처 없음 — 행정구역 경계 자료로 이 장소의 시·군을 확인하지 못했습니다(<사유>). 어느 기관도 문의처로 넣지 않았습니다. 담당 시·군을 직접 확인하십시오. 주민에게는 …" / "No contact line — this place's 시·군 could not be read from the boundary file (<reason>). No issuer is named here. Check which 시·군 is responsible. Residents get …"
  - The date comes from the label's own source line (BASE_DATE). <reason> is always a plain phrase, never a status code.
  - The lines never tell staff to "fix" a correct entry: 영덕군 staff writing for the 27 place-scenarios in 청송군/영양군 entered the right name.
- An absent or malformed label is never read as established (`parseSigungu`).
- The decree report carries the same staff line. The new contact statuses are `jurisdiction_mismatch` and `jurisdiction_not_established`.
- If `planner/tools/extract_places.py` regenerates the place files, the labels are lost, and every contact line fails closed until `apply_sigungu.py` is run again. The tool's docstring says so (Mira N1). CI is the guard: with unlabelled place files, 8 tests in `npm test` fail (Mira's check). `apply_sigungu.py` also stops if an origin's point, road-entry node or entry coordinates differ from those that were labelled (Mira, ledger 95): a place that moves keeping its id is never given its old label. Tested, and the test fails with the check removed.

## Pass rule (tests in tests/planner/wkit.channels.test.ts, "jurisdiction"; tests/…/JURISDICTION/test_label_sigungu.py)

| Item | Result |
|---|---|
| 1. No cross-county lines | **0** for every registered issuer over the 531 real place-scenarios. 영덕군 on 의성–안동: 0 (from 258). 의성군 on 영덕: 0 (from 273). |
| 2. No line where not established | Every reason, plus an absent or malformed label → no line, status `jurisdiction_not_established`, staff line in KO and EN. The parser refuses 6 malformed shapes. |
| 3. Every withheld line has a staff warning in both languages | Yes for every withheld place-scenario, in `staff.jurisdiction` and in the decree report. |
| 4. Nothing else changes | Checked over 531 real + 600 synthetic place-scenarios. With no issuer, the label changes no output. Withheld outputs equal the no-issuer resident outputs and violations: 1,872 withheld, 390 matched. Matched outputs equal the pre-rule kit. The field-message snapshot (fc426e8c…) is unchanged once the echoed input field is left out, and the label is shown to change no message. |
| 5. Labels complete and explained | 177/177, each with one status and the source line; counts as above. |
| 6. Sanity | Daniel's run: the five counties exist under 경북, 군위군 is under 대구, and the source sha256s are recorded. |
| 7. Mutations | (a) rule disabled → 4 tests fail. (b) two labels swapped across counties → 3 tests fail. (c) margin 0 m, fixture point 10 m inside → caught by the Python test (as before). |

**Correct-county coverage (reported, not gated).** For each registered county, the line renders on 100 % of the place-scenarios in its own county: 의성군 144/144, 안동시 114/114, 영덕군 246/246, 청송군 12/12, 영양군 15/15. That is well above the 50 % stop line.

**Changed test (owner decision on 영덕군).** With a 영덕군 issuer record, 246 of the 273 영덕 place-scenarios gain a line, not all 273. The other 27 are places in 청송군 (12) and 영양군 (15), which are now withheld by the rule. The W6 mechanics tests (budgets, SMS fit, decree, replay mark, English names) keep their assertions: they now label each test place as lying in the supplied issuer's own 시·군 through a test-only helper, which is documented in the file.
