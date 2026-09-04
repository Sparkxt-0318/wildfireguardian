# WildfireGuardian autonomous loop — charter

**Read this file first in every agent session, cloud or local.** It is the standing
brief for the loop that keeps developing this repository while the author is away.
Written 2026-09-03; the loop may edit it, but only to make it truer.

## 1. Mission and dates

WildfireGuardian forecasts where an already-burning Korean wildfire will be next and
turns that forecast into household-level evacuation and rescue-dispatch decisions for
rural elderly residents. Three goals, in priority order until 2026-10-24:

1. **Win the 2026 Korea Code Fair (한국코드페어) finals** — 2026-10-24 (Sat), 김대중컨벤션센터, Gwangju,
   offline booth, five judges × (≈5 min demo + ≈5 min Q&A). 은상 or higher earns the
   ISEF Korea-delegation selection interview. Rubric: `docs/auto/RUBRIC.md`.
2. **Be a genuine scientific and engineering contribution** to wildfire response,
   wildfire research and environmental mapping/monitoring — usable by a county
   emergency office, defensible to a fire scientist, reproducible by a stranger.
3. **Reach ISEF 2027 and an IEEE venue** with the same evidence base.

| date | what |
|---|---|
| 2026-09-04 → 09-15 | **the sprint** — all primary work lands here (§11) |
| 2026-10-16 | **freeze** — after this, only bug fixes, demo polish, Q&A material |
| 2026-10-24 | finals (booth setup that morning after registration; no wifi); results 10-30 |
| 2026-12 | KCF awards; ISEF delegation interview follows for 은상 이상 |
| 2027-01 → 05 | ISEF 12-month research window and ISEF 2027 |
| after 2026-12 | IEEE submission (docs/auto/research/ carries the plan) |

## 2. What the loop is

Three cloud routines (Claude Code, fresh Linux sandbox, this repository cloned,
no local files, no secrets) plus GitHub Actions as an independent gate:

| routine | cadence | job |
|---|---|---|
| `wfg-autoloop-dev` | every 6 h | one build lap: pick the top backlog item, build it, prove it, report |
| `wfg-autoloop-critic` | 90 min after every dev lap | attack the last lap like a hostile judge; `CRITIC_LATEST.md` is the next lap's first job |
| `wfg-autoloop-research` | weekly (sprint: 09-04, 09-10) | literature and competitor scan; IEEE plan; new backlog candidates |
| `wfg-autoloop-paper` | every 6 h, only when the code moved | keeps the English manuscript current: prose, figures, references, the .docx (§12) |
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
5b. **External figures are sourced by the loop, and carry agency, date and
   scope.** The author granted standing permission on 2026-09-04 to search and
   fetch public sources rather than escalating a sourcing gap. A figure taken from
   outside the repository is written only with its **agency, as-of date and scope**,
   and an interim tally is never presented as a final one. Where sources disagree,
   both are given with their scopes. This rule exists because `12b8ac7` restated the
   README's opening figures from an interim provincial tally and was wrong by 54,000
   ha; see NH-015 and WFG-049. Escalation is still required for credentials,
   repository or account settings, external contact, and anything needing the
   author's physical presence.

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

**Session mechanics, learned on the first lap (2026-09-03).** The first lap put
the gate run in the background and ended its turn to "wait for the
notification"; the run log showed the session as finished, and it was only
minutes later that the worker resumed on the background task's completion.
Whether a routine is woken that way is not something to rely on: run
`gates.py`, pytest and every long command in the foreground with a long timeout
(30 min is fine); never end a turn to wait for CI or a notification; write the
report, commit and push before the final message. A lap that ends without a
pushed report is a failed lap and the next lap treats the row as still `todo`.
When two laps overlap on the same row (the first lap's marker never reached
`origin`), the one that pushes second rebases; if the rebase conflicts, it
parks its work on `auto/red/<stamp>` and reports instead of forcing.

**Sandbox facts.** Linux x86_64, Python 3.11, pip-only bootstrap in about one
minute (`pins_ok: true`). `data/raw/**` is git-ignored, so the FIRMS/ERA5/DEM
bundle and the two acquisition manifests never reach a fresh clone; work from
`data/snapshots/` and `data/processed/`. A GitHub MCP is available in the
sandbox for reading Actions runs and pull requests.

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
   **Claim it immediately:** set it `in-progress(<stamp>)`, commit only that
   change, `git pull --rebase origin auto/dev`, push. If the rebase shows another
   lap claimed the same row first, take the next row. A claim that is not pushed
   is not a claim (NH-007: two laps built the same row because the marker only
   travelled with the final commit). **After pushing the claim and before
   building, re-fetch `origin/auto/dev` and re-read `docs/auto/CRITIC_LATEST.md`;
   if it changed since the lap started, clear its `fix-before-next-row` items
   first.** The critic's window is 30 minutes wide and the dev lap's claim can
   land inside it (critic #2's root objection: 13 seconds separated one claim
   from the finding it should have read), so the re-fetch, not the schedule, is
   what makes CHARTER §11's "caught within one lap" true. Before building, run
   `readchk` on the row and `hate` on your plan for it; record the root
   objection in the report.
