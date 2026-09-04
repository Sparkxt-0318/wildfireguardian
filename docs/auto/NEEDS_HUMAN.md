# Needs a human — the loop's escalation ledger

The autonomous loop appends here whenever it cannot or must not decide alone. Each
entry has a severity and a status; `scripts/auto/report.py` lists every `open` entry
in every report, so nothing here is silent. The human closes an entry by changing
`open` to `closed` (and, ideally, adding one line on what was decided).

Severities:
- **BLOCKER** — the loop cannot continue this thread until you act.
- **DECISION** — the loop continues on other threads; this needs your choice.
- **FYI** — no action required; recorded so the report carries it once.

Header format (machine-read): `## NH-### · SEVERITY · open|closed · short title`

**How to decide (author):** reply to any report email with one line per item,
`NH-###: <your decision>`; the next lap records it here with the Gmail message id and
date (`scripts/auto/decisions.py`), acts on it, and confirms in its report. Entries
that need a choice carry an `**Options:** A) … B) …` line; a letter is enough.

---

## NH-001 · DECISION · open · Email delivery needs three repository secrets

**What:** Reports are committed under `docs/auto/reports/` on every lap. To also
receive them at siyeong0318@gmail.com, add repository secrets on GitHub
(Settings → Secrets and variables → Actions → New repository secret):
`SMTP_USERNAME` (the sending Gmail address), `SMTP_PASSWORD` (a Gmail *App
Password*, created at Google Account → Security → 2-Step Verification → App
passwords; never the account password), `REPORT_TO` (`siyeong0318@gmail.com`).
**Why it needs you:** secrets are credentials; the agent must not create or enter
them. **Until then:** reports are visible on GitHub and on the routine's page at
https://claude.ai/code/routines, and the cloud routine sends email itself whenever a
Gmail connector is attached to it on claude.ai.

## NH-002 · DECISION · open · Optional: `@claude` on GitHub issues and PRs

**What:** `.github/workflows/claude.yml` lets you steer the loop from your phone by
commenting `@claude do X` on any issue or PR. It needs the `ANTHROPIC_API_KEY`
repository secret and the Claude GitHub App installed on the repository. Skip if
the cloud routines are enough.

## NH-003 · FYI · open · `Main` is behind the working line by design

**What:** Sessions 18–22 (through 2026-09-02) lived only on the local branch
`ordering-boundary`; it is now pushed and `auto/dev` continues from it. The loop
never pushes to `Main` (docs/HANDOFF_ROUND3.md §5.1). Merge `auto/dev` → `Main`
whenever you want the stable line to catch up; the open pull request is the place
to do it in one click.

## NH-004 · FYI · open · The sandbox has no API keys, so the loop works from committed snapshots

**What:** FIRMS, OpenTopography, CDS, Twilio and Gmail keys live only in the
git-ignored `.env` on your laptop. Every experiment the loop runs uses the
committed snapshots (`data/snapshots/`, `data/processed/`), which is also what a
judge can reproduce. Any item needing fresh acquisition is logged here as a
DECISION when it comes up, with the exact command for you to run locally.

## NH-005 · DECISION · open · Building footprints for Yeongdeok (Session 21 blocker)

**What:** `docs/BLOCKERS.md` (Session 8/22): 도로명주소 건물 데이터 requires a
logged-in portal download, so every household count is provisional on the 124
OSM buildings. If you can download the Yeongdeok 건물 shapefile from
https://business.juso.go.kr (도로명주소 전자지도 → 건물) and place it under
`data/raw/juso_buildings/`, the loop can run the real-footprint replacement it
already scripted. The loop will first check whether an open global dataset covers
the area (see backlog WFG-013) so this may close itself.

**Options:** A) I will download the 도로명주소 건물 layer into data/raw/juso_buildings/ by <date>  B) skip; provisional OSM counts stand for the finals


## NH-006 · DECISION · closed · Confirm the finals date: 10.18 (your notice) vs 10.24 (June schedule post)

**Decided 2026-09-03 by the author: the finals are 2026-10-24.** Freeze moved to
2026-10-16; STATE.json, CHARTER §1, LOOP_CONFIG and the backlog header now say so.

**What (the question as it stood on 2026-09-03; a record, superseded by the
decision above — every 10.18 and 10-10 below is the retired reading, kept
because §3.7 annotates rather than deletes):** The finals notice you supplied
says booth setup is on the day itself,
**10.18**, with judging from 10:30 and close at 18:00. The research sweep found a
KCF "전체 일정 공지" post dated 2026-06-24 (kcf.or.kr/84, idx 171991931) that lists
the finals as **10.24 (Sat), 김대중컨벤션센터**, results 10.30 14:00. The charter,
backlog priorities and the 10-10 freeze are set against 10.18; if the fair moved
to 10.24 the freeze can slide to 10-16. Reply with the confirmed date (or
close this entry with the date) and the loop will re-plan. Nothing else depends
on it.

## NH-007 · DECISION · closed · Two dev laps ran at once and duplicated a row

**What:** On 2026-09-03 two `wfg-autoloop-dev` sessions overlapped almost
entirely (`session_01Xi39Zu…` reported at 05:14Z; this one bootstrapped at
05:04Z and reported at 05:34Z).
Both fetched `auto/dev` at `017c9ec`, both claimed WFG-001, and both fixed the
same five tests. The second discarded its duplicate (preserved at
`auto/lap-b1989d5-superseded`) and salvaged the one change that was additive,
but roughly a lap's worth of sandbox time went into work that already existed.

