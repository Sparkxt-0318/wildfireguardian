# Critic #71 — the next dev lap reads this first

**2026-09-12T0157Z. Head reviewed and shipped in: `e7ba085`.** Window: the 24 h to
`e7ba085` on `auto/dev` (`c7de4c0..e7ba085`), covering the WFG-259, WFG-260 and WFG-262
laps and the paper routine's `e0a3c2a`.

---

## 1. This lap's `fix-before-next-row` items: NONE

CHARTER §14b says **at most** one per critic lap, not one every lap. Critic #71 found no
minutes-sized defect on a judge-facing surface and no red gate, so it spends none and the
next dev lap goes straight to the top row. What was checked, so the next lap does not
re-check it:

- The judge-facing set (README, `docs/auto/JUDGE_QA.md`, `docs/auto/DEMO_SCRIPT_5MIN.md`,
  `docs/auto/finals/`, `web/finals.html`, `paper/manuscript.md`) carries **zero** hits of
  either sentence this window replaced. One grep, both spellings.
- `gates.py --mode full` exits **0** on its first run at `664ca6f` (2202 passed, 65
  skipped, 3 xfailed, pytest 311.2 s); `--assert-head` and `--assert-reported` both exit 0.
- GitHub `auto-gates` run **391** is `success` at `664ca6f`. Run **392** was still
  `in_progress` at `e7ba085` when this was written. **No run in this lap's window concluded
  `failure`** (381 was `cancelled`; 386 at `edd0ec0` belongs to critic #70's window and was
  disclosed, repaired and ruled on there).
- The printed kit hashes **7 of 7** (`WFG_printables_20260911T2137Z.pdf`, **60** pages) and
  the release bundle **19 of 19**, both re-hashed in this lap's own process, and the bundle
  names that kit.
- All **fifteen** reports in the window record `Reviewed by:`.
- Critic #70's item is **closed**: `README.md`'s Round-4 scope clause now names
  「완충거리를 폭까지 훑어 정식 상대로 세운 쪽」, matching `:339`, and the duplicated
  「거기서 나온 수치는 이 README 에 옮겨 적지 않습니다」 is down to one copy.

---

## 2. The root objection, and the one §3b row move that was spent on it

**The project audits the sheet it publishes and not the sheet it hands over.**

`docs/routing_limitations.md` now holds **six** numbered audits of A4 dispatch-sheet
sentences, and **every one of the six is on the 459 walk series**. The sheet the booth
physically opens is the **439 vehicle** series:

- `docs/auto/JUDGE_QA.md:1308` tells the student 「실물을 열어 드릴 수 있습니다 —
  `outputs/dispatch/` 에 마을별 A4 출동 지시서」.
- Q39 at `docs/auto/JUDGE_QA.md:1554` says **30 of its 33** sheets are reprinted for the
  booth with `python scripts/generate_dispatch_outputs.py`.
- That script, at `:102` and `:134`, emits
  「예산 내 차량 진입로가 화재로 차단됨(우회 포함)」 — a budget was consumed **and** detours
  were tried, the identical two-clause form §1 removed from `fa_exceeds_budget` on
  2026-08-10 and §6 removed from `no_safe_route` on 2026-09-12.

**Measured in this lap's own process**, not read from a report:
`outputs/dispatch/20260801T163042Z/` holds **33** committed cluster directories and **33**
`dispatch_a4.html`; **17 of the 33** print that sentence and the other 16 carry no
unreachable point; **3** sheets are committed as `dispatch_a4.pdf` and **1 of those 3**
(`02-천전공원-일대`) carries it, so it is on paper in the booth and not only in the tree.
One grep for the sentence across `docs/`, `paper/` and `README.md` returns **nothing**: no
file in this repository states what its code condition is.

⚠ **It is NOT established false, and it must NOT be repaired by analogy.** Nobody has read
the 439 arm's unreachable condition out of the code. The WFG-262 lap refused to rewrite it
on a guess and that refusal was **right** — it is the trap that row pre-registered against.
The job is to read the condition and write it down, the way §1 and §6 did for theirs.

⚠ **The honest wording already exists in this codebase**, at
`src/wildfireguardian/delivery/printable.py:105`:
`UNREACHABLE_REASON_FALLBACK = 「차량 진입로가 화재로 차단됨」`, the same sentence without
either disputed clause. **That is evidence about where to look, not a licence to
substitute it.** Half (a) of the row still governs.

### Why the move was spent, and what the author may reverse

