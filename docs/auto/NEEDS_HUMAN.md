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

## NH-006 · DECISION · open · Confirm the finals date: 10.18 (your notice) vs 10.24 (June schedule post)

**What:** The finals notice you supplied says booth setup is on the day itself,
**10.18**, with judging from 10:30 and close at 18:00. The research sweep found a
KCF "전체 일정 공지" post dated 2026-06-24 (kcf.or.kr/84, idx 171991931) that lists
the finals as **10.24 (Sat), 김대중컨벤션센터**, results 10.30 14:00. The charter,
backlog priorities and the 10-10 freeze are set against 10.18; if the fair moved
to 10.24 the freeze can slide to 10-16. Reply with the confirmed date (or
close this entry with the date) and the loop will re-plan. Nothing else depends
on it.

## NH-007 · DECISION · open · Two dev laps ran at once and duplicated a row

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
