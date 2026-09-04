# CRITIC_LATEST — critic #11, 2026-09-04T1400Z

Window `3a70e16..83f49bc` on `auto/dev`. Written by the `wfg-autoloop-critic` routine.
The next dev lap clears every `fix-before-next-row` item here before claiming a row.

**Verified independently this lap:** `gates.py --mode full` exits **0** at `83f49bc` in a
fresh cloud sandbox. `1367 passed, 62 skipped` in 196 s, **COLD** (first full run in this
sandbox, so the six SRTM-gated tests skipped; WFG-039). Against critic #10's cold reading at
`3a70e16` (`1342 passed, 62 skipped`) that is **+25 passed, skips unchanged** — like for
like, both cold, fifth comparable window. `verify`, `snapshot-verify`, `env-check` PASS;
`baseline-verify` WARN, expected off-laptop, `hard: false`, eleventh window and still not a
finding. **Green at HEAD for an eighth consecutive critic lap** — and this lap is the one
that has to say out loud what that sentence is worth.

**The window's headline: an external dataset was ingested with every discipline this
repository has, and it is the wrong county.** The author sent two 주소정보누리집 downloads;
`scripts/extract_juso_yeongdeok.py` cut what it calls the 영덕 subset, committed it with a
manifest carrying both zip digests, the data dates, the agency, the CRS decision and the
filter string, registered eight counts, and wrote `docs/juso_yeongdeok.md` with a
「What it does not show」 section. Every one of those is the right habit. The filter constant
is `47920`, labelled `# 경상북도 영덕군`, and it selects a different county about 45 km away.

This lap did not need a source to find it. **The repository already stores the answer:**
`regions.lookup('yeongdeok_2025').bbox_wgs84` is `(129.25, 36.30, 129.55, 36.60)`, and every
one of the 239 committed points falls at 128.65–129.15 E / 36.78–37.05 N. The two boxes do
not overlap on either axis.

**That is the root objection, and it is bigger than the bug.** Every gate in this tree checks
that a number matches an artifact. Not one checks that the artifact is of the thing its label
names. Nine laps of sourcing discipline — agency, as-of date, scope, URL, forbidden
phrasings, digests — and the field none of it constrains is **scope**, because scope is prose
a lap typed. Here the number and the document agree perfectly with each other and both are
wrong about the world, and a green test **pins the mistake in place**.

---

## fix-before-next-row

**Two items. Neither needs the author, and neither is the re-cut.**

1. **WFG-075 (F54) — contain it.** Annotate the eight `juso_yeongdeok_*_count` entries in
   `docs/NUMBERS.json` additively (add, never edit; CHARTER §3.2/§3.3) as scope-wrong and not
   to be used; put the correction at the **top** of `docs/juso_yeongdeok.md`; correct the
   2026-09-04 annotations on NH-005 and NH-012, which currently tell the author that 영덕's
   designated 지진옥외대피장소 and 무더위쉼터 are in the repository; leave WFG-073 and
   WFG-074 `blocked` (this lap set them). `tests/test_juso_yeongdeok.py:11` asserts
   `man["sigungu_cd"] == "47920"` — do **not** delete that test; mark it `xfail` with a reason
   naming NH-022, so the record of what was enforced survives.
   **Do not guess the correct 시군구 code.** WFG-066 is the standing rule that an identifier
   not read off a record is not written down, and this lap could not open 행정표준코드 to
   read it. The re-cut is NH-022 and needs the laptop; the raw zips are git-ignored.

2. **WFG-067 (fourth window).** `web/finals.html` still carries `"git":"a562045"` and
   `git cat-file -t a562045` still answers `fatal: Not a valid object name` in a fresh clone.
   One rebuild after a rebase, plus the one-line gate that the stamp must satisfy
   `git cat-file -e`. It is a single character of real work and it has now outlived four
   critic laps on a **☑** readiness line — the line whose whole job is to let a judge verify
   the build.

---

## The findings, ranked

### F54 · **CRITICAL** · the artifact labelled 영덕 is not 영덕, and the suite enforces it

`scripts/extract_juso_yeongdeok.py:32`: `SIGUNGU = "47920"  # 경상북도 영덕군`.

Measured this lap by reading the coordinates out of the eight committed GeoJSON files in
`data/processed/external/juso_yeongdeok/`:

| layer | n | lon range | lat range |
|---|---:|---|---|
| minwon_agencies | 74 | 128.686–129.067 | 36.799–37.051 |
| samul_eqout_point (지진옥외대피장소) | 27 | 128.732–129.064 | 36.817–37.047 |
| samul_coolingcen_point (무더위쉼터) | 99 | 128.665–129.148 | 36.786–37.063 |
| samul_busst_point (버스정류장) | 28 | 128.649–129.102 | 36.785–37.064 |
| samul_firehydr_point (소화전) | 6 | 128.736–129.058 | 36.883–37.015 |
| samul_lifesav_point (인명구조함) | 5 | 128.729–128.954 | 36.788–37.011 |
| samul_eqwav_point (지진해일긴급대피장소) | **0** | — | — |
| samul_emerwat_point (비상급수시설) | 0 | — | — |

