> **ARCHIVED, not live.** Retired 2026-09-04 at the author's instruction (NH-008): the
> Korea Code Fair 운영사무국 confirmed no AI-disclosure artifact is required for this
> entry, and the file was deleted in `fbe71de`. CHARTER §3 rule 7 says archive, never
> delete, so the retired text is kept here verbatim and this copy is the record.
> **The live practices are `docs/auto/CHARTER.md` §9**, which keeps every one of them
> for booth explainability rather than for a form. Nothing below is current guidance.
> Restored by the 2026-09-04T0400Z dev lap (critic #5, F24).

# AI contribution ledger

**Why this file exists.** Regeneron ISEF rules for 2026–27 accept AI-generated
code only with an explicit citation of which portions were AI-generated and a log
of the prompts, require the research plan, abstract and poster to be the
student's independent work, and add a Student Support Disclosure form (Form 2A)
for every project. The Korea Code Fair 심사개요 excludes work judged to be
대리(표절)작. An autonomous agent loop that develops this repository therefore
has to leave a ledger a judge can audit, and the student has to be able to
explain and defend every line of it at the booth. This file is that ledger's
index; the detail is in the repository's own history.

## Where the record lives

| what | where |
|---|---|
| every agent-authored commit | `git log --grep='Co-Authored-By: Claude'` (every loop commit carries the trailer) |
| the standing prompts of the three cloud routines | `docs/auto/CHARTER.md` §2 and §4; the verbatim prompts are on https://claude.ai/code/routines and copied in `docs/auto/ROUTINE_PROMPTS.md` |
| what each lap did, why, and with what evidence | `docs/auto/reports/<stamp>-<kind>.md` |
| lessons the loop drew | `docs/auto/MEMO.md` |
| earlier overnight agent sessions (2026-05 → 2026-09) | `docs/OVERNIGHT_REPORT*.md`, `docs/SESSION*_REPORT.md`, `docs/SESSION*_LOG.md` |
| decisions the student made or must make | `docs/auto/NEEDS_HUMAN.md` (closed entries record the decision) |

## Rules for the loop

1. Never remove the `Co-Authored-By` trailer from a commit; never squash agent
   commits into human-authored ones.
2. Every experiment's `docs/<topic>.md` states in its header whether the method
   was proposed by the student (from the submitted 서식, a NEEDS_HUMAN decision,
   or a backlog row the student wrote) or by the loop.
3. The student's own words stay the student's: `README.md` Round-2 section, the
   submitted 서식 (outside the repository), the abstract and any poster text.
   The loop may draft (`docs/auto/ABSTRACT_EN.md`, `JUDGE_QA.md`) and must label
   drafts as drafts.
4. Before ISEF forms are filed, the loop produces `docs/auto/FORM_2A_DRAFT.md`:
   which portions of the code are AI-generated (by directory and by commit
   range), which ideas were the student's, and where the prompt log is.

## Summary as of 2026-09-03

- Research design, problem framing, the withdrawn-claim record, data
  acquisition on the laptop, the firefighter consultation, the submitted
  documents: the student.
- Large parts of the implementation since 2026-05 were written in agent
  sessions directed by the student's briefs (see the session logs above); the
  student reviewed, ran and submitted them.
- From 2026-09-03 the three cloud routines work from `docs/auto/BACKLOG.md`;
  each lap's report names the row, the method and the evidence.
