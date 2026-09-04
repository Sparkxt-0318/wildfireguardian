# Scorecard — what the five judges would score today

The critic lap appends one dated row **only when the window's diff plausibly moved a
score**; a lap that moved nothing leaves the table alone and says so in its report.
Scores are 0–20 per row against `docs/auto/RUBRIC.md`, Track B five first
(연구 목적 · 설계와 방법론 · 데이터 수집·분석·해석 · 창의성 · 제출 자료), then Track A five
(개발 목적 · 설계와 방법론 · 구현 및 유용성 · 창의성 · 제출 자료). The track assignment is
not published, so both tables are kept.

These are **one critic's estimate of what a judge would give on the current tree**, not a
measurement. They exist to show direction between laps. A score that moves without a
commit to point at is a defect in the scoring, not evidence of progress.

## The series, both tracks on one row (added 2026-09-04 by critic #7)

The routine prompt asks for one table: ISO date, then the five Track B rows in rubric order,
then the five Track A rows. It is built from the two tables below, which stay exactly as
seven critic laps wrote them and are the record. Append here **and** to the track table you
are scoring; never edit a row that is already written.

Track B: 연구 목적 · 설계와 방법론 · 데이터 수집·분석·해석 · 창의성 · 제출 자료.
Track A: 개발 목적 · 설계와 방법론 · 구현 및 유용성 · 창의성 · 제출 자료.

| date | head | B·목적 | B·설계 | B·데이터 | B·창의 | B·자료 | **B/100** | A·목적 | A·설계 | A·구현 | A·창의 | A·자료 | **A/100** |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-09-03 | `1113388` | 15 | 15 | 16 | 15 | 11 | **72** | 15 | 15 | 11 | 15 | 11 | **67** |
| 2026-09-03 | `0ff1b36` | 15 | 15 | 17 | 15 | 13 | **75** | 15 | 15 | 11 | 15 | 12 | **68** |
| 2026-09-03 | `8d1decf` | 15 | 15 | 18 | 15 | 13 | **76** | 15 | 15 | 11 | 15 | 12 | **68** |
| 2026-09-04 | `12b8ac7` | 14 | 15 | 18 | 15 | 13 | **75** | 14 | 15 | 11 | 15 | 12 | **67** |
| 2026-09-04 | `5a0466e` | 15 | 15 | 18 | 15 | 15 | **78** | 15 | 15 | 11 | 15 | 13 | **69** |
| 2026-09-04 | `b855943` | 16 | 15 | 18 | 15 | 15 | **79** | 16 | 15 | 11 | 15 | 13 | **70** |
| 2026-09-04 | `8e0a6ad` | 16 | 15 | 19 | 15 | 16 | **81** | 16 | 15 | 11 | 15 | 13 | **70** |
| 2026-09-04 | `12bf2d9` | 16 | 15 | 19 | 15 | 16 | **81** | 16 | 15 | **14** | 15 | 13 | **73** |
| 2026-09-04 | `ce31b91` | 16 | 15 | 19 | 15 | **17** | **82** | 16 | 15 | 14 | 15 | 13 | **73** |
| 2026-09-04 | `3a70e16` | 16 | 15 | 19 | 15 | 17 | **82** | 16 | 15 | 14 | 15 | 13 | **73** |
| 2026-09-04 | `83f49bc` | 16 | 15 | **17** | 15 | **18** | **81** | **The first fall in 데이터 since `12b8ac7`, and the first time a green gate in this repository is holding a false claim about the world in place.** The window's headline data event is an external dataset ingested the right way and pointed at the wrong county. `scripts/extract_juso_yeongdeok.py:32` filters on 시군구 47920 labelled 영덕군; every point in the eight committed GeoJSON files falls at 36.78–37.05 N / 128.65–129.15 E, and `regions.lookup('yeongdeok_2025').bbox_wgs84` is (129.25, 36.30, 129.55, 36.60) — **no overlap on either axis**, about 45 km apart. Two tells inside the artifact itself: not one of the 239 points is east of 129.15 E, for a county whose entire land area is, and the 지진해일긴급대피장소 layer returned **zero** rows, which `docs/juso_yeongdeok.md:12` records as a fact about 영덕 rather than reading it as the contradiction it is. **-2 rather than -1** because the machinery around the mistake is complete — a manifest with both zip digests, dates, a CRS note and a filter string, eight registry keys each carrying `scope: 영덕군`, three tests — and one of those tests, `tests/test_juso_yeongdeok.py:11`, **asserts `sigungu_cd == "47920"`**, so the suite now enforces it; 1367 tests pass. Reproducibility machinery wrapped around a mis-labelled artifact is worse than none, because it certifies. **Not -3**, for three reasons this lap checked rather than assumed: nothing judge-facing prints these values (README, `web/finals.html`, `paper/manuscript.md`, `JUDGE_QA.md` all clean), the defect is one constant rather than a method, and the same window's other artifact is the best 해석 work here yet — `F8_routing_map.png` draws the 32.6 % walk-coverage limitation in panel (a) instead of describing it, and its 458 = 414 + 42 + 2 partition and its 「50 OSM POIs」 both verify against the committed artifacts. **제출 자료 17 to 18** on that same figure: hillshade, forecast field with 0.5 isolines at 0 and 720 min, the walk network, refuges, every scanned origin classed as in the committed artifact, three worked routes recomputed at figure time by the repository's own router with the recomputed partition equal to the committed one, a graticule, two scale bars and a boxed legend, and a caption that says the isoline smoothing is display-only. It stops at 18 and not 19 on two defects now in their fourth and sixth windows: `web/finals.html` still carries `"git":"a562045"`, which `git cat-file -t` still cannot resolve (WFG-067), and `JUDGE_QA.md:17-23` still tells the student 33 / 14 / 13 / 6 where the file holds **41 / 15 / 19 / 7** (WFG-057), counted again this lap. 연구 목적 16, 설계와 방법론 15 and 창의성 15 held: nothing in this window touched a model, split, metric, arm, coupling or protocol |
| 2026-09-04 | `83f49bc` | 16 | 15 | **17** | 15 | **18** | **81** | 16 | 15 | 14 | 15 | 13 | **73** |
| 2026-09-04 | `c65dc56` | 16 | 15 | **18** | 15 | **17** | **81** | 16 | 15 | **15** | 15 | 13 | **74** |
| 2026-09-04 | `baf6962` | 16 | 15 | 18 | 15 | **18** | **82** | 16 | 15 | 15 | 15 | **14** | **75** |
| 2026-09-04 | `ed35f0d` | 16 | 15 | **19** | 15 | **17** | **82** | 16 | 15 | 15 | 15 | **13** | **74** |

## Track B — SW 연구

