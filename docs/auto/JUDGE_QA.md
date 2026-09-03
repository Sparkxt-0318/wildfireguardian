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

| Item in 서식2 | Submitted value | Current canonical value | Source |
|---|---|---|---|
| Ⅲ-9 459-series split | 459 · 438 / 18 / 3 (`routing_demo.npz`, sha 5bed5026…) | 458 · **414 / 42 / 2** on `routing_demo_canonical.npz` (sha 81b4e4d1…); FA-only 3.70 % → **9.17 %** | HANDOFF §1.1, §2-A; `decision_shift.md` §3.3 (no per-origin ledger for this pair) |
| Ⅲ-9 "핵심 영역 241→244 셀, 거의 변화 없음" | quasi-static core | core growth **+316 %** (249 → 1,036 cells); the quasi-static reading was a property of the reverted field | HANDOFF §1.1 |
| Ⅲ-9 잔여 한계 "OSM 간선에 DEM 경사를 적용하지 않아" | not applied | **applied** at 60 m sampling (+26.6 % traversal time), null on buckets | HANDOFF PHASE 2 |
| Ⅲ-11 ML baseline table | RF 0.920 ± 0.036, LR 0.903, GBM 0.889 ± 0.107 | committed `ml_baselines.json`: RF **0.914 ± 0.044**, LR 0.903 ± 0.060, GBM **0.894 ± 0.092** (ordering unchanged) | README |
| Ⅲ-4 far-band AUC 0.925 (n=3) | 0.925 | committed `auc_intervals.json` **0.904 ± 0.100**; corrected-DEM pooled far-band 0.8408 (vs 0.877) | README, MODEL_CARD |
| Ⅴ-2 "PR-AUC·Brier 미산출, 향후 과제" | not computed | **computed**: AP 0.169 vs 0.0197 baseline; Brier 0.0183, ECE 0.0086 (RF 0.0174/0.0068) | `oof_classification_metrics.json`, `calibration_metrics.json` |
| Ⅲ-6-2 / Fig. 3 "0/30/60분 → 6/24/66곳" | 6→24→66 | README §rescue routing says "6 → 34 as delay goes 0 → 60 min" — **internal inconsistency inside the repo**, UNRESOLVED (which artifact is 34?) | README vs 서식2/개정대조표 |
| Ⅲ-4 "DEM" lineage of the headline AUC | 0.890 mean-of-folds | unchanged as headline, but trained on a raster with the sea at −497 m; corrected re-run +0.0048 mean-of-folds (not adopted) | HANDOFF §4 |
| Ⅱ-2 contribution ② "여유 오름차순 우선 출동 배정 목록" | ordering is the contribution | **restated 2026-08-10**: the *information* (`ingress_survival_time_min`) is the contribution; the ordering is only valid when W exceeds corridor closure, and W=75 does not | `dispatch_ordering.md` §0 |

None of these contradicts the submitted *purpose/theme*; all are corrections in the direction the 서식 itself invites (Ⅴ-4 lists most of them as future work). But the student must be able to recite this table without notes, or a judge will conclude the documents were not written by the person at the booth.

---

---

## 1. The hardest questions the 예상질의 notes do not answer well

The notes (A-1…F) cover: number provenance, retired numbers, Build A, 38 %/11 %, f = 0.3, Monte Carlo 21 %/86 %, probability-scale null, MC lineage, DNN choice, physics-vs-data, IoU table removal, the three routing configurations, 9-hour fixed observed area, forward-sim drift, two bboxes, acquisition automation, why-needed vs 국가산불위험예보, the 0-change rescue constraint, where future-aware is validated, unverified assumptions. They were written 2026-07-23, **before** Round 3–5 (canonical field, multi-region, dispatch ordering, recall at threshold, vulnerability layer, GK2A, horizon grounding, refuge placement). Everything below is new ground.

**Q1 (ML researcher / statistician). "AUC 0.89 is a ranking score. At the threshold your simulator and router actually use, what fraction of real ignitions does the model catch?"**
Answer to give: "0.138 pooled; 0.087 mean-of-folds; three of six held-out fires have zero true positives at 0.3, and almost all recall comes from 영덕 (0.456). We report it in the model card above the AUC. The router does not apply that cut — it consumes the probability surface — but the forward simulation's advance rule does, so the hazard field's *extent* inherits it. The honest ranking summary is average precision 0.169 against a 0.0197 no-skill baseline, 8.6×. The threshold was never tuned; the F1-optimal cut (0.14 → F1 0.218) is recorded and deliberately not adopted because choosing it on the scored probabilities is optimistic." Proof: `docs/MODEL_CARD.md` (recall section), `data/processed/oof_classification_metrics.json`, `docs/SESSION18_REPORT.md` Phase 4. What does not exist: any experiment showing how bucket counts move if the advance threshold changes (see improvement #4/#5).

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
Answer: "Because you can check them: 244 of 260 registered values re-derive from committed artifacts under `make verify`, the other 16 are labelled 'verified, not reproducible' because the OSM graph behind them was overwritten on 2026-07-24. The gates catch a retired number being re-quoted and a region literal; they cannot catch a number that was never registered or an event that never happened — that class was caught by looking things up, and we wrote the failure mode down. Here is the list of what moved since submission —" and then §1.4 above, from memory, in this order: 438/18/3 → 414/42/2 (why: reverted-run field, corrected DEM), RF 0.920 → 0.914, far-band 0.925 → 0.904, slope now applied, PR/Brier now computed, contribution ② restated. Proof: HANDOFF §1.1, §4-B, `docs/NUMBERS.json`, `scripts/verify_numbers.py`.

Three more, lower probability but lethal if unprepared:

- **Q11 (official). "Elderly residents don't leave because they can't see the fire. Which line of your system changes that?"** → None; compliance is out of scope; the only link is a hypothesis that showing *future* closure time addresses the perception gap; unmeasured. `firefighter_consultation.md` §3.2–3.3.
- **Q12 (any). "Who from the field validated this?"** → One serving firefighter, informal oral, N = 1, affiliation/date/consent **unrecorded** (§8 of that doc); three academic advisers named in HANDOFF §8 with the same "judgment, not measurement" status. Never say "현장에서 검증".
- **Q13 (software engineer). "Your Dijkstra minimises a different quantity from the one you report and isn't provably optimal. Why trust the routes?"** → Contrasts are valid (both arms scored by `_evaluate_path`), absolute exposures should not be quoted as minimised, no counterexample constructed at 10-min bins, results are deterministic and reproduce. `routing_limitations.md` §2/§4. A fixed router: **does not exist**, on purpose (would move every committed count).

---
