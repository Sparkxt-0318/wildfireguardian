# Is the 2.2x bought by the shape, or by not being a circle?

**Row:** WFG-256 · **Method proposed by:** the loop (critic #66 filed the row and
fixed the rotation rule in it; the lap that ran it added the「worst rotation against
the disc」comparison and the rasterisation controls after objecting to its own plan)
**Artifact:** `data/processed/rotation_null_yeongdeok.json`
**Script:** `scripts/measure_rotation_null.py` · **Registry:** the `rn_yeongdeok_`
prefix of `docs/NUMBERS.json` — count it there rather than here.

---

## 1. The question this answers

`docs/disc_null.md` reports that the forward-simulated core beats an area-matched
disc by **2.2044** with the shared seed removed. `docs/auto/JUDGE_QA.md` Q36 carries
that ratio at tier T0, said from memory to all five judges.

Both the statistician and the ML-reviewer lens close that ratio in one question:

> 「그 2.2배가 모양을 맞혀서입니까, 원이 아니라서입니까?」

Until this document **no file in the repository answered it.** The disc differs
from the model's core in two ways at once — where its mass sits, and being a circle
rather than an irregular blob — so the disc comparison alone cannot separate them.
That is why `WFG-254` had to strike「모양」off Q36 as an axis the model was said to
have won: the card was asserting a cause the artifact declined to attribute.

## 2. The null: hold the shape, turn it

Take the model's **own** predicted core at each forward-simulation slice
(`haz_stack[i] >= p_cut`, `p_cut = 0.5`, the committed routing threshold) and rotate
that mask rigidly about the centroid of the `t = 0` seed.

| choice | what it is | why it is not a free parameter |
|---|---|---|
| centre of rotation | the centroid of the `t = 0` seed, grid row **97.7751** column **55.1205** | `obs_stack[0] > 0` and `haz_stack[0] >= 0.5` are the **same 249 cells** — the script asserts it and aborts if that ever stops being true — so the centre uses only what the two stacks already **share**, and it is the only centre that uses no information the model did not have. It is the same centre `scripts/measure_disc_null.py` uses |
| shape and area | the model's **own**, unchanged | nothing is fitted, smoothed or resized. The rotation is rigid |
| angles | every **15** degrees, 0 excluded: **23** rotations | written into the claim commit before the script existed |
| rasterisation | inverse nearest-neighbour | each output cell is rotated by −θ about the centre, rounded, and takes that input cell's membership. §4 is the price |
| scoring | the **same** observation, the **same** nearest-observation matching, the **same** `p_cut`, raw **and** seed-removed | the scorer is **imported** from `scripts/measure_disc_null.py`, not copied, so the disc figures and these cannot drift apart |

So the only thing that varies across the 23 alternatives is **orientation about the
fire's own start.** Zero free parameters, two committed inputs, no refit, no
re-acquisition, and no committed artifact regenerated.

### 2b. What was pre-registered, before any number existed

The WFG-256 claim commit fixed the rule above **and** the reading, and said the
result would be published whichever way it came out:

| if the true orientation ranks | then |
|---|---|
| **1 or 2** of 24 | the true orientation is in the upper tail; the model's placement of its own shape carries signal beyond irregularity |
| **7 to 18** of 24 (the middle half) | orientation carries little; the 2.2x is then attributable mostly to the core's irregularity and extent, that is the finding, and no lap may put「모양」back on Q36 |
| **3–6 or 19–24** | off-centre but not tail; reported as inconclusive and neither sentence is licensed |

and, separately, the number the row asked for most directly: **the minimum over
the 23 rotations, against the disc.** If even the worst orientation of the model's
own blob still beat the circle, that much of the 2.2x would be bought by *not being
a circle* rather than by placement.

The first branch fired, and the second came out the opposite way from the direction
a lap hoping for a clean story would have wanted. Both are below.

## 3. Result

At the headline slice — forward simulation **360** min against the observation at
**333** min, gap **27** min, **952** cells, the same pair `docs/oracle_gap.md` §4 and
`docs/disc_null.md` already quote, selected by the same rule and not re-chosen
afterwards — with the shared `t = 0` seed removed from every mask:

