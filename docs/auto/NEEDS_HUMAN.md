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

## NH-006 · DECISION · closed · Confirm the finals date: 10.18 (your notice) vs 10.24 (June schedule post)

**Decided 2026-09-03 by the author: the finals are 2026-10-24.** Freeze moved to
2026-10-16; STATE.json, CHARTER §1, LOOP_CONFIG and the backlog header now say so.

**What:** The finals notice you supplied says booth setup is on the day itself,
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

## NH-008 · DECISION · open · Five questions for the KCF 운영사무국 (by 2026-09-07)

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

## NH-009 · DECISION · open · Repository decisions only the author can take (this week)

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

## NH-014 · DECISION · open · Run the booth recipe once on the real laptop (after 09-10, before 10-16)

**What:** When WFG-037 lands, `docs/auto/finals/BOOTH_SETUP.md` gives the exact
steps for the judged machine. Run it once on the laptop you will carry to
Gwangju (env, `make all-checks`, open `web/finals.html` from `file://` with
Wi-Fi off, copy `release/kcf-finals-2026/` to two USB sticks). Close this entry
with the date and the laptop's Python version. It is KCF_READINESS line R12 and
the only readiness line the loop cannot tick for you.

## NH-015 · DECISION · open · The three sources behind the README's opening numbers (by 2026-09-08)

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
