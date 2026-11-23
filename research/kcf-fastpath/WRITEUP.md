# kcf-fastpath: a faster, lighter deadline field with the same answers

Protocol: `PROTOCOL.md` (frozen at `c1213cb3`, before any fast solver was timed; amendments at its end). Code:
`fastfield.py` (the solver), `run_fast.py` (benchmark runner), `eq_real.py`, `test_fastfield.py`, `mutants.py`
(equality tests), `bench.sh`, `summarize.py`. `deadline_field/core.py` is unchanged and is the baseline.

## 0. Headline

* **The answers do not change.** Every equality test passed with **zero differences** for each change alone and for
  both together. That covers Feas(o) of all 1,574 origin sets on the six caches, second by second; every state set
  and the fixed-point certificate; the verdict, arrival and full leg sequence of all 9,722 jobs; 6,000 random
  instances, 4,000 of them also against brute force; and the pruning guard. Seven deliberately wrong solvers were
  each caught. The timed runs agree as well: all four solvers give the same SHA-256 of the per-job answers on all
  18 job sets.
* **Change 1 (scalar fast path) is the win.** The field time drops by **1.8× to 2.6×** (medians) on all six caches
  (`full` job sets), "faster" by the protocol's range rule everywhere. The whole run is 1.2× to 1.6× faster on the
  four caches where the field dominates. On UA 03-24 and UA 03-25 the witness routes dominate the run, so the whole
  run is "not distinguished".
* **Change 2 (pruning) alone is not worth it on these caches.** It is faster only on UA 03-23 and UA 03-24
  (1.4×). On the other four it is "not distinguished", and its median is slightly slower on two Yeongdeok caches.
  Its forward bound removes only 7% (Uiseong) to 15% (Yeongdeok) of the states, and its solver allocates more.
  **Both changes together** are as fast as the scalar path alone (1.8× to 2.8×), not faster.
* **Memory is lighter overall, not on every field.** Summed over each cache's specs, the scalar solver's peak
  allocation is **46% to 58% of the baseline's** on all six caches (both changes: 54% to 67%). Its finished field
  keeps 1.7 to 4.4 MiB, against 13.5 to 32.4 MiB, on the caches where every state is scalar. But on the three caches that have some interval states (UA 03-24,
  UA 03-25, YD 03-26), the **largest single spec** allocates 11% to 31% more than the baseline. The whole-process peak
  RSS is "not distinguished" on every cache: the field is a small part of the process (graph, packet model, witnesses).
* **Fast-path share.** With the hypotheses checked per state on their usable windows, the scalar share is 100%
  (UA 03-23, YD 03-25 19Z and 23Z), 99.4% (YD 03-26), 96.9% (UA 03-25) and **93.9% (UA 03-24)**. With the plain
  THEOREM.md hypotheses it would be 4.9% on UA 03-24: the 88 reopening edges reach almost every state. The window
  that changes this is sound (§A.2).
* **Verdict under PROTOCOL.md §5** ("lighter" read strictly: lower both summed over the specs and on the largest spec).
  * Change 1 **partly passes**: correctness gate passed, field faster on all six caches, lighter on three (UA 03-23,
    YD 03-25 19Z, YD 03-25 23Z), not lighter on UA 03-24, UA 03-25 and YD 03-26 (largest spec heavier).
  * Change 2 **partly passes**: gate passed, faster on two caches, heavier on all six.
  * Both together **partly pass**: as for change 1.

## B. Results

Machine: Apple M5 Pro (5 performance and 10 efficiency cores), 24 GB, macOS 27.0.1, Python 3.13.13 (conda-forge),
numpy 2.5.0 (`runs/HOST.json`). Code: `fastfield.py` as frozen with the protocol (`runs/COMMITS.txt`). The 360 timed
runs ran from 23 Nov 2026 08:43 to 14:10 UTC, one at a time, inside the Claude Code command sandbox (macOS
Seatbelt), which applies to all four solvers alike. The 1-minute load average before a run was 1.8 to 18.9 (median
5.0). This is the user's working Mac, not an idle machine. No run failed, none was dropped or re-run. Full tables for
all 18 job sets: `results/tables.md`; numbers: `results/RESULTS.json`; raw files: `runs/`.

