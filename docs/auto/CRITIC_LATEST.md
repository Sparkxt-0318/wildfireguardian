# CRITIC_LATEST — critic #17, 2026-09-05

Window `1049db4..26e200d` on `auto/dev` (6 commits; 25 files, 1,542 insertions).
Written by the `wfg-autoloop-critic` routine. The next dev lap clears every
`fix-before-next-row` item here before claiming a row.

## fix-before-next-row

**One item, WFG-103: the core act of the booth script says the comparison is against a map that
sees the fire now. It is against a map that does not see the fire at all.**

`docs/auto/DEMO_SCRIPT_5MIN.md:108-109`, inside 3막, the segment the same document calls
「이 작품의 전부」, is spoken aloud to five judges:

> **STATIC VIEW.** 거리 기준 직행 경로입니다. **지금 이 순간만 보는 지도라면 이 길을 권했을 겁니다.**

The arm that route comes from is not a map that sees this moment. It is fire-blind, and this
repository says so in its own source and its own method document:

- `src/wildfireguardian/routing/evacuation.py:270` — `"""Fire-blind shortest path to the
  nearest shelter, then scored against the hazard."""`
- `docs/real_roads_real_hazard.md:50` — 「**naive** — the fire-blind shortest walk to the
  nearest refuge (the status quo)」

The difference is not cosmetic and it runs in the project's favour. A map that sees the fire
where it is now already refuses the cells that are burning now, so some share of the
**91 origins of 368 (24.73 %)** the student attributes to knowing where the fire *will* be is
bought by knowing where it *is*. The spoken sentence hands the weaker baseline the stronger
description, and the number in the next sentence is read against it.

**Why this is the item.** It is one sentence, on the highest-value 60 seconds of the booth, on
the document R4 is ticked for, and it is a claim-accuracy defect of exactly the class this
repository gates elsewhere. Every fact needed to fix it is already committed. The honest
sentence is that the comparison is against a route that does not look at the fire at all, which
is what a walker without this tool has. **Do not enlarge the row into the arm study** — that is
WFG-104 and NH-027, below, and it is not the dev lap's to decide.

## Findings, ranked

**F1 · WFG-103 · judge-facing · the 3막 baseline sentence.** Above. One sentence.

**F2 · WFG-104 · judge-facing · the strongest objection to the headline has no card in the bank.**
`docs/auto/JUDGE_QA.md` holds 41 questions and none of them is 「불을 전혀 모르는 경로와 비교하신
겁니다. 지금 불이 있는 자리만 피하는 경로와 비교하면 어떻게 됩니까?」 I searched the bank for
naive / perimeter / buffer / 기준선 / 베이스라인 / 대조군 and there is no card. The repository
knows the question is coming: `docs/auto/BACKLOG.md` WFG-033 names the arm that answers it —
「(b) static current perimeter (slice 0, p ≥ p_cut) + fixed buffer 0.5/1/2 km」 — with a
`done when` that says 「says plainly whether the learned field beats "current perimeter +
buffer" on routing decisions」. **WFG-033 is P2, which by CHARTER §11 means after the finals.**
So the one measurement that decides whether the headline is a contribution or an artefact of a
weak baseline is scheduled after the event the headline is presented at. That may well be the
right call for a twelve-day sprint — it is not a defect in the science — but a T0 card must say
it out loud, the way 4막 already says 「저희가 진 결과도 화면에 있습니다」. The scope question is
**NH-027**.

**F3 · WFG-105 · judge-facing · 5.61 syllables per second is a floor, not a rate, and the
external number nobody had looked up says so.** WFG-100 is real work and it closed the defect it
was filed for: `docs/demo_script_pace.md` counts 1,684 spoken syllables, allocates 300 s by
largest remainder, and the six segments now run 5.55–5.66 syl/s where they ran 4.51–7.29. I
re-derived every cell of its table and they hold (161+246+280+338+331+328 = 1,684;
29+44+50+60+59+58 = 300; 338/60 = 5.63). Two things the page does not say:

1. **5.61 syl/s is charged against all 300 s as if all 300 s were speech.** §2 of the same
   script guarantees five judge interruptions *inside* those 300 s, and the pace page itself
   says 「a real delivery is longer than its text」. So 5.61 is the rate the student must beat
   before a single breath, pause or interruption — a floor, and the page presents it as the
   rate.
2. **The comparison is one search away and CHARTER §3.5b permits the search.** I ran it. The
   phonetics literature separates *articulation rate* (physical pauses **excluded**) from
   *speaking rate* (pauses **included**) — Yun, 「Effects of gender, age, and individual speakers
   on articulation rate in Seoul Korean spontaneous speech」, *Phonetics and Speech Sciences*
   10(4), https://www.eksss.org/archive/view_article?pid=pss-10-4-19, which reports means around
   **5.2–6.4 syl/s** for short units and calculates them 「as the duration between pauses」; the
   same distinction is stated in 「Speech rate in Korean across region, gender and generation」,
   https://koreascience.or.kr/article/JAKO201713647763102.page (412 speakers). **5.61 is a
   speaking rate sitting inside the published band for articulation rate.** That is not proof
   the script overruns — no lap has held a stopwatch, and R12 / NH-014 is still the answer — but
   it is the first external number anyone has put beside 5.61, and it points one way.

   (b) The same row carries a smaller thing found by `factchk`: `docs/auto/RUBRIC.md:10-11`
   quotes the 심사개요 as 「각 5분 **내외**」 and 「5분을 넘지 않는 것을 **권장**」.
   `docs/auto/DEMO_SCRIPT_5MIN.md:272` restates that as 「300초는 심사 운영요강이 **정한** 총량」
   and `docs/demo_script_pace.md:120` as 「300 s is **fixed by** the 운영요강」 — while line 12 of
   that same page gets it right (「recommends and may enforce」). One page, two readings of one
   quoted rule.

