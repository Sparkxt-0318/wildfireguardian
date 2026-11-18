# The one-pass margin field

Stage 3 of `research/kcf-idea-routing`. Code: `margin_field/pl.py`, `margin_field/field.py`. The existing code in
`research/harness-2026-11/F-3.1/deadline_field` is used read-only and is not changed. Model and notation are those
of `research/kcf-theorem/THEOREM.md` §1 ("THEOREM" below).

## 0. Result in four lines

* **What it returns.** For every edge state s and second t, the number μ_s(t): the largest safety margin m (in
  seconds) such that t is still in the deadline field when **every closure is widened by m seconds on both sides**
  (the road closes m seconds earlier and reopens m seconds later). One pass returns this for all margins 0..M.
* **Exactness (Theorem 1).** {t : μ_s(t) ≥ m} is exactly the F-3.1 field of the m-widened instance, for every m.
* **Meaning (Theorem 2).** μ_o(t) ≥ m iff departure t has one route that stays valid whenever every closure boundary
  is wrong by at most m seconds. It cannot be read off the windows (Proposition 3).
* **Algorithm (Theorems 4, 5).** Every function involved is piecewise linear in t with slopes −1, 0, +1. One
  heap-ordered backward pass over such functions computes μ. Its cost is stated in pieces, not in M.

What is and is not new is in §6. In short: Theorem 1 is an instance of a published general theorem; the algorithm and
its exactness for this model were not found in the literature.

## 1. The margin family

Fix an instance I = (graph, D, forbidden turns, waitable nodes, H, B, W, A, IB, AN) as in THEOREM §1, and a largest
margin M ≥ 0. For a set X ⊆ ℤ and m ≥ 0 write

  X ⊕ m = {t : |t − x| ≤ m for some x ∈ X}  (widening),  X ⊖ m = {t : [t − m, t + m] ⊆ X}  (narrowing).

**The m-widened instance I(m)** has the same graph, D, turns, waitable nodes and H, and

  B_j(m) = B_j ⊕ m, W_v(m) = W_v ⊕ m, IB_o(m) = IB_o ⊕ m.

Acceptance has two variants, chosen by the caller (`erode_accept`):
* **keep**: A_j(m) = A_j, AN_o(m) = AN_o (shelter windows are not uncertain);
* **erode**: A_j(m) = A_j ⊖ m, AN_o(m) = AN_o ⊖ m (also the m seconds next to each end of an acceptance interval are
  dropped).

I(0) = I. In code: `field.widen(inst, m, erode_accept=...)`.

**Level functions.** For t ∈ ℤ define, with max ∅ = −1 ("bottom"):

  β_j(t) = max{m ∈ {0..M} : t ∉ B_j(m)} = min(M, dist(t, B_j) − 1),

where dist(t, X) = min_{x ∈ X} |t − x| (∞ if X = ∅). So β_j(t) = −1 iff t ∈ B_j. In the same way ω_v from W_v, ι_o
from IB_o, and for acceptance α_j(t) = max{m ≤ M : t ∈ A_j(m)}: in the keep variant α_j = M on A_j and −1 elsewhere;
in the erode variant α_j(t) = min(M, dist(t, ℤ \ A_j) − 1). β_j is restricted to t ∈ [0, H − D_j] and ω_v to
[0, H − 1] (a move must end by H); outside they are −1.

**(L)** For every m ∈ {0..M}: t ∉ B_j(m) ⟺ β_j(t) ≥ m, and likewise for ω, ι, α. *Proof.* The sets B_j(m) grow with
m, so {m : t ∉ B_j(m)} is an initial segment of {0..M}; its maximum is β_j(t). ∎

**The margin field.** With R\*_s(m), G\*_s(m), Feas(o; m) the truth sets of THEOREM §1 for I(m):

  μ\*_s(t) = max{m ∈ {0..M} : t ∈ R\*_s(m)},  γ\*_s(t) = max{m : t ∈ G\*_s(m)},  μ\*_o(t) = max{m : t ∈ Feas(o; m)},

each −1 if the set is empty (in particular for t ∉ T).

## 2. Theorem 1: threshold decomposition

**Lemma 2.1 (nested).** If m ≤ m′ then R\*_s(m′) ⊆ R\*_s(m), G\*_s(m′) ⊆ G\*_s(m), Feas(o; m′) ⊆ Feas(o; m).
Hence t ∈ R\*_s(m) ⟺ μ\*_s(t) ≥ m for all m ∈ {0..M}, and likewise for γ\* and μ\*_o.

