# kcf-fastpath: a faster, lighter deadline field with the same answers

Protocol: `PROTOCOL.md` (frozen at `c1213cb3`, before any fast solver was timed; amendments at its end). Code:
`fastfield.py` (the solver), `run_fast.py` (benchmark runner), `eq_real.py`, `test_fastfield.py`, `mutants.py`
(equality tests), `bench.sh`, `summarize.py`. `deadline_field/core.py` is unchanged and is the baseline.

<!-- RESULTS -->

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
