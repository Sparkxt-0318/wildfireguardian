# Judge Q&A bank — v2 seed (2026-09-03)

**Status: DRAFT written by the research sweep (agent), for the student to rehearse,
rewrite in their own words, and confirm against the artifacts.** The 2026-07-23
예상질의 notes (outside the repository) cover number provenance, retired numbers,
Build A, 38 %/11 %, f = 0.3, the Monte Carlo, DNN choice, physics vs data, the
three routing configurations, the two bboxes and the 국가산불위험예보 contrast.
Everything below is new ground since Round 3 (canonical field, multi-region,
dispatch ordering, recall at threshold, vulnerability layer, GK2A, horizon
grounding, refuge placement). Each answer names the file that proves it or says
plainly that the evidence does not exist yet; those gaps are backlog rows.

Rules for this file (docs/auto/CHARTER.md §9): answers are drafts until the
student has rewritten them; never quote a number here that is not in
`docs/NUMBERS.json` or a committed artifact; the critic lap adds questions it
could not answer from a file and marks them "no evidence yet".

## 0. The superseded-number list a judge can trip over (서식2 as submitted → repo now)

**The table lives in one place: [`docs/submission_reconciliation.md`](../submission_reconciliation.md)** —
Korean, one printable A4 page, eleven rows, each with the submitted value, the current
canonical value, why it moved, what did *not* move, and a 30-second spoken version to
recite at the booth. It is the sheet to print and carry. Do not restate its rows here;
a second copy is a second thing to keep in sync, and this file has already drifted from
it once (WFG-018).

Two things that page settles and that a judge is most likely to probe:

- **459-series split** — 459 · 438 / 18 / 3 as submitted (제출 시점 기록, `routing_demo.npz`)
  against 458 · **414 / 42 / 2** on the canonical field. There is no per-origin ledger for
  that pair, so never say "N origins were reclassified" (HANDOFF §5.24), and 18/459 is
  **3.92 %**, not the 3.70 % that belongs to a different retired run.
- **README.md:731 is the one place where the repository, not the 서식, is wrong**: it
  states the delay row as "6 → 34" where `rescue_verify.json` carries
  `[6, 11, 24, 51, 66]` (registered as `rescue_unreachable_delay_row_cutoff_0p7`).
  Fixing that line is WFG-004.

None of these contradicts the submitted *purpose/theme*; all are corrections in the direction the 서식 itself invites (Ⅴ-4 lists most of them as future work). But the student must be able to recite that sheet without notes, or a judge will conclude the documents were not written by the person at the booth.

---

---

## 1. The hardest questions the 예상질의 notes do not answer well

The notes (A-1…F) cover: number provenance, retired numbers, Build A, 38 %/11 %, f = 0.3, Monte Carlo 21 %/86 %, probability-scale null, MC lineage, DNN choice, physics-vs-data, IoU table removal, the three routing configurations, 9-hour fixed observed area, forward-sim drift, two bboxes, acquisition automation, why-needed vs 국가산불위험예보, the 0-change rescue constraint, where future-aware is validated, unverified assumptions. They were written 2026-07-23, **before** Round 3–5 (canonical field, multi-region, dispatch ordering, recall at threshold, vulnerability layer, GK2A, horizon grounding, refuge placement). Everything below is new ground.

