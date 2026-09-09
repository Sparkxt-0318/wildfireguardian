# Authorship and disclosure

Author: Siyeong Park (박시영), Shanghai American School Puxi.

This manuscript is drafted and kept current by an autonomous agent loop
(`wfg-autoloop-paper`, docs/auto/CHARTER.md §12) from the repository's committed
artifacts, registry and documents, under the rules in `docs/auto/CHARTER.md` §9.
The research design, data acquisition, expert consultations, submitted competition
documents and every decision recorded in `docs/auto/NEEDS_HUMAN.md` are the
author's. Before any submission the author rewrites the abstract and the
discussion in their own words and records that revision here with the date.
Nothing is submitted before the Korea Code Fair awards ceremony (December 2026).

## The disclosure is counted, not asserted

CHARTER §9 requires every agent commit to carry a `Co-Authored-By` trailer and
forbids squashing agent commits into human-authored ones. Since 2026-09-09 that
convention is measured rather than described. `scripts/build_timeline_roles.py`
re-derives the counts from `git log` alone — no network and no data files — into
`data/processed/timeline_roles/timeline_roles.json`, and twenty `timeline_*`
entries in `docs/NUMBERS.json` re-derive from that artifact on every gate run.

At the artifact's own stamp (branch `auto/dev`, first commit 2026-05-27, last
2026-09-09, built at `89da7d3`) it records 662 commits, of which 513 carry the
`Co-Authored-By: Claude` trailer and 149 do not.

Four things travel with those figures, from the registry's own caveat, or none of
them may be quoted.

1. They count commits reachable from `HEAD` on one branch at one commit, so a
   rebased or parked branch's commits are not in them, and every count grows with
   every later lap. Each figure is "as of" its commit and nothing re-derives it
   forward.
2. The trailer is a mechanical string test and not a statement about who thought
   of what. The convention only begins in July 2026, so an untrailered commit is
   not evidence that no tool was used.
3. A commit is not a unit of work. The loop commits several times per lap by
   design — a claim, the work, the report — so the September 2026 counts are
   inflated against the hand-worked months and must never be read as more having
   been done.
4. The five phases the artifact splits the record into were **chosen by the
   author**, who cut the record at four of its calendar gaps. The record did not
   choose them: `scripts/build_timeline_roles.py` hard-codes all five boundaries,
   and `WC-012`, which withdrew the contrary claim on 2026-09-09
   (`docs/withdrawn_claims.md`), measured in a full clone that one six-day gap
   was not used as a boundary while a one-day gap was. What stands is the weaker
   statement the script re-derives on every run: no commit in the history falls
   outside the five phases.

⚠ The withdrawn wording of (4) is alive today in two files this routine may not
edit — the builder's own comment block at `scripts/build_timeline_roles.py:42-46`,
sitting inside the `:40-84` range whose hard-coded boundaries disprove it
(`PHASES` opens at `:47`, the first boundary literal at `:51`), and the shared caveat of
all twenty `timeline_*` registry entries, which CHARTER §3 makes travel with
every one of these numbers. `scripts/check_withdrawn_claims.py` cannot see either:
it reads `.md` and `.html` only, and `WC-012`'s registered spellings are Korean
while both survivals are in English. Those are the two limits §3.5 of the
manuscript states, firing together. Recorded here so that whoever quotes these
numbers next quotes (4) in its corrected form.
