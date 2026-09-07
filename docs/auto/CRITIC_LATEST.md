# CRITIC_LATEST — critic #34, 2026-09-07T1100Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3), and clears every
`fix-before-next-row` item below first. Reviewed head: `2720840`. Window: `b2bdaf0..2720840`, the
24 h to 2026-09-07T11:00Z, 59 commits.*

✅ **The baseline is GREEN. Run it on the DEFAULT clone before you deepen anything.** `gates.py
--mode full` exits **0** here at this head with `is-shallow-repository` = `true` and `rev-list --count
HEAD` = **50**. Critic #33's red is cleared. ⚠ If you ever see `tests/test_finals_screen.py` red on a
staleness message, that is **not** CHARTER §4 step 2's 「red baseline, do not build」 — the remedy is
`make finals` on the commit you are pushing and it takes a minute. The rule that should say so is
**NH-043** and it is not written yet, which is the point of that entry.

**Critic #33's two falsifiable tests, answered first, because both were about the dev lap.**

1. **「If a lap runs `make finals`, pushes, and files nothing about recurrence, WFG-119 has been reset
   and not closed.」** **It was not reset.** The 09:18Z lap ran `make finals` **and** built a
   depth-independent carrier: `test_the_screen_is_rebuilt_before_its_stamp_ages_out_of_this_clone`
   fires at 30 commits behind `HEAD`, a question answerable at any clone depth, so sandbox and CI
   reach the same verdict for the same reason. Its grader pins the policy with two hard-coded
   distances (29, 31) rather than deriving them from the constant — the correct repair of a first
   version that was arithmetically incapable of failing, which the lap's **own reviewer** caught and
   the lap conceded rather than argued. Good work, and I say so before I take it apart.
2. **「If WFG-146 is fixed in `docs/related_work.md` and not in `RELATED_WORK_PANEL.md`, the printed
   page keeps the wrong date.」** **Not triggered — it was fixed in neither.** Unchanged at this head,
   third critic lap. It is this lap's one item, below.

## What is green, verified rather than read, all at `2720840`

- **`gates.py --mode full` ALL GREEN, exit 0**, on the routine's **default** clone before any
  deepening: `is-shallow-repository` = `true`, `rev-list --count HEAD` = **50**, `1650 passed,
  62 skipped, 2 xfailed`, pytest 260.6 s. `verify`, `snapshot-verify`, `env-check` PASS;
  `baseline-verify` WARN is the documented CHARTER §3d state.
- **The finals screen is current.** `web/finals.html` names `7308b06`, **6** commits behind `HEAD`,
  inside the new limit of 30, and `7308b06` is on `origin/auto/dev`.
- `gates.py --assert-reported --base b2bdaf0` over the whole 59-commit window exits **0**: 59
  substantive paths travelling with `docs/auto/reports/2026-09-07T1002Z-dev.md`.
- GitHub Actions, through the MCP (`curl` is 403 here, WFG-119): `auto-gates` runs **181 to 205** on
  `auto/dev` are **22 `success`, 3 `cancelled`, no `failure`**; run **205** at this head is `success`.
  **No CHARTER §4b finding.**
- Every **dev** report in the window carries `Reviewed by:`. The research report does not (WFG-147).
- **The WFG-138 caveat propagation is COMPLETE, and this is the good news of the window.** Every
  judge-facing surface that states 42 or 91 carries both binding caveats (fire-blind opponent; upper
  bound for a noiseless forecast): `README.md`, `web/finals.html`, `docs/auto/JUDGE_QA.md`,
  `docs/auto/DEMO_SCRIPT_5MIN.md`, `paper/manuscript.md`. The one apparent miss in
  `release/kcf-finals-2026/README_KO.md` is the directory stamp `20260801T163042Z`, not the claim — I
  opened the line rather than trusting the grep.
- **KCF_READINESS 6 of 11**, unchanged, with R9 and R7 both ticked inside this window, so the
  "zero for two consecutive critic laps" direction finding does not fire.
- No author reply on either channel. The Gmail search returns threads that are every one a single
  message this loop sent; PR #31 has no comments. `decisions_seen.json` unchanged.

## fix-before-next-row (exactly one, CHARTER §14b)

**WFG-146 — the 사이언스타임즈 date is wrong on three lines, one of which is printed on the booth
kit and is on the USB stick. Minutes, judge-facing, and re-verified from the source this lap.**

Eligible under §14b as a fix of **minutes** on a **printable**, which §14b names as judge-facing.

Measured at `2720840`, not inherited from critic #33. I fetched
<https://www.sciencetimes.co.kr/nscvrg/view/menu/249?searchCategory=221&nscvrgSn=261448> in this
sandbox and parsed it:

- The page carries `2026-02-13` **twice** — its byline reads `연합뉴스 2026-02-13` and its
  copyright line reads `저작권자 2026-02-13 ⓒ ScienceTimes`.
- It carries **no** `2026-02-12` as a date. The three `2026/02/12` strings on it are 연합뉴스 image
  CDN paths of the form
  `https://img8.yna.co.kr/etc/inner/KR/2026/02/12/AKR20260212072300063_02_i_P4.jpg` — the **wire
  original's** date and id, which 사이언스타임즈 republished a day later.
- So the repository pairs one publisher with another's date. CHARTER §3 rule 5b makes the as-of date
  load-bearing, and 출처 명기 is a named criterion on the 제출 자료 row of **both** rubric tables.
