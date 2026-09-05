# CRITIC_LATEST — critic #19, 2026-09-05

Window `e2628f3..92bfc4f` on `auto/dev` (5 commits; 1,141 authored insertions,
images and the generated board excluded). Written by the `wfg-autoloop-critic`
routine.

## fix-before-next-row

**WFG-109 — the judged screen and the file it is built from disagree, and the file wins.**

`scripts/finals.template.html:1378` (KO) and `:1381` (EN) still carry the STATIC VIEW sentence
WFG-103 withdrew: 「지도가 지금 이 순간만 본다면, 이 경로를 권했을 것입니다」 and 「A map that only
sees the present would recommend it」. The built `web/finals.html:1378`/`:1381` carry the correction
(「화재를 전혀 보지 않는 지도가 그리는 경로입니다」 / 「This is the route a fire-blind map draws」).
I diffed the two files at this head; the third and fourth branches of the same expression already
agree, so it is exactly these two lines.

Nothing is wrong on the judged screen today. The next `make finals` puts a claim this repository has
established is false back in front of five judges, no gate reads the template, and the only thing
standing between them is a paragraph of `docs/auto/finals/BOOTH_SETUP.md` §3.4 asking a student not to
run a command. **Done when** the template says what the built screen says, `make finals` is run so the
two agree, the manifest is re-derived, and a test compares the STATIC VIEW captions in both files.

**Why an item at all, one lap after critic #18 proved the empty block works.** Because #18's test
resolved and its rule is now standing (see `DIRECTION.md`), and because readiness did not stall for
want of direction this window: it stalled on paper and on an email. This item is judge-facing under
CHARTER §14b, it is minutes, and it is the first critic item in nine that is not another sentence of
`docs/auto/DEMO_SCRIPT_5MIN.md`.

## Findings, ranked

**F1 · WFG-109 · judge-facing · P0 · above.** Filed by the WFG-037 lap and verified here on disk rather
than read from its report.

**F2 · WFG-106 · corrected before a lap writes a card on it · the row's own opening names the wrong
objection.** Critic #18 filed WFG-106 as 「the number that answers the strongest objection outright」.
It is not, and the difference is the kind a judge finds. There are two objections to the headline and
they are not the same question:

- **(i) dilution** — 「91 of 368 includes 265 walkers who were never in danger」;
- **(ii) the opponent** — 「you compared against a router that does not look at the fire at all」, which
  is critic #17's root objection, WFG-104's card, and NH-027's experiment.

`mr_uiseong_fa_rescue_rate` answers (i). It cannot answer (ii), because its denominator is *defined by*
the arm in dispute: the derivation string reads 「of the origins whose **FIRE-BLIND** route is unsafe」.
So the conditional rate inherits the same opponent, and a card offering it as the answer to (ii) would
be a stronger overclaim than the sentence WFG-103 withdrew a day ago. The row is still worth doing and
its numbers are still absent from every judge-facing file (I re-drilled: `88.3`, `27.99`, `103 / 368`,
`23.1` and `95.5` appear zero times in `JUDGE_QA.md`, `DEMO_SCRIPT_5MIN.md`, `paper/manuscript.md` and
`docs/finals_screen_v2.md`). Row updated, not duplicated.

⚠ And its caveat is wrong on two keys, not one. I read all three entries in `docs/NUMBERS.json`:
`mr_yeongdeok_fa_rescue_rate`, `mr_uiseong_fa_rescue_rate` and `mr_uljin_fa_rescue_rate` carry a
**byte-identical** caveat reading 「Conditional rate on a SMALL denominator (13-20 origins)」, while
`docs/multi_region.md:431-433` gives the denominators as 44 / 458, 103 / 368 and 13 / 393. True of one,
false of two.

**F3 · WFG-110 · judge-facing · P0 · R1 has been ☐ for nineteen critic laps on a condition nobody had
sized, and it is six table rows wide.** Critic #18 wrote 「no such table exists」. Too strong, and the
correction is the finding: `docs/auto/DEMO_SCRIPT_5MIN.md` §3 **is** a mapping table, but it runs
script → key, and R1 asks screen → key, which is the direction that answers a judge pointing at the
screen. Measured here using §3's own criterion for 화면 (does `scripts/finals.template.html` reference
the key, not does the built page contain it): the template references **28** registry keys, §3 names
**22**, and **six** are in no committed mapping table — `objective_canonical_longest_walk_saving_min`,
`oof_average_precision`, `rescue_dispatch_count`, `responder_exposure_shortest_path_mean`,
`responder_exposure_survival_aware_mean`, `slope_canonical_fa_routes_changed_60m`.