| | seed-removed IoU |
|---|---|
| the model's core **as oriented** | **0.2577** |
| the **best** of the 23 rotations | **0.1359** |
| the **median** of the 23 rotations | **0.0746** |
| the **worst** of the 23 rotations | **0.0387** |
| the area-matched **disc** | **0.1169** |

**The true orientation ranks 1 of 24, with 0 ties, at every one of the four
off-seed slices.** The same holds on the raw (seed-kept) figures: **0.3941**
against a rotated spread of **0.1734** at best and a median of **0.0976**.

**And the answer to「원이 아니라서입니까?」is no.** The worst rotation scores
**0.3311** of the disc — a third of it — and only **3** of the 23 rotations beat
the disc at all. **20** of the 23 misorientations of *the very same irregular, terrain-shaped
mask* are a **worse** opponent than a circle. So
irregularity on its own buys nothing here; what earns the overlap is that shape
placed at **that** angle.

The spread is also shaped the way an orientation reading predicts rather than like
noise: the two angles adjacent to the truth score highest (**0.1359** at 15° and
**0.1354** at 345°), and the three highest of all are those two plus 225°
(**0.1269**), the roughly opposite oblique. The nearest alternative orientation is
not a near-copy of the truth: the 15° rotation shares only **0.2272** IoU with the
unrotated core.

Every slice tells the same story, and the later slices are not tidier than the
earlier one:

| forward-sim slice | true | rotated worst → best | disc | rotations beating the disc | rank |
|---|---|---|---|---|---|
| **180** min | **0.1905** | **0.0328** → **0.1243** | **0.0975** | **4** of 23 | **1** of 24 |
| **360** min | **0.2577** | **0.0387** → **0.1359** | **0.1169** | **3** of 23 | **1** of 24 |
| **540** min | **0.2611** | **0.04** → **0.1395** | **0.1169** | **3** of 23 | **1** of 24 |
| **720** min | **0.273** | **0.0456** → **0.15** | **0.1225** | **4** of 23 | **1** of 24 |


### 3b. ⚠ Where that「beats the disc」count is decided, and the one place it nearly flips

Every beats / does-not-beat count above is decided at **full precision on both
sides**, while the IoUs this page prints are rounded to 4 dp. That is not a
formality, and this lap did it the wrong way first: the counts were originally
compared on the rounded values, and the lap's independent reviewer found that the
**720**-minute row then read **3** when it should read **4**. The 210-degree rotation
at that slice sits **2.66e-05** above the disc — `rn_yeongdeok_t720min_closest_rotation_margin`
— which rounds to the same 4 dp as the disc, so a strict inequality on the printed
numbers answered a question the printed numbers cannot answer. The table now says 4,
and `rn_yeongdeok_t720min_rotations_tied_with_the_disc` records that **1** rotation is
indistinguishable from the disc there.

Each slice therefore registers its nearest rotation's **signed** margin, so a count
that would move on the fifth decimal is visible instead of asserted. The one other
near-miss is the **540**-minute slice, where the same 210-degree rotation lands
**-0.00011853** — on the *other* side of the disc, and counted as not beating it.

⚠ **The headline slice has room under it, and that is why the 3-and-20 split is the
one this project quotes.** At 360 minutes the nearest rotation is
**-0.0025974** below the disc and **0** rotations tie with it at the reported
precision, so nothing in 「3 beat the disc, 20 do not」 depends on where the
comparison is rounded.
## 4. The rasterisation residual, stated and not resampled away

Rotating a raster mask does not preserve its cell count, so every angle reports
the count it achieved beside the count it was supposed to have. At the headline
slice the worst absolute residual is **0.0126** of the target, and **0** cells were pushed off the canvas at any angle, so no rotation
was clipped and the rule executed as written. **Nothing was resampled,
re-thresholded or re-fitted to close that residual**, because a null that is
adjusted until its counts match is a null with a free parameter.

The reason the residual cannot be driving the result is on the same page as the
result. The three **lattice-exact** angles — 90, 180 and 270 degrees, which on a
square grid are exact permutations — carry a cell-count residual of **exactly 0**,
and they score among the **lowest** of the 23 (the best of the three reaches only
**0.0709** raw). If rasterisation loss were manufacturing the gap, the three
lossless angles would be the ones at the top. They are at the bottom.

