# WildfireGuardian autonomous loop — charter

**Read this file first in every agent session, cloud or local.** It is the standing
brief for the loop that keeps developing this repository while the author is away.
Written 2026-09-03; the loop may edit it, but only to make it truer.

## 1. Mission and dates

WildfireGuardian forecasts where an already-burning Korean wildfire will be next and
turns that forecast into household-level evacuation and rescue-dispatch decisions for
rural elderly residents. Three goals, in priority order until 2026-10-18:

1. **Win the 2026 Korea Code Fair (한국코드페어) finals** — 2026-10-18, Gwangju,
   offline booth, five judges × (≈5 min demo + ≈5 min Q&A). 은상 or higher earns the
   ISEF Korea-delegation selection interview. Rubric: `docs/auto/RUBRIC.md`.
2. **Be a genuine scientific and engineering contribution** to wildfire response,
   wildfire research and environmental mapping/monitoring — usable by a county
   emergency office, defensible to a fire scientist, reproducible by a stranger.
3. **Reach ISEF 2027 and an IEEE venue** with the same evidence base.

| date | what |
|---|---|
| 2026-10-10 | **freeze** — after this, only bug fixes, demo polish, Q&A material |
| 2026-10-18 | finals (booth setup that morning after registration; no wifi) |
| 2026-12 | KCF awards; ISEF delegation interview follows for 은상 이상 |
| 2027-01 → 05 | ISEF 12-month research window and ISEF 2027 |
| after 2026-12 | IEEE submission (docs/auto/research/ carries the plan) |

## 2. What the loop is

Three cloud routines (Claude Code, fresh Linux sandbox, this repository cloned,
no local files, no secrets) plus GitHub Actions as an independent gate:

| routine | cadence | job |
|---|---|---|
| `wfg-autoloop-dev` | every 6 h | one build lap: pick the top backlog item, build it, prove it, report |
| `wfg-autoloop-critic` | daily | attack the last 24 h like a hostile judge; file findings into the backlog |
| `wfg-autoloop-research` | weekly | literature and competitor scan; IEEE plan; new backlog candidates |
| `auto-gates` (Actions) | every push | re-run all gates on a clean machine |
| `report-email` (Actions) | on report | email the report (needs secrets, NH-001) |

Skills available in `.claude/skills/` (vendored paperthin, MIT): `catchup` (rebuild
context), `nba` (the single next action), `readchk` (confirm the read of a brief),
`re0-loop` / `re0-memo` / `re0-work` (build → prove → learn → restart when the
foundation is wrong), `hate` (one load-bearing objection + cheapest test),
`prism` (independent lenses), `factchk` (verify claims both ways), `mandela`
(leakage audit of an eval), `sip` (taste-test your own output), `shower`
(cold read), `ssotize` (one fact, one home), `re0` (rewrite a drifted doc as v0),
`autobahn` (carve unsafe scope out, run the rest at full speed), `dedash`,
`debloat`, `detool`, `reorder`. Also the repository's own `systematic-debugging`
and `verification-before-completion`.

## 3. Non-negotiables

These come from `docs/HANDOFF_ROUND3.md` §5 (all 24 rules apply; the ones below
are the ones the loop meets daily), from the KCF 운영요강, and from safety.

1. **Never push to `Main`.** Work on `auto/dev`. Merging is the author's decision.
2. **Never modify, overwrite or regenerate a committed artifact.** New results get
   new filenames. Protected: everything under `data/processed/` and
   `docs/figures/` that is tracked, `data/raw/firms_data/fire_manifest.json`,
   `data/snapshots/**`, `docs/NUMBERS.json` entries already registered (add, never
   edit a value). `make verify` and `make baseline-verify` enforce most of this.
3. **Every number in prose traces to a committed artifact**, registered through
   `scripts/build_numbers.py` → `docs/NUMBERS.json` → `make verify`. A number you
   cannot register, you do not write. Superseded values are annotated, never
   deleted (`scripts/check_number_collisions.py`).
4. **Never change the project's purpose or theme.** The KCF rule (운영요강 p.9)
   voids the entry if the finals work reads as a different 작품. The submitted
   frame is in `docs/auto/RUBRIC.md` and the 서식 documents the author holds:
   spread forecast → rescue-aware routing → decision/report layer, for rural
   elderly Koreans. Extend it; do not pivot it.
5. **No fabricated evidence, no fabricated citations, no rounding a limitation
   away.** The project's credibility rests on its withdrawn-claim record (README
   TL;DR). When a result is weak, say so in the artifact and the report.
6. **No secrets, no paid services, no human-subject data collection, no sending
   messages to anyone but the author's report channel.** The delivery layer's
   real sends (`scripts/send_dispatch_email.py`, `delivery/sms.py`) stay dry-run.
7. **Never delete.** Archive (`docs/auto/archive/` or a branch), and say why.
8. **Never force-push. Never rewrite history on a shared branch.**
9. **Gates before pushes.** `python scripts/auto/gates.py --mode full` exits 0, or
   the work goes to `auto/red/<stamp>` with a `red` report and a NEEDS_HUMAN entry.
10. **Never pipe a gate** (`make verify | tail` swallows the exit code; §5 story).
11. **Do not re-acquire Yeongdeok OSM data, do not mosaic DEM providers, do not
    route on a partial DEM** (§5.4, §5.17). The sandbox has no keys anyway.
12. **Do not touch the author's submission materials** (they live outside this
    repository) and do not edit `README.md`'s Round-2 section, which is a record.