**F4 · the direction rule fires for the fourth time and is measuring the wrong thing.** Readiness is
4 of 11 and no line has moved since critic #16. But this window the loop built exactly the artifact the
last three critics named. The lines did not move because R7 and R9 both wait on **the printables**
(WFG-007, P1, never claimed by any lap) and R3 waits on **the author** (NH-029). The queue is no longer
what holds the checklist, and `DIRECTION.md` now says so with a falsifiable test for critic #20: if
WFG-109 closes and the printables still do not exist, WFG-007's **priority** is the defect, not its
position, and it should be raised to P0.

**F5 · the best thing this window produced, and the lap did not claim credit for it: NH-029.** Writing
the recipe forced someone to actually run `make all-checks`, the command R3 has named for nineteen laps.
It fails, and only two of its six differences are the sandbox. `registry_entries: 320 -> 326` and three
tracked `data/processed/demo_script_pace/pace_*.json` files are in every clone, the author's included.
I ran `make baseline-verify` here rather than quoting the lap and got the same six lines. **Eighteen
critic laps, mine among them, wrote 「WARN, expected off-laptop, `hard: false`」 and read past four
differences that are not off-laptop at all.** That is a finding about this routine as much as about the
tree, and it is why F4 is worded as it is.

**F6 · WFG-111 · P1 · R5 promises that every T0 answer cites a file, and nothing checks the file is
there.** `tests/test_judge_qa_bank.py` gates phrasing and tiers, not paths. I extracted all 75
path-shaped citations from `docs/auto/JUDGE_QA.md` and resolved each from the repository root: three do
not resolve, all bare names whose full path appears elsewhere in the same file (`check_forbidden.py`,
`check_number_collisions.py` at `:751-752`; `delivery/sms.py` at `:672`). Nothing is wrong today and no
answer is unsupported. What is missing is the gate, and the failure it would catch between now and 10-24
is a rename leaving a T0 answer pointing at nothing, with the bank green.

**F7 · checked and NOT findings, recorded so no later lap re-derives them.**
(a) `BOOTH_SETUP.md`'s two code citations resolve exactly: `web/finals.html:2154` is
`lang === 'ko' ? 'EN' : 'KO'` and `:2145` is the `state.view === 'live'` guard on keys 1-4. The §6 key
table matches the handler, including that `→`/`←` act only while `GUIDED.active()`.
(b) §7.2's 「한국어 글꼴은 꾸러미 안에 있습니다」 is true: `IBMPlexSansKR-{Regular,SemiBold}.woff2` and
`Pretendard-arrow.subset.woff2` are three of the bundle's seventeen files.
(c) `make finals-bundle` exits 0 (`byte-identically, 17 files`) and `check_bundle_copy.py` agrees on the
built folder. WFG-108 stays open and its booth risk is mitigated by §2, not fixed.
(d) The window's one change to `DEMO_SCRIPT_5MIN.md` is §0's language-button correction and it is right.
(e) The `.gitignore`, `Makefile` and `build_finals_bundle.py` changes are all comments, one payload entry
and one ignore line; the withdrawn docstring sentence is struck **in writing** with the measurement that
falsified it, which is this repository at its best.

**F8 · loop hygiene, clean, and it takes one line.** `auto-gates` runs 111 to 130 on `auto/dev`: no
`failure` anywhere in the window; 130 at this head is `success`; 125, 116 and 115 were `cancelled` by a
superseding push. Fifteen of fifteen pushes pass `--assert-reported`. Every dev, paper and manual report
in the window carries `Reviewed by:`. `gates.py --mode full` exits 0 here at `92bfc4f`
(`1506 passed, 62 skipped`, 197.4 s, cold; +22 like for like over critic #17's cold run).

## Root objection (hate), unchanged and now sharper

**The headline credits the forecast with what merely seeing the present fire would have bought.** Every
comparison the project ships is against `naive`, which is fire-blind. Critic #18's proposed answer does
not close it, for the reason in F2: the conditional rate is conditioned on that same arm. The cheapest
test is still the one the paper routine's reviewer wrote into `paper/GAPS.md` G7 — slice-0 hazard mask as
a node filter, the existing `naive_route`, only the origins that enter the hazard, every input already
committed — about one lap and no new data. **It is the author's call (NH-027), and it has been open since
09-05 with four options.**

## Scorecard

B 84 unchanged (16 / 15 / 19 / 15 / 19). A 78 to **79**, on 구현 및 유용성 17 to 18, the first row to move
in three laps. Evidence per row in `docs/auto/SCORECARD.md`.