*Proof.* A journey is valid iff its edge starts avoid B, its wait seconds avoid W, its departure avoids IB, its turns
are allowed, its moves end by H, and its final arrival is in A (THEOREM §1). I(m′) has larger B, W, IB and smaller A
than I(m), and everything else is equal. So a journey valid in I(m′) is valid in I(m). The set of m with
t ∈ R\*_s(m) is therefore an initial segment, and its maximum is μ\*_s(t). ∎

**Theorem 1.** (a) μ\* is the unique family of functions μ_s : ℤ → {−1, 0, …, M}, equal to −1 outside T, with

  μ_s(t) = max( max_{j : tail(j) = head(s), (s, j) ∉ F} min(β_j(t), γ_j(t + D_j)),
         [head(s) ∈ Wt] min(ω_head(s)(t), μ_s(t + 1)) ),  γ_j = max(α_j, μ_j).  (E_μ)

(b) For every m ∈ {0..M} and every edge state s: {t : μ\*_s(t) ≥ m} = R\*_s(m) and {t : γ\*_s(t) ≥ m} = G\*_s(m).
These are the sets the existing `backward` returns on I(m) (THEOREM, Theorem 1).

(c) For an origin o: μ\*_o = min(ι_o, max(α^N_o, c_o)), where c_o is the waiting closure (§3.3) of
X_o(t) = max_{j out of o} min(β_j(t), γ\*_j(t + D_j)) if o is waitable, and c_o = X_o otherwise; α^N_o is the level
function of AN_o. And {t : μ\*_o(t) ≥ m} = Feas(o; m) = `issue_set` on I(m).

*Proof.* (b) is Lemma 2.1. For (a), fix s, t ∈ T and m ∈ {0..M}. THEOREM Lemma 1.1 applied to I(m) says
G\*_j(m) = A_j(m) ∪ R\*_j(m) and

  t ∈ R\*_s(m) ⟺ (∃ allowed j: t ∉ B_j(m) and t + D_j ∈ G\*_j(m)) or (head(s) ∈ Wt, t ∉ W(m), t + 1 ∈ R\*_s(m)).

By (L) and Lemma 2.1 the right side reads: (∃ j: β_j(t) ≥ m and γ\*_j(t + D_j) ≥ m) or (ω(t) ≥ m and
μ\*_s(t + 1) ≥ m). Since min(x, y) ≥ m iff both are, and a maximum is ≥ m iff one term is, this is exactly
"the right side of (E_μ), evaluated on μ\*, is ≥ m at t". The left side is "μ\*_s(t) ≥ m". Two numbers in
{−1..M} that pass the same thresholds m = 0..M are equal. The same argument gives γ\* = max(α, μ\*). So μ\* solves
(E_μ). *Uniqueness:* the right side of (E_μ) at t uses only values at t + D_j > t and t + 1 > t (C1). Two solutions
agree for t > H (both −1), hence, by induction downwards on t, everywhere.

(c) is the same argument applied to the origin read-off in the proof of THEOREM Theorem 1: the first-move set is the
union over out-edges, closed under waiting at o when o is waitable; AN_o is added without waiting closure; IB_o is
removed. Each step is a union (max), an intersection with a complement of a closure (min with a level function) or
the waiting closure, whose threshold form is Lemma 3.3(a). ∎

## 3. Theorem 2 and Proposition 3: what the number means

**Perturbation class.** 𝒫(m) is the set of instances I′ with the same graph, D, turns, waitable nodes and H as I and
B′_j ⊆ B_j(m), W′_v ⊆ W_v(m), IB′_o ⊆ IB_o(m), A′_j ⊇ A_j(m), AN′_o ⊇ AN_o(m). It contains every instance obtained
from I by moving each start and each end of each closure interval by at most m seconds (and, in the erode variant,
each end of each acceptance interval), or by deleting closures.

**Theorem 2.** For an origin o, a second t and m ∈ {0..M} the following are equivalent:
1. μ\*_o(t) ≥ m;
2. there is **one** journey from o departing at t that is valid in every I′ ∈ 𝒫(m);
3. for every I′ ∈ 𝒫(m) there is **some** journey from o departing at t valid in I′.