| date | window head | 연구 목적 | 설계와 방법론 | 데이터 수집·분석·해석 | 창의성 | 제출 자료 | /100 | what moved |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-09-03 | `1113388` | 15 | 15 | 16 | 15 | 11 | **72** | baseline (first critic lap) |
| 2026-09-03 | `0ff1b36` | 15 | 15 | 17 | 15 | 13 | **75** | +1 데이터: the survey evidence card, digest-gated extractor and doc-to-artifact tests. +2 제출 자료: 21 verified references (F2 closed, N4 closed), a 7,204-word manuscript, F3 fixed. 연구 목적 held at 15 by F5, still open |
| 2026-09-03 | `8d1decf` | 15 | 15 | 18 | 15 | 13 | **76** | +1 데이터 (재현) only: 545 test lines under a detector that had none, six registry keys bound to the artifact, and a Korean §12 that states what the tests do NOT show. Everything else held. Nothing in the window touched the screen, the printables, the bundle or `paper/`. The branch being red at HEAD (F13) is a process defect and is not scored here, because a judge scores the tree the author brings to the booth, not the loop |
| 2026-09-04 | `12b8ac7` | 14 | 15 | 18 | 15 | 13 | **75** | **-1 연구 목적**, the first fall in this table. `12b8ac7` rewrote the opening paragraph and replaced an overstated figure with an understated one: 45,157 ha for a chain that burned 99,289 ha, plus a scope note telling the reader the 104,788 ha nationwide total is a different event when about 95 % of it is this chain, plus 영덕 8명 against this repository's own correction to 10 at `f2eecf9` (F16, F17). Unsourced-and-too-big scored 15; wrong-in-two-directions-with-no-URL scores 14. 데이터 18 and 제출 자료 13 both **held** on two offsetting moves: `DETECTION_FLOOR_CARD.md` with 17 registry-binding tests is the first judge-holdable card that cannot drift (+), and `docs/data_sources.md` gained eleven figures with no URL in the document named 데이터 출처 (-) |
| 2026-09-04 | `5a0466e` | 15 | 15 | 18 | 15 | 15 | **78** | **+1 연구 목적 (14 to 15) and +2 제출 자료 (13 to 15).** The opening paragraph's figures are now correct and every one traces to a primary page a lap opened: critic #5 re-opened the 경상북도 release (99,289 ha / 149시간 / 3,819동 / 2,246세대 3,587명 / 1조 505억), the 경향신문 joint-survey article and the 산림청 season-end release, and all of them hold. 제출 자료 gains the two points critic #4 took off it and one more: `docs/data_sources.md` table A now carries a URL on every row, the eleven-figures-no-URL section is gone, `data/processed/external/fire_2025_scale.json` gives each figure agency + as-of + scope + status + the verified quote, 16 `fire2025_*` keys are registered, and `make verify` now refuses a paragraph that drops a final figure or states an interim one as final. That is the strongest sourcing standard in the repository, in the document named 데이터 출처. 연구 목적 stops at 15 and not 16 because of F21: the scope note still tells the reader this fire is 「about 43 %」 of the national total, which is false and contradicts the repository's own registered 94.8. 데이터 18 and 설계와 방법론 15 held; nothing in the window touched a model, a split or a metric |
| 2026-09-04 | `b855943` | 16 | 15 | 18 | 15 | 15 | **79** | **+1 연구 목적 (15 to 16), the first 16 this table has recorded.** The 「약 43 %」 sentence critic #5 called false is gone from both languages, deleted rather than rewritten a fourth time, and the lap that deleted it checked the critic's reasoning and found one of its three premises wrong: 산림청 told 경향신문 that 산불영향구역 and 피해면적 「개념이 달라서 단순 비교할 수 없고」, which is a better reason to refuse the ratio than the directional one the critic gave. The opening paragraph now states figures that are all sourced and makes no claim about them that is not sourced. 데이터 18, 설계 15, 창의성 15 and 제출 자료 15 all held; see the window note for the two moves that cancel in 데이터 |
| 2026-09-04 | `8e0a6ad` | 16 | 15 | 19 | 15 | 16 | **81** | **+1 데이터 (18 to 19) and +1 제출 자료 (15 to 16).** 데이터 recovers the point critic #6 withheld: the detection-ordering split it named is closed, the booth card and the design doc now say what the paper says, no number moved, and a 15-test gate holds the withdrawal. What earns it rather than a hold is that the loop **withdrew a headline verdict it liked** and kept the weaker conclusion that survives. 제출 자료 rises on the figure work: seven figures restyled to a published standard with the rules written down in `docs/auto/knowledge/FIGURE_STYLE_REFERENCE.md` so the next figure inherits them, and a 14,000-word knowledge base whose every reference carries one of three verification tags — a sourcing discipline no rubric asked for, applied to documents no judge will read. Neither row reaches 20 or 17: WFG-063 (the trigger recommendation now has no source), WFG-051 (one death toll, three agencies, third window), WFG-064 (two figures with colliding labels) and WFG-066 (one bibliographic record written from memory) are all open. 연구 목적 16, 설계와 방법론 15 and 창의성 15 held; nothing in this window touched a model, split, metric, arm or coupling |
| 2026-09-04 | `12bf2d9` | 16 | 15 | 19 | 15 | 16 | **81** | **Every row held, and the hold on 제출 자료 is the finding.** 데이터 19 held on two moves that cancel: `tests/test_finals_screen.py` binds 26 assertions from the built screen back to the committed artifacts byte for byte, which is real 재현 machinery on the surface that had none (+), and the SYSTEM INTEGRITY panel that same screen renders prints `commit a562045`, an object `git cat-file -t` cannot resolve in a fresh clone (F41, WFG-067) (-). Nothing touched a model, split, metric, arm or coupling. 제출 자료 16 held rather than rising to 17, and both halves are worth naming: WFG-064 is **closed** (F2 writes its values inside the bars with the two reference rules in a boxed legend, F7 reads vermilion = deadline-first and teal = nearest-first in both panels, and the paper lap found and fixed two further defects nobody had named), and `references.bib` gained an entry that **corrects the registry** from a page the lap opened. That is a clear +1 on 「그래픽 및 범례의 명확성」 and 「출처 명기」. It is spent on 「자료의 논리적 구성」 by F42: `JUDGE_QA.md:240` (Q10, **T0**) tells the student to say 「신고의 99 %가 목격 신고」, and `:353` (Q10d, **T0**) lists that same sentence under 「말하면 안 되는 것」. One document, two opposite recitation orders, same tier, and the student is told to memorise both. A 제출 자료 row does not rise while the document the student recites from contradicts itself. 연구 목적 16, 설계와 방법론 15, 창의성 15 held |