`config/default.yaml:83` and `regions.lookup('yeongdeok_2025').bbox_wgs84` give 영덕 as
`(129.25, 36.30, 129.55, 36.60)`. **No point in any layer is inside it, and none is
adjacent:** the easternmost point is 0.10 degrees west of 영덕's western edge and the
southernmost is 0.18 degrees north of its northern edge, roughly 45 km diagonally.

**Two tells inside the artifact itself, both written up as facts about 영덕:**

1. 영덕 is an East Sea coastal county. Not one of the 239 points is east of 129.15 E.
2. `samul_eqwav_point` — 지진해일긴급대피장소, tsunami emergency evacuation sites — returned
   **zero rows**, and `docs/juso_yeongdeok.md:12` records that as a property of 영덕
   (「지진해일대피장소 and 비상급수 have no 영덕 rows」). A coastal county on the East Sea has
   designated tsunami evacuation sites; a landlocked one has none. **That zero was the
   evidence, and it was filed as data.** The centroid (36.915 N, 128.871 E) sits beside
   봉화읍, which ko.wikipedia's 경상북도 article (opened this lap) lists among the inland
   northern counties while naming 영덕 among the 동해안 ones.

**What carries it.** Eight registry keys (`juso_yeongdeok_minwon_agencies_count`,
`…_samul_eqout_point_count`, `…_coolingcen_…`, `…_lifesav_…`, `…_firehydr_…`, `…_busst_…`,
and the two zero-valued ones), every one with `scope: 영덕군 · …` and a `derivation` reading
「count of … with sigungu code 47920 (영덕군)」; `docs/juso_yeongdeok.md` entire; the
2026-09-04 annotations on **NH-005** and **NH-012**, which tell the author that 영덕's
designated sites are now in the repository; and **WFG-073** and **WFG-074**, which would have
put these points into the router as 영덕 refuge candidates and 119 depots. Both are now
`blocked(WFG-075)`.

**What does not carry it, checked rather than assumed.** `README.md`, `web/finals.html`,
`paper/manuscript.md` and `docs/auto/JUDGE_QA.md` print none of these values. **Nothing at
the booth is wrong today.** This is contained, and it stops being contained the moment
WFG-073 or WFG-074 runs.

**And the gate holds it in place.** `tests/test_juso_yeongdeok.py:11`:

    assert man["sigungu_cd"] == "47920"

All **1367** tests pass. `make verify`, `snapshot-verify` and `env-check` pass. The artifact
manifest was rebuilt and the phase-13 baseline deliberately re-frozen, both correctly and
both said so in the commit message. Every mechanism in this repository worked exactly as
designed, on the wrong county.

**Filed as WFG-075** (the containment half, agent-doable) and **NH-022** (the re-cut, which
needs the laptop: `data/raw/juso/` is git-ignored and `extract_juso_yeongdeok.py` returns
early without it).

### F54-root · the objection this lap would put to the loop

*Every gate here checks that a number matches its artifact. None checks that the artifact is
of the thing its label names.*

WFG-049 bound prose figures to a registry. WFG-062 and WFG-071 are about claim sentences and
external figures. All three constrain a **document** against a **number**. F54 is the first
defect in eleven windows where the document and the number agree perfectly and both are
wrong about the world — and the check that would have caught it was already committed here
and consulted by nothing.

**The cheapest test, and it needs no external source:** for every artifact whose name or
registry `scope` carries a region this repository already knows, assert its geometry lies
inside `regions.lookup(<region>).bbox_wgs84` plus a stated, committed buffer. One function,
offline, and it catches this, the next mis-keyed 시군구 code, and any wrong-`.prj` or
wrong-CRS assignment — including the EPSG:5179 inference `docs/juso_yeongdeok.md:26` honestly
records as an inference rather than a reading. **Filed as WFG-076, P0**, with NH-021's
standard attached: publish the catch rate against a mutation set its author did not write.

It is the geometric sibling of WFG-071 (「drive it off the registry; match the value, not the
sentence」). Take them together.

### F55 · P1 · two backlog rows were filed under IDs that were already taken

`3fdb888`'s commit message and `docs/auto/reports/2026-09-04T1318Z-manual.md` both say
「WFG-072 (designated sites as refuge candidates), WFG-073 (agency depots and notification
targets)」. The rows actually in the table are **WFG-073** and **WFG-074**; **WFG-072** is the
English-claim-rule row filed by the 1310Z cloud dev lap inside the same half hour. The table
was renumbered; the commit message and the report were not, so both records now point at a
row that means something else.

This is the **third** measured instance of the ID-collision class recorded in NH-016's
critic #7 note (「an ID is allocated while writing, not while claiming, so the
claim-before-build rule does not cover it」) and the first where the surviving record is
wrong rather than merely expensive. Not worth its own row while WFG-062 is the author's
chosen next job; recorded here so the next lap reading either document is not misled.

### F56 · P0 · WFG-067, fourth window · the integrity panel still names a commit that does not exist

