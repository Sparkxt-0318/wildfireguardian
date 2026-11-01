# Batch 1 review (checkpoint 3)

Independent review, 2026-11-01, of Track C batch 1 (E1, E3, E4, the 5-seed baseline re-runs, the harness rules)
and the wave-1 deliverables (H0, Track A's fresh-holdout proposal). Reviewed commits: `evacplan/phase0` @
`18841678`, `firecast-lab/phase0` @ `58ce939e`. One agent reproduced from a clean detached checkout with a fresh
venv (R0). Five agents that wrote none of the code reviewed one area each: harness and leaderboard, E1, E3, E4, and
H0 with the Track A proposal. One or two further agents then tried to refute each of the reviewers' 32
discrepancies; the verdict is after the arrow, and a verifier's correction of the reviewer is kept. Fix status: last
section.

## Reproduction (R0)

- **Install.** `uv pip freeze` of the fresh venv is identical to `evacplan/requirements.lock` (40 of 40 packages).
- **Suites** (one lock hold, real data present): evacplan 374 passed, 0 failed (the 2 KR-2025 packet-metadata
  items deselected; the 2 KR-2025 graph-conversion items ran and read those graphs; R0-D1 below; 9 min 39 s);
  hazard_contract 76 passed; program 6 passed.
- **Headlines, same VM session as the rows** (`vm boot ff671362`):
  - E1 seed 0: 1445, as committed, identical on every instance; the plans differ on 3 M instances (time-limited
    search), so its slack columns move.
  - B2 seed 0 on M-geo-t25-s106: 155 delivered, 0 unresolved, objective 15210, as committed.
  - E4: 25 on S-grid-t75-s103 and 144 on M-geo-t75-s108; dual bounds equal to every printed digit.
  - E3 cell (plan A8-g0 on S-geo-t75-s104 against all 256 fresh members): plan, support set and all 256 check
    records identical.

## Track C: harness, baselines and leaderboard

**Recomputed without importing evacplan** (rows at `18841678`, dev / 60 s / this session): noop 0; B0 1157 ×5;
B1 1353 ×5; B2 1749 ×5; B3 103 [103–104] on S; E1 1445/1444/1446/1443/1444. Best-of-baselines 1750; bar
max(recorded 1750, 1750) = 1750; E1 "no". The regenerated leaderboard and figure are byte-identical; 280 of 280
rows match their saved oracle results; every commit is clean; B2's commit has the baselines' code and E1's commit
adds only E1. Margin columns (prefix rule) recomputed for three rows: equal. Bound-only rows handled as #94.

**Discrepancies.**
- harness-D1 B2's 5-seed hold (05:03–05:55) overlapped about 3 min of single-threaded work run outside the lock
  (E4's Reach and LP probes and two short pytest calls, small E3 and E1 checks), not recorded → **partly, minor**.
  Rule 6 was broken; the numbers were not affected: 9 of 10 instances have identical plans in all 5 seeds,
  including every heavily overlapped seed, and the one differing plan (L-geo seed 0, the source of B2's slack ≥ 5
  range) ran in a window with no outside work.
- harness-D2 the harness times only the solve; its untimed oracle check of a B2 L plan takes about 33–36 s, while
  E1 certifies inside its 60 s → **confirmed, minor** (disclosed, but unquantified in the decision).
- harness-D3 a host-class recorded observation defines a bar, and allows "beats B2", in a session where B2 never
  ran → **confirmed, minor** (latent; untested).
- harness-D4 rows over budget still get a verdict → **confirmed, minor** (no row is over budget).
- harness-D5 the harness's bar is 1750, one below Siyeong's stated 1751 (the 1751 best-of-baselines total came
  from an earlier session of this VM: B2 517 on L-grid-t50-s109); the observation line says "this host" for an
  earlier session → **confirmed, minor**.
- harness-D6 / E1-D3 the E1 README still says best-of-baselines 1749 and "B1 has no rows on this host"; its figure
  names B1 but draws none → **confirmed, minor**.
- R0-D2 E1's slack columns spread beyond the 5-seed range (slack ≥ 15 total 1256 vs 1267 [1265–1267]); delivered
  identical → accepted as stated (not put to a verifier): five repeats understate a time-limited search's spread.
- R0-D3 the README's suite time ("about four minutes") is stale (9 min 39 s); the editable install writes
  git-ignored `src/*.egg-info` folders → accepted as stated.

## Track C: experiments

**E1** (ALNS with the oracle in the loop). Rules 3 and 4 hold; pre-registration (`8cef0955`) precedes every run;
parameters from the literature; tests and profiling use generated instances outside the split; 0 of 50 rows over
budget; every number in the README tables recomputes.
- E1-D1 the pre-registered rule (from the orchestrator's brief) replaced the budget Siyeong approved at checkpoint
  2 ("2 iterations. KILL if the minimum of 3 is still ≤ 1750 after the second"), and the change was recorded nowhere;
  under the approved budget the status is ITERATE, not KILL → **confirmed, major** (both verifiers).
- E1-D2 the KILL depends on how certification time is counted → **partly, minor**. A verifier's full rerun through
  the harness (post hoc, not pre-registered, same session, under the lock) of E1 with no oracle use inside the
  budget, the plan certified by the harness's untimed check like every baseline's: 1777/1775/1774/1799/1780 per
  seed, worst 1774 > 1751, 0 unresolved; L-grid beats B2 in 5 of 5 seeds, L-geo in 3 of 5 (against the morning
  hold's 528). In the reviewer's runs B2 certifying inside its own 60 s delivered 951 on L, so the bar would be ≥ 1574
  and E1 (1443) would still lose. It cannot re-decide E1 (rule 9); it can inform the second iteration (E1b), not
  predict it.
- E1-D4 four timing statements inexact (M stop times, skipped certifications counted twice, L calibration range,
  L room at safety factor 1.0 is 0–12 s) → **partly, minor**.
- E1-D5 the uninterruptible part at tiny budgets is the setup (Reach and the latest-departure sweep), not the B1
  loop, which stops at the deadline and leaves an empty plan at 1.5 s; the budget test passes on empty plans
  → **confirmed, minor**.
- E1-D6 the README omits the E4 agent's ~20 s of unlocked work at the start of E1's final run (S-grid-t25-s101
  seeds 0–1; both delivered the proven 23/23) → **confirmed, minor**.

**E3** (scenario robustness). Every reported number recomputes from the raw records with independent code
(pooled 3.89 % [KG 2.94, 5.03], Kish 6.25 %, U(1 min) 4.55 %, M-grid-t75-s107 37.1 %), except one interval end
rounded twice (13.0 for 12.9; found by a verifier); members bit-identical and disjoint; verdicts only from
`Oracle.check_plan`; KEEP and the 1-min margin follow the pre-registered rule.
- E3-D1 the Korn-Graubard interval lacks its degrees-of-freedom factor (it is the pre-registered interval; with
  the factor no pick changes) → **confirmed, minor**.
- E3-D2 the per-resident metric was redefined after the pushed pre-registration (`71a694de` → `758b1d55`, before
  any data); under the original metric α = 1 % gives 45 min instead of none ≤ 60 → **confirmed, minor**.
- E3-D3 "more i.i.d. members help roughly like 1/K" and "P2 holds" rest on one instance (M-grid-t75-s107); arm-A
  plans are often identical across K → **confirmed, minor**.
- E3-D4 the scenario bound's premises (consistency, determinism, i.i.d.) are unstated, arm A is not i.i.d., and the
  greedy support depends on removal order on 3 of 10 plans → **partly, minor** (the bound stays valid).
- E3-D5 S-grid-t25-s101 is named as a carrier of violations; it carries 0.6 % → **confirmed, minor**.
- E3-D6 "monotone" holds only on the harness grid for B1; the 1–30 min bin range is 3.5–15 % → **confirmed, minor**.
- E3-D7 the α = 5 % "1 min" certificate covers the residents of these 10 instances; with instances as the sampling
  unit the answer ranges from 1 min (instance bootstrap) to 20 min (Korn-Graubard, df 9) to none ≤ 60 min
  (max(KG, Kish)) → **partly, minor**.
- E3-D8 E3's B2 plans cannot be regenerated (load-dependent search; they differ from the leaderboard's on 2
  instances) and the reproduce command omits `--diagnostics` → **confirmed, minor**.

**E4** (flow-over-time bound). No counterexample: the validity argument holds against the code and the oracle,
validator and reach semantics; all 270 dev plans map into E4's networks with 0 violations; 1,755 random plans
and 8,000 random duals found none; all rows of both host strings are within the bound. KEEP stands.
- E4-D1 README gaps and check counts are pre-merge (M-grid-t75-s107: 6.25 % and 44 % of the trivial gap closed,
  not 12.5 % and 29 %) → **confirmed, minor**.
- E4-D2 budget changed from the pre-registered 600 s to 900 s without an amendment note (decided before the run,
  edited during it); config.yaml still says 600; the lock hold was 59.6 min (STATUS said 63), plus about 3 min run
  outside the lock, against "at most 1 h" → **confirmed, minor**.
- E4-D3 when PDLP's certificate wins, the diagnostics keep the interior point's status and objective; the README's
  L sentence is wrong for L-geo → **confirmed, minor** (no bound changes).
- E4-D4 the written argument omits the departure cutoff at facility-only locations and the alive pruning (both
  valid) → **confirmed, minor**.
- E4-D5 the variants' "known optimum" is a brute-force family optimum → **partly, no defect**: an independent
  exact search shows it is the true optimum on all 10.
- E4-D6 the README omits the lock overlap that STATUS records → **confirmed, minor**.

## H0 and the Track A proposal

H0's verdict (SYNTHETIC "much hotter") reapplies exactly from `results.csv` and from the raw 4.0 M records; a
500-record re-query matches; the pre-registration came first; H0's own code reads only the 3 dev fires.
- H0-D1 stays beyond about 375 m are "dose-safe for 30 min in both panels" only on dose_lower; on dose_upper, which
  the oracle certifies on, 0.8–3.9 % of Korean far stays reach the budget → **confirmed, minor**.
- H0-D2 = R0-D1 evacplan's real-data adapter tests read the KR-2025 road graphs and parsed each packet's whole
  `NATIVE_METADATA.json` (only the affine transform and graph revision are asserted; in the dev packets the same file
  also holds the present-fire cells at issue time) in every suite run with `WFG_ROUTING_INPUTS` set since `997d6d7a`
  (2026-10-31), against DECISIONS ("not read") → **confirmed** (R0: major, rule 5; verifier: minor, nothing was
  computed or stored from them).
- A-D3 MTBS had at least 16 fires of 2025 by its 2026-04-07 release, not "5" → **partly, minor**.
- A-D4 the eligibility rules amend the frozen membership rule beyond what §5 asks; E4 (final size) is an
  outcome-based exclusion → **partly, minor**.
- A-D5 the release path does not exclude a release that also contains the reserved 2026 surveys → **confirmed,
  minor**.
- A-D6 the FTP archive layout is one geographic area's convention → **partly, minor**.

## Found while fixing: the VM's speed drifts within a session

B2's quiet re-run, with nothing else running and hypervisor steal about 1 % (since boot), found fewer solutions than
the morning hold on 9 of 10 instances: 14–28 % fewer (means over seeds; S-grid-t25-s101: 23,888–26,257 against
30,424–33,621; L-geo-t50-s110: 122–178 against 186–191); on L-grid-t50-s109 it found 104 in 4 of 5 seeds, as in the
morning. It delivered 500–516 on L-geo where the morning hold delivered 528, and 509 on L-grid once. On
M-grid-t25-s105 and M-geo-t25-s106 it found exactly the plans E3's slower B2 had found (all 5 seeds). So on this
cloud VM "same host, same session" does not mean "same speed". R0's E1 run (10:16–10:29) had made 35–37 % fewer
iterations than the final run (08:15–09:07) on the two M-grid instances, though 19–44 % more on the two M-geo ones.
A calibration with B1, which does deterministic work, took 7–18 % less time at 16:00 than its seed-0 rows of
09:15–09:20 on three of the same instances; B1's runtimes already vary between seeds of one hold (L-grid 7.6–10.1 s),
so this suggests rather than proves that the speed goes up and down. No reported verdict depends on it (E1's
worst 1443 is far below any B2 level), but comparisons between holds hours apart carry this uncertainty. Proposed
for batch 2 (checkpoint 3): run B2 interleaved with each challenger in one hold, and record a speed probe in every row.

## Fix status

Every confirmed finding is fixed on its track branch and merged into `next/integration` (`0123649a`), or answered in
the checkpoint 3 report where it is Siyeong's decision. Track C: `cbbc8490` (code and docs), `b0bd9b7d` (B2's quiet
rows), `262ac6c6` (regenerated outputs), `9d2ae36f` (corrections from the checkpoint-3 verification); Track A:
`ed5a4b4b`. Each code fix has a test that fails on the old code.
Suites: in one lock hold on the Track C worktree with the fixes (just before the commit; the edits after it touched
only docs and docstrings), with the real-data tests on (dev fires only), evacplan 377 passed and hazard_contract 76
passed; on the merge, program 6 passed and the lock-related evacplan tests 43 passed (the 7 real-data tests skipped
there); `test_e1_alns.py` again under the lock on the committed code, 9 passed.

- **Rule 5 (R0-D1 / H0-D2).** The adapter tests read the three Korean dev fires only;
  `test_real_data_tests_read_dev_fires_only` checks the list against `firecast-lab/SPLITS.json` and that the whole
  KR-2025 season is test. DECISIONS corrects its "not read" entry; the reads are reported to Siyeong (checkpoint 3,
  question 13). H0's README and ASSUMPTIONS #31 are scoped. (While checking this report, a verifier's grep listed the
  names of the frozen planner's KR-2025 cache files, `planner/cache/`, tracked in the repo since `55d5499d`; none was
  opened.)
- **Rule 6 (harness-D1).**
  - B2 was re-run × 5 in one quiet hold (14:56–15:49 UTC, code `18841678`, rows `b0bd9b7d`) with a `/proc` sampler:
    every other process used 4.7 % of one core in all, almost entirely the agent harness, and at most 1.0 CPU-s in
    any 5 s. Its rows replace the earlier ones: 1726/1737/1737/1737/1721, median 1737 [1721–1737], 0 unresolved (the
    morning hold: 1749 × 5). The bar stays 1751 through the recorded observations, and no verdict changes.
  - The evacplan suite refuses to start outside the bench lock (exit 75; `tests/conftest.py`,
    `test_bench_guard.py`); evacplan/CLAUDE.md sends probes that build Reach, an LP or a solver through the lock.
  - An E4 verifier found a third overlap (about 27 s beside E3's compute hold, which included B2 runs). STATUS and the
    E4 README record all three; the E1 and E3 READMEs record those that touched their runs.
- **The bar (harness-D3, D4, D5).** A recorded observation only raises a part of the bar that the session's own rows
  define; a method with a row over its budget gets "n/a"; the best-of-baselines total 1751 of `b43990bb` is recorded
  for the VM's host class, so the dev bar on this VM is 1751, as Siyeong stated. The observation lines name their
  scope ("an earlier session of this host class"). Three new tests.
- **E1 (E1-D1 to D6, harness-D2, harness-D6, R0-D2).** Decision relabelled **ITERATE: 1 of the 2 approved iterations
  run**, with the history; DECISIONS records the orchestrator's unrecorded cut. The counterfactual, its labels and the
  untimed check times are in Next step; the script and its rows are kept in `experiments/E1-alns/posthoc/`. Stale
  numbers, timing statements and the warm-start attribution are corrected; the overlap is recorded; `results.csv`
  and the figures are regenerated with B1's rows. The budget test now says the setup is what cannot be interrupted
  and asserts a non-empty, complete warm start at 6 s.
- **E3 (D1 to D8).** The interval is named as computed (Korn-Graubard without the df factor, as pre-registered) with
  the df sensitivity; the metric amendment and its α = 1 % consequence are disclosed; the K-trend, scenario-bound,
  carrier and monotonicity sentences are corrected; the instance-level sensitivity precedes the recommendation; the
  raw records (B2 plans included) are committed under `raw/` (132 KB), and the reproduce command has
  `--diagnostics`.
- **E4 (D1 to D6).** README numbers updated to the merged rows (and `results.csv` regenerated); the 600 → 900 s budget
  change recorded as an amendment and `config.yaml` set to 900; the PDLP diagnostics fixed in code (the winner's
  status and objective, the first solver's kept beside; test extended) and the L sentence corrected; the validity
  argument covers the departure cutoff and the alive pruning (README, ASSUMPTIONS #95, module docstring); the
  variants' optima noted as independently confirmed; all three of E4's overlaps with timed holds recorded.
- **R0-D3.** README: suite time about ten minutes; the editable installs' `src/*.egg-info` folders named.
- **Track A (A-D3 to D6).** `FRESH_HOLDOUT.md`: the MTBS count (at least 16 by 2026-04-07, 21 by 2026-05-27) and the
  faster USGS products; every membership-rule amendment listed in §5, the final-size rule flagged as an outcome-based
  exclusion with a non-outcome alternative; a release that bundles 2026 surveys waits for the owner's OSF
  registration; the FTP layout described per geographic area.