**Why it needs you:** the charter says "if two laps overlap, the later one takes
the next row" (§4.3), and that rule cannot work as written — a lap marks its row
`in-progress` only in a commit it pushes at the END, so a concurrent lap sees a
`todo` row for the whole of its run. The loop cannot fix the schedule itself.
Either (a) confirm one dev routine on a 6-hour cadence and cancel any duplicate
on https://claude.ai/code/routines, or (b) keep two and say so, in which case the
next infra row should add a real claim mechanism (a lightweight lock pushed to
`auto/dev` before the build, not after).

**Until then:** the loop re-fetches `origin/auto/dev` immediately before
claiming a row and again before its first commit (MEMO 2026-09-03), which
narrows the window but does not close it.

**Closed 2026-09-03 by the kickoff session.** Cause: the kickoff session
triggered a manual run of `wfg-autoloop-dev` while the first run was still
alive (its worker had resumed on a background-task notification). Two loop-side
fixes, no author action needed: (1) the dev routine now pushes its
`in-progress(<stamp>)` marker to `auto/dev` the moment it picks a row, before
building, so a concurrent lap sees the claim (CHARTER §4 step 3, routine
prompt updated); (2) the kickoff session will not trigger manual runs while a
run is active. The superseded branch `auto/lap-b1989d5-superseded` stays as the
negative corpus.

## NH-008 · DECISION · closed · Five questions for the KCF 운영사무국 (by 2026-09-07)

**What:** Only the organisers can settle these, and the backlog is keyed to the
answers (WFG-022): (1) finals date 10.18 vs 10.24 (NH-006); (2) which 참가부문
track this entry is registered under (Track A application vs Track B SW 연구);
(3) whether restating 기여 ② from "deadline-sorted dispatch list" to "per-home
closure time" stays within 운영요강 p.9 (작품 목적·주제에 반하지 않는 범위);
(4) how AI-assisted / autonomous-agent development must be disclosed, given
심사개요 "대리(표절)작 판정 시 심사 제외 가능"; (5) what 제출 자료 is scored at the
finals (기제출 서식2 only, a poster, handouts?) and the poster spec.
Contact per the research sweep: koreacodefair@gmail.com / 070-5066-1963 (verify
on kcf.or.kr). **Why only you:** external contact; Pass/Fail exposure.

**CLOSED 2026-09-04 by the author** · channel: author reply in a Claude Code session ·
received: 2026-09-04 · verbatim: "Everything is fine here. Don't worry about
this, and continue with the project." (quoted verbatim; the reply arrived where this
repository cannot see it, and NH-017 asks the author to confirm it). No contact with the 운영사무국 will be made.
Consequences the loop now carries instead of an answer: (1) the finals date stays
**10-24** per NH-006; (2) the 참가부문 track is not re-verified; (3) 기여 ② keeps its
current wording rather than the restatement, since only the organisers could have
approved the change; (4) AI-assisted development is disclosed on the loop's own
initiative. **Superseded 2026-09-04:** the author reports the organisers addressed
this directly and no disclosure artifact is required, so `docs/auto/AI_DISCLOSURE.md`
was removed at the author's instruction and CHARTER §9 keeps only the practices that
make the work explainable at the booth;
(5) finals 제출 자료 scope is assumed to be the 기제출 서식2 plus a booth demo, which
is what `docs/auto/KCF_READINESS.md` already plans for.

## NH-009 · DECISION · closed · Repository decisions only the author can take (this week)

**What:** (a) Protect `Main` on GitHub (require a PR and the `auto-gates` check;
block force-push). (b) Ratify `auto/dev` as the working branch so
`docs/HANDOFF_ROUND3.md` §5.1 ("all work stays on round3-dev") can be rewritten
(WFG-024). (c) Decide in writing the two open HANDOFF §4 items: which routing
field the finals narrative uses (the brief recommends the canonical 414/42/2 with
the reconciliation sheet, WFG-018) and whether the corrected-DEM LOFO ever
replaces the committed `spread_v2_lofo.json` (recommendation: not before the
finals; keep it as a separate lineage). (d) Approve or veto the refuge-density
decimation experiment (WFG-034; HANDOFF §4 says the user confirms before it
starts). Close NH-001 and NH-002 either way.

**CLOSED 2026-09-04 by the author** · channel: author reply in a Claude Code session ·
received: 2026-09-04 · verbatim: "If there is something better though, make your own
decision to implement better ones along the way." (quoted verbatim; the reply arrived
where this repository cannot see it, and NH-017 asks the author to confirm it). The
author ratified the recommendations and delegated the rest. Resolutions:

- **(a) Protect `Main` — NOT YET DONE, and it is the one item still owed.** The
  session that closed this entry was blocked from writing repository settings. The
  author runs it; the required status check is **`gates`** (the job id), *not*
  `auto-gates` (the workflow name) — requiring the latter would deadlock every merge
  because no check by that name is ever produced.
- **(b) `auto/dev` is ratified** as the working branch. WFG-024 may now rewrite
  `docs/HANDOFF_ROUND3.md` §5.1 ("all work stays on round3-dev"), which is stale.
- **(c) Both HANDOFF §4 items decided as recommended.** The finals narrative uses the
  canonical **414/42/2** with the reconciliation sheet (WFG-018). The corrected-DEM
  LOFO does **not** replace `spread_v2_lofo.json` before the finals; it stays a
  separate, named lineage. Neither may be silently revisited.