| 2026-09-04 | `ce31b91` | 16 | 15 | 19 | 15 | **17** | **82** | **+1 제출 자료 (16 to 17), and it is the point critic #8 named and withheld.** That lap held this row at 16 for one reason, written down: `JUDGE_QA.md:240` (Q10, **T0**) told the student to say 「신고의 99 %가 목격 신고」 and `:353` (Q10d, **T0**) listed the same sentence under 「말하면 안 되는 것」, so 「자료의 논리적 구성」 could not rise while the document the student recites from held two opposite recitation orders at the same tier. That is closed at `ce31b91` and closed the expensive way: one sentence — 「이 측정이 말하는 것은 위성을 일차로 둘 수 없다는 것까지이며, 어떤 소스가 일차여야 하는지는 재지 않았습니다」 — copied to Q10, `detection_floor.md` §10 (whose 우선순위표 is replaced by a 「이 측정이 말하는 것」 table where the 사람 신고 row reads 「재지 않았습니다」), the booth card's front and trigger table, and `docs/SESSION19_REPORT.md` Phase 3, which was **annotated rather than edited** because it is a record. Verified independently this lap by grep over every `.md` and `.html` in the tree: the only surviving affirmative-primacy strings are the SESSION19 record inside its own dated withdrawal block and §10's paragraph explaining what the table used to be. Also worth the point on 출처 명기: the card's new 「보여주지 않는 것」 bullet describes the withdrawn 99 % statistic **in words**, because the card's own registry gate refused to let it reprint an unregistered number while withdrawing it. It stops at 17 and does not reach 18 on three things this lap measured and could not fix: the bank's header says 33 questions and 14 T0 while the file holds **41 / 15 / 19 / 7** (F49, WFG-057, P0, worse than last window), 사망 26명 still carries 중앙재난안전대책본부 in the registry and 「경상북도 최종 집계·중앙재난안전대책본부 확인」 in `README.md:198` with nothing in the repository supporting the confirmation (WFG-051, fifth window), and `docs/detection_floor.md:13` opens the very file this fix cites by asserting 「한국의 산불 탐지는 사실상 전부 사람입니다」 on the statistic §10 forbids (F48, WFG-069). 연구 목적 16, 설계와 방법론 15, 창의성 15 and 데이터 19 all held: nothing in this window touched a model, split, metric, arm, coupling or protocol, and the window's new machinery is a string gate whose measured catch rate against an outside mutation set is 2 of 20 (F47) — said explicitly so that 39 new tests are not read as 재현 progress |
| 2026-09-04 | `3a70e16` | 16 | 15 | 19 | 15 | 17 | **82** | **Every row held, and 제출 자료 is the row this lap argued itself out of raising.** The window is one dev lap (WFG-069) and critic #9's own report commit. What earns a +1 and does not get it: `docs/detection_floor.md` §0 no longer opens by asserting 「한국의 산불 탐지는 사실상 전부 사람입니다」 on a statistic §10 of the same file forbids in bold. It opens instead on a **count** — 경북 산불감시카메라 152대, 대당 약 6천만 원, **최초 발견 0건**, over **2022년 한 해와 2023년 4월 28일까지** — with the agency, the article date and the URL in the same paragraph, and it says in as many words that what comes in the satellite's place 「이 저장소가 재지 않았습니다」. **Critic #10 opened the source article rather than trusting the citation** (경향신문 2023-04-28, <https://www.khan.co.kr/article/202304281446001>): 「경북에는 152개의 산불감시카메라가 설치돼 있다 … 대당 6000만원 정도다」, 「감시카메라로 산불을 먼저 발견한 건수는 '0'건 이었다」, and the 99 % figure carries the article's own 「올해」, which is the interim scope §0 now prints beside it. Every element of the new paragraph holds against the primary source. That is the strongest 출처 명기 work yet done in a judge-facing Korean document. **What spends it, and it is new information this lap:** critic #9's window certified that a grep of 「every `.md` and `.html` in the tree」 left no surviving instance of the withdrawn ordering claim. Both claim gates and that grep are **Korean-only**, and the claim is alive in English at `docs/auto/research/RESEARCH_BRIEF_2026-09-03.md:75` — 「a satellite trigger would have fired +22/+34/+64 min *after the human report* … the design is report-first, satellite-confirm」 — under the heading 「the ten hardest judge questions, with the answers that survive the verdicts」, in the file the routine tells every lap to read, and again at `docs/auto/research/sweeps_2026-09-03/R3_science_gaps.md:22` (WFG-070, P0). 출처 명기 rose and 자료의 논리적 구성 fell by the same amount, so the row holds at 17 rather than moving in either direction. It does not reach 18 on three unchanged defects: the bank header still says 33 / 14 / 13 / 6 where the file holds **41 / 15 / 19 / 7** (WFG-057, **fifth** window, and it is now blocking this routine's own judge-drill output for a second lap — a critic that cannot add a question without making the miscount worse cannot do step 3 of its job); WFG-051, **sixth** window, now sharper — `fire2025_chain_deaths` carries `agency: 중앙재난안전대책본부` while `paper/manuscript.md:37` calls the same 26 deaths 「the **provincial** disaster headquarters' count」, four documents and three attributions; and the 8.2 km h⁻¹ spread rate is still in no document a judge is handed (WFG-065, fourth window). 연구 목적 16, 설계와 방법론 15, 데이터 19 held: nothing in this window touched a model, split, metric, arm, coupling or protocol. **창의성 15 held, and it was the closest call.** `tests/test_external_figures_carry_their_scope.py` contains `test_the_escapes_this_gate_cannot_close_are_still_open`, which fails when the gate starts catching something its own docstring says it cannot — executable documentation of a limit, and the first instrument in this repository whose job is to keep its author honest rather than its documents consistent. That is real novelty. It is novelty in the **loop's process**, not in the 작품 a judge scores, and the same window's evidence is that the process produced its **third** parallel hand-rolled string family (WFG-071) rather than the general one WFG-062 asks for. Credited in words, not in a point |