- I also checked the substance the citation carries, and it is characterised correctly: 「지형 분석
  정밀도를 5ｍ 수준까지 높인다」 and 「산불확산예측 정밀도를 기존 대비 약 30% 향상」 are agency plan
  statements in the future tense. Nothing else on this citation needs to change.

**Where it is live:** `docs/related_work.md:104`, `docs/related_work.md:187`, and
`docs/auto/finals/RELATED_WORK_PANEL.md:43` — the last being 3 of the 36 printed pages of kit
`20260907T0953Z`.

**Done when:** all three read `2026-02-13`, **and the kit is rebuilt in the same lap** (WFG-152), so
the printed page matches the tree and `tests/test_printables.py` stays green.

⚠ **Take it together with WFG-144 (below), which needs the same single `make printables`.** One kit
rebuild pays for both.

## The other findings, filed and not carried

- **WFG-144 is this lap's one row move: P1 → P0, position 1 of the table.** §14b: a judge-facing
  finding larger than minutes becomes a P0 row at position 1 and is **never a preemption**, so the
  top of the table is displaced by WFG-146's minutes and by nothing else. Re-measured at this head:
  the only `산림청` hits in `docs/auto/JUDGE_QA.md` are the burned-area lines at `:399` and `:1003`,
  and there is no card for 「산림청·경기도가 이미 산불확산예측을 하고 있는데 무엇이 다릅니까?」 while
  the kit prints three pages that invite it. **Seventh consecutive critic lap measuring this, and
  the sixth to decline to promote it because the one allowed item went elsewhere.** That is the
  pattern NH-038 is about; this lap ends it. ⚠ I may not write the card myself — JUDGE_QA is a
  printables `SOURCES` document and a one-line edit turns the freshness gate red, so only a lap that
  rebuilds the kit in the same lap may touch it (WFG-152).
- **WFG-110 is the sole remaining blocker of R1 and is what holds Track A 구현 및 유용성 at 19.**
  DIRECTION position 2. Critic #33 said a stale build stamp was what stopped a 20 on that row; that
  is cleared, and the point it buys is spent on critic #32's older blocker, which is unchanged: 6 of
  the 28 registry keys `scripts/finals.template.html` references are in no committed mapping table.
  Nine infra rows sit behind R1 under §14b.
- **WFG-139 unrepaired, seventh consecutive measurement, and this one is on my own clock rather than
  a pass/skip delta.** `data/raw/` held only `.gitkeep` and `README.md` (mtime 2026-09-04T16:57:27Z)
  at container start; bootstrap finished 10:59:40Z; `pytest-full` ran 260.6 s; afterwards
  `data/raw/dem/srtm/N36E129.hgt` (**25,934,402 B**) and its `.gz` carry mtime **11:02:33Z**. The
  suite downloaded 25.9 MB over the network inside a gate run. My counts are therefore neither cleanly
  cold nor warm and I say so: `1650 / 62` on a run that fetched the DEM partway through.
- **WFG-160 (new, P1).** The staleness threshold's stated frequency is contradicted by this branch's
  own rate. The test comment argues 30 commits ≈ 「roughly 18 hours, or six dev laps」 from
  「~40-55 commits/day」. Measured on an unshallowed clone (540 commits): **194** commits in 72 h =
  **64.7/day**; per day **94**, **64**, **52**, and **29** in 11 h today. No sprint day is inside the
  quoted band. At 64.7/day a 30-commit budget is **11.1 hours**, about **3.7** dev laps. Same class as
  the number the lap's reviewer blocked, one paragraph over. Held behind R1/R3/R8 as hygiene.
- **NH-043 + WFG-161 (new).** The recurrence is legible but not routed: when the new gate fires — on
  the measured rate, about every 11 hours — CHARTER §4 step 2 still tells the lap to stop, and the
  only override is a `CRITIC_LATEST.md` line that expires with every critic report. Escalated with
  four options; my recommendation is to fold `make finals` into the push path **and** write the
  exception down.

## The root objection, and it is on this loop's own steering page

**The page that tells every lap where the project is going asserted the one thing the repository
spent this week retracting.** `docs/auto/DIRECTION.md`'s thesis read 「A forecast of where the fire
will be, **not where it is**, changes which walking route and which rescue order are safe, and the
repository **proves that**」. In the same window `README.md` gained 「it does not separate knowing
where the fire will be from knowing where it is」 and 「42 is an upper bound」, and `JUDGE_QA.md` Q36
tells the student to say 「저희 모델이 실제로 사는 값은 아직 재지 않았습니다」 before a judge digs.
**The cheapest test was one grep and it was run:** the caveat reached every judge-facing surface and
missed only DIRECTION — the surface every lap reads first. That is WFG-138's propagation shape landing
on the loop's steering rather than on its output. **Corrected this lap**, since the critic owns that
page (CHARTER §14), and added to its *What not to do* list.

## Falsifiable tests for critic #35

1. If a lap fixes WFG-146 in `docs/related_work.md` and not in `docs/auto/finals/RELATED_WORK_PANEL.md`,
   the printed page keeps the wrong date and the propagation shape has completed a second lap.
2. If the WFG-119 staleness gate goes red in a dev lap's baseline and that lap parks under CHARTER §4
   step 2 instead of running `make finals`, then the recurrence was made legible without being routed,
   and NH-043 is the reason.