### B.1 Equality (untimed)

| cache | specs | E1 origin sets | E2 states compared (per variant) | E3 jobs (routes) | E5 guard checks | differences |
|---|---|---|---|---|---|---|
| UA 03-23 | 32 | 254 | 1,402,432 | 1,523 (1,188) | 96 | 0 |
| UA 03-24 | 31 | 253 | 1,358,606 | 1,518 (1,158) | 93 | 0 |
| UA 03-25 | 31 | 253 | 1,358,606 | 1,557 (1,068) | 93 | 0 |
| YD 03-25 19Z | 153 | 272 | 17,124,372 | 1,810 (1,522) | 459 | 0 |
| YD 03-25 23Z | 152 | 271 | 17,012,448 | 1,673 (1,512) | 456 | 0 |
| YD 03-26 | 152 | 271 | 17,012,448 | 1,641 (1,522) | 456 | 0 |
| **all** | 551 | **1,574** | | **9,722 (7,970)** | 1,653 | **0** |

Each row holds for all five variants: `scalar`, `prune`, `both`, and `scalar` and `both` with the plain hypotheses
(`results/eq_*.json`). E4 (`results/random.json`): 6,000 instances, 627,252 state sets, 275,388 origin sets,
1,688,910 witnesses (166,851 also checked by `checker.check_route`), 15,961 brute-force origin sets, 36,000
fixed-point certificates, 78,858 guard checks: **0 differences**. Mutants (`results/mutants.json`, 300 instances
per family) all caught: hypotheses M1/M2 assumed 1,908; M3 assumed 1,718; pruning bound +1 s 1,871; bound not a
lower bound 838; no origin guard 14,958; destination window 1 s too narrow 222; unmutated 0.

### B.2 Field time, `full` job sets (5 repeats; ratio = baseline ÷ solver, median [min÷max, max÷min])

| cache | baseline s | scalar s | ratio | prune s | ratio | both s | ratio |
|---|---|---|---|---|---|---|---|
| UA 03-23 | 6.84 | 2.61 | **2.62** [2.27–3.27] faster | 4.84 | 1.41 [1.21–1.77] faster | 2.41 | **2.84** [2.68–3.49] faster |
| UA 03-24 | 7.16 | 2.87 | **2.50** [1.79–2.67] faster | 5.18 | 1.38 [1.27–1.49] faster | 2.68 | **2.67** [2.31–2.83] faster |
| UA 03-25 | 4.86 | 2.46 | **1.97** [1.75–2.39] faster | 4.79 | 1.01 [0.80–1.21] not distinguished | 2.52 | **1.93** [1.53–2.27] faster |
| YD 03-25 19Z | 52.10 | 29.31 | **1.78** [1.63–2.17] faster | 60.58 | 0.86 [0.74–1.02] not distinguished | 29.69 | **1.76** [1.53–2.07] faster |
| YD 03-25 23Z | 61.56 | 29.58 | **2.08** [1.82–2.51] faster | 66.71 | 0.92 [0.86–1.23] not distinguished | 30.56 | **2.01** [1.82–2.45] faster |
| YD 03-26 | 72.79 | 32.43 | **2.24** [2.08–2.87] faster | 63.97 | 1.14 [0.94–1.46] not distinguished | 32.44 | **2.24** [1.99–2.88] faster |

The `pass1` and `repeat` job sets give the same picture (scalar and both faster on all 12, prune faster on 3 of 12;
`results/tables.md`).

### B.3 Whole run, `full` job sets (wall; the run also loads the graph and packet, builds instances, reads off every job and extracts witnesses)