| 2026-09-04 | `c65dc56` | 16 | 15 | **18** | 15 | **17** | **81** | **데이터 recovers one of the two points F54 cost, and 제출 자료 pays one back, so the total holds at 81 on a changed composition.** **데이터 17 to 18.** The wrong county is corrected and I verified it without trusting the lap that fixed it: reading the eight committed GeoJSON files directly, `minwon_agencies` holds 55 features whose road-address strings contain 영덕군 **56 times and 봉화군 zero times**, `samul_eqwav_point` (지진해일긴급대피장소) is populated at **92** rows where the first cut returned zero, and every non-empty layer now overlaps `regions.lookup('yeongdeok_2025').bbox_wgs84` with 57 to 84 % of its points inside. The extractor and `tests/test_juso_yeongdeok.py` now assert the address check and set containment, so this artifact carries the check its absence caused. Why +1 and not +2, which is what F54 took: the same commit registered `juso_yeongdeok_samul_lifesav_point_count` = 0 and `juso_yeongdeok_samul_emerwat_point_count` = 0 and wrote at `docs/juso_yeongdeok.md:58` 「(인명구조함 and 비상급수시설 have no 영덕 rows)」 as a fact about the county, in the same commit whose MEMO lesson reads 「a "zero rows" result for a layer that must exist in the region is a wrong-filter signal, not a fact」 (WFG-080); and eight registry values were **edited in place** with their caveats deleted, against CHARTER §3 rules 2 and 3, the replacement caveat stating the position outright as 「The wrong first values are kept in git history (3fdb888), not here」 (WFG-078). A 재현 row does not take the full recovery in a window where the registry stopped being append-only and no gate noticed. **제출 자료 18 to 17.** For it: WFG-067 closed, so the screen's own SYSTEM INTEGRITY line resolves to a commit reachable from HEAD (`d5e2562`), which is the defect that capped this row for four windows. Against it, three defects all in documents the student recites from: `docs/juso_yeongdeok.md` contradicts itself twice inside one file, reprinting at `:61` both the withdrawn 45 km figure its own `:15` forbids and the county name its own `:29` refuses to write without the record (WFG-079); `JUDGE_QA.md` Q35 still tells the student to answer 「아니오」 and 「그 줄은 지금 틀렸습니다」 about the very stamp that was fixed, quoting `a562045`, which is on neither the screen nor the judge's mind (WFG-081); and the bank header still reads 33 / 14 / 13 / 6 where the file holds **41 / 15 / 19 / 7**, counted again this lap and unmoved for three windows (WFG-057). Two of those three were written **in this window**, which is why the net is negative rather than a hold. **연구 목적 16, 설계와 방법론 15, 창의성 15 held:** nothing in this window touched a model, split, metric, arm, coupling or protocol. |
| 2026-09-04 | `baf6962` | 16 | 15 | 18 | 15 | **18** | **82** | **+1 제출 자료 (17 to 18), and it is exactly the point critic #12 named and withheld.** That lap capped this row on three defects in documents the student recites from; **two of the three closed in this window and I verified both from the files rather than from the laps that fixed them.** **WFG-057:** `docs/auto/JUDGE_QA.md` now says 41 questions and T0/T1/T2 = 15/19/7, and counting the file directly gives **41 questions, 15 / 19 / 7** - the header, the four drill rounds and the file finally agree, and the drill table names every one of the 41 by number where it had been naming 33. The regex now reads the lettered suffix and the parenthesised provenance, so the next question added makes the header and the table wrong together and the gate red. That miscount had stood for six windows and, worse, it was disabling this routine's own judge drill. **WFG-081:** Q35 no longer scripts the student to open with 「아니오, 그 줄은 지금 틀렸습니다」 about a defect fixed nine hours earlier. The rewritten answer is 「예」, and it holds: `web/finals.html` carries `"git":"d5e2562"`, `git cat-file -t` resolves it and `git merge-base --is-ancestor d5e2562 HEAD` succeeds in this fresh clone. The item keeps the history as 내력 rather than deleting it, which turns the repaired defect into the file's best worked example of what reachability means and why existence is the weaker check. Its two supporting claims also verify: `tests/test_finals_screen.py` holds **32** tests and two of them read that line. **Judge-drill evidence for the point, not just the repairs:** I resolved every one of the **77 distinct file paths** the bank cites; all 77 exist (five are directory-relative shorthands - `check_forbidden.py`, `check_number_collisions.py`, `delivery/sms.py`, `routing_demo.npz`, `routing_demo_canonical.npz` - resolving under `scripts/`, `src/wildfireguardian/` and `data/processed/`). I then drilled the hardest T0, Q1, against the artifacts: pooled recall **0.138**, mean-of-folds **0.0867**, average precision **0.169**, prevalence **0.0197**, threshold 0.3 and router cut 0.5 all re-derive from `data/processed/operating_point/per_fire_recall.json` and `docs/NUMBERS.json` exactly as the answer states. **No question in this bank went unanswerable from a file this lap**, so no 「근거 없음」 entry was added; the one that was already open, Q34 (spread rate, WFG-065), is open for a fourth window. **Why 18 and not 19.** The third defect is untouched: `docs/juso_yeongdeok.md` still contradicts itself inside one file, its `:61` correction paragraph writing both the 「약 45 km」 its own `:15` forbids in bold and the 봉화군 its own `:29` refuses to name without 행정표준코드 (WFG-079), and `:58` still records two zero-row layers as facts about the county against its own commit's MEMO lesson (WFG-080). **데이터 18, 연구 목적 16, 설계와 방법론 15, 창의성 15 all held:** nothing in this window touched a model, split, metric, arm, coupling or protocol, and WFG-078 (eight registry values edited in place, caveats deleted) is unchanged. The window's six red `auto-gates` runs are not scored, on critic #3's standing precedent that a judge scores the tree the author brings to the booth and not the loop - and they are closed anyway (`21b8740`, verified: run 95 at `baf6962` is `success` and `gates.py --mode full` exits 0 here) |
| 2026-09-04 | `ed35f0d` | 16 | 15 | **19** | 15 | **17** | **82** | **B holds at 82 and the two moving rows move against each other, which is the honest reading of this window.** **데이터 18 to 19:** `paper/manuscript.md:656-671` now states that every refuge in every result is an OpenStreetMap point, names the agency-designated inventory that no result uses, gives both data dates and the county-versus-walk-box extent mismatch, and weakens the category claim to what the seven-layer cut supports — a concession made from the data rather than extracted by a critic, which is the behaviour this row is for. WFG-062 adds the second half: the record of what this repository withdrew is now machine-read against **915 gated files** of 989 tracked, not 11, and `docs/withdrawn_claims.md` §4 publishes in bold what that did NOT buy. I measured the unbought half from outside — a 26-sentence probe set written without reading the patterns: **verbatim 6/6, rewordings 1/20** — and it confirms the document rather than contradicting it. **제출 자료 18 to 17:** `docs/auto/JUDGE_QA.md:585-603`, Q18, is a **T0** answer telling the student that the designated-shelter comparison is blocked by a portal login, while `6f33eca` put the re-cut 영덕 designated-site layers in the tree and NH-012 is closed. Scored on the same surface critic #13 raised this row on and in the opposite direction, because it is the same kind of defect: the bank teaching a sentence the tree has moved past (WFG-087) |
## Track A — 애플리케이션 / 실생활 도구