The lap that found this filed it as **WFG-264, P1, at table row 259 of 258**, writing the <!-- forbidden-ok: 264, this is the BACKLOG ROW ID WFG-264 and not the gangneung_donghae_2022 Build-A positive count the gate anchors that value to. Same false-positive class as ba437f5, where the gate read a lap stamp as a camera count. No figure is asserted on this line. -->
reason into the row: 「Held until R1, R3, R4, R7, R8 and R9 tick (CHARTER §14b)」.

§14b names what waits behind those ticks, and it is a list:
「**loop hygiene** (report certification, gate-on-gate, commit-id bookkeeping, mechanics of
the routines) is a P1 row that waits until readiness lines R1, R3, R4, R7, R8 and R9 are
ticked」. A sentence printed on a booth printable is on none of those, and the **same
sentence** of §14b says where it does go: 「anything larger, however judge-facing, is filed
as a **P0 row at position 1** of the table and is never a preemption」. Booth printables are
in §14b's own enumeration of judge-facing surfaces.

The consequence is arithmetic, not rhetoric: **R3 is the only one of the six ticks still
outstanding**, it is `blocked(NH-046)`, NH-046 came due **2026-09-10**,
`docs/auto/decisions_seen.json` still records `"seen": []`, and the sprint ends
**2026-09-15**. Filed as it was, the row could not have been started at all.

So critic #71 spent its one §3b move: **WFG-264, P1 → P0, table row 259 → position 1.** <!-- forbidden-ok: 264, this is the BACKLOG ROW ID WFG-264 and not the gangneung_donghae_2022 Build-A positive count the gate anchors that value to. Same false-positive class as ba437f5, where the gate read a lap stamp as a camera count. No figure is asserted on this line. -->
The author's half is **NH-060**, which carries both readings as options. **If the author
picks B the row goes back to P1 and WFG-256 returns to position 1.**

---

## 3. What the lap under review got right, stated because it is the record

The WFG-262 lap is the best-controlled lap in this repository this week and nothing above
takes that back.

- It was handed a premise (「at least one member of the bucket did neither」), read code that
  contradicted it, and wrote **both** interpretations into the claim commit `c83e8d2`
  **before any number existed**, including 「if the count is ZERO ... that is the lap's
  finding and goes on the page in those words」.
- It **imported** the committed origin rule from
  `run_real_roads_real_hazard_slope.candidate_origins` rather than restating it.
- Its identity controls are **gating, not reported**: the script refuses to exit 0 unless
  `n_nodes` and `n_origins_scanned` re-derive exactly against each committed artifact, and
  for the two regions that committed bucket membership every listed member was tested
  individually.
- The answer was **0** on all three regions against committed buckets of 2, 12 and 10, and
  it published that, which made its own assignment less dramatic.
- It shipped the sentence repair anyway and said why the repair never depended on the
  premise.
- It disclosed the tautology (the origin filter removes the population the count then looks
  for) in the claim commit, the artifact, the registry caveat and §6, and its reviewer
  logged the same thing as a `mandela` pattern-4 hit. **A disclosed tautology is not a
  defect.**

**Verified here rather than taken on trust:** no caller in `src/` or `scripts/` passes a
non-zero `departure_min`, so §6's caveat 「it says nothing about a scan called with
`departure_min > 0`」 is a real limit correctly stated and not a hedge, and the invariant
holds on every committed path.

---

## 4. The loop, and one thing it did right

`report.py` stamped a **RED, stale** gate table into the 0135Z report body and into the
email header — naming `09eea5b`, a commit no clone can resolve — on a branch that was
green. The lap **caught it before the email went out**, re-ran the gates at the pushed head,
superseded the 0135Z body under CHARTER §3.7 rather than editing it, and re-stamped as
0146Z, **ALL GREEN at `664ca6f`**. Nothing wrong reached the author.

That is the correct handling, and it cost a second gate cycle and a second report.
**WFG-263** is the row that would stop it costing one each time. It stays P1: it is loop
hygiene by §14b's own enumeration, which is exactly the distinction this lap is drawing.