Unchanged and re-checked in this fresh clone: `web/finals.html` carries `"git":"a562045"`;
`git cat-file -t a562045` answers `fatal: Not a valid object name`. The RELIABILITY tab
renders it as the first line of the panel a judge is invited to verify the build with. On the
one `KCF_READINESS.md` line that is ticked for the finals screen. Four critic laps.

### F57 · P0 · WFG-057, sixth window · the Q&A bank still miscounts itself, and it is blocking this routine's step 3

Counted again this lap. `docs/auto/JUDGE_QA.md:17-23` tells the student **33 questions, T0
14, T1 13, T2 6**. The file holds **41 / 15 / 19 / 7**. Critic #9 established that no
question may be added while the header lies, because adding one makes the miscount worse.
That means this routine's judge drill has had nowhere to put its output for a **third**
consecutive lap: the questions it cannot answer from a file become backlog rows instead of
`JUDGE_QA` entries marked 「근거 없음」, which is not what CHARTER §4 asks for. A P0 that
disables a daily check is more expensive than its diff.

### F58 · FYI · the only lap in this window that shipped data had no independent reviewer

Every cloud dev report in the 24-hour window carries a `Reviewed by:` line except
`2026-09-04T0401Z-dev.md`. The three **manual** reports (`1231Z`, `1252Z`, `1318Z`) carry
none, and manual laps are not dev laps, so CHARTER §4 step 5 does not require it. But the
1318Z manual lap is the one that shipped F54, and it is the only lap in this window that
touched data, a script, the registry and the tests at once. `LOOP_CONFIG.json` → `review:
subagent` reaches dev laps only; there is no equivalent for a laptop lap, and a laptop lap is
exactly where the author's own external data enters the repository. Recorded as an
observation, not a rule violation. The structural answer is WFG-076, which would have caught
it with no reviewer at all.

---

## What went right in this window, and it should not be lost under F54

**`paper/figures/F8_routing_map.png` is the best judge-facing graphic this repository has
produced.** Opened and read this lap. Panel (a): SRTM hillshade, P(ignite) at 720 min in
YlOrRd, the P ≥ 0.5 cells at 0 min, the 720-min 0.5 isoline, the reported ignition, and the
walk-network rectangle. Panel (b): the walk network, 50 refuge nodes, all 458 scanned origins
classed **exactly as the committed artifact** (414 safe on both / 42 safe only forecast-aware
/ 2 with no safe route — verified: 414 + 42 + 2 = 458, and `n_refuges` in
`data/processed/rescue_routing.json` is **50**, matching the caption), and three worked
origins with the fire-blind route against the forecast-aware one. Graticule, two scale bars,
boxed legend, and a caption that says the isoline smoothing is display-only.

Two things earn it more than tidiness. The routes are **recomputed at figure time by the
repository's own router** and the recomputed partition equals the committed one, so the
figure is a re-derivation rather than an illustration. And panel (a) **draws the project's
worst limitation instead of describing it**: the predicted hazard core runs well west of the
walk box, which is the 32.6 % coverage caveat made visible to a judge in one glance. It is
also, this lap notes without pleasure, drawn over the correct 영덕 — 129.3–129.5 E with the
coastline on the right — in the same window in which the same repository committed a 영덕
dataset 45 km inland.

**The author's decision channel worked.** Twelve NEEDS_HUMAN entries were closed on
2026-09-04 through the Claude Code session channel (`docs/auto/decisions_seen.json`), and
only **four** entries are now open, two of them FYI. NH-020's finding — twenty-nine reports
into a void — is closed. This lap added exactly one entry, NH-022, because it is the one
thing in F54 that the loop genuinely cannot do.

---

## The judge drill, and why it produced rows instead of questions

Ten hardest questions in `docs/auto/JUDGE_QA.md` re-run against files. The one that fails
today is new and is F54's:

**「이 대피 지점들은 어디서 나온 겁니까?」** — Until this window the honest answer was: OSM
tags, the 공공데이터포털 standard when configured, and a documented synthetic fallback, all in
`docs/data_sources.md`. This window added an answer the student would rather give — 「행정
안전부가 지정한 대피 장소입니다」 — and that answer is currently about another county. The
student must not use it until NH-022 is answered. The old answer is unaffected and still
correct; `F8`'s 50 refuges are the OSM ones.

No new `JUDGE_QA` entry was written, for the reason critic #9 and critic #10 both gave and
which F57 now makes concrete: the file's header is wrong about its own contents by 8
questions, and adding a ninth is not a contribution. The drill's output went to WFG-075 and
WFG-076 instead.

---

## Scores

Track B **82 → 81** (데이터 19 → 17, 제출 자료 17 → 18). Track A **73 → 73**, every row held.
Evidence per row in `docs/auto/SCORECARD.md`, appended at `83f49bc`.

Track A's note this window carries a correction the table owed the loop: 구현 및 유용성 has
held at 14 for twelve windows and previous critics called it slippage. It is not. NH-021
closed on 2026-09-04 with the author choosing 「Do WFG-062 now; booth rows resume after」, so
WFG-003, WFG-037 and WFG-036 are behind a gate row **by the author's own decision**, taken
against this exact trade-off written out for them. The consequence is still scored; the
adjective is withdrawn.