| date | window head | 개발 목적 | 설계와 방법론 | 구현 및 유용성 | 창의성 | 제출 자료 | /100 | what moved |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-09-03 | `1113388` | 15 | 15 | 11 | 15 | 11 | **67** | baseline (first critic lap) |
| 2026-09-03 | `0ff1b36` | 15 | 15 | 11 | 15 | 12 | **68** | +1 제출 자료 only: the survey card gives Q17 a file to point at. 구현 및 유용성 does not move, because nothing in this window touched the screen, the printables or the bundle (R1, R2, R7, R9 all still ☐) |
| 2026-09-03 | `8d1decf` | 15 | 15 | 11 | 15 | 12 | **68** | **held, every row.** Track A's judges score a working tool at a booth. This window added tests to a script that runs offline in the sandbox and never appears on the screen. R1, R2, R7, R9 are still ☐, and R2 is now blocked on WFG-021's stranded status rather than on work (F15). Said explicitly so 545 test lines are not read as progress on the thing these judges watch |
| 2026-09-04 | `12b8ac7` | 14 | 15 | 11 | 15 | 12 | **67** | **-1 개발 목적**, the same paragraph, and these judges read it at the booth with a phone in hand. 구현 및 유용성 **11, held for the fifth consecutive window**: no commit in this window touched `web/`, the printables or the release bundle, and R1, R2, R7 and R9 are all still ☐. WFG-017 is now the single most overdue thing in the sprint plan |
| 2026-09-04 | `5a0466e` | 15 | 15 | 11 | 15 | 13 | **69** | **+1 개발 목적 (back to 15), +1 제출 자료 (12 to 13).** These judges read the opening paragraph at the booth with a phone in hand, and the phone now agrees with the paragraph. 제출 자료 rises on the sources table gaining a URL per row. **구현 및 유용성 11, held for the sixth consecutive window.** No commit in this window touched `web/`, the printables or the release bundle; R1, R2, R4, R7 and R9 are all still ☐ with eleven days left in the sprint. Three windows ago this was a note, two ago a risk. It is now the finding that decides the score: the artifact five judges watch for five minutes still does not exist in its finals form, and WFG-017 has been named the next row by two critic laps running |
| 2026-09-04 | `b855943` | 16 | 15 | 11 | 15 | 13 | **70** | **+1 개발 목적 (15 to 16)**, the same deletion, read at the booth. **구현 및 유용성 11, held for the SEVENTH consecutive window.** No commit in this window touched `web/`, the printables or the release bundle. `docs/auto/KCF_READINESS.md` has 2 of its 11 lines ticked (R5, R6) with eleven days of sprint left, and R1, R2, R4, R7, R9 and R11 are all still ☐. 제출 자료 13 held: `references.bib` gained five entries whose notes are the best sourcing work in this repository (one of them re-opens its own URL and corrects a paraphrase the previous lap wrote), and against that the 사망 26명 attribution disagreement is now in three documents instead of two |
| 2026-09-04 | `8e0a6ad` | 16 | 15 | 11 | 15 | 13 | **70** | **Every row held.** 제출 자료 does **not** take Track B's +1: the figure restyle is manuscript work and a manuscript is not what these judges score, which is the same reading critic #2 used. **구현 및 유용성 11, eighth consecutive window** — and this lap owes the table a correction rather than another adjective. Three critic laps called this row's backlog item 「the single most overdue thing in the sprint」 and 「the largest single risk in the sprint plan」. Against the sprint plan at the top of `docs/auto/BACKLOG.md`, **WFG-017 is due 09-07 and today is 09-04**, and every row the plan dates 09-04 (WFG-002, WFG-004) and 09-05 (WFG-020, WFG-021) is `done`. The loop is **ahead of its own schedule**, and 「seventh/eighth consecutive window」 counts critic windows, not missed dates. What is true, and is enough: `web/` has not been touched since `25f1e14` on 2026-09-02, so the artifact five judges watch for five minutes has **never once been exercised** by this loop, and the cost of the first attempt is therefore unknown with 11 days left. That is a risk statement, not a slippage statement, and this table should have said so three windows ago |
| 2026-09-04 | `12bf2d9` | 16 | 15 | **14** | 15 | 13 | **73** | **구현 및 유용성 11 to 14, the first move on this row in nine windows, and the largest single move this table has recorded.** `web/finals.html` had not been opened by this loop since 2026-09-02. It now carries five evidence cards (운영점, 탐지 바닥, 240분 지평, 대피 지점 배치, 제출본과 정본), `build_finals.py --verify` runs three gates at build time and prints their exit codes on the RELIABILITY tab, 26 tests bind every card value to the artifact it came from, nine screenshots are committed as the lap's record of looking at what it shipped, and `docs/finals_screen_v2.md` says for each card what it does **not** say. `KCF_READINESS.md` R2 ticks today. Why 14 and not 17: R1 (a committed mapping of every on-screen number to a registry key), R4 (the 5-minute script), R7 (printables) and R9 (the bundle) are all still ☐, no one has opened this file on the booth laptop (R12, NH-014), the automated smoke is WFG-009, and the panel a judge is invited to verify the build with prints a commit that does not exist (F41). These judges score a working tool at a booth; there is now a tool, and it has not yet been to a booth. 제출 자료 13 held: the figure and citation work is manuscript work these judges do not read, and what they **do** read, the screen's own 출처 line, resolves to nothing. 개발 목적 16, 설계와 방법론 15, 창의성 15 held |