*Proof.* (1 ⟹ 2) By Theorem 1(c) there is a journey valid in I(m). Validity only asks that certain seconds are
outside the closure sets and one second is inside an acceptance set; I′ has smaller closure sets and larger
acceptance sets than I(m). (2 ⟹ 3) is trivial. (3 ⟹ 1) I(m) itself is in 𝒫(m). ∎

So the robust reading (one route for all errors) and the adaptive reading (a route for each error) coincide, because
I(m) is the worst member of 𝒫(m) in every component at once. This would fail for an additive quantity such as a dose
summed along the route with member-dependent doses (`SURVEY.md` §5).

**Proposition 3 (the margin is not the distance to the edge of the window).** In the erode variant, if
μ\*_o(t) ≥ m then every t′ ≥ 0 with |t′ − t| ≤ m is a feasible departure of I, with the same route shifted by t′ − t.
So μ\*_o(t) ≤ min(M, d − 1), where d is the distance from t to the nearest infeasible second of I at or above 0. The
inequality can be strict by any amount.

*Proof.* Take the journey valid in I(m) and start every move t′ − t seconds later (or earlier). Each edge start u
moves to u′ with |u′ − u| ≤ m, and u ∉ B_j ⊕ m gives u′ ∉ B_j; the same for waits and the departure. The final
arrival a ∈ A_j ⊖ m gives a′ ∈ A_j ⊆ T, so every move still ends by H; starts stay ≥ t′ ≥ 0. Turns are unchanged.
*Strictness:* two parallel edges 0 → 1, D = 1, H = 12, A = [0, 12]; edge 1 has B = [6, ∞), edge 2 has B = [0, 5].
Feas(0) = [0, 11]: one unbroken window. The nearest infeasible second to 5 is 12, so the bound gives 6. But at margin
m ≥ 1 edge 1 is open only up to 5 − m and edge 2 only from 6 + m, so μ\*_0(5) = 0. ∎
(`tests/test_margin_field.py::test_two_route_example`.)

This is why a wide window is not evidence of a safe leave-by time: the window can be the union of two routes' windows
that meet where one road closes and another opens.

## 4. The algorithm

### 4.1 Tent functions

**Definition.** 𝒯 is the set of functions f : ℤ → {−1} ∪ ℕ with finite support {f ≥ 0} that are given by finitely
many pieces (lo, hi, v, σ): f(t) = v + σ(t − lo) on the integer interval [lo, hi], σ ∈ {−1, 0, +1}, all values ≥ 0,
pieces disjoint. |f| is the number of pieces in the greedy-maximal form (`pl.canon`).

**Lemma 4.1 (closure).** If f, g ∈ 𝒯 then so are t ↦ f(t + d) (shift), the restriction of f to an interval, min(f, g)
and max(f, g), and they are computed in O(|f| + |g|) time by one merge of the two piece lists.

*Proof.* Shift and restriction are immediate. On an integer interval where both are linear, f − g is linear with slope
in {−2, …, 2}, so it changes sign at most once; the interval splits at an integer into at most two parts on each of
which min (and max) is one of the two pieces. The split point is ⌊−d₀/δ⌋ past the left end, d₀ the difference at the
left end and δ its slope (`pl.pmin`, `pl.raise_to`). The crossing of a +1 and a −1 line can fall on a half-integer;
on the grid the two integer neighbours are each on one piece, so nothing is lost. The merge visits each piece
once. ∎

**Lemma 4.2 (level functions are tents).** β_j, ω_v, ι_o and α_j are in 𝒯, with at most 3 pieces per gap between
consecutive closure intervals (rise, flat at M, fall).

*Proof.* Between two consecutive closure intervals with last second ℓ and first second r,
min(M, dist(t, B) − 1) = min(M, t − ℓ − 1, r − t − 1). Before the first or after the last interval one of the terms
is absent. ∎ (`pl.tent`.)

### 4.2 The waiting closure

For μ, ω ∈ 𝒯 let cl_ω(μ) be the least function c with c ≥ μ and c(t) ≥ min(ω(t), c(t + 1)) for all t.

**Lemma 4.3.** (a) cl_ω(μ)(t) = max_{u ≥ t} min( μ(u), min_{t ≤ x < u} ω(x) ) (the inner minimum is +∞ for u = t).
Its level set at m is the downward waiting closure of {μ ≥ m} under the wait mask {ω < m}, i.e. `_wait_close` of the
existing code applied to I(m).