⚠ **`KCF_READINESS.md`: ZERO lines ticked for the twenty-eighth consecutive critic lap.**
`git diff 8952a5b..e7ba085 -- docs/auto/KCF_READINESS.md` is empty and the file's newest
commit is still `c241904` (critic #66). It stands at **8 of 11**.

---

## 5. Findings, ranked

1. **WFG-264 was filed at the wrong priority and the wrong place** (§2 above). Re-filed P0 <!-- forbidden-ok: 264, this is the BACKLOG ROW ID WFG-264 and not the gangneung_donghae_2022 Build-A positive count the gate anchors that value to. Same false-positive class as ba437f5, where the gate read a lap stamp as a camera count. No figure is asserted on this line. -->
   at position 1. Author's half: **NH-060**.
2. **The judge drill found two questions no file answers**, both on that same surface, and
   both are now halves (e) and (f) of WFG-264: 「이 A4 시트가 지금 심사위원 손에 있습니다. <!-- forbidden-ok: 264, this is the BACKLOG ROW ID WFG-264 and not the gangneung_donghae_2022 Build-A positive count the gate anchors that value to. Same false-positive class as ba437f5, where the gate read a lap stamp as a camera count. No figure is asserted on this line. -->
   이 문장은 프로그램이 실제로 확인한 것입니까?」 and 「보행 쪽은 오늘 고쳤다고 하셨는데
   커밋된 시트에는 옛 문장이 그대로입니다」. The second is answered today **only** on
   `docs/live_pipeline.md`, a developer page.
3. **A life-safety sheet line has never been executed** — `route_region`'s `origin_refused`
   branch, which §6 discloses in its own words. Filed as **WFG-265** (P1, product).
4. **`WFG-263` (P1) sits above the first `todo` P0 row** in the table, against this page's
   own rule. Flagged, not moved: the move budget was spent, CHARTER §4 step 3 takes the
   highest-**priority** row and not the highest table row, and DIRECTION names the row
   anyway.
5. **Zero readiness lines ticked, twenty-eighth lap.** Reported, not re-filed: it is
   NH-046 and it is the author's.

`factchk`: **zero new claims about the world** in the window's prose. Everything new in
`docs/routing_limitations.md` §6 and `docs/live_pipeline.md` is a claim about this
repository's own code, checkable in the tree and checked above. No new external figure, no
new citation, nothing to verify outward.

---

## 6. Scorecard

**NO row moves. Track B HOLDS at 96, Track A HOLDS at 97.** Evidence per row is in
`docs/auto/SCORECARD.md` at `e7ba085`.

⚠ **Pre-registered DOWNWARD for critic #72: Track A 구현 및 유용성 falls 20 → 19 if
WFG-264 is still `todo`.** By then the project will have known for two days that a sentence <!-- forbidden-ok: 264, this is the BACKLOG ROW ID WFG-264 and not the gangneung_donghae_2022 Build-A positive count the gate anchors that value to. Same false-positive class as ba437f5, where the gate read a lap stamp as a camera count. No figure is asserted on this line. -->
on its own booth printable is unjustified and chosen not to spend a lap reading the
condition.

⚠ **Pre-registered UPWARD for critic #72: Track B 제출 자료 rises 19 → 20** when WFG-264 (a) <!-- forbidden-ok: 264, this is the BACKLOG ROW ID WFG-264 and not the gangneung_donghae_2022 Build-A positive count the gate anchors that value to. Same false-positive class as ba437f5, where the gate read a lap stamp as a camera count. No figure is asserted on this line. -->
and (b) land — the 439-series condition read out of the code and written down, kit
reprinted and bundle re-pointed if a card changes — and **not** on a report that says so.

⚠ **Critic #70's downward condition on 구현 및 유용성 is DISCHARGED and does not fire:** it
was set for critic #72 「if WFG-262 is still open」, and WFG-262 closed at `77d44b6`.

---

## 7. Notes that expire at critic #72 unless that lap re-checks them (CHARTER §14c)

- **Do not `git fetch --unshallow`.** Re-run in this lap's own process: the clone is
  shallow at **52** commits, was not deepened, and `gates.py --mode full` exits 0 on its
  first run. Cost stated: `tests/test_timeline_roles.py:234` **SKIPS** rather than runs in
  a shallow clone, so a green critic gate does not certify that check; GitHub at
  `fetch-depth: 0` does, and run **391** is green. Covers that one line and that one
  measurement; it freezes no file and no question.
- **NH-049's reprint requirement is live.** Re-hashed here: kit 7 of 7 at 60 pages
  (`WFG_printables_20260911T2137Z.pdf`), bundle 19 of 19, bundle names that kit. Editing
  `docs/auto/JUDGE_QA.md`, `docs/auto/DEMO_SCRIPT_5MIN.md` or
  `docs/auto/finals/RELATED_WORK_PANEL.md` requires `make printables` at a new stamp and a
  re-pointed `release/kcf-finals-2026/MANIFEST.json`. Covers those three paths and those
  two hash counts.

Everything else this lap says about what not to do lives in `docs/auto/DIRECTION.md` and is
not restated here.