| 2026-09-04 | `ce31b91` | 16 | 15 | 14 | 15 | 13 | **73** | **Every row held, and 제출 자료 is the one this lap argued with itself about.** Track B takes +1 for the Q&A bank no longer contradicting itself at T0. These judges do not read `docs/auto/JUDGE_QA.md`; they hear the student, for five minutes, at a booth. What changed this window is a **document** the student recites from, not a rehearsal: `docs/auto/DEMO_SCRIPT_5MIN.md` still does not exist (R4 ☐, WFG-003), `docs/auto/finals/BOOTH_SETUP.md` still does not exist (R3's booth half, WFG-037), `release/kcf-finals-2026/` still does not exist (R9 ☐, WFG-036), and no one has opened the screen on the booth laptop (R12, NH-014). Three of eleven `KCF_READINESS.md` lines are ticked with eleven days of sprint left. The same discipline critic #2 and critic #8 used to refuse Track A the manuscript's points refuses it this one, and the refusal should be revisited the moment a script exists. **구현 및 유용성 14, held:** no commit in this window touched `web/`, and the defect that capped it at 14 last window is unchanged — the SYSTEM INTEGRITY panel still prints `commit a562045`, and `git cat-file -t a562045` in this fresh clone still answers `fatal: Not a valid object name` (WFG-067, P0, second window). The one improvement these judges would feel is real and is priced into the hold rather than a rise: the sentence the student will say when a judge asks about the trigger now matches the screen behind them, which it did not two windows ago. 개발 목적 16, 설계와 방법론 15, 창의성 15 held |
| 2026-09-04 | `3a70e16` | 16 | 15 | 14 | 15 | 13 | **73** | **Every row held, and the hold on 구현 및 유용성 is the eleventh consecutive window without a commit to `web/`.** Nothing in this window touched the screen, the printables or the bundle. `docs/auto/DEMO_SCRIPT_5MIN.md` still does not exist (R4 ☐, WFG-003, which has been the next `todo` row in table order for two windows), `docs/auto/finals/BOOTH_SETUP.md` still does not exist (R3's booth half, WFG-037), `release/kcf-finals-2026/` still does not exist (R9 ☐, WFG-036, plan date 09-10, six days out). **Three of eleven `KCF_READINESS.md` lines are ticked** (R2, R5, R6) with eleven days of sprint left. The defect capping this row is unchanged and is now in its **third** window: `git cat-file -t a562045` in this fresh clone still answers `fatal: Not a valid object name`, and `web/finals.html` still carries `"git":"a562045"` in the panel whose whole job is to let a judge verify the build (WFG-067, P0). These judges score a working tool at a booth; the tool exists, has still never been opened on the booth laptop (R12, NH-014), and the one line on it that invites verification resolves to nothing. 제출 자료 13 held: what moved this window is a Korean design document and a test file, and these judges read neither. 개발 목적 16, 설계와 방법론 15, 창의성 15 held |
| 2026-09-04 | `83f49bc` | 16 | 15 | 14 | 15 | 13 | **73** | **Every row held, and this table owes the loop a correction it has been getting wrong for four windows.** 구현 및 유용성 14 holds for the twelfth consecutive window without a commit to `web/`, and three of eleven `KCF_READINESS.md` lines are still ticked. Previous critic laps called that slippage. It is not: **NH-021 closed on 2026-09-04 with the author choosing 「Do WFG-062 now (the withdrawn-claims registry gate first; booth rows resume after)」**, so WFG-003, WFG-037 and WFG-036 are behind a gate row **by the author's own decision**, taken against exactly this trade-off written out for them. This table should score the consequence and stop calling it overdue. The consequence is real and unchanged: `DEMO_SCRIPT_5MIN.md` (R4), `finals/BOOTH_SETUP.md` (R3 booth half) and `release/kcf-finals-2026/` (R9) do not exist, nobody has opened the screen on the booth laptop (R12, NH-014), and the one line on the screen inviting a judge to verify the build still prints a commit that does not resolve (WFG-067, **fourth** window on a ☑ line). 제출 자료 13 held: F8 is manuscript work and these judges do not read the manuscript, the same discipline critics #2, #8 and #9 applied. The window's data defect (F54) does not move this row either, because nothing on the screen or in the printables consumes it — but it would have, through WFG-073 and WFG-074, which are now blocked. 개발 목적 16, 설계와 방법론 15, 창의성 15 held |
| 2026-09-04 | `c65dc56` | 16 | 15 | **15** | 15 | 13 | **74** | **구현 및 유용성 14 to 15, the second move on this row in fourteen windows, and it is one defect closed rather than one capability added.** WFG-067 is done: `web/finals.html` carries `"git":"d5e2562"` and `git merge-base --is-ancestor d5e2562 HEAD` succeeds in this fresh clone, so the one line on the screen that invites a judge to verify the build now resolves. The gate asserts **reachability from HEAD** rather than existence, which is the right instrument and is better than the row asked for, because `git cat-file -e` passes for a rebased-away object and would have stayed green on the machine that made the defect. That defect had stood for four consecutive critic windows on a ☑ line. Why 15 and not more: nothing in this window added anything to the screen, and the definition of done has not moved. **Three of eleven `KCF_READINESS.md` lines are ticked** (R2, R5, R6). `docs/auto/DEMO_SCRIPT_5MIN.md` does not exist (R4), `docs/auto/finals/BOOTH_SETUP.md` does not exist (R3 booth half), `release/kcf-finals-2026/` does not exist (R9), the printables do not exist (R7), and nobody has opened the screen on the booth laptop (R12, NH-014). Critic #11 corrected this table for calling that slippage, and the correction stands: the booth rows are behind WFG-062 by the author's decision in NH-021. What this lap adds to that correction is the part that is nobody's decision: **WFG-062 is still `todo` too**, 22 commits and 14 reports after the author chose it, so the loop holds neither the gate it deferred the booth for nor the booth. **제출 자료 13 held**, and Q35 is why it did not rise with the stamp. These judges do not read the registry; they hear the student for five minutes. The bank still drills the student to volunteer a fault that no longer exists, about a commit id that is not on the screen behind them (WFG-081). The point WFG-067's fix earned on the screen is spent on the document that tells the student what to say about it. **개발 목적 16, 설계와 방법론 15, 창의성 15 held.** |
| 2026-09-04 | `baf6962` | 16 | 15 | 15 | 15 | **14** | **75** | **+1 제출 자료 (13 to 14), the first move on this row since `5a0466e`, and it is the same Q&A repair scored on the surface that matters most for Track A.** Track A's 자료 row has sat at 13 through fourteen windows while Track B's climbed 11 to 18, and the gap was never really about the registry - it was that the document the student actually speaks from was drifting from the tree behind it. Both drifts closed here. The bank now counts itself correctly (41 questions, 15/19/7, verified by counting the file), so the four drill rounds a student is told to rehearse finally name every question that exists; before this lap **Q10d was T0 and was in no drill round at all**, and its whole purpose is to stop the student re-stating a withdrawn ordering claim (WFG-053). And Q35 stopped drilling the student to volunteer a fault that had been fixed nine hours earlier about a commit id no longer on the screen behind them. For five judges at five minutes each, a rehearsal script that matches the screen is worth more than any registry key. **Why 14 and not 15:** `docs/juso_yeongdeok.md` still contradicts itself twice inside one file (WFG-079), and the printables that this row ultimately needs do not exist (R7). **구현 및 유용성 15 held: nothing in this window touched `web/`.** Three of eleven `KCF_READINESS.md` lines are ticked (R2, R5, R6) and **no line has been ticked for four consecutive critic laps** - the last was R2 by critic #8 at `12bf2d9` (0750Z), and critic #12 did not write the file at all. `docs/auto/DEMO_SCRIPT_5MIN.md` (R4), `docs/auto/finals/BOOTH_SETUP.md` (R3 booth half) and `release/kcf-finals-2026/` (R9) are all still absent on disk, checked this lap. **개발 목적 16, 설계와 방법론 15, 창의성 15 held** |
| 2026-09-04 | `ed35f0d` | 16 | 15 | 15 | 15 | **13** | **74** | **-1 제출 자료 (14 to 13), the same Q18 defect scored on the booth-materials row, and 구현 및 유용성 holds 15 for a TWELFTH window with no commit to `web/`.** A Track A judge scores what the tool does and what the booth shows. What the tool does did not change in this window: no code outside `scripts/check_withdrawn_claims.py` and its tests, nothing in `src/`, nothing in `web/`. What the booth shows got one point worse, on the one document the student is drilled from. The three artifacts this row would actually move — `docs/auto/DEMO_SCRIPT_5MIN.md`, `docs/auto/finals/BOOTH_SETUP.md`, `release/kcf-finals-2026/` — do not exist at `ed35f0d`, checked on disk. WFG-062's gate is real engineering and a Track A judge will never see it |

## 2026-09-03 · `25f1e14..1113388` — why these numbers

**연구 목적 / 개발 목적 · 15.** The problem is specific, the population is specific, and
the frame (spread forecast → rescue-aware routing → decision layer) is the submitted one.
It loses points on its own opening paragraph: three scale figures with no URL, no registry
key, and one that exceeds the national total (CRITIC F5, WFG-043). A judge who checks the
motivation before the method finds the softest evidence in the repository first.

**설계와 방법론 · 15 (both tracks).** Leave-one-fire-out is the right design and is
enforced, variables and controls are named, and the negative results are kept rather than
buried. Held back by 기존 연구와의 차별점: the related-work table is WFG-026 and unstarted,
and the one related-work citation that exists is not the paper at its URL (F2). 일정·역할
(WFG-027) is also unstarted.

**데이터 수집·분석·해석 · 16 — the strongest row.** Six fires, event-held-out, an operating
point owned rather than hidden (pooled recall 0.138, three folds with zero true positives),
mean-of-folds and pooled kept apart as different quantities, a 296-entry registry that
re-derives, and a lineage gate that found four real instances the moment it was switched
on. It is not 18+ because the loop's own suite instrument is compromised: every recorded
pass/skip baseline is an unlabelled mixture of cold-run and warm-run readings (F8,
WFG-038/039), so the "no test was lost" comparison has been comparing different quantities.

**창의성 · 15.** The coupling — a calibrated held-out hazard field driving a time-expanded
pedestrian router with a rescue-ingress term — is the creative claim and it is real. Nothing
in this window added to it; the window was traceability and scaffolding work.

**제출 자료 · 11 — the weakest row, and the cheapest to move.** 출처 명기 is scored, and it
is where the repository is thinnest: the opening scale figures are unsourced (F5), one
`verified` citation is the wrong paper (F2), SRTM / ESA WorldCover / OpenStreetMap are used
and uncited in the manuscript (N4), and the finals screen, printables, README Round-4
section and release bundle (R1, R2, R7, R8, R9) do not exist yet. Logical 구성 is good; the
graphics are good; the sourcing is not.

**구현 및 유용성 · 11 (Track A only).** `web/finals.html` v2, the 5-minute script, the booth
recipe and the release bundle are all still `todo` (WFG-017, WFG-003, WFG-037, WFG-036).
This row is scored on what a judge can watch at the booth, and that artifact does not exist
in its finals form yet. It should move most between 09-07 and 09-14.

**Not scored here:** the two Pass/Fail rows (서류 구비, 위험성 검토). 서류 is the author's
(WFG-022 / NH-008); 위험성 is not at risk — the delivery layer stays dry-run by design.

## 2026-09-03 · `a278a56..0ff1b36` — why these numbers moved (critic #2)

Two rows moved and three did not. The window was one dev lap (WFG-020, the survivor
survey) and the first real paper lap (605 words to 7,204).

**데이터 수집·분석·해석 · 16 → 17.** `docs/evidence/greenpeace_2026_survey.md` plus
`data/processed/evidence/greenpeace_2026_survey.json` plus
`scripts/extract_survey_evidence.py`, which refuses to read a digit until the source
sha256 matches, is the first time this repository has taken a third-party measurement
and made the transcription itself machine-checkable rather than hand-typed beside a
hash. `tests/test_greenpeace_evidence.py` then binds both the evidence card and the
booth answer to the artifact, and its own docstring records the mutation that shows
where the binding stops. That is the behaviour the row scores. It is +1 and not +2
because the survey evaluates nothing about our model, which the card says plainly.

**제출 자료 · 11 → 13 (Track B), 11 → 12 (Track A).** 출처 명기 was named the weakest
and cheapest row at the baseline, on four specific defects. Two are closed: the
`verified` citation that was not the paper at its URL (F2) and the three uncited data
sources SRTM, ESA WorldCover, OpenStreetMap (N4). `references.bib` is now 21 entries,
each opened at its URL by the lap that added it. The manuscript is a real artifact a
judge can be handed. It is not more than +2 because F5 (the opening scale figures) is
untouched, F11 (21 citations, no bibliography) is new, and R1, R2, R7, R8 and R9 are
still ☐. Track A gets +1 rather than +2 because a manuscript is not what its judges
score.

**연구 목적 / 개발 목적 · 15, held.** The paragraph that states why the project exists
still carries ~116,000 ha (F5). One search, in the first thing a judge reads.

**설계와 방법론 · 15, held; 창의성 · 15, held.** Nothing in this window changed a method
or the coupling. The paper *describes* them better, which is the 제출 자료 row.

**구현 및 유용성 · 11, held (Track A).** No commit in this window touched `web/`, the
printables or the release bundle. Said explicitly so the manuscript is not read as
progress on the thing the booth judges actually watch.

## 2026-09-03 · `1c1561e..8d1decf` — why these numbers

**데이터 수집·분석·해석 · 17 → 18 (Track B).** `scripts/gk2a_detection.py` produces the
+22 / +34 / +64 minute figures and the 0-of-709 false-alarm bound, both of which are
quoted on judge-facing documents, and until this window it had no tests at all.
`tests/test_gk2a_detector.py` binds six registry keys to
`data/processed/detection/*.json`, reproduces the recorded 21.964 K contextual threshold
from the artifact rather than from a literal, and pins the geometry that makes 영덕's
교란 classification mean something. `docs/detection_floor.md` §12 then states, in bold,
which groups are synthetic and that their gains are the test's own and must not be cited
as GK2A calibration. It is +1 and not +2 because the tests mostly ask the code to agree
with itself, which §12 says first, and because the one group with outside ground truth is
opt-in and runs for nobody by default (N14).

**제출 자료 · 13, held (Track B); 12, held (Track A).** No citation, reference or
submission artifact changed. F11 (21 citations, no bibliography) is untouched because
`paper/` did not move.

**연구 목적 / 개발 목적 · 15, held.** F5 is in its third critic lap. The opening paragraph
still carries a burned area larger than the national total, and it is blocked on the
author's sources (NH-015), not on a lap.

**설계와 방법론 · 15, held; 창의성 · 15, held.** The `contextual_flag` extraction is
semantics-preserving by design and by inspection. Nothing in this window changed a method,
a coupling or an experimental arm.

**구현 및 유용성 · 11, held (Track A).** No commit touched `web/`, the printables or the
release bundle. Fourth consecutive window in which that is true, which is the one thing in
this table the sprint plan should worry about: the finals screen is what five judges
actually watch for five minutes, and WFG-017 is still ahead of the loop.

## 2026-09-04 · `9bf15fb..12b8ac7` — why these numbers

**연구 목적 / 개발 목적 · 15 → 14.** The first fall this table has recorded, and it is
deliberate. For three critic laps this row was held at 15 with F5 open: the opening
paragraph carried ~116,000 ha, unsourced and larger than the national total. That is a
figure a judge distrusts. `12b8ac7` replaced it with 45,157 ha, which is the 경북 provincial
interim tally on 2025-03-27, one day before 주불 진화 on 03-28, for a chain whose final
burned area is **99,289 ha** — and added a 범위 주의 note asserting that the 104,788 ha
nationwide figure belongs to a different event, when the chain is about 95 % of it. The
same commit left 영덕 **8명** standing in both languages twelve hours after this repository
corrected that figure to **10** in `docs/evidence/greenpeace_2026_survey.md` §7. One wrong
number a judge can find is a 15; two wrong numbers in opposite directions, one of which
contradicts the project's own committed evidence card, is a 14.

**데이터 수집·분석·해석 · 18, held.** Nothing in this window changed a method, a split, a
metric or an eval; `mandela` fires on nothing. The window's data work is traceability, and
it is good traceability: `tests/test_detection_floor_card.py` binds every figure on the new
card to `docs/NUMBERS.json` and binds each delay inside its own table row, so a swapped
attribution fails rather than passing on a substring. That is worth saying and it is not
worth a point, because the underlying result is the one already scored at `8d1decf`.

**설계와 방법론 · 15, held; 창의성 · 15, held.** No coupling, arm or protocol moved.

**제출 자료 · 13 (Track B) / 12 (Track A), held, on two moves that cancel.** Up:
`docs/auto/finals/DETECTION_FLOOR_CARD.md` is the first evidence card in this project a
judge can hold whose every digit is checked against the registry by a test, and the lap that
wrote it left a number **off** the card because it has no key (WFG-048) rather than typing
it. That is the sourcing standard this row has been asking for since the baseline. Down:
`docs/data_sources.md` gained a section of eleven figures across two tables with an 출처
column of agency names, a 기준일 column, and **not one URL, 보도자료 number or page** — in
the document whose title is 데이터 출처, closing the entry that existed to put sources under
exactly these numbers. The previous text at least named three checkable outlets. A judge
scoring 출처 명기 would read the card and the table in the same sitting.

**구현 및 유용성 · 11, held (Track A). Fifth consecutive window.** Five windows is no longer
a note, it is the sprint's main risk: the artifact five judges watch for five minutes does
not exist in its finals form, and every lap since 09-03 morning has improved something
those judges will never see. WFG-017 should be the next row after WFG-043.

**Not scored here:** the two Pass/Fail rows. 서류 is now the author's own decision under the
NH-008 closure (no contact with the 운영사무국 will be made); 위험성 is not at risk.


---

## Window 2026-09-04 `a4dc9a7..5a0466e` (critic #5)

**연구 목적 · 15, recovered, and capped there by one sentence.** Three laps spent a whole
window on the first paragraph a judge reads, and the figures are now right: checked cold
against four primary pages this lap, not one is wrong. The row does not go back to 16
because the paragraph still asserts, in both languages, that a like-for-like comparison
would put this fire at about 43 % of the national total. 산불영향구역 includes the unburned
ground inside the fire line and is normally the larger of the two statistics, so a 45,157 ha
영향구역 under a 99,289 ha 피해면적 is the relation inverted; the article the repository
cites for the definition calls the 45,157 an undercount that the survey more than doubled;
and `docs/NUMBERS.json` records the share as 94.8. One deleted sentence is the whole fix
(F21) and it is worth a point.

**제출 자료 · 15 (Track B) / 13 (Track A), the largest single-window rise in this table.**
The mechanism is what earns it, not the prose. A figure in the opening paragraph now has a
registry key, an artifact row with agency and as-of date and scope and status, the URL a lap
opened, and the sentence that page actually said; two gates hold the paragraph to it; and
the sourcing rule was applied where it cost something, with two figures removed rather than
kept at lower confidence. A judge who asks 출처가 어디입니까 can be shown a chain from the
screen to the page in four steps.

**설계와 방법론 · 15, 창의성 · 15, 데이터 · 18: held.** No model, split, metric, arm or
protocol moved. Said explicitly so 44 new tests are not read as scientific progress.

**구현 및 유용성 · 11 (Track A), sixth consecutive window.** Eleven days of sprint remain
and the finals screen has not been touched since 09-03. Every lap since then improved
something these five judges will never see. This is now the largest single risk in the
sprint plan, larger than any finding in this report.

**Not scored here:** the two Pass/Fail rows. 서류 is the author's own under the NH-008
closure; 위험성 is not at risk.

---

## Window 2026-09-04 `5a0466e..b855943` (critic #6)

**연구 목적 / 개발 목적 · 15 → 16.** The first 16 in this table. Three critic laps in a row
named the opening paragraph as the softest evidence in the repository; it is no longer that.
Every figure has a registry key, an artifact row carrying agency and as-of date and scope and
status and the sentence the page actually said, a URL a lap opened, and two gates holding the
prose to all of it — and as of this window the paragraph also makes no *claim* about those
figures that is not sourced. What earns the extra point rather than a hold is how the last
sentence went: the lap deleted it, checked the critic's argument for deleting it, found one
of the critic's three premises was wrong (산림청 itself says 산불영향구역 and 피해면적
「개념이 달라서 단순 비교할 수 없고」, so the directional argument does not hold), and wrote
the agency's wording into `docs/data_sources.md` 함정 1 and 함정 6 instead of the critic's.
A loop whose reviewer can be wrong and whose lap checks it is a different object from a loop
that obeys its reviewer.

**데이터 수집·분석·해석 · 18, held, on two moves that cancel.** Up: `paper/manuscript.md`
§4.7 is a real new result written the way this project's best work is written — a negative
control with its numerator at zero reported as an upper bound and not a rate, a sub-pixel
size floor given as an order of magnitude because the flame-temperature assumption moves it
eightfold, one of the four fires excluded as confounded rather than counted either way, and
an n = 3 comparison labelled a description of three events rather than an operating
characteristic. The same lap's reviewer blocked an ordering claim it could not source and
the lap **reverted the claim rather than repeating it**, filing `paper/GAPS.md` G5 and
NH-019. Down, and exactly offsetting: the repository now holds two answers to that same
question. `docs/detection_floor.md` §9, `docs/auto/finals/DETECTION_FLOOR_CARD.md` and
`docs/auto/JUDGE_QA.md` Q10 all still assert that the satellite rang after the telephone,
and the manifest they measure from calls the reference field the ignition (F27, WFG-053).
A row scored on 재현 가능성 and 논리적 해석 cannot rise while the paper and the booth card
answer one question differently.

**설계와 방법론 · 15, held; 창의성 · 15, held.** No model, split, metric, arm, coupling or
protocol moved. Said explicitly so that a 938-line manuscript rewrite is not read as
scientific progress: it is 제출 자료 work and one new result, and the new result is §4.7.

**제출 자료 · 15 (Track B) / 13 (Track A), held.** The references work in this window is the
best sourcing this repository has produced. `references.bib` gained five entries, and the
WWA note does something no gate asked for: it re-opened its own URL and corrected the
paraphrase the previous lap's note carried, which had rendered 「Uiseong was hardest hit,
with 26 deaths, while four occurred in Sancheong」 as "26 of them in Uiseong-gun" — turning a
fire attribution into a county one and dropping the four deaths that reconcile 26 with 32.
Against that: F23 is unfixed in its second window and has now **propagated**. 사망 26명 is a
중앙재난안전대책본부 count in the registry, a 경상북도 재난안전대책본부 count in
`docs/data_sources.md:190`, and "the provincial disaster headquarters' count" in
`paper/manuscript.md:37`, and the README link a judge would click still carries no death
figure at all. And the manuscript is 7,479 words against a 7,500 hard fail, enforced as a
proxy for a 20-page limit the loop's own recount puts at about 21 pages (F29). A row scored
on 출처 명기 and 논리적 구성 does not rise on excellent citations while the same window leaves
one figure with three agencies and a length gate measuring the wrong quantity.

**구현 및 유용성 · 11 (Track A), seventh consecutive window, and this is now the report's
second finding rather than a note.** Since 2026-09-03 morning, every lap has improved
something these five judges will never see. `KCF_READINESS.md` is the definition of done for
the final product and it has **2 of 11 lines ticked**. Eleven days of sprint remain. The
backlog table order puts WFG-017 next once WFG-021 stops reading as `todo`, which this lap
fixed by parking its unrunnable part; nothing else stands between the loop and the screen.

**Not scored here:** the two Pass/Fail rows. 서류 is the author's own under the NH-008
closure; 위험성 is not at risk, the delivery layer stays dry-run.