(b) Let ω be linear on [x, y] (one piece) and c = cl_ω(μ). Then for t ∈ [x, y]

  c(t) = max( μ(t), min( ω(t), max( Q(t + 1), min(c(y + 1), ω(y)) ) ) ),  Q(t + 1) = max_{t < u ≤ y} min(μ(u), ω(u − 1)),

with Q(y + 1) = −1. Outside the support of ω, c = μ.

(c) cl_ω(μ) ∈ 𝒯, and it is computed by processing the pieces of ω from right to left with the operations of Lemma
4.1 and one suffix maximum per piece.

*Proof.* (a) Call the right side r. r ≥ μ (take u = t). r(t) ≥ min(ω(t), r(t + 1)), because every term of r(t + 1)
with index u, cut by ω(t), is the term of r(t) with the same u. If c ≥ μ and c(t) ≥ min(ω(t), c(t + 1)), then by
induction on u − t, c(t) ≥ min(μ(u), min_{t ≤ x < u} ω(x)); so c ≥ r. The level set statement follows by taking
thresholds as in Theorem 1. (b) Split the maximum in (a) at u = t, t < u ≤ y, and u > y. For t < u ≤ y, ω is linear
on [t, u − 1], so its minimum there is at an end: min(ω(t), ω(u − 1)). This gives min(ω(t), Q(t + 1)). For u > y
every term passes through all of [t, y], whose minimum is min(ω(t), ω(y)), and the rest of the term is a term of
c(y + 1); taking the maximum over u > y gives min(ω(t), ω(y), c(y + 1)). (c) q(u) = min(μ(u), ω(u − 1)) is in 𝒯 by
Lemma 4.1. Its suffix maximum is in 𝒯: scanning pieces from the right with running maximum k, a piece with slope ≥ 0
contributes the constant max(k, its right-end value); a piece with slope −1 contributes itself where it exceeds k and
the constant k elsewhere, split at one integer (`pl.suffix_max`). The rest is min and max. ∎ (`field.wait_close`.)

### 4.3 The pass

```
beta_j, alpha_j, omega_v  <- tents of the instance (Lemma 4.2)
mu_s <- bottom for every s;   dirty <- {}
for every j with alpha_j not bottom:  dirty[j] <- hull of the support of alpha_j;  push (top of hull, j)
while the heap is not empty:
    pop the entry with the largest key, state j;   [a, b] <- dirty.pop(j)   (skip if j has no dirty hull)
    g    <- max(alpha_j, mu_j) restricted to [a, b]                 # the part of gamma_j not yet delivered
    cand <- min(beta_j, g shifted by -D_j)                          # on [a - D_j, b - D_j] ∩ [0, H - D_j]
    for every s with head(s) = tail(j) and (s, j) not forbidden:
        new <- max(mu_s, cand);   if new = mu_s: continue
        if head(s) is waitable:  new <- cl_omega(new)               # Lemma 4.3
        [c, d] <- hull of {t : new(t) > mu_s(t)};   mu_s <- new
        dirty[s] <- hull(dirty[s] ∪ [c, d]);   push (top of dirty[s], s)
```

One dirty interval (a hull) is kept per state, and a popped state delivers the whole of it. The existing `backward`
pushes every new piece separately.

**Theorem 4 (the pass is exact).** `margin_field` terminates, and on return mu_s = μ\*_s and
gamma_s = γ\*_s for every edge state s; `issue_margin(fld, o)` = μ\*_o for every node o.

*Proof.* Write μ for the current values and γ_j = max(α_j, μ_j).

*(i) Sound: μ ≤ μ\* always.* Initially μ = −1. A candidate satisfies cand(t) = min(β_j(t), γ_j(t + D_j)) ≤
min(β_j(t), γ\*_j(t + D_j)) ≤ μ\*_s(t) by (E_μ) and induction. For the closure: μ\*_s(t) ≥ min(ω(t), μ\*_s(t + 1)) by
(E_μ), so μ\*_s is one of the functions over which cl_ω takes the least; hence cl_ω(new) ≤ μ\*_s whenever
new ≤ μ\*_s.

*(ii) Wait-closed: at a waitable head, μ_s(t) ≥ min(ω(t), μ_s(t + 1)) always.* True for −1; every update ends with
cl_ω.