**Q1 (ML researcher / statistician). "AUC 0.89 is a ranking score. At the threshold your simulator and router actually use, what fraction of real ignitions does the model catch?"**
Answer to give: "0.138 pooled; 0.087 mean-of-folds; three of six held-out fires have zero true positives at 0.3, and almost all recall comes from 영덕 (0.456) — 351 of the 412 pooled true positives. Two of those three folds cannot produce a true *or* a false positive at 0.3 at all, because no cell in them reaches it: the ceiling is 0.0241 on 강릉 and 0.296 on 홍성. The remaining folds' false-negative rates are 0.977 (의성·안동), 0.959 (울진·삼척), 0.544 (영덕). We report it in the model card above the AUC. **Two different thresholds:** 0.3 is `forward_sim_advance_threshold`, applied per simulation step, so the hazard field's *extent* inherits it; the router cuts the *cumulative* survival-accumulated field at `walk_cutoff_p` = 0.5. Recall at 0.3 is therefore not the routing field's miss rate. The honest ranking summary is average precision 0.169 against a 0.0197 no-skill baseline, 8.6×. The threshold was never tuned; the F1-optimal cut (0.14 → F1 0.218) is recorded and deliberately not adopted because choosing it on the scored probabilities is optimistic."
**If pushed — "then calibrate a threshold that guarantees a miss rate":** "We ran it and it is a negative result. Nested leave-one-fire-out with a 0.20 false-negative budget: without a finite-sample term the bound breaks on 3 of 6 held-out fires, worst case 0.750. With the leave-one-out correction 1/(n+1) — at n = 5 calibration fires that is 0.167, which eats 83 % of a 0.20 budget — the bound holds on 6 of 6 and a bound-satisfying threshold flags 26–46 % of every cell on the map, against a 1.97 % prevalence. For this model at six fires you can have the guarantee or a usable hazard field, not both, so we keep the ranking-driven forward simulation at an untuned default and say why. We are careful about which half is which: the 83 % is arithmetic in the fire count and holds for any model, but the 26–46 % is this model's probability distribution, and we did not run the control that would separate 'too few fires' from 'probabilities too compressed'. And neither column is a real guarantee: the held-out fire's probabilities come from a model trained on the calibration fires, and 1/(n+1) is a fire-level term applied to a cell-level quantile — it is an optimistic bound, and even the optimistic version is unusable."
Proof: [`docs/operating_point.md`](../operating_point.md), `docs/MODEL_CARD.md` appendix (WFG-019), `data/processed/operating_point/per_fire_recall.json`, `data/processed/oof_classification_metrics.json`, `docs/SESSION18_REPORT.md` Phase 4. Registry keys: `optpoint_gangneung_ceiling_probability`, `optpoint_hongseong_ceiling_probability`, `optpoint_uiseong_fnr_advance_cut`, `optpoint_uljin_fnr_advance_cut`, `optpoint_yeongdeok_fnr_advance_cut`, `optpoint_zero_truepositive_fold_tally`, `lofocal_finite_sample_correction`, `lofocal_correction_share_of_budget`, `lofocal_uncorrected_bound_upheld_tally`, `lofocal_uncorrected_heldout_fnr_worst`, `lofocal_corrected_flagged_share_floor`, `lofocal_corrected_flagged_share_ceiling`. What does not exist: any experiment showing how bucket counts move if the advance threshold changes (see improvement #4/#5).

**Q2 (fire scientist). "ERA5 is 0.25° and published with ~5 days' delay. Your 'live trigger' cannot be using real weather. What field does it route on?"**
Answer: "A pre-computed field at a fixed reference time. We measured the upper bound of the loss from swapping instantaneous weather for a forecast-like proxy — mean-of-folds −0.020 — but the real substitution was never run; PHASE 14 stopped there and we say so on the RELIABILITY tab: '완전한 실시간 운영이 아닙니다'. LDAPS is recorded, not used." Proof: `docs/weather_dependency.md`, `docs/live_pipeline.md`, HANDOFF §14. Evidence that a real-time weather source would help: **does not exist**.

**Q3 (statistician). "Your top permutation feature, days-since-rain, is pinned to the download-window start for half your fires, and removing it *improves* out-of-fold AUC. Isn't the model partly learning how you built the dataset?"**
Answer: "Yes, for that feature, and we measured it rather than hid it: +0.027 mean-of-folds, +0.053 far-band when dropped. We did not retrain the committed model because every downstream number would move and the submission's lineage would break; the corrected re-run exists as a separate file. The routing layer consumes the committed field. The lesson is registered: an acquisition parameter leaked into a feature." Proof: `docs/weather_dependency.md` §②, README. What does not exist: a *committed* canonical retrain without the feature (frozen by §5 rule 2; a user decision).

**Q4 (emergency-management official). "Your submitted contribution ② is a deadline-sorted dispatch list. You then measured it against nearest-first and it never wins at your own 75-minute window. So what exactly is the contribution?"**
Answer: "The per-home quantity `ingress_survival_time_min` — when each approach road closes — which nothing in the compared systems computes. Sorting on it is only informative when the operating window outlasts corridor closure; at W = 75 all homes share ~2 deadlines and the sort carries no information, so nearest-first wins by saving 6–13 min per trip. We left the shipped order unchanged and state the condition. A serving firefighter told us independently that a fixed time budget does not exist in field decisions — the decision is 'can we get out alive', which is our survival term, not our clock term." Proof: `docs/dispatch_ordering.md` §0/§6, `docs/firefighter_consultation.md` §1.2–1.3. Do not say "verified" — N = 1 and the two sources are independent, not mutually confirming.

**Q5 (fire scientist). "Your household vulnerability and refuge-placement layer: you showed the failing set is identical with the fire removed. So the fire contributes nothing there — is this a wildfire result at all?"**
Answer: "For that layer, at 영덕, with the elliptical hazard: correct, and we retracted 'distance drives vulnerability' to 'this is a reachability restatement'. The fire *does* bind on the routing axis — 42 of 458 origins at 영덕 and 91 of 368 at 의성·안동 reach a refuge only on the time-aware route — but the household layer sits on a hazard that never reaches the refuges (0/120 survival-filter hits). We kept the survival check outside the objective and labelled the placement result 'geometric recommendation under stated assumptions'. What would make the fire bite there is listed and untried: stronger scenario, ignition prior inside the household cluster, arrival-time survival buffer, a site whose refuges actually burn." Proof: `docs/SESSION17_REPORT.md`, `docs/SESSION22_REPORT.md` §Phase 3, `BLOCKERS.md` Session 17 future work. Evidence of a fire-conditional household result: **does not exist**.

**Q6 (fire scientist / modeller). "Why is 'ignition probability ≥ 0.5 by the next satellite overpass' the definition of an impassable road? Ignition in a 375 m cell is not flame on the road."**
Answer: "It is a threshold we chose, not one we derived; we treat it as a controlled variable with p_cut swept 0.4–0.6 for walking and 0.5–0.9 for vehicles in the 439 series, and the honest statement is that a probability of detection-by-next-overpass is a proxy for 'the fire will be there', coarse in both space (375/500 m) and time (3-hour slices). A branch adopted 0.30 and re-ran everything; we did not merge it because it would change every committed count and the registry would hold two cutoffs." Proof: 서식2 Ⅱ-3 (조작 변수), HANDOFF §4 (hazard-resolution branch, `p_cut = 0.30`), `docs/routing_limitations.md` §3. A physically grounded impassability criterion (flame length, radiant flux): **does not exist**.

**Q7 (statistician). "Your walk bbox covers 32.6 % of the demonstration fire's core; the other two regions cover 99 % and 82 %. Isn't 영덕 — the fire you built the story on — the least valid case?"**
<!-- collision-ok: 24.7 — the 의성·안동 time-aware-only share (91 of 368), not the core-growth correlation -->
Answer: "Its absolute rates are rates on the covered third, and every one carries that caveat; the paired contrasts (same origin, two routes) do not depend on the frame. The fix is not a bbox edit — the bbox is coupled to the simulation canvas, so it is a full re-simulation, and we recorded the decision not to. On the region with 99 % coverage and an advancing front, the same method gives a time-aware-only share of 24.7 %, seven times 영덕's. We do not rank the three regions: n = 3, and coverage, core growth and envelope area move together." Proof: HANDOFF §2-A, §5 rules 14/19, README Round-3 table, `docs/multi_region.md` §8.

**Q8 (emergency-management official). "What are your 'refuges'? Are any of them designated 대피소?"**
Answer: "Fifty OSM POIs at 영덕, 46 snapped to the network; the RELIABILITY tab says it plainly — most are `leisure=park`/정자-type tags, unverified against 행안부 지정 대피소. The 공공데이터포털 national shelter file has a loader with a labelled synthetic fallback, but the committed runs use OSM. Between-region 'shelter density' differences are partly mapping practice. Refuge *survival* under the fire is a separate filter and never bound in these runs." Proof: 서식2 Ⅲ-9-1, `finals.html` RELIABILITY strings ("대피 지점의 다수는 OSM의 공원·정자류 태그입니다"), `docs/global_portability.md` §3b. A cross-check against the official shelter list: **does not exist** (portal download is JS/CAPTCHA-gated; see student list).

**Q9 (fire scientist / official). "The 2025 fire reached 영덕 from 안동 in about 40 minutes. Your hazard slices are 3 hours apart and satellites pass every 6–16 hours. Can this system say anything on the timescale that killed people?"**
Answer: "Not at minute resolution, and the A4 sheet's 「남은 시간」 can only read 180/360/540/720/확인 불가 on this field; the '< 30 min → 긴급' tag is structurally unreachable. We measured the detection floor too: with GK2A at 2-minute cadence, a satellite trigger would still have fired 22–64 minutes *after* the human report in every fire we could test, so the trigger interface is designed report-first, satellite-confirm. What the system is for is the 4-hour behavioural window — 79 % of Korean fires are contained within 240 min of report (n = 2,008), while fires ≥ 100 ha run a median 67 hours — so 'act now on foot' vs 'send a vehicle' is the decision it informs, not 'run left or right in the next ten minutes'." Proof: `docs/routing_limitations.md` §3, `docs/SESSION19_REPORT.md` / `detection_floor.md`, `docs/horizon_grounding.md`. Finer-slice re-run of the routing axis: **does not exist** (PHASE 2-C-3 never started).

**Q10 (software engineer / any judge). "You publish 24 'never do' rules, a registry of retired numbers and a record of five fabricated citations caught in one week. Why should I trust *today's* numbers, and which numbers in your submitted 서식 are wrong now?"**
Answer: "Because you can check them: 261 of 295 registered values re-derive from committed artifacts under `make verify`, the other 34 are labelled 'verified, not reproducible' — 16 because the OSM graph behind them was overwritten on 2026-07-24, and 18 because they are values from earlier runs registered so the reconciliation sheet resolves. The gates catch a retired number being re-quoted and a region literal; they cannot catch a number that was never registered or an event that never happened — that class was caught by looking things up, and we wrote the failure mode down. Here is the list of what moved since submission —" and then the reconciliation sheet, from memory, in its own order. Proof: [`docs/submission_reconciliation.md`](../submission_reconciliation.md), HANDOFF §1.1, §4-B, `docs/NUMBERS.json`, `scripts/verify_numbers.py`.

Three more, lower probability but lethal if unprepared:

- **Q11 (official). "Elderly residents don't leave because they can't see the fire. Which line of your system changes that?"** → None; compliance is out of scope; the only link is a hypothesis that showing *future* closure time addresses the perception gap; unmeasured. `firefighter_consultation.md` §3.2–3.3.
- **Q12 (any). "Who from the field validated this?"** → One serving firefighter, informal oral, N = 1, affiliation/date/consent **unrecorded** (§8 of that doc); three academic advisers named in HANDOFF §8 with the same "judgment, not measurement" status. Never say "현장에서 검증".
- **Q13 (software engineer). "Your Dijkstra minimises a different quantity from the one you report and isn't provably optimal. Why trust the routes?"** → Contrasts are valid (both arms scored by `_evaluate_path`), absolute exposures should not be quoted as minimised, no counterexample constructed at 10-min bins, results are deterministic and reproduce. `routing_limitations.md` §2/§4. A fixed router: **does not exist**, on purpose (would move every committed count).

---
