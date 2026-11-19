# Stage 2: candidate directions

Written after the survey (`SURVEY.md`) and before the method was fixed. Seven directions. For each: the idea, what
would be new, what is already known (with the survey section that says so), and the main risk. The choice and its
reasons are at the end.

Notation is that of `research/kcf-theorem/THEOREM.md`: edge states s, sets R_s ⊆ T = {0..H}, closures B_j, W_v, IB_o,
acceptance A_j, travel times D_j ≥ 1, the one-step equation (E). "The pass" is `deadline_field.core.backward`.

## C1. Delta field: exact update after one closure or reopening

**Idea.** Keep the field. When a mask changes, repair only what changed.
* A reopening or a delayed closure removes seconds from some B_j. The field can only grow, and the new field is the
  least fixed point above the old one. Seeds are the newly open arcs whose end already lies in the old field:
  ((G_j − D_j) ∩ (B_j^old \ B_j^new)) \ R_s. Run the pass from those seeds only.
* A new closure adds seconds to B_j. The field shrinks. Because every move takes ≥ 1 s the time-expanded graph is
  acyclic, so a second leaves R_s exactly when every one of its supports has left. Re-deriving in descending time
  needs no over-delete phase.

**What would be new.** A bound in the number of changed *intervals* (not changed seconds), for interval sets with
gaps and no-wait nodes; and the remark that on this acyclic structure deletion needs no re-derivation phase.

**Known.** Bounded incremental computation (Ramalingam and Reps), LPA* and D* Lite, DRed and counting for
least fixed points, semi-naive evaluation (`SURVEY.md` §3). The growth direction is exactly semi-naive evaluation.
No exact incremental update was found for SIPP-type interval structures (§2), so the specialisation looks unpublished,
but the technique is standard.

**Risk.** Novelty: a referee would call it an application of a known technique. Speed gain is certain.

## C2. Shift-and-mask algebra; closed-form stars; contraction

**Idea.** A path acts on a set of arrival seconds as X ↦ (X − d) ∩ O, a pair (delay d, open set O). Sum is union,
product is composition: (d₁, O₁)(d₂, O₂) = (d₁ + d₂, O₁ ∩ (O₂ − d₁)). The existing waiting closure is the Kleene
star of a self-loop with d = 1, in closed form. One could eliminate nodes (shortcuts) in this algebra, as contraction
hierarchies do for travel-time functions.

**What would be new.** Not the algebra (see below). Only a closed form for the star of a cycle of delay d > 1 (a downward closure inside each residue class mod d).

**Known.** The algebra itself, in forward form: Minoux 1976, chapter III (interval sets, union, shift and mask, a
parking operator), who also notes that the product of two such operators is no longer one triple, so only images are
computed. Tarjan's path expressions; time-dependent contraction hierarchies under FIFO (`SURVEY.md` §4, §1).

**Risk.** Without FIFO a shortcut is a set of pairs that can grow without bound. No-wait feasibility is weakly
NP-hard in the encoding of times (Zeitz 2023, §1), and a 2-cycle with no waiting already gives a feasible set of
"every other second": H/2 intervals. So no algorithm polynomial in the number of intervals can exist in general, and a
contraction scheme has no guarantee. Not chosen.

## C3. Windows as a function of the safety margin, in one pass

Two versions.

**C3a. Time margin (chosen).** Widen every closure by m seconds on both sides: the road closes m seconds earlier and
reopens m seconds later. The instances I(m) are nested. Define μ_s(t) = the largest m at which t is still in R_s.
* μ solves a (max, min) version of (E), in which the level function of an edge is the distance to its closed set
  minus one, a "tent".
* All functions are piecewise linear in t with slopes −1, 0, +1 on the integer grid. That class is closed under the
  operations of the pass. So one pass over such functions returns the windows for every margin 0..M, at a cost that
  does not grow with M.
* μ_o(t) ≥ m has a plain meaning: departure t has one route that stays valid whenever every closure boundary is
  wrong by at most m seconds.
* μ is not the distance to the edge of the window: a second in the middle of a wide window can have margin 0, because
  the window is the union of different routes' windows.

**C3b. Reach margin (spread rate).** With permanent closures at c = d_c · ρ (d_c the cell's distance to the known
fire, ρ seconds per metre), the latest departure is L(ρ) = max over paths of min_k (d_k ρ − offset_k). The same
threshold argument gives, for each departure second, the fastest fire it still outruns; the level functions are
linear in t with slope 1/d_c. Needs exact rational arithmetic.

**What would be new.** For C3a: the theorem above for this model (gaps, no-wait nodes, turn bans), the closed class of
tent functions with the exact waiting closure, and the one-pass algorithm. For C3b: no algorithm or breakpoint bound
was found for the mixed form "bottleneck with path offsets, parameter inside the min" (`SURVEY.md` §5).