- **(d) WFG-034 approved, but demoted to P2** — a lap decision, taken because the
  author delegated it. The experiment earns a real judge answer ("what if a village
  has fewer refuges?"), but it is a robustness nicety while 28 rows are still `todo`
  and 7 `blocked` against a 10-16 freeze. It may start only once every P0 and P1 row
  is `done`. If the sprint ends with it untouched, that is the correct outcome.

## NH-010 · DECISION · open · Expert consultations and the firefighter record (by 2026-09-20)

**What:** Two or three structured consultations by phone or video (이장, 119
상황실 dispatcher, 사회복지사) using the protocol the loop drafts (WFG-028); close
the blanks in `docs/firefighter_consultation.md` §8 (affiliation/rank, date,
written consent for anonymous vs named attribution); ask the three academic
advisers whether a one-line quoted judgment may be shown at the booth. No
numbers derived, no data about persons. **Why only you:** contacting people;
consent.

## NH-011 · DECISION · open · One real, recorded email send from a network that works in Shanghai (by 2026-09-20)

**What:** The email channel's verification send never completed (outbound SMTP
blocked on the working network; `docs/delivery_channels.md`). Either send once
over a VPN-routed SMTP path, recording the path in `email_sent.json`, or
authorise the Gmail-API adapter the loop builds (WFG-029) one time. Do not touch
Twilio or pursue SMS unless individual 발신번호 registration is confirmed in
writing. **Why only you:** credentials and network.

## NH-012 · DECISION · open · Portal downloads the loop cannot do (by 2026-10-01)

**What:** (a) 도로명주소 건물 layer for 영덕 from business.juso.go.kr into
`data/raw/juso_buildings/` (NH-005); (b) the 공공데이터포털 national shelter file,
which answers "are any of the refuges designated 대피소?"; (c) a KMA API Hub key
only if the post-finals sub-daily GK2A label experiment is wanted. **Why only
you:** login and CAPTCHA.

## NH-013 · FYI · open · Optional: a stable web address for the visual board

**What:** Report emails now embed this lap's five images by GitHub raw URL and
link the board through htmlpreview.github.io, which needs no setting. If you
would rather have a permanent address (for example to open on your phone
without the preview proxy), enable GitHub Pages on the repository: Settings →
Pages → Source "Deploy from a branch" → branch `auto/dev`, folder `/docs`. The
board would then be at `https://sparkxt-0318.github.io/wildfireguardian/auto/dashboard.html`.
The repository is already public, so this exposes nothing new. Not required.

**Options:** A) enable GitHub Pages as described  B) skip; the htmlpreview link is enough


## NH-014 · DECISION · open · Run the booth recipe once on the real laptop (after 09-10, before 10-16)

**What:** When WFG-037 lands, `docs/auto/finals/BOOTH_SETUP.md` gives the exact
steps for the judged machine. Run it once on the laptop you will carry to
Gwangju (env, `make all-checks`, open `web/finals.html` from `file://` with
Wi-Fi off, copy `release/kcf-finals-2026/` to two USB sticks). Close this entry
with the date and the laptop's Python version. It is KCF_READINESS line R12 and
the only readiness line the loop cannot tick for you.

## NH-015 · DECISION · closed · The three sources behind the README's opening numbers (by 2026-09-08)

**What:** `README.md:193` (Korean) and `README.md:488` (English) open the project
with the 2025 fire's scale: 사망 27명, 약 116,000 ha 소실, 주택 4,000여 채 파손,
sourced to 「한겨레·세계일보·서울환경연합」 with no link. You supplied those three
sources; the loop cannot open them without knowing which articles they are.

**Why it matters now.** The hectare figure is the one a judge can falsify in a
single search. Public reporting puts the **nationwide** March–May 2025 total
(347 fires) near 104,788 ha, and the World Weather Attribution report on these
fires gives about 48,000 ha for the fires it analysed. Your line attributes
~116,000 ha to the 의성→안동→청송→영양→영덕 chain **alone**, which is larger than
every national figure available. Either the figure means something wider than
the sentence says (2025 전국 전체? 산불 피해면적 including non-forest?), or it is
wrong. The same paragraph already footnotes the 27-vs-"30명 이상" scope
difference and carries no footnote for the area — so the paragraph shows it
knows this trap exists and steps into it one number later.

**What I need from you:** the three article URLs (or their titles and dates), so
the loop can record what each one actually says and the scope it says it for.
If they are not to hand, reply "use 산림청" and the loop will re-source all three
figures from 산림청 / 행정안전부 published totals and state the scope explicitly
instead.

**What happens either way:** WFG-043 registers each figure with its scope, adds
the missing scope footnote, and fixes `paper/manuscript.md:9`, which currently
attributes 27 deaths to the WWA report — a source that reports 32 casualties, 26
of them in 의성군. Nothing else is blocked on this; it is a P0 because it is the
first paragraph a judge reads.

**CLOSED 2026-09-04, then CORRECTED the same night.** · channel: author reply in a Claude
Code session · received: 2026-09-04 · verbatim: "use 산림청" (quoted verbatim; the reply
arrived where this repository cannot see it). The author replied "use 산림청"
and granted the loop standing permission to source public data itself (now CHARTER §3).
The first attempt at this fix, commit `12b8ac7`, **was wrong in the opposite direction
and critic #4 caught it 80 minutes later (F16, F17).** Both the original error and the
correction are recorded here because the pattern matters more than either number.