*(iii) Delivered: for every edge j, every s ∈ pred(j) and every t ∈ T outside dirty[j] with t − D_j ≥ 0:
μ_s(t − D_j) ≥ min(β_j(t − D_j), γ_j(t)).* Initially γ_j = α_j, which is −1 outside the seed hull. Popping j
delivers every t ∈ [a, b] with the current γ_j, and μ_s only grows afterwards. γ_j changes only where μ_j is
raised, and those seconds are put into dirty[j] in the same step.

*(iv) Termination.* A push after the seeds follows a strict increase of some μ_s(t). Values lie in {−1..M} and
t ∈ T, so there are at most |E|(H + 1)(M + 1) such pushes.

*(v) Complete.* At the end dirty is empty, so by (iii) and (ii) μ_s(t) ≥ right side of (E_μ) evaluated on μ, for
all s and t. Induct on t from H down: μ\*_s(t) equals the right side of (E_μ) on μ\*, which uses μ\* at later
seconds only, where μ\* ≤ μ by induction; so μ\*_s(t) ≤ right side on μ ≤ μ_s(t).

(i) and (v) give μ = μ\*; `issue_margin` evaluates the formula of Theorem 1(c). ∎

`field.check_fixed_point` checks (E_μ) with equality on the stored functions. By the uniqueness part of Theorem 1 that
alone certifies a stored field, independent of the order of solving.

**Theorem 5 (cost).** Let P be the number of pops, Δ the largest number of edges into a node, π the largest number
of pieces of any function during the run, and w the largest number of pieces of an ω_v. Then the pass takes
O(P · Δ · (π · max(1, w) + log P)) time and O(Σ_s |μ_s| + Σ_j (|β_j| + |α_j|) + Σ_v |ω_v|) memory, with
P ≤ |E| + |E|(H + 1)(M + 1) and π ≤ H + 1.

*Proof.* One pop does one restriction, one max, one shift and one min (Lemma 4.1: O(π)), then for each of at most Δ
predecessors one max (O(π)), at a waitable head one closure (w pieces of ω, each O(π), Lemma 4.3(c)) and one hull
comparison (O(π)), and one heap push (O(log P)). P is bounded in Theorem 4(iv). ∎

**What the bound does and does not say.** M enters only through π and P. The worst-case bound on P is
pseudo-polynomial and does grow with M; no better worst-case bound is proved here (and, by `SURVEY.md` point 3, a
bound polynomial in the number of intervals should not be expected even for M = 0). The claim "the cost does not grow
with the number of margins" is therefore an **empirical** claim about the recorded data, measured in `BENCH.md`. The
baseline for the same output is one existing pass per margin.

**Under M1–M4 (permanent closures, keep variant)** every level set is a prefix (THEOREM, Theorem 2, applied to each
I(m), which again satisfies M1–M4), so μ_s is non-increasing in t, and the leave-by time as a function of the margin
is L_o(m) = max over paths P of min(a_P, c_P − m), with a_P = a − len(P) the acceptance bound and
c_P = min_k (c_{j_k} − 1 − offset_k) the closure bound of the path: flat where a long safe route binds, slope −1
where a closure binds, and it can switch from one route to another as m grows.

## 5. What the code returns

| call | returns |
|---|---|
| `margin_field(inst, M, erode_accept=False)` | `MarginField` with `mu`, `gamma` (per edge state), tents, `stats` |
| `issue_margin(fld, o)` | μ\*_o as a tent function |
| `issue_set_at(fld, o, m)` | Feas(o; m) as an interval list (equals `core.issue_set` on `widen(inst, m)`) |
| `leave_by(fld, o)` | [(m, end of the first window if it starts at 0)] at every margin where it changes |
| `field_at(fld, m)` | an ordinary F-3.1 `Field` of I(m), read off without a new pass; the unchanged `core.witness` and `core.check_fixed_point` work on it |
| `check_fixed_point(fld)` | certificate: (E_μ) holds with equality |
| `widen(inst, m, ...)` | the instance I(m) |

With M = 0 every function is 0 or −1, and the pass is a second, independent implementation of the F-3.1 field.

## 6. Search for this exact result

Search run 18 Nov 2026, 22:59–23:03 UTC, by a search agent; full record with URLs and reading levels in
`survey_notes/G_prior_art_margin_field.md`. It covered temporal robustness of signal temporal logic, robustness of
timed automata under guard shrinking, scheduling slack, max-min path algebra and multi-valued model checking, and
evacuation routing with time buffers. It was a short, targeted search with no citation-forward step; an obscure exact
match cannot be excluded.

