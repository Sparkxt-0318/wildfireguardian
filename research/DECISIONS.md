# Research program design decisions

Dated log. Newest last. Every entry says what was decided, why, and what would
change it. A decision that no agent can point to here is not a decision, it is a
habit.

---

## 2026-09-16 · D-001 · The research tree is additive and touches nothing else

**Decision.** Everything the program produces lives under `research/`. No file
under `src/wildfireguardian/`, `demo/`, `tests/`, `docs/figures/` or the poster
sources is created, edited or regenerated.

**Why.** The Korea Code Fair finals build is frozen until 2026-10-24 in Gwangju
and the Korea Code Fair 운영요강 rules void an entry whose finals work reads as a different work.
The repository's own charter (`docs/auto/CHARTER.md` section 3) already forbids
modifying a committed artifact; this program adds the stricter rule that it does
not touch the finals tree at all.

**What would change it.** John's approval, after the finals, for the phase 6
integration adapters.

---

## 2026-09-16 · D-002 · Claims discipline is enforced inside `research/`, not by editing the repository registry

**Decision.** The three research questions are held as hypotheses in
`research/FORBIDDEN_CLAIMS.md` and enforced by
`research/shared/check_research_claims.py`, which scans tracked files under
`research/` for forbidden claim shapes and for em dashes. The equivalent patch
to `scripts/check_forbidden.py` is drafted but not applied.

**Why.** The program brief says to add the three questions to the repository's
forbidden-claims list, and it also says that any change outside `research/` is a
human gate. Both cannot be satisfied at once. The research-local checker covers
exactly the tree where these claims would first be written, so the protection is
real today, and the repository-wide patch waits for John as **WJ-002**.

**What would change it.** John clears WJ-002, at which point the ten rules move
into `scripts/check_forbidden.py` and the research-local checker keeps only the
em-dash duty.

**Validation record.** Ten rules, each carrying a corpus of overclaim spellings
it must fire on and a corpus of legitimate hedged neighbours it must not fire
on. At the time of writing: 28 of 28 catches, 27 of 27 spares, 0 findings
against the research tree. The bar is the one `docs/region_literals.md` section
5 sets for this repository. Three first-draft rules failed their own spares
corpus and were rewritten before the checker was committed.

**Known limitation, stated plainly.** Any line carrying a hedge word escapes
every rule. This is a copy-paste ratchet, not a claim detector. It stops an
assertive spelling from spreading across the tree; it does not replace A6's
read.

---

## 2026-09-16 · D-003 · Work lands on the session's designated branch, not on `research/<direction>-<topic>`

**Decision.** Phase 0 and the first research rounds are committed to
`claude/wonderful-gates-jlutm9`.

**Why.** The program brief asks for branches named `research/<direction>-<topic>`.
This session operates under a standing instruction to develop and push only on
its designated branch and never to push elsewhere without explicit permission.
The purpose behind the brief's rule, which is that research work must not land
on the finals line, is met either way: nothing here touches `Main`, `auto/dev`
or the finals tree, and all of it lives in the `research/` directory.

**What would change it.** John says the word in **WJ-003**, after which each
direction is re-cut onto its own `research/<direction>-<topic>` branch.

---

## 2026-09-16 · D-004 · No agent runs a git command

**Decision.** Specialist agents write files only. Branch selection, staging,
committing and pushing are the orchestrator's, done once per round.

**Why.** All agents share one working tree. A `git checkout` by one agent while
another is mid-write corrupts both. The charter also bans `git add -A`, which is
easy for an agent to reach for and hard to notice afterwards.

---

## 2026-09-16 · D-005 · EPSG:5186 for analysis, EPSG:4326 for exchange

**Decision.** Korea 2000 Central Belt (EPSG:5186) is the analysis CRS for every
direction. EPSG:4326 is used only for exchange and for registry entries.
Deviations need A6's approval, recorded here.

**Why.** Distances matter in all three directions: barrier width and approach
angle in roads, slope units in landslides, access distance in suppression. A
geographic CRS gives wrong distances, and mixing projections across directions
makes the three layers impossible to overlay later.