| figure | original README | `12b8ac7` wrote | correct |
|---|---|---|---|
| chain burned area | 약 116,000 ha | 45,157 ha (03-27 잠정) | **99,289 ha** (final) |
| 영덕 deaths | 8명 | 8명 | **10명** (already corrected at `f2eecf9`) |
| chain housing | 주택 4,000여 채 | 150동 (03-26 잠정) | **3,819동** |
| scope note | none | "104,788 ha is a different event" | the two are on different bases and different periods; **no ratio is printed** (see below) |

The same sentence was therefore wrong twice: once by overstating (116,000 ha exceeds
the national total) and once by understating (45,157 ha is a pre-containment provincial
interim). The second attempt also introduced a *new* falsifiable disclaimer the first
did not have, and cited WWA's "more than 48,000 ha" — which is WWA's figure for
**southeastern Korea**, not this complex.

Corrected at the commit that carries this entry. `docs/data_sources.md` now separates
scope A (the chain: 99,289 ha, 26 deaths, 영덕 10, 3,819 homes) from scope B (the
nationwide 347-fire total: 104,788 ha).

**AMENDED 2026-09-04 by the 0017Z dev lap, which was building the same fix in parallel.**
Two claims in the paragraph above were checked against primary sources and did not hold:

1. **"A is about 95 % of B" is withdrawn.** It divides A's *surveyed 산림피해 면적*
   (99,289 ha) by a nationwide total on a different basis. Measured like-for-like on
   산불영향구역 the chain is 45,157 ha, i.e. about **43 %** of B. A ratio that moves by a
   factor of two on basis choice is a framing, not a quantity, so the README prints none.
2. **B is not a March total.** The 산림청 release of 2025-05-16 gives 347건 / 104,788 ha
   for the **봄철 산불조심기간, 2025-01-24 to 05-15**
   (https://www.pcccr.go.kr/base/board/read?boardManagementNo=43&boardNo=5375&menuLevel=2&menuNo=92).
   The nationwide **32 deaths** figure is not in that release and has been removed from
   table B until a first-hand source is found; its previous citation was a ko.wikipedia
   page which does not contain the number 347 at all.

Every row of table A now carries a URL a lap opened. **Nothing here needs the author.**

**The real lesson, which is WFG-049, not this entry — now partly closed for this
paragraph.** `tests/test_motivating_event_figures.py` (2026-09-04) is the gate these
figures never had: it pins each one in the spelling the document uses and fails on a
swapped basis, a lost scope label, a dropped source URL or a collapsed disagreement.
It constrains *drift*, not *truth* — its ground truth is a sibling document, which is
the leakage filed as WFG-050. The general WFG-049 class stays open. Every gate in this
repository passed on `12b8ac7`. This paragraph is the only judge-facing prose carrying numbers with
no artifact, no registry key and no URL, so it is the only prose that can be rewritten
wrongly without a gate noticing — in either direction. Registering these figures is
WFG-049; until it lands, this paragraph stays the softest evidence in the repository,
which is what critics #1, #2, #3 and #4 have now each said in turn.

`paper/manuscript.md` was checked and does **not** contain the 27-death attribution;
`paper/references.bib` records WWA's figures correctly, with WWA's own scope.

## NH-016 · DECISION · open · The critic routine has 30 minutes to land its findings, and needs about 40 (by 2026-09-05)

**Why this is yours:** the cadence lives on the routine
(https://claude.ai/code/routines), not in this repository, so no lap can change it.

**What is happening.** `dev` fires at even hours `:17` and `critic` at odd hours
`:47`. That is 90 minutes after a dev lap starts, as CHARTER §11 intends, but only
**30 minutes before the next one**. A critic lap re-runs the full gates, re-runs
pytest for a census reading, reads the window and writes findings; critic #1 took
34 minutes and pushed its verdict **13 seconds after** the 1851Z dev lap had already
claimed its row, so CHARTER §11's promise that "the next dev lap clears every
`fix-before-next-row` item before it claims a new row" was not kept on the first
try. Critic #2 (this lap) started at 19:47 against a 20:17 dev lap and hit the same
wall. The critic prompt's own budget ("under 40 minutes so your findings are on
`auto/dev` before the next dev lap starts at the next even hour :17") cannot be
satisfied: 19:47 + 40 = 20:27.

**What I need from you:** move the critic routine's schedule from `47 1-23/2` to
`17 1-23/2` (odd hours `:17`). That keeps it 60 minutes after each dev lap and gives
it 120 minutes of clear air before the next one. Reply "move it" and it is a
one-field change on the routine page.

**What the loop does meanwhile, without you.** A dev lap will add one sentence to
CHARTER §4 step 3: after pushing its claim and before building, re-fetch and re-read
`docs/auto/CRITIC_LATEST.md`, and clear any `fix-before-next-row` item that appeared
since the lap started. That closes the race at the cost of one `git fetch`, so
nothing is blocked on this decision; the schedule change just stops the loop paying
for it every lap.

**UPDATED 2026-09-04 — the author asked for a recommended grid instead of the
one-field patch.** Measured lap durations, first sprint night: dev **22 / 34 / 36 /
67 min**; critic **15 / 31 / 34 min**. Worst case is therefore **70 + 40 = 110
minutes of work inside a 120-minute cycle**. Ten minutes of slack for two jobs is
not a schedule, and moving the critic to odd `:17` only redistributes it — the
2-hour dev cadence is the actual constraint, not the critic's offset.

**Recommended (option A, a 3-hour grid with real gaps) — all UTC:**

| routine | cron | fires | gap to next job |
|---|---|---|---|
| dev | `17 */3 * * *` | 00:17, 03:17 … 21:17 (8/day) | worst case ends h+1:27 → **30 min** |
| critic | `57 1-22/3 * * *` | 01:57, 04:57 … 22:57 (8/day) | worst case ends h+2:37 → **10 min** |
| paper | `47 2-23/6 * * *` | 02:47, 08:47, 14:47, 20:47 | → next dev **30 min** |

Every job gets clear air on both sides, and the critic gets 80 minutes before the
next dev instead of 30. The cost is 8 dev laps a day instead of 12 — **96 clean laps
across the 12-day sprint**, which is far more than the 28 `todo` rows need. Last
night proved the reverse trade is the expensive one: three of four dev laps spent
their opening minutes repairing a collision rather than claiming a row.

**Option B, if you want maximum throughput:** keep dev at `17 */2` and drop the
critic to `17 1,7,13,19 * * *` (every 6 h, 60 min after a dev lap). Cheaper in wall
clock, but the critic then reviews only every third lap, and the per-lap subagent
reviewer — which blocked a bad push last night — becomes the only gate on the other
two. Option A is the recommendation.

---

**Critic #7 note, 2026-09-04 — the collision is now costing whole commits, not just minutes.**
A fresh instance in this window, and it is the cleanest one yet. The 0401Z laptop lap and the
0501Z cloud lap both allocated **WFG-058 and WFG-059** while neither could see the other's
push, because neither had pushed. The rebase kept both sides, and a whole extra commit
(`8e0a6ad`) was spent renumbering one lap's rows to WFG-061/062 and chasing every reference
to them across `BACKLOG.md`, `KCF_READINESS.md`, `docs/horizon_grounding.md` and a test
docstring. That is the same failure NH-007 recorded for backlog *rows* in the loop's first
hours, now recurring for backlog *IDs*, and the claim-before-build rule does not cover it
because an ID is allocated while writing, not while claiming. Nothing was lost and no number
moved; the cost was one lap's tail. Recorded here because it is the third measured cost of
the overlap and this entry is where the author's one-field answer lives.

**Options:** A) adopt the recommended cadence (dev every 3 h, critic 3-hourly offset, paper 6-hourly)  B) keep the current cadence  C) another cadence (say which)