**Outcome: the result as a whole was not found. Parts of it are known.**

| claim | status |
|---|---|
| Theorem 1 (threshold decomposition) | **Known in general form.** It is a direct corollary of the reduction theorem for multi-valued model checking (Bruns and Godefroid 2004, Lemma 1 and §3.2): on a bounded horizon the time-expanded graph is a finite structure with transitions valued in the chain {−1..M}, μ is the value of a reachability formula, and "value ≥ m iff the m-thresholded structure satisfies the formula". The same fact is the threshold decomposition of max-min matrices (`SURVEY.md` §4). Only the step "β_j(t) ≥ m iff t ∉ B_j ⊕ m" is specific. Not found written for this model. |
| Theorem 2 (robust = adaptive, exact) | Not found. The sufficiency half is the analogue of Donzé and Maler 2010, Theorem 2. The exactness half is a three-line argument here because the property is monotone in the closure sets; the temporal-logic papers stress that their measure is sufficient only. |
| Proposition 3 | **Known phenomenon**, not found for this model: it is the gap between "synchronous" and "asynchronous" temporal robustness (Rodionova et al. 2022, Theorem 4.10, "often strict"). |
| Lemmas 4.1–4.3, Theorems 4 and 5 (tent class closed under the pass including the waiting closure; one heap-ordered pass for all margins) | Not found. Closest: Donzé and Maler compute time robustness of a formula over one signal with piecewise-linear functions. No pass over a cyclic road graph with reopening closures and blocked waiting was found; the general reduction above costs one Boolean run per threshold. |

**The three closest prior works and the difference.**

1. **Donzé and Maler, "Robust satisfaction of temporal logic over real-valued signals", FORMATS 2010; Rodionova,
   Lindemann, Morari, Pappas, "Temporal robustness of temporal logic specifications", ACM TECS 2022.** Their
   time robustness is built the same way: signed distance to the nearest switching time at the leaves, then min and
   max, with a tolerance theorem and piecewise-linear computation. Difference: theirs is for a logic formula over one
   trace, with one-sided shifts and a sufficiency theorem. Here it is the least fixed point over a cyclic graph with
   travel-time shifts, turn bans and per-node waiting, two-sided, and exact (Theorems 1, 2).
2. **Bruns and Godefroid, "Model checking with multi-valued logics", ICALP 2004.** Their reduction theorem contains
   Theorem 1. Difference: no time structure, no distance functions, no widening or robustness reading, and the
   algorithm it gives is one Boolean run per threshold, which is the baseline here, not one pass.
3. **Sankur, Bouyer, Markey, "Shrinking timed automata", FSTTCS 2011; Jaubert and Reynier, "Quantitative
   robustness analysis of flat timed automata", FoSSaCS 2011.** Timed automata whose guards are tightened by a
   parameter. Difference: Sankur et al. decide whether some small enough shrinking keeps behaviour, Jaubert and
   Reynier compute the largest safe enlargement for flat automata. Neither returns the largest margin per state and
   per second for reachability, nor all margins in one pass.

Closest in application: Artigues et al. 2018 maximise the smallest slack between fire deadlines and the last use of
each evacuation arc, for the same stated reason (uncertain closure times), with fixed routes, closures that never
reopen and one optimal value. FlexSIPP (Hanou et al. 2026) computes a scalar slack along one fixed trajectory.

**Decision.** The exact result is not published as far as this search shows, so there is no return to Stage 2. The
novelty claim made in Stage 5 is limited to: the result for this model, Theorem 2's exactness, and the algorithm
(§4). Theorem 1 is credited to the general theorem above.

## 7. Limits

* The margin is in **time**. A reach margin in kilometres is a different family: its level functions are linear in t
  with slope 1/d_c, Theorem 1 holds for it word for word, but the tent class (slopes ±1) does not; it needs
  rational slopes and is not implemented (`CANDIDATES.md` C3b).
* All closures get the **same** m. Per-cell or per-member margins are not covered.
* Unpredicted closures far from any predicted one are outside 𝒫(m). The margin protects against timing error, not
  against fire where none was forecast.
* The margin field inherits every assumption of the F-3.1 instance (THEOREM §7), including that the dose budget does
  not bind (C3); with a binding dose the robust and adaptive readings separate (§3).
