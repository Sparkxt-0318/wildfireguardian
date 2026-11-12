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

## Kit rule

`buildChannels` renders a registered issuer's contact line only when the place's `sigungu` is established **and** names the issuer's own 시·군.
- Otherwise there is no line.
- A staff line in both languages names the problem. It is DRAFT wording, waiting for Iris and Sofia:
  - **mismatch:** "문의처 없음 — 고칠 항목: 기관명. 입력한 기관(X)이 이 장소가 속한 시·군(Y)과 다릅니다." / "No contact line — field to fix: issuer name. The issuer (X) is not this place's 시·군 (Y)."
  - **not established:** "문의처 없음 — 이 장소가 속한 시·군을 행정구역 경계로 확정하지 못했습니다(<reason>). 어느 기관도 문의처로 넣지 않습니다." / "No contact line — this place's 시·군 could not be established from the boundary file (<reason>). No issuer is named here."
- An absent or malformed label is never read as established (`parseSigungu`).
- The decree report carries the same staff line. The new contact statuses are `jurisdiction_mismatch` and `jurisdiction_not_established`.
- If `planner/tools/extract_places.py` regenerates the place files, the labels are lost, and every contact line fails closed until `apply_sigungu.py` is run again. The tool's docstring says so (Mira N1). CI is the guard: with unlabelled place files, 8 tests in `npm test` fail (Mira's check).

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