| cache | baseline s | scalar ratio | prune ratio | both ratio |
|---|---|---|---|---|
| UA 03-23 | 11.8 | 1.57 [1.28–1.94] faster | 1.20 [1.01–1.48] faster | 1.54 [1.44–1.93] faster |
| UA 03-24 | 67.8 | 1.07 [0.65–1.18] not distinguished | 1.04 [0.90–1.15] not distinguished | 1.06 [0.94–1.18] not distinguished |
| UA 03-25 | 40.5 | 0.99 [0.84–1.25] not distinguished | 0.99 [0.71–1.22] not distinguished | 1.02 [0.86–1.23] not distinguished |
| YD 03-25 19Z | 121.9 | 1.23 [1.06–1.55] faster | 1.00 [0.86–1.20] not distinguished | 1.23 [1.02–1.47] faster |
| YD 03-25 23Z | 128.4 | 1.40 [1.19–1.75] faster | 0.97 [0.90–1.33] not distinguished | 1.35 [1.18–1.70] faster |
| YD 03-26 | 142.5 | 1.44 [1.32–1.85] faster | 1.13 [0.94–1.45] not distinguished | 1.44 [1.27–1.86] faster |

On UA 03-24 and UA 03-25 the witness routes take most of the run (about 55 s and 30 s of 68 s and 41 s), and they
are untouched by either change. The two changes speed up building the field, not extracting routes from it.

### B.4 Memory (untimed probe, `tracemalloc` around each solver call, `full` job sets)

| cache | baseline peak, sum over specs / largest spec, MiB | scalar | prune | both | field kept, largest spec: baseline / scalar |
|---|---|---|---|---|---|
| UA 03-23 | 541 / 17.5 | **248 / 7.8** | 579 / 21.7 | 294 / 9.5 | 13.5 / 1.7 |
| UA 03-24 | 510 / 17.5 | 264 / *19.5* | 558 / 21.3 | 305 / *19.4* | 13.5 / 11.2 |
| UA 03-25 | 440 / 15.7 | 253 / *20.6* | 544 / 19.4 | 295 / *19.7* | 11.7 / 12.4 |
| YD 03-25 19Z | 5,543 / 41.4 | **3,025 / 19.8** | 6,602 / 51.0 | 3,737 / 33.0 | 31.2 / 4.4 |
| YD 03-25 23Z | 5,788 / 42.6 | **3,008 / 19.8** | 6,648 / 52.2 | 3,717 / 33.0 | 32.4 / 4.4 |
| YD 03-26 | 6,350 / 45.5 | 3,046 / *55.6* | 6,835 / 53.2 | 3,746 / *50.7* | 35.2 / 34.4 |

Italics: the largest single spec is heavier than the baseline's. Every one of these is a cache with some interval
states (§B.5). When a field mixes the two kinds, the solver holds the per-state arrays of the scalar phase (latest
times, windows, kinds, hypothesis flags, the destination bound) **and** the interval lists of the dirty states, so a
spec dominated by interval states costs more than the baseline. When every state is scalar, the field shrinks to a
few integers per state. Peak RSS of the whole process: "not distinguished" on every cache (`results/tables.md`).

### B.5 Fast-path share per cache (share of (spec, state) pairs, all specs; from `results/eq_*.json`)

| cache | scalar, windowed (benchmarked) | scalar, plain THEOREM.md M1–M3 | both: scalar / interval / pruned away |
|---|---|---|---|
| UA 03-23 | 100% | 100% | 93.0% / 0% / 7.0% |
| UA 03-24 | 93.9% | **4.9%** | 87.0% / 6.0% / 7.0% |
| UA 03-25 | 96.9% | 96.9% | 90.0% / 3.0% / 7.0% |
| YD 03-25 19Z | 100% | 100% | 85.4% / 0% / 14.6% |
| YD 03-25 23Z | 100% | 100% | 85.3% / 0% / 14.7% |
| YD 03-26 | 99.4% | 99.4% | 84.7% / 0.5% / 14.8% |

No state was "R-clean only" (no late-opening shelter reached a clean state). The interval states on UA 03-25 and
YD 03-26 come from the late-opening shelter windows (M3), and on UA 03-24 from the reopening roads that can still
be used before H.

### B.6 What this means

* For a deadline field, keep change 1. It is exact by construction (Theorem B) and by test (zero differences on
  every set, answer and route). It halves the field time, and it needs no assumption from the data: where the data
  break the hypotheses, those states fall back to intervals.
* Change 2 is exact (§A.3), but on these caches the forward bound removes too little to pay for the forward search
  and the clipping. It may pay off when the origins are few and far from most of the graph, which is not the case
  for any recorded spec.