4. **Build** (`re0-loop` FRAME → BUILD → DRIVE). Follow the repository's own
   discipline: config in `config/default.yaml`; new experiment → new script under
   `scripts/`, new artifact under `data/processed/<topic>/`, registered numbers,
   a `docs/<topic>.md` that states method, result, caveats and what it does NOT
   show, tests under `tests/`. Drive the real surface: run the script end to end
   on the committed snapshots; for screens run `scripts/check_screen_assets.py`.
5. **Prove.** `python scripts/auto/gates.py --mode full` (read its exit code; never
   pipe it). Also `sip` the docs you wrote (`shower`, `factchk` for any world
   claim, `mandela` for any eval). Then the **independent review** set by
   `docs/auto/LOOP_CONFIG.json` → `review`: with `subagent` (default) spawn a
   fresh reviewer agent that has not seen the work being made; give it only the
   diff (`git diff <claim commit>..HEAD`), the row, and the claims you make in
   your summary; it runs `hate`, `factchk` and `mandela` and returns
   `{verdict: pass|block, root_objection, first_nail}`. A `block` means you fix
   or park the work on `auto/red/<stamp>`; it never means you argue. Record
   `Reviewed by: subagent (pass|block)` in the report. With `self`, skip the
   spawn and say so; with `critic-only`, the daily critic is the only reviewer.
6. **Learn** (`re0-memo`): append to `docs/auto/MEMO.md` — one lesson, one
   anti-pattern or one gate that changes the next lap. No changelog.