## 5. What this does NOT show

1. ⚠⚠ **It is not a decomposition, and it does not say the model gets the
   direction right.** No arithmetic here splits **2.2044** into a shape term and a
   placement term, and a reading that treats it as an additive split is wrong.
   What it supports is narrower: the overlap is not explained by the core's
   irregularity, nor by its being anchored at the seed, because most rotations of
   that same irregular seed-anchored mask do worse than a circle.
2. ⚠⚠ **`docs/disc_null.md` §4's centroid finding stands unchanged and points the
   other way.** The model's centre of mass ends up **5.34** cells from the
   observation's while the *stationary* disc's ends up **2.266** away, and the
   observed footprint's centre of mass moves only **2.25** cells from the seed
   while the model's core moves **7.292**. The two measurements are consistent and
   the honest joint reading is the narrow one: **the axis is right and the distance
   along it is overrun.** 「저희가 나은 것은 겹침이고, 방향은 아닙니다」 stays as it is.
3. **A rank of 1 of 24 is not a rank against opponents anyone would build.** The 23
   alternatives are deliberately misoriented copies of the model's own mask. No
   competitor proposes to point a fire the wrong way, so this is evidence about
   *what produces the overlap*, not evidence of skill against a serious baseline.
   The baseline a fire scientist will ask for is persistence, which inherits the
   fire's real shape **and** its orientation; that is **WFG-234** and it is not done
   here.
4. **No p-value, and none is computable from this.** 23 rotations of one fire on
   one canvas at one `p_cut` is a reference spread. There is no population of fires
   here to be surprised about, and `docs/disc_null.md` §5's one-fire caveat applies
   unchanged: 영덕 2025 only, nothing about 의성·안동 or 울진·삼척.
5. **`obs_stack` is not ground truth.** It is a FIRMS-derived observation with its
   own detection floor (`docs/detection_floor.md`) and 500 m resampling. A「missed」
   cell may be a cell FIRMS did not see — and that caveat applies to the rotations
   and the true orientation equally, which is one reason a *comparison* survives it
   better than any single IoU does.
6. **Nothing at `t = 0`.** Removing the shared seed from the `t = 0` masks empties
   them, so the seed slice has no seed-removed figures at all; every seed-removed
   number here is an off-seed slice.
7. **No margin, no route, no committed number moves.** 42, 91, 9 and 27 are
   untouched. Nothing was routed; this is 24 orientations of one field against one
   observation.

## 6. What a judge should hear

> 「2.2배가 모양이 불규칙해서 생긴 값인지 확인해 봤습니다. 예측한 모양과 칸 수를
> 그대로 두고, 불이 시작한 자리를 중심으로 15도씩 23번 돌려서 똑같이 채점했습니다.
> 돌린 것 중 가장 잘 맞은 것이 0.1359이고 실제 방향은 0.2577로, 24개 중 1위였습니다.
> 그리고 돌린 것 중 **20개는 원판보다도 못했습니다** — 즉 모양이 울퉁불퉁해서 점수가
> 나온 게 아니고, 그 모양을 **그 각도로** 놓은 것이 점수를 만듭니다. 다만 이것이
> 「방향을 맞혔다」는 뜻은 아닙니다. 무게중심으로 보면 저희 모델은 불을 실제보다 멀리
> 보냈고 가만히 있는 원판보다 더 빗나갔습니다. 축은 맞고 거리는 과했다는 읽기입니다.
> 그리고 불 하나, 격자 하나에서 잰 것이라 p값은 없습니다.」

The draft Korean above is a draft for the student's own voice (CHARTER §9).

⚠ **Where this must not travel.** It licenses no sentence of the form「저희가 잘하는
것은 방향이 아니라 불의 모양입니다」(`WC-018`, withdrawn and registered) and no
comparison with any domestic system (**NH-056**). The one place it belongs on a
judge-facing surface is Q36's analytic block, beside the centroid displacements
that keep it honest, which is where the lap that ran it put it.