**F4 · loop hygiene, P1, parked behind the readiness lines by CHARTER §14b · this routine's own
count was unreproducible.** `docs/demo_script_pace.md:92-108` is the best paragraph the loop
wrote this window and it is about me: critic #16's per-segment syllable counts
(161/235/279/318/319/318 = 1,630) are reproduced by **no** convention the dev lap implemented,
and its nearest variant agrees on the total by cancellation while differing per segment. Critic
#16 published a table from a rule it never wrote down. The dev lap was right to refuse to
paper over it, right to keep both sets separate, and right to say the defect survives the
disagreement — every convention finds a spread of 1.62–1.73× and every one puts 마무리 fastest
and last. **The rule for this routine from now on: a critic table of counted things ships its
counting rule or it ships no table.** Filed as part of WFG-105's notes rather than as its own
row, because §14b holds loop hygiene behind R1, R3, R4, R7, R8, R9.

**F5 · not a finding, recorded so the next lap does not re-derive it.** Four rows are `P0` and
`todo` and sit below roughly forty `P1` rows in the table — WFG-051 (line 70), WFG-076 (90),
WFG-082 (94), WFG-078 (95). All four are `infra`. CHARTER §3b forbids a P0 below a non-P0 and
§14b holds loop-hygiene rows behind the readiness lines, so these four are P0 by their own
filing and P1 by the charter's rule, and the table records the contradiction rather than either
answer. One reorder per lap means I cannot fix it here and it is not judge-facing. It is a
question for the author, appended to **NH-027** rather than opened as its own entry.

## Verification of the loop's claims

- `gates.py --mode full` **ALL GREEN at `26e200d`** in this fresh cloud sandbox: `1484 passed,
  62 skipped` in 303.7 s, **COLD** (the six SRTM-gated tests skip, WFG-039), against critic
  #16's cold `1464 / 62` at `43710f7`: **+20 passed, skips unchanged**, like for like, tenth
  comparable window. `verify`, `snapshot-verify`, `env-check` PASS; `baseline-verify` WARN,
  expected off-laptop, `hard: false`, seventeenth window and still not a finding.
- **GitHub's own runs (CHARTER §4b).** `auto-gates` on `auto/dev` in the window: run **117
  (`26e200d`, this head) `success`**, 116 and 115 `cancelled` by the next push, 114 and 113
  `success`. **No red run stands behind a green report this window.** The last `failure` is run
  110 (`d2418c2`, 03:20Z), which is the episode already filed as NH-026 and WFG-102 and is
  outside this window.
- **Every dev report of the last 24 h records `Reviewed by:`** — 1555Z, 1609Z (`self`, and it
  says why), 1851Z, 2154Z, 0059Z, 0404Z, 0702Z. Seven of seven. `--assert-head` and
  `--assert-reported` both exit 0 at `26e200d`.
- **`make finals-bundle` re-run by me, not read:** exit 0, `OK — release/kcf-finals-2026/
  rebuilt byte-identically, 16 files`.
- **Author decisions applied this lap: none.** The Gmail search
  `from:siyeong0318@gmail.com subject:"WildfireGuardian autoloop" newer_than:14d` returns only
  the loop's own outbound reports, every thread one message long, no reply; PR #31 carries no
  comment in `NH-###:` form. `docs/auto/decisions_seen.json` is unchanged.

## Root objection (`hate`), on the headline narrative

**「예측이 경로를 바꾼다」 is demonstrated against a walker who cannot see the fire, and the
repository has scheduled the only experiment that would test it against a walker who can for
after the competition.** The cheapest test is not the arm study: it is one card in the Q&A bank
that states the baseline plainly and names WFG-033 as the unrun arm. A judge who hears
「불을 전혀 보지 않는 경로와 비교했고, 지금 불만 피하는 경로와의 비교는 아직 돌리지 않았습니다」
scores 과학적 사고 up. A judge who has to extract it scores it down. That is F1 and F2, and it
is the whole of what I would change before the next row.

## Readiness and scores

**KCF readiness: 4 of 11 (R2, R4, R5, R6), no line moved this window.** R4 was ticked inside the
last 24 h (critic #15, `43710f7`, 0200Z), so the 「zero for two consecutive critic laps」
direction finding does **not** fire. R1 could not move: nothing has touched `web/` since
`deeb147` (2026-09-04T15:59Z) and the screen's content is unchanged since `dc63a06`. R3's booth
half, R7 and R9 are held by the same two absent artifacts as yesterday —
`docs/auto/finals/BOOTH_SETUP.md` (WFG-037) and any printable under `docs/auto/finals/`
(WFG-007), both checked on disk at this head.

**Track B 83 → 84** (제출 자료 18 → 19). **Track A 77 → 78** (제출 자료 14 → 15). Both moves are
the same one: WFG-100 closed the defect that explicitly capped both rows last lap, and it closed
it better than the row asked for — the before state is committed as an artifact rather than
asserted, and the failure to reconcile with critic #16 is published instead of smoothed. Neither
row reaches the next step because of F1: the document those rows are scored on mis-describes the
baseline of its own core act. 연구 목적, 설계와 방법론, 데이터, 창의성 and 구현 및 유용성 all
held — no model, split, metric, arm or coupling moved, and nothing touched `web/`, the
printables or the bundle.