* Memory: one integer per scalar state is lighter only when nearly every state is scalar. A mixed field should not
  allocate the scalar arrays for interval states. That is a possible follow-up, **not** measured here.

### B.7 Not as planned, and limits

* E1–E3/E5 on UA 03-24 were split over six processes (PROTOCOL Amendment A1). The timing was not affected (it
  ran afterwards, alone).
* macOS cannot pin a process to one core. Each run was one single-threaded process, run strictly one after another.
  The machine was in use (load above).
* The runs went through the command sandbox of the session. All four solvers ran under it alike.
* The repeat-1 per-job answers (about 150 MB) were kept outside the repository; their SHA-256 digests are in the
  committed run files.
* Not claimed: other machines, other data, a compiled version, physical safety of any route.


## A. Proofs

Notation and the model are those of `research/kcf-theorem/THEOREM.md` §1. R\*_s, G\*_s are the true sets
(THEOREM.md §1), and (E) is the one-step equation of its Lemma 1.1. Every journey move takes at least one second.

### A.1 Lower bounds used by both changes

**Forward bound e (change 2).** With pruning for a source set σ (the origins of the field), e(v) is the shortest
travel time from σ to v over the road graph with D as lengths, ignoring closures, waits, turns and acceptance;
e(v) = 0 for v ∈ σ, e(v) = ∞ if unreachable. Without pruning, e ≡ 0. Put Λ_s = e(tail s) + D_s with pruning
(capped at H + 1), and Λ_s = 0 without. Three facts:

* (F1) For an allowed successor j of s, tail(j) = head(s) and e(head s) ≤ e(tail s) + D_s, so
  e(tail j) ≤ Λ_s. (Without pruning both sides are 0.)
* (F2) Λ_j ≤ Λ_s + D_j for an allowed successor j of s (from F1). 
* (F3) A journey from a source o ∈ σ departing at any t ≥ 0 is at node v only at seconds ≥ e(v), starts an edge j
  only at seconds ≥ e(tail j), and arrives over j only at seconds ≥ e(tail j) + D_j. *Proof:* its moves form a walk
  from o to v whose length (sum of D) is ≥ e(v), and waits only add time. ∎

**Destination bound h (change 1, windows).** h = `core.static_to_dest`: h(head j) = 0 when A_j ≠ ∅, and h(u) ≤ D_j +
h(head j) for every edge j = (u, ·). (F4) From any configuration at node v and second x, every accepting
configuration reachable is at a second ≥ x + h(v). *Proof:* by induction on the moves (an edge move adds D_j ≥ h(u) −
h(head j), a wait adds 1), and the final configuration is (head e, e, τ, 1) with τ ∈ A_e, so A_e ≠ ∅ and h(head e) =
0. ∎ Consequently a move that is part of an accepted journey starts an edge j at τ ≤ up_j := H − D_j − h(head j),
and a wait at v at τ ≤ H − 1 − h(v).

**Windowed sets.** R'_s = R\*_s ∩ [Λ_s, H] and G'_s = G\*_s ∩ [Λ_s, H]. Without pruning, R' = R\* and G' = G\*.

**Lemma W (windowed equation).** For every state s and t ∈ [Λ_s, H]: t ∈ R\*_s iff
(i) some allowed successor j has t ∉ B_j and t + D_j ∈ G'_j, or (ii) head(s) is waitable, t ∉ W_head(s) and
t + 1 ∈ R'_s. The family (R'_s) is the **unique** family X_s ⊆ [Λ_s, H] with X_s = {t ∈ [Λ_s, H] : (i) or (ii) with
G' replaced by X ∪ (A ∩ window)}.

*Proof.* (E) says the same with G\*_j and R\*_s. By F2, t + D_j ≥ Λ_s + D_j ≥ Λ_j, so G\*_j and G'_j agree at
t + D_j; and t + 1 ≥ Λ_s. Uniqueness: each condition at t refers only to seconds t + D_j > t and t + 1 > t, so a
downward induction on t from H fixes membership (THEOREM.md Lemma 1.2). ∎

### A.2 Change 1: which states may use one number, and why the mixed solver is exact

**Hypotheses, per state, checked on the instance.** Windows: lo_j = e(tail j) for edge starts, lo_v = e(v) for
waits (0 without pruning), up_j as above (with `windows=False`: up_j = H − D_j and H − 1, the plain THEOREM.md
windows).

* M1'(j): B_j ∩ [lo_j, up_j] is empty or [c, up_j]. c_j = its first element, or up_j + 1 if empty.
* M2'(v): for waitable v, W_v ∩ [lo_v, H − 1 − h(v)] is empty or reaches H − 1 − h(v).
* M3'(s): A_s ∩ [Λ_s, H] is empty or [Λ_s, a'_s].