## NH-017 · DECISION · open · Three entries were closed on replies the repository cannot see, and one of them was wrong (by 2026-09-06)

**What:** `12b8ac7` closed NH-008, NH-009 and NH-015 by quoting your replies
("Everything is fine here. Don't worry about this, and continue with the project.",
"If there is something better though, make your own decision to implement better
ones along the way.", "use 산림청") with no channel, no message date and no thread
reference. The quotes may be exactly right; the repository has no way to tell, and
CHARTER §10 makes this file your own layer.

Two things follow, and only you can settle the first.

**(1) Confirm the three closures, and where the replies arrived.** NH-008's closure
now commits the loop, for the rest of the sprint, to making no contact with the KCF
운영사무국 at all and to five consequences that follow from that, including keeping
기여 ② as submitted and assuming the finals 제출 자료 scope. NH-009's closure ratifies
`auto/dev`, decides both HANDOFF §4 items, and demotes WFG-034 to P2. Those are large
standing decisions to rest on an unverifiable transcription. Reply with a yes, or
correct whichever one is wrong.

**(2) NH-015's closure was substantively wrong, and the loop is fixing it without you.**
The rewrite it produced states the 의성발 경북 chain burned **45,157 ha** and adds a note
telling the reader that the 104,788 ha figure belongs to a different event. The chain's
final area is **99,289 ha**, about 95 % of that nationwide total, so the note points the
wrong way; the same paragraph also reasserts 영덕 **8명** against this repository's own
correction to **10** at `f2eecf9`. Details and sources are in
`docs/auto/CRITIC_LATEST.md` F16 to F18, and the fix is WFG-043, raised to the next dev
lap's first job. **Nothing is blocked on you for this half** — your standing permission to
source public data is what makes it a lap's job rather than yours. It is recorded here
because a closed entry that was wrong should not read as settled.

**What changes in this file from now on.** Every future closure carries three fields:
`channel` (report email reply / PR comment / session), `received` (date), and the quoted
text marked `verbatim`. Where a reply arrived somewhere the repository cannot see, the
closure says so in those words rather than reading as a citation.

**Why only you:** you are the only source for what you actually said and where.

**Part (2) done, 2026-09-04 (lap on the laptop):** every closure now carries `channel`,
`received` and a `verbatim` marker, and NH-008, NH-009 and NH-015 are backfilled as
"author reply in a Claude Code session, 2026-09-04, verbatim quoted". Part (1), your
confirmation of the three quotes, is still yours; this entry stays open for it.

## NH-018 · DECISION · open · Two laps read the same primary sources and disagree on two sentences (by 2026-09-08)

**What:** The 0100Z cloud lap and the 2026-09-04 laptop lap both sourced the README's
opening figures from primary pages on the same day. They agree on every figure the
README now prints (99,289 ha, 149 h, 26, 영덕 10, 3,819동, 2,246세대 / 3,587명, 1조 505억 원,
347건, 104,788 ha). They disagree on two things, and under the "no fourth rewrite" rule
the laptop lap changed nothing in the paragraph and asks you instead:

1. **"사망 32명 was not in the 산림청 release."** The 0100Z lap removed the nationwide
   death toll from `docs/data_sources.md` table B on that ground. The laptop lap opened
   the same release on 대한민국 정책브리핑 (korea.kr newsId=156689401) and it reads
   「사상자도 86명(사망 32명, 부상 54명)으로 많은 인명 피해가 발생했다」. The figures are
   registered (`fire2025_nationwide_deaths`, `fire2025_nationwide_injured`) with that quote;
   the README does not currently print them. Nothing to decide unless you want the
   paragraph to state the season's toll again.
2. **The "약 95 %" share, and the "43 %" counter-example now in the README.** The 0100Z
   lap withdrew the share as a framing (different period and basis) and wrote into both
   paragraphs that a like-for-like ratio "on 산불영향구역" would be about 43 %. The laptop
   lap's reading: 104,788 ha (산림청 2025-05-16) postdates the joint survey and is built on
   surveyed 피해면적 (99,289 chain + 3,397 경남 + 1,190 울산 + smaller fires ≈ 104,788), so
   final-over-final is ~95 % and 45,157 / 104,788 = 43 % divides an initial 산불영향구역
   estimate by a surveyed final, which is the mixed-basis ratio the paragraph warns against.
   The laptop lap could not open a primary page that states which basis the 104,788 total
   uses, so it did not touch the sentence. **Your call:** keep the 0100Z scope note as it
   stands (safe: it prints no share), or ask a lap to remove the "약 43 %" sentence (it is
   the one line in the paragraph that itself mixes bases). `fire2025_chain_share_of_nationwide_pct`
   stays registered as an arithmetic record and is not printed anywhere.

**Why only you:** two agents disagree on a framing sentence in the judge-facing paragraph,
and the rule after two wrong rewrites is that no agent rewrites it a fourth time.

**Critic #5 note, 2026-09-04T0147Z (this entry stays open; nothing is closed here).**
Item 2 is resolvable from public sources and does not need your decision. The laptop lap
left the sentence standing because it "could not open a primary page that states which
basis the 104,788 total uses". That page is not required, because three separate checks
settle it and each is in the report at `docs/auto/reports/2026-09-04T0203Z-critic.md`
(finding F21):

1. 산불영향구역 is the area inside the fire line and includes the ground inside that line
   that did not burn; 피해면적 is the surveyed area that actually burned. The 영향구역 is
   normally the larger of the two. A 산불영향구역 of 45,157 ha under a surveyed 피해면적 of
   99,289 ha, for the same fire, is that relation inverted.
2. The 경향신문 article this repository already cites for the 45,157 row
   (https://www.khan.co.kr/article/202504171020011, opened 2026-09-04) frames that figure as
   the 산림청 estimate the joint survey more than doubled, under the headline
   「초기 추산 엉터리」. It is a superseded undercount, not a coexisting basis.
3. 경북 99,289 + 경남 3,397 + 울산 1,190 = 103,876 ha, which is 99.1 % of the 104,788 ha
   national total and leaves 912 ha for the roughly 340 other fires of the season. For that
   denominator to carry this chain at 45,157 instead, those fires would need 55,044 ha
   between them.

So the "약 43 %" sentence divides a superseded numerator by a current denominator, which is
the mixed-basis division the paragraph exists to forbid, and it contradicts this
repository's own `fire2025_chain_share_of_nationwide_pct = 94.8`. The critic's
recommendation is the one the laptop lap already offered as an option: **delete that one
sentence in both languages and print no ratio at all**, which is a deletion rather than a
fourth rewrite and leaves the rule the sentence was attached to intact. Item 1 (whether the
paragraph should state the season's 32 deaths) and your confirmation of both readings remain
yours.

**Dev lap 2026-09-04T0400Z — item 2 is DONE, on evidence, not on your decision. Item 1 and
your confirmation stay open, and this entry stays open with them.** The lap took the
critic's recommendation and deleted the "약 43 %" sentence in both languages rather than
rewriting the paragraph a fourth time (`README.md`, Korean and English scope notes). Under
CHARTER §3 rule 5b the loop has standing permission to settle a sourcing question from
public sources, and this one was settled by a check that needs no source at all: this
repository's own `docs/data_sources.md` 함정 1 already records 45,157 ha as the estimate the
joint survey **more than doubled**, so the same file was calling it a superseded estimate in
함정 1 and a parallel basis you may divide by in 함정 6. Both 함정 are corrected. No ratio is
printed in either language, and `tests/test_motivating_event_figures.py` now scans both
whole paragraphs — the earlier line-scoped version passed on the very sentences it banned.

**One of the critic's three premises did not survive, and the conclusion did.** critic #5
argued that 산불영향구역 is *always* larger than 피해면적, so 45,157 under 99,289 has the
relation inverted. This lap checked that and it is not what 산림청 says. 산림청 told
경향신문 that 「산불영향구역과 피해면적은 개념이 달라서 **단순 비교할 수 없고**」 and that
「실제 피해면적은 **줄어들 수도 있고 늘어날 수도 있다**」 — the two are different concepts
for different purposes, not two sizes of one thing (경향신문 2025-04-17, 김현수·이종섭,
<https://www.khan.co.kr/article/202504171020011>, opened 2026-09-04; the same article this
repository already cites for the 99,289 ha figure). The definitions themselves — 화선 경계
observed for firefighting strategy, versus a field survey for recovery — are 문화일보
2025-04-18, 김창희, <https://www.munhwa.com/article/11499954>. That is a better reason to
refuse the ratio than the directional one, so `docs/data_sources.md` 함정 1 and 함정 6 now
carry the agency's wording under each of its two sources, not the critic's claim.

Recorded here because the loop's own reviewer should be checkable against the same standard
as everything else — and because this lap's *first* attempt at this paragraph put both
quotes under the 문화일보 link, which carries only the definitions. The lap's independent
reviewer caught it and blocked the push, and the fix was to split the citation. A lap whose
whole subject is a sentence that shipped with a source that did not carry it does not get to
ship one of its own.

What is left for you: item 1, and saying whether you agree with the reading. If you do not,
reply `NH-018: <your decision>` and a lap will restore whatever you ask, verbatim.
---

**Paper lap 3 note, 2026-09-04 (this entry stays open; nothing is closed here). The prose
stopped printing the ratio; the registry still asserts it, and a gate enforces it.** The
manuscript now states no share of any nationwide total, and `README.md` and
`docs/data_sources.md` print none either. But `docs/NUMBERS.json` was never part of that
correction, and two entries still carry the withdrawn framing in their caveats:
`fire2025_chain_area_ha` reads "It is about 95 % of the nationwide 104,788 ha" and
`fire2025_nationwide_area_ha` reads "The 의성발 chain is 99,289 ha of this, about 95 %:
never describe this figure as a different event from the chain", the latter with
`forbidden_phrasings` `["belongs to a different event", "다른 사건"]` that a gate enforces
against any prose. CHARTER §12 says a number's caveats travel with it, so the paper is
currently declining to repeat a caveat its own registry still carries, and a future lap
reading the registry rather than the prose would put the ratio back.

This is not the same question as the 43 % sentence, which item 2 settled from sources. No
source settles this one: whether two totals compiled on different bases over different
periods may be divided at all is a claim-shape judgment, and it touches gate-enforced
behaviour. Under CHARTER §3 rule 2 the entries are add-never-edit, so the fix is an
annotated superseding entry, not a rewrite, and only a dev lap can make it. Raised by the
paper lap's independent reviewer. **Nothing is blocked on you** — the manuscript's position
is the conservative one and ships as it is.

**Options:** A) keep the 0100Z scope note as it stands (prints no share)  B) remove the "약 43 %" / "about 43 %" sentence, keep the rest — **already done 2026-09-04T0255Z on evidence, per critic #5 F21; reply B only to confirm, or A to have it put back**  C) also restate the season toll (32 deaths) in the scope note  D) annotate the two registry caveats so they stop asserting the ~95 % ratio the prose withdrew (dev lap; add-never-edit)


## NH-019 · DECISION · open · One report time, for one fire, decides what the detection result is allowed to say (by 2026-09-08)

**What:** every delay in the paper's new detection section — +22, +34 and +64 minutes —
is measured from `docs/data_provenance/fire_manifest.json`'s `start` field.
`docs/detection_floor.md` §1 reads that field as the **신고접수시각** and builds its whole
verdict on the reading: "위성은 사람보다 느렸습니다", and from there §10's recommendation
that the trigger interface treat 사람 신고 as the primary source and GK2A as 보조.

The reading is not supported anywhere in the repository. The manifest says of that same
field "start/end/reported_ha are provenance only", gives no source for the times of day
(11:25 / 12:15 / 11:00 / 08:22), and in its own notes describes the event start as the
ignition ("first hit 2025-03-22 may lag ignition"). No committed artifact records a
신고접수시각 for any of these fires. So the delays might be detection-behind-report, in
which case the verdict stands, or detection-behind-ignition, in which case the human
report time is simply unmeasured and could fall *after* the satellite — and the safeguard
sentence, that the bias "flatters the satellite", is only true under the first reading.

**What the paper did about it this lap.** It reverted the claim rather than repeat it. The
manuscript now states the delays against "the recorded occurrence time", says in Table 3's
caption and in §6 exactly why that clock is unsourced, and makes no claim about whether a
satellite trigger precedes the call. `paper/GAPS.md` G5 carries the gap. The size floor
(0.1–1 ha) is unaffected and is what the paper leans on instead. Found by the lap-2
independent reviewer, which blocked the push until this was fixed.

**What we need from you:** for **any one** of 의성·안동 2025, 강릉 2023 or 홍성 2023,
either

- a 산림청 / 119 / 중대본 record giving the 신고접수시각, with its date — one lookup, no
  rerun, no raw bundle; or
- the acquisition note saying where that minute came from, if you have it outside the
  repository.

With that, the value is registered with its agency and the paper can state the ordering.
Without it, `docs/detection_floor.md`'s verdict and its §10 trigger recommendation are
resting on an unsourced re-labelling, and the booth answer should be the narrower one:
a 2 km pixel does not see a fire below roughly a hectare, so a satellite cannot be an
ignition-scale alarm — which is true either way.

**Why only you:** the repository has no channel to a 신고 record, and the design document
that asserted the reading does not say where it came from.

**Critic #6 note, 2026-09-04 (this entry stays open; nothing is closed here).** Two things
this entry left open are now settled from artifacts, and neither needs you.

1. **The manifest does not merely fail to support the 신고 reading; for one fire it says the
   opposite.** Checked this lap in `docs/data_provenance/fire_manifest.json`: all four
   detection fires carry `start/end/reported_ha are provenance only` and a note whose only
   description of the event start is the **ignition** (`first hit … may lag ignition`). Not
   one entry contains the word 신고 or any report-time language. For `yeongdeok_2025` the
   field is `2025-03-22T12:15:00+09:00` and the same note reads `first hit (2025-03-25) lags
   the 2025-03-22 ignition by days`, so the manifest names that date the ignition. The
   caveat inherits the error: `DETECTION_FLOOR_CARD.md:11-13` tells a judge the delays are
   written 「실제보다 위성에 유리하게」 *because* the clock is a report time, which under the
   manifest's own reading is not true either.
2. **The narrowing does not wait on you, and one half of the repository has already done
   it.** `paper/manuscript.md:492-497` states the delays against the recorded occurrence
   time and says in as many words that the measurement cannot say whether the satellite
   preceded the call. `docs/detection_floor.md` §9, §10 and
   `docs/auto/finals/DETECTION_FLOOR_CARD.md` still assert the ordering, and so does
   `docs/auto/JUDGE_QA.md` Q10, which is one of the fourteen T0 answers the student is told
   to know by heart. A judge who reads the card and the paper gets two answers. Filed as
   **WFG-053**, agent-doable, raised to the next dev lap's first job.

**Dev lap 2026-09-04T0419Z — the loop's half is DONE; this entry stays open for yours.**
WFG-053 narrowed every judge-facing document to the paper's wording. `docs/detection_floor.md`
§1 now states the delays against the 기록된 발생일시 and quotes the manifest's own
`provenance only` sentence and its ignition note; §9's 평결 is the **size floor**, which
holds under either reading; §10 keeps 사람 신고 first on the 99 %-목격신고 statistic instead
of on the ordering; `docs/auto/finals/DETECTION_FLOOR_CARD.md`'s front sentence and caveat
match; `docs/auto/JUDGE_QA.md` Q10 (T0) was rewritten and Q10c lost its 「근거 없음」 banner
and is now the standard answer. `docs/SESSION19_REPORT.md` keeps its text as a record and
carries a dated annotation. **No number moved and no registry key changed** — the delays are
still +22 / +34 / +64 / +28 minutes with the same keys; only the label on the clock changed.
`tests/test_detection_ordering_is_not_claimed.py` (15 tests) now fails the build if any of
those documents asserts the ordering again.

**What is still yours, unchanged:** one 신고접수시각 from a 산림청 / 119 / 중대본 record for
any one of 의성·안동 2025, 강릉 2023 or 홍성 2023, or the acquisition note saying where that
minute came from. With it the ordering can be stated and the 평결 restored. Without it the
booth answer is the size floor, which holds either way. **Nothing is blocked on you** — the
booth has a defensible answer today; your reply would only make the stronger one available.

**Critic #7 note, 2026-09-04 (this entry stays open; nothing is closed here). Your one lookup
now unblocks two claims, not one.** When WFG-053 withdrew the ordering, it also removed the
only support for the *other* half of `docs/detection_floor.md` §10 — the recommendation that
사람 신고 be the **primary** trigger source. §10 reached for 「신고의 99 %가 목격 신고」 as a
replacement ground; that lap's own reviewer showed the 99 % is an unregistered year-to-date
interim and had it struck from the booth card, and §10 now forbids its use at `:310`. What
remains is the size floor, and the size floor rules the **satellite out** without ruling the
**human in**. So today the repository recommends a trigger design it cannot source, and the
loop is narrowing that claim too (WFG-063, agent-doable, nothing blocked on you).

A 신고접수시각 for any one of the three fires would restore both at once: the ordering
(NH-019 as written) and the trigger priority that depends on it. That raises the value of
option A; it does not change what is asked of you, and option B remains defensible, because
「위성을 일차 트리거로 둘 수 없다」 is true either way and is what the booth will say.

**Options:** A) I will look for the 신고접수시각 for one fire  B) skip; keep the narrowed claim (size floor only) for the finals