## 4. One lap — the dev routine's protocol

Time-box: finish cleanly inside about two hours of wall-clock; a half-done change
is worse than no change. Every step leaves the tree consistent.

0. **Bootstrap.** `git fetch origin && git checkout -B auto/dev origin/auto/dev`
   (create from `origin/Main` only if `auto/dev` does not exist yet). Then
   `bash scripts/auto/bootstrap.sh` and use `.auto/venv/bin/python` for everything.
1. **Catch up** (`catchup`): this file; `docs/auto/BACKLOG.md`;
   `docs/auto/NEEDS_HUMAN.md`; the last three files in `docs/auto/reports/`;
   `docs/auto/MEMO.md`; `git log --oneline -30`; `docs/HANDOFF_ROUND3.md` §3–§5;
   `docs/BLOCKERS.md`. Skim the newest `docs/SESSION*_REPORT.md`.
2. **Baseline.** `python scripts/auto/gates.py --mode quick`. Red baseline → do
   not build. Diagnose; fix only if the cause is clearly environmental and the
   fix touches no artifact; otherwise write a NEEDS_HUMAN BLOCKER and a `red`
   report, and stop.
3. **Choose one item** (`nba`): the highest-priority backlog row that is
   `todo`, `agent_doable: yes`, unblocked, and not `in-progress` by another lap.
   Set it `in-progress` with the lap stamp. If two laps overlap, the later one
   takes the next row. Before building, run `readchk` on the row and `hate` on
   your plan for it; record the root objection in the report.
4. **Build** (`re0-loop` FRAME → BUILD → DRIVE). Follow the repository's own
   discipline: config in `config/default.yaml`; new experiment → new script under
   `scripts/`, new artifact under `data/processed/<topic>/`, registered numbers,
   a `docs/<topic>.md` that states method, result, caveats and what it does NOT
   show, tests under `tests/`. Drive the real surface: run the script end to end
   on the committed snapshots; for screens run `scripts/check_screen_assets.py`.
5. **Prove.** `python scripts/auto/gates.py --mode full`. Also `sip` the docs you
   wrote (`shower`, `factchk` for any world claim, `mandela` for any eval).
6. **Learn** (`re0-memo`): append to `docs/auto/MEMO.md` — one lesson, one
   anti-pattern or one gate that changes the next lap. No changelog.
7. **Report.** Write `.auto/summary.md` (what, why, evidence, what did not work,
   next), then `python scripts/auto/report.py --kind dev --summary .auto/summary.md`.
   Update the backlog row (`done`, `blocked`, or back to `todo` with a note).
8. **Commit and push.** Commit messages in commit-economy form (`re0-git` style:
   subject states the durable truth, body says why). `git pull --rebase origin
   auto/dev` then `git push origin auto/dev`. Green only; red → `auto/red/<stamp>`.
9. **Email**, if an email/Gmail tool is available in the session: send the report
   body to siyeong0318@gmail.com with the report title as subject. If not, the
   GitHub workflow delivers it once NH-001 is closed. Never email anyone else.

The **critic** lap runs steps 0–1, then reads the diff of the last 24 h and the
latest reports, runs `prism` with lenses {KCF judge (software professor), KCF
judge (disaster-response official), fire scientist, ML reviewer, statistician},
`hate` on the current headline narrative, `factchk` on new prose, a judge-Q&A
drill against `docs/auto/JUDGE_QA.md`, and writes findings as backlog rows or
NEEDS_HUMAN entries, plus a `critic` report. It changes no code.

The **research** lap runs steps 0–1, then updates `docs/auto/research/` (weekly
literature scan with URLs, competitor and ISEF-landscape notes, IEEE plan status),
proposes backlog rows with evidence, and writes a `research` report.

## 5. Backlog conventions

`docs/auto/BACKLOG.md` is a table plus a details section per row. Columns:
`ID | P | goal | title | status | rubric rows | done when | constraints`.
Priorities: **P0** ships before the 2026-10-10 freeze; **P1** before 2026-10-18;
**P2** after the finals, for ISEF; **P3** for the IEEE paper. Status:
`todo | in-progress(<stamp>) | done(<commit>) | blocked(NH-###) | dropped(why)`.
Goals: `KCF | ISEF | science | IEEE | infra`. Rows are concrete enough that a
fresh agent with no memory can start them; a row that is not, gets rewritten
before it is started. Anything the loop discovers goes in as a row, never as a
loose TODO in code.

## 6. Escalation — when to stop and ask

Write a NEEDS_HUMAN entry (see that file's format) instead of deciding when:
credentials or a login are needed; money would be spent; an external party would
be contacted; a committed headline number would change meaning; the KCF frame
would move; a §5 rule would be broken to proceed; hardware must be bought; a human
participant would be involved; two laps disagree on direction. BLOCKER stops the
thread only — every other backlog row keeps moving.

## 7. What a good lap produces

Not lines of code. A lap is good when at least one of these is true: a rubric row
got measurably stronger with an artifact a judge can open; a scientific claim got
tested and either survived or was withdrawn in writing; a judge question that had
no answer now has one that points at a file; the next lap is cheaper because a
gate now catches a failure class. Restraint counts: a lap that verifies and finds
nothing to change reports exactly that.

## 8. Style

Documents that face judges are in Korean with the repository's existing tone
(direct, caveats first, numbers with sources); code, commit messages and reports
to the author are in English. No em-dashes in shipped screens (font subset). Keep
the README's Round-2 section untouched; add Round-4 material below Round 3.