**Known.** Threshold decomposition of max-min systems; monotonicity of L/U parametric timed automata (Hune et al.);
min-max bottleneck problems reduce to one solve on the worst case (Aissi et al.); SIPP "temporal flexibility"
(FlexSIPP) as a fixed scalar slack; wildfire trigger buffers re-run per scenario (§5, §6, §2).

**Risk.** C3a: the number of pieces could blow up and erase the gain; that is measurable. C3b: cannot be tested on
graphs with reopening or on the six caches (their closures do not come from a reach curve), which Stage 4 requires.

## C4. Windows safe under every forecast member, without solving each member

**Idea.** Two readings. (i) One route safe in every member: this is the field of the instance whose closures are the
union over members, one ordinary pass. (ii) For every member some route: the intersection of the members' fields; a
field with values in subsets of members (a bitmask per piece) computes all members in one pass and shares the pieces
on which members agree.

**What would be new.** For (ii), the member-set-valued field for this model.

**Known.** (i) is the published reduction of min-max bottleneck problems to the worst-case instance (Aissi, Bazgan,
Vanderpooten 2009, Prop. 3; `SURVEY.md` §5), and the cert rule already takes the union. (ii) is lifted (family-based)
analysis and bit-parallel multi-source search in other fields. With a heat-dose budget summed per member the
single-route question becomes a multi-scenario additive problem, NP-hard already for two scenarios (Yu and Yang, §5).

**Risk.** (i) is not new; (ii) shares little when members disagree near the fire, which is where it matters; the dose
version is hard. Not chosen.

## C5. One pass that returns the gain from delaying every cell

**Idea.** Delaying cell c opens arcs U^c. A journey that gains must use one of them; after its last such arc it is in
the old field. So the gain set of every origin is generated by the seeds {(j, t) : t ∈ U^c_j, t + D_j ∈ G_j}, and a
candidate with no seed gains nothing (this is the exact pruning rule of kcf-defend, in set form). Run the growth pass
of C1 from each candidate's seeds, or all candidates together with labelled pieces.

**What would be new.** The seed theorem in the set-valued model; one labelled pass for all candidates.

**Known.** For shortest paths, all single-arc improvements follow from one forward and one backward tree. I found no
bottleneck-with-offsets analogue in closed form (`SURVEY.md` §3): the value through an upgraded arc depends on a
profile from the origin, not on one number, so there is no two-field formula. What remains is C1 applied per
candidate.

**Risk.** Covers single cells only; a held front section changes hundreds of cells, and rank 1 in kcf-defend is a
front section at every hour. Not chosen; it is C1 with a different driver.

## C6. Sandwich by two monotone relaxations

**Idea.** Make every closure permanent from its first second (lower instance, Corollary 3 of THEOREM.md) and, the
other way, keep only the final permanent part of each closure (upper instance). Both satisfy M1–M4, so two scalar
Dijkstra passes give ℓ⁻_s ≤ ℓ⁺_s with [0, ℓ⁻_s] ⊆ R_s ⊆ [0, ℓ⁺_s]. Where they agree the field is known exactly; the
interval pass runs only on the band between them.

**What would be new.** The exactness certificate "two scalar passes agree" and the residual pass.

**Known.** Upper and lower bound functions in approximate time-dependent contraction hierarchies (§1).

**Risk.** A shelter that opens late makes the lower instance empty, so the whole spec falls back to the interval
pass. The gain is a constant factor. Kept as the fallback if C3a failed.

## C7. Periodic sets for no-wait cycles

**Idea.** Represent R_s as an eventually periodic set, to compress the "every other second" case of C2.

**Risk.** Never occurs in the recorded data (every measured set is one interval). Not chosen.

## Choice: C3a, the one-pass margin field

Reasons, in the order of the brief (time, accuracy, memory):

1. **It is defined on every instance**, including roads that reopen and the six recorded caches, so every Stage 4
   check applies. C3b and C5 are not.
2. **Time.** The baseline for "windows at K margins" is K passes; the candidate is one pass whose cost should not
   depend on K. A probe before choosing (not a result; the frozen benchmark is `BENCH_PLAN.md`): on one spec of one
   cache the prototype with M = 600 took about as long as one existing pass.
3. **Accuracy.** Every level set can be compared exactly with the existing pass and with the brute-force oracle on
   the widened instance. A probe on 3,000 random graphs showed no difference.
4. **It answers a question the field cannot answer today**: how much timing error in the fire forecast a leave-by
   time absorbs. Proposition 3 of `METHOD.md` shows this cannot be read off the windows.
5. **Novelty risk is moderate, not low.** The threshold argument is classical. What is claimed new is the result for
   this model and the tent algebra with its exact waiting closure. Stage 3 searches for the exact result.

If Stage 3 finds C3a published, the second choice is C1 (largest certain speed gain), then C6.