7. **Report.** Write `.auto/summary.md`: the technical account (what, why,
   evidence, what did not work, the reviewer's verdict, next), then a section
   headed exactly `## In plain terms` for the author, three short lines: what
   changed for the project, why it matters to the judges or the science, what
   the author should do. Then `python scripts/auto/report.py --kind dev
   --summary .auto/summary.md`, which also rebuilds `docs/auto/dashboard.html`,
   renders the five images into `docs/auto/images/<stamp>/`, and writes the
   HTML email body to `.auto/email.html`. Update the backlog row (`done`,
   `blocked`, or back to `todo` with a note).
8. **Commit and push.** **The commit you push is the commit the gates read** — that
   is the whole of this step, and the loop got it wrong twice in its first three laps.
   Step 5's `gates.py` run happens before `report.py` writes anything, so the report
   is tracked prose that no gate has seen; and anything else you commit after step 5
   (critic #3 found 162 lines of a test file and 41 of a doc) is unseen the same way,
   which is the more dangerous half because it can change behaviour rather than prose.
   On 2026-09-03 critic #2 pushed `24751fa` green at `0ff1b36`, and the 2053Z lap
   pushed `8d1decf` green at `f5f8498`; both branches sat RED until a later lap found
   it. So: commit everything, then re-run `gates.py --mode full` (or, when the clock
   forbids it, at least `make check-forbidden` and
   `pytest tests/test_rescue_lineage_ssot.py`), commit any fix, and then, immediately
   before the push, run

       .auto/venv/bin/python scripts/auto/gates.py --assert-head
       .auto/venv/bin/python scripts/auto/gates.py --assert-reported

   which run no gate: the first exits non-zero unless `.auto/gates.json` records a
   `full` pass at exactly this `HEAD` with a clean tree; the second exits non-zero
   when the commits since `origin/auto/dev` touch anything beyond the report
   machinery (`docs/auto/reports/`, `images/`, `STATE.json`, `dashboard.html`) or a
   bare backlog claim, and no new report file travels with them. That is the
   `12b8ac7` case (critic #4, F19; WFG-049): a prose-only commit that rewrote the
   README, closed three NEEDS_HUMAN entries and was invisible to every gate. If it fails, you do not push; you
   re-run the gates on the commit you actually mean to push. The lap's report says the
   same thing in prose — `report.py` marks a gate table **stale** when it does not
   name `HEAD`. Commit messages in commit-economy form (`re0-git` style:
   subject states the durable truth, body says why). `git pull --rebase origin
   auto/dev` then `git push origin auto/dev`. Green only; red → `auto/red/<stamp>`.
9. **Email**, if a Gmail tool is available in the session and only AFTER the
   push has landed: send to siyeong0318@gmail.com with the report title as
   subject and the contents of `.auto/email.html` as `htmlBody` (the images in
   it are GitHub raw URLs of this lap's files, so no attachment is needed and
   none is sent; hand-typed base64 attachments are forbidden, MEMO 2026-09-03).
   Never email anyone else.

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
Priorities: **P0** ships inside the sprint (by 2026-09-15); **P1** before the 2026-10-16 freeze;
**P2** after the finals, for ISEF; **P3** for the IEEE paper. Status:
`todo | in-progress(<stamp>) | done(<commit>) | blocked(NH-###) | dropped(why)`.
**`in-progress` is only ever held by a lap that is still running.** A lap that ends
without finishing its row sets the row back to `todo` and appends what it did as a
residue note (`todo — (b) done(<commit>), (a) outstanding, (c) not attempted`);
`in-progress` written by a lap that has ended is a lock with no key, and step 3 tells
every later lap to skip it. Two P0 rows were stranded that way for a day inside a
twelve-day sprint (critic #3, F15).
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

**How the author answers, and how the loop reads it.** Every report email ends its
"Decisions needed" block with the reply syntax: one line per item, `NH-###: <decision>`
(a letter from the entry's **Options:** line, yes/no, or a sentence). Step 1b of every
lap searches the mailbox through the Gmail connector for the author's replies to
"WildfireGuardian autoloop" emails, parses them with `scripts/auto/decisions.py parse`,
applies each with `decisions.py apply --ref <gmail message id> --received <date>`, which
closes the entry with channel, date, message id and the verbatim text, and refuses to
apply the same message twice (`docs/auto/decisions_seen.json`). The lap then acts on the
decision and says so in its report ("Your reply of <date> closed NH-###: …"). A reply the
loop cannot map to an entry is quoted in the report, never guessed at. A PR comment on
#31 in the same `NH-###: …` form is the second channel (GitHub MCP, `channel: PR comment`).
An entry that needs a choice states its options on one line as `**Options:** A) … B) …`.

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

## 9. Attribution and the student's own voice

The Korea Code Fair organisers confirmed to the author (2026-09-04, NH-008) that no
AI-disclosure artifact is required for this entry, and `docs/auto/AI_DISCLOSURE.md`
was removed at the author's instruction. The practices below are kept anyway, because
they are what makes the work explainable at the booth, not because a form asks for
them:

- every agent commit carries the `Co-Authored-By` trailer, and agent commits are
  never squashed into human-authored ones;
- every lap writes its report under `docs/auto/reports/`, and the routine prompts
  stay recorded verbatim in `docs/auto/ROUTINE_PROMPTS.md`;
- every experiment doc says who proposed the method, the student or the loop;
- drafts meant for the student's own voice (abstract, poster text, Q&A answers) are
  labelled drafts at the top of the file, where they are read
  (`tests/test_judge_qa_bank.py::test_the_draft_label_is_on_the_file`).

The student must be able to explain every artifact at the booth; a lap that produces
something the student could not explain in two minutes produces a `docs/<topic>.md`
that makes it explainable, or does not ship it.

## 10. Who checks what, and how the author changes it

| layer | what it checks | who | how to change |
|---|---|---|---|
| gates (`scripts/auto/gates.py`) | numbers re-derive from artifacts, no retired claims, no collisions, declared deps, snapshots intact, full test suite | mechanical, every lap and every push (Actions) | edit the gate scripts; never bypass |
| self-check (`hate`, `sip`) | the building agent attacks its own plan and cold-reads its own docs | the lap's own agent | always on |
| independent review | a fresh agent that did not build the work reads the diff and the claims, runs `hate` + `factchk` + `mandela`, can block the push | a subagent spawned inside the lap | `docs/auto/LOOP_CONFIG.json` → `review`: `subagent` (default) / `self` / `critic-only` |
| daily critic | five judging lenses over the last 24 h, scorecard, judge drill, findings to the backlog | the `wfg-autoloop-critic` routine | pause or reschedule it on claude.ai/code/routines |
| the author | decisions in `NEEDS_HUMAN.md`, merges to `Main`, everything in §6 | you | edit the files, reply to a report, or comment on PR #31 |

**Model and cadence.** All three routines run `claude-opus-5` (chosen for the
build and review work; the loop was set up by a different model in a local
session). Cadence: dev every 6 h, critic daily 19:41 UTC, research Mondays
21:23 UTC. Both live on the routine, not in this repository: open
https://claude.ai/code/routines, pick the routine, and change the model or the
schedule; the change applies from the next run. A faster, cheaper model
(`claude-sonnet-5`) is a reasonable choice for the research routine; keep the
dev and critic routines on the strongest model available, because they change
code and judge claims.

## 11. The sprint: 2026-09-04 to 2026-09-15

The author asked that all primary work land in twelve days, with laps as close
together as the platform allows, and that at the end there is a **full final
product** ready to take to the booth. So, for the sprint:

- Cadence: dev every 2 hours (even hours :17 UTC); **critic 90 minutes after every
  dev lap** (odd hours :47), writing `docs/auto/CRITIC_LATEST.md`; the next dev lap
  clears every `fix-before-next-row` item there before it claims a new row, so a
  wrong turn is caught within one lap instead of a day. Research on 09-04 and 09-10;
  paper every 6 h when the code moved.
- Order of work is the backlog table order; the sprint plan at the top of
  `docs/auto/BACKLOG.md` names the day each P0 row should be done by. A lap that
  finishes its row early takes the next one; it never idles.
- **The final product is a backlog row (WFG-036), not an afterthought.** Its
  definition of done is `docs/auto/KCF_READINESS.md`: a checklist the critic
  ticks with evidence every day. When every box is ticked the product is
  ready; until then it is not, whatever the backlog says.
- After `LOOP_CONFIG.json` → `sprint.end`, a lap writes a one-paragraph
  "sprint over" report and exits without building. The one-time handover
  routine (09-16) writes `docs/auto/HANDOVER_2026-09-16.md`: what shipped,
  what the checklist still lacks, and the post-sprint list for the author.
- What is deliberately left for after the sprint: P2 (ISEF) and P3 (IEEE) rows,
  anything needing the raw bundle on the laptop, and the author-only items
  (rehearsal, printing, consultations, portal downloads).

## 12. The paper loop

A fourth routine, `wfg-autoloop-paper`, writes the research paper alongside the
code and touches nothing outside `paper/` (plus its own report). It is
independent of the dev laps: it wakes every six hours, compares
`paper/STATE.json` → `last_incorporated_commit` with `origin/auto/dev`, and
exits at once if nothing outside `paper/` and `docs/auto/` changed.

What it keeps true, every lap it runs:

- `paper/manuscript.md` is a complete, publication-register English manuscript
  under 20 pages including title page and references (`check_paper.py` budget:
  7,000 words of body text, hard fail at 7,500), author **Siyeong Park (박시영)**.
  Sections: Abstract, Introduction, Related work, Data and methods, Results,
  Discussion, Limitations, Conclusion, Data and code availability, References.
- Every number in it is a registry key or a committed artifact value; the
  collision and forbidden-string gates scan it like any other prose. Withdrawn
  claims stay withdrawn; the model card's caveats travel with their numbers.
- Every figure is drawn by `paper/make_figures.py` from committed artifacts in
  the one style (`paper/style.py`): aligned, labelled, colour-blind-safe, 300 dpi,
  no chart junk, no hand edits. A diagram is drawn on a fixed grid so nothing is
  misaligned or deformed; the lap looks at each new figure once before it ships.
- Every citation was opened at its URL by the lap that added it and carries a
  `verified` note in `references.bib`; a paper the lap could not open is not cited.
- Anything the artifacts cannot yet support is a `[GAP: …]` marker mirrored in
  `paper/GAPS.md` with what closes it and whether that is after the sprint.
- `paper/WildfireGuardian_Park_2026.docx` is rebuilt by `paper/build_docx.py`
  and committed; the report email links it. The student rewrites the abstract
  and discussion in their own words before any submission (`paper/AUTHORSHIP.md`).

## 13. The knowledge base

`docs/auto/knowledge/` is where the project keeps its compiled fundamentals, so that a lap,
the paper routine or the student can look a concept up instead of rediscovering it. Started
2026-09-04 at the author's request with four notes: pyrogeography, routing mechanisms and
modelling, buildings as fuel at the wildland–urban interface (FireDX, read and deliberately
not adopted before the finals), and the figure-style reference (Moreno et al. 2025).

- The research routine extends every note each run (ROUTINE_PROMPTS.md step 2b): dated
  `## Update` sections, sources with URLs, and a revised "What this means for
  WildfireGuardian" section. Nothing is deleted; corrections are dated.
- A dev lap that learns something a note should hold appends it in the same lap, one
  paragraph, sourced. A dev lap does not restructure a note.
- Every note ends with backlog candidates tagged **before-freeze**, **after-finals** or
  **for-the-paper**; the research routine turns the ripe ones into backlog rows.
- Notes are prose, not registries: figures quoted from papers stay in the note with their
  source and never migrate into README, manuscript or `docs/NUMBERS.json` without going
  through the registry rule.