## NH-020 · DECISION · open · Twenty-five report emails, no reply, and the decision channel has never once been exercised (by 2026-09-06)

**Why this is yours:** only you can tell the loop whether the email is arriving, whether the
reply syntax works, and whether you want to keep answering this way.

**What is happening.** `scripts/auto/decisions.py` was built on 2026-09-04 so that a one-line
reply to a report email (`NH-###: <your decision>`) closes an entry with its channel, date
and message id. Critic #8 searched the mailbox this lap
(`from:siyeong0318@gmail.com subject:"WildfireGuardian autoloop" newer_than:14d`, 25 threads,
every thread fetched) and every thread holds exactly **one** message: the loop's own report.
PR #31 has **zero** comments. `docs/auto/decisions_seen.json` does not exist, because
`decisions.py apply` has never recorded anything. The whole decision channel is untested in
both directions.

Meanwhile **eleven other entries are open**, four of them dated: NH-016 was due 2026-09-05 (that
is tomorrow), NH-017 by 09-06, NH-018 and NH-019 by 09-08. NH-016 is the cheapest and the
most expensive to leave: it is a one-field change on the routine page, and until it is made
the critic routine keeps landing its findings 30 minutes before the next dev lap instead of
120.

Two possibilities and the loop cannot tell them apart. Either the reports are reaching you
and you are reading without replying, which is entirely reasonable and means the loop should
stop asking twelve questions per email and ask one; or they are not reaching you at all
(spam, a filter, the send-to-self threading), in which case every 「Decisions needed」 block
written since 2026-09-03 has gone nowhere and the loop has been reporting into a void for
a full day of a twelve-day sprint.

**What I need from you:** one reply to this email, any words at all. If you want to spend
thirty seconds rather than five minutes, reply with just the two lines below and the loop
will act on both immediately.

**Options:** A) reply with `NH-016: move it` and `NH-020: email works, I read them` (the loop keeps the current format and applies the cadence change)  B) reply `NH-020: too many questions` (the loop cuts every report to one decision, the highest-severity open entry, and parks the rest until you ask)  C) reply `NH-020: use PR #31` (the loop moves the decisions block to a comment on the pull request and the email becomes read-only)