**R-clean / G-clean** is the largest set of states with: s R-clean ⇒ M2'(head s) when waitable, and every allowed
successor j satisfies M1'(j) and is G-clean; s G-clean ⇔ s R-clean and M3'(s). The solver computes the complement by
spreading "dirty" backwards from the states that fail a check (`fastfield.solve`). States with Λ_s > H ("void")
have empty windowed sets, which are empty intervals; they are G-clean by definition and do not spread dirt (an edge
with Λ_j > H has an empty M1' window, so it cannot fail M1'). The hypotheses are **checked**, never assumed: a state
is scalar only if its own checks and those of every state it can reach pass.

**Theorem A (shifting earlier, per state).** If s is R-clean, t ∈ R'_s and Λ_s ≤ t' < t, then t' ∈ R'_s. If s is
G-clean, the same holds for G'_s.

*Proof.* Take an accepting journey π from (head s, s, t, α) (α = 0 for R; for G, either t ∈ A_s and π is empty, or
α = 0 and t ∈ R\*_s). Put δ = t − t' > 0 and let π' make the same moves, each δ seconds earlier.

* *Every state π passes through is G-clean, and every edge it takes satisfies M1'.* π's edges j₁, j₂, … form a chain
  of allowed successions s → j₁ → j₂ → … (waits keep the last edge). R-clean(s) gives M1'(j₁) and G-clean(j₁);
  G-clean(j_k) ⇒ R-clean(j_k) ⇒ M1'(j_{k+1}) and G-clean(j_{k+1}). Every wait happens at head(s) or at
  head(j_k), where R-cleanness gives M2'.
* *Edge moves stay legal.* Let π start j at τ ≥ t. Then τ ∉ B_j, and τ ≤ up_j by F4 because π is accepting.
  Lower end: π reaches tail(j) from head(s), so τ − t ≥ the fire-free distance d from head(s) to tail(j), and
  e(tail j) ≤ e(head s) + d ≤ Λ_s + d (F1) ≤ t' + (τ − t) = τ − δ. So τ − δ and τ both lie in [lo_j, up_j].
  If τ − δ were in B_j, M1' (upward closed in the window) would put τ in B_j. So π' may start j at τ − δ, and it
  ends at τ − δ + D_j ≤ H. Turns are unchanged.
* *Waits stay legal*, by the same argument with M2' and the window [e(v), H − 1 − h(v)].
* *The end is still accepted.* A non-empty accepting journey ends with an edge move over some e at τ_end ∈ A_e
  (a wait clears admission). τ_end − δ ≥ e(tail e) + D_e = Λ_e by the bullet above (0 without pruning), and
  τ_end ≤ H; M3'(e) says A_e ∩ [Λ_e, H] = [Λ_e, a'_e] ∋ τ_end, so τ_end − δ ∈ A_e. If π is empty, t ∈ A_s and
  M3'(s) gives t' ∈ A_s.
* t' ≥ Λ_s, so t' is in the window of s. ∎

**Theorem A' (one number per clean state).** For R-clean s, R'_s = [Λ_s, r_s] (empty if r_s < Λ_s) with

  r_s = max over allowed successors j with G'_j ≠ ∅ of τ'_j(ℓ_j),  τ'_j(x) = min(c_j − 1, x − D_j),

and for G-clean s, G'_s = [Λ_s, ℓ_s] with ℓ_s = max(a'_s, r_s). These equations have exactly one solution.

*Proof.* By Theorem A, R'_s is empty or an interval starting at Λ_s; only its end is unknown. Lemma W: a point of
type (ii) has t + 1 ∈ R'_s, so it is never the maximum. Type (i) for a successor j (G-clean, so G'_j = [Λ_j, ℓ_j]):
let u = ℓ_j − D_j. By F4, ℓ_j ≤ H − h(head j), so u ≤ up_j. For t ∈ [Λ_s, u]: t + D_j ≥ Λ_s + D_j ≥ Λ_j (F2) and
≤ ℓ_j, so t + D_j ∈ G'_j; t ≥ Λ_s ≥ lo_j (F1) and t ≤ up_j, so t lies in the M1' window, where t ∉ B_j ⇔ t < c_j.
For t > u, t + D_j > ℓ_j. So the type-(i) set for j is exactly [Λ_s, min(c_j − 1, u)], and r_s is the largest end.
G'_s = R'_s ∪ (A_s ∩ [Λ_s, H]) is a union of two intervals starting at Λ_s. Uniqueness: τ'_j(x) ≤ x − D_j < x,
so the argument of THEOREM.md Theorem 2(b) applies (pick a state where two solutions differ with the larger value
largest; it is a τ' of a successor with a strictly larger value, where they agree). ∎

**The scalar phase computes that solution.** It is a reverse Dijkstra on ℓ: seeds ℓ = a'_s for G-clean states with
A_s ∩ [Λ_s, H] ≠ ∅; popping j with its current value ℓ_j gives each clean predecessor s the candidate v = τ'_j(ℓ_j)
(kept only if v ≥ Λ_s); r_s keeps the maximum, and a G-clean s whose value rises is pushed again; stale heap
entries are skipped. (a) Every value ever stored is ≤ the true one (it is a term of the right-hand side evaluated
at values ≤ the true ones, and τ' is non-decreasing). (b) Suppose some G-clean s ends below its true ℓ_s ≥ Λ_s;
take the largest such ℓ_s. It is not a'_s (seeded), so ℓ_s = τ'_j(ℓ_j) with ℓ_j > ℓ_s; by the choice of s, j ends
at ℓ_j, so it was pushed with that value and popped with it, and that pop gave s the value ℓ_s. Contradiction. The
same pop argument gives r_s for every R-clean s, because all its successors are G-clean. ∎

**Theorem B (the mixed solver is exact).** After both phases, the solver's R_s and G_s equal R'_s and G'_s for
every state s.

*Proof.* Clean and void states: Theorem A' and the scalar phase (void: both sides empty). The clean set is closed
under allowed successors, so no clean state's equation mentions a dirty state, and the clean values are final
before the interval phase starts. The interval phase is `core.backward`'s loop with three differences: only dirty
predecessors are updated; each clean successor j that has a dirty predecessor is entered once, with its whole
(exact) G'_j as heap pieces; and every piece added to a dirty R_s, including the waiting closure, is cut to
[Λ_s, H]. The five steps of THEOREM.md Theorem 1 go through with Lemma W in place of (E):

1. *Soundness.* A second t enters a dirty R_s from a popped piece of G'_j: t ∈ [Λ_s, H], t ∉ B_j, t + D_j ∈ G'_j
   (popped pieces are subsets of G'_j: exact for clean j, by induction for dirty j), so t ∈ R'_s by Lemma W(i). The
   waiting closure adds [max(w + 1, Λ_s), lo − 1] below a piece starting at lo, where w is the last wait-closed
   second below lo: none of these seconds is in W_v, and t + 1 ∈ R'_s by downward induction from lo, so Lemma W(ii)
   applies.
2. *Termination.* Every push after the seeds adds at least one new second to some R_s.
3. *Every second of every final G'_j that a dirty state reads lies in a popped piece*: clean G'_j is pushed whole;
   dirty A_j ∩ [Λ_j, H] is seeded; every new second of a dirty R_j outside A_j is pushed.
4. *Closure.* If t ∈ [Λ_s, H], t ∉ B_j and t + D_j ∈ G'_j, then t + D_j lies in a popped piece [lo, hi], and in
   that pop t ∈ [max(lo − D_j, 0), hi − D_j] \ B_j, cut to [Λ_s, H], so t ends in R_s. If u ∈ R_s, u − 1 ≥ Λ_s and
   u − 1 ∉ W_v, then u entered inside a closed piece [lo', hi] with lo' = Λ_s or lo' − 1 ∈ W_v; u ≠ lo' (u = lo'
   would give either u − 1 < Λ_s or u − 1 ∈ W_v), so u − 1 ∈ [lo', hi] ⊆ R_s.
5. *Completeness.* Downward induction on t with Lemma W and step 4.

So the dirty R_s solve the windowed equation with the clean sets fixed at their true values, and by the uniqueness in
Lemma W they are the true R'_s. G_s = R_s ∪ (A_s ∩ [Λ_s, H]) = G'_s. ∎

So the **mixed solver is sound**, and it is used. A whole-instance fallback is the case where every state is dirty,
which the solver handles with the same code. Without pruning (Λ ≡ 0) the sets are exactly `core.backward`'s.

**Why `windows=True` is allowed.** The only difference from THEOREM.md's M1–M3 is the upper end up_j = H − D_j −
h(head j) (and H − 1 − h(v) for waits). Theorem A uses the window only at seconds τ that start a move of an
accepting journey, and F4 puts every such τ inside it. A road that reopens after up_j cannot be used by any journey
that still reaches a shelter by H, so that reopening cannot change any set. On UA 03-24 this is the difference
between about 5% and about 94% of states on the fast path (§C).

**M4 is not needed.** The origin read-off stays `core.issue_set` (interval form), which subtracts any IB_o and adds
AN_o without any monotonicity.

### A.3 Change 2: pruning cannot change Feas(o), any departure, or any witness route

Let o be a source of the forward search (o ∈ σ) and t ≥ 0.

1. *No journey uses a discarded second.* By F3, every journey from o departing at t ≥ 0 arrives over any edge s
   only at seconds ≥ e(tail s) + D_s = Λ_s, and stands at head(s) after arriving over s only at seconds ≥ Λ_s
   (waiting only moves later). The discarded parts of R_s and G_s are exactly the seconds below Λ_s. So no journey,
   from any source, at any departure, ever occupies a (state, second) pair that was discarded.
2. *Feas(o) is unchanged.* `core.issue_core` reads G_j for the edges j out of o at seconds t + D_j with t ≥ 0. Since
   e(o) = 0, Λ_j = D_j (capped at H + 1, and an edge with D_j > H is never usable), so (G'_j − D_j) ∩ [0, ∞) =
   (G\*_j − D_j) ∩ [0, ∞): the discarded seconds of G_j are exactly those that would shift below 0. The waiting
   closure at o, AN_o and IB_o are read as before. So Feas(o) is the same set, second by second.
3. *Every witness route is unchanged.* `core.witness` (and `witness_greedy`) start at (o, t) and test only
   membership of an arrival second in G_j or of a waiting second in R_s for configurations reachable from (o, t).
   By point 1 each tested second is ≥ the window start, where the pruned and unpruned sets agree. Every test gives
   the same answer, so the search visits the same states in the same order and returns the same journey.
4. *Origins outside the search.* For o ∉ σ, e(o) may be > 0 and point 2 fails (a set may have lost seconds that o
   could use). `fastfield.issue_set` and `fastfield.witness` therefore refuse such an origin, and with
   `fallback=True` solve an unpruned field for it: pruning is off for every origin that was not in the forward
   search. ∎

### A.4 What the tests add to the proofs

The proofs are about the model; the tests check the code. E1–E3 and E5 compare every origin set, every state set,
every job's answer and witness route on all six recorded caches with the unchanged `core.backward`; E4 does the same
on 6,000 random instances and against brute force on 4,000 of them; `mutants.py` shows that each of seven ways of
getting the rules wrong (hypotheses assumed, either bound off by one second, a bound that is not a lower bound, the
origin guard removed) is caught. The windowed fixed-point certificate (`fastfield.check_fixed_point`) is checked on
every fast field: by the uniqueness in Lemma W it certifies the stored sets independently of how they were computed.
