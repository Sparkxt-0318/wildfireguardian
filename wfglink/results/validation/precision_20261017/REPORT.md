# Final report: opt-in high-precision ember track verifier (2026-10-17)

Scope: wfglink only. The verifier is opt-in (`--high-precision METHOD`), never the default; legacy outputs are unchanged (final/identity.json). No tag, no merge, no promotion.

## Bottom line

No candidate meets the precision target, and the sealed test cannot establish precision, recall or the false-alarm rate. Every accuracy figure rests on agent-only labels and reviews, so all of them are PROVISIONAL. Do not claim improved precision from this run.

- Selected point (blind calibration review, protocol amendment 2): `rules_q0.3`, the strictest rules point. Reviewed precision 13 true, 1 false (0.93; exact one-sided 95 percent lower bound 0.70), target missed. Every patch and temporal point reviewed at 0.12 or below.
- Sealed test (scored once from 114b833): the selected point accepted 1 track in 11.19 supported minutes; the blind review judged it true. Precision 1 of 1 (lower bound 0.05), recall 0 of 9 observable ember-positive truth tracks, false alarm 0 per supported minute (upper bound 0.27, above the 0.1 target). All three are INSUFFICIENT_EVIDENCE. The accept_all control reviews at 9 true of 76 judged (0.12).
- The selected rules are calibrated for the file_native profile only; the live booth profile (live_downscaled) reports the method unavailable, so the booth would count nothing in high-precision mode.

## Gates (gates.md, scripts/precision_gates.py)

| Gate | Status | Estimate | Bound | Basis |
|---|---|---|---|---|
| precision (sealed test, both strata pooled) | INSUFFICIENT_EVIDENCE, PROVISIONAL | 1 | one-sided 95% lower 0.05 | 1 true, 0 false of 1 accepted; window-judged n/a over 0 tracks |
| precision, low-observability stratum (reported) | INSUFFICIENT_EVIDENCE, PROVISIONAL | 1 | one-sided 95% lower 0.05 | 1 true, 0 false of 1 accepted; window-judged n/a over 0 tracks |
| precision, ember-positive stratum (reported) | FAILED, PROVISIONAL | n/a | one-sided 95% lower n/a | 0 true, 0 false of 0 accepted; window-judged n/a over 0 tracks |
| recall (ember-positive stratum) | INSUFFICIENT_EVIDENCE, PROVISIONAL | 0 | two-sided 95% lower 0 | 0 of 9 observable truth tracks matched |
| false alarm (sealed test, review) | INSUFFICIENT_EVIDENCE, PROVISIONAL | 0 per supported min | one-sided 95% upper 0.2678 | 0 false reviewed, inclusion 1, 11.19 min; window 0 per min (upper 23.06, not gated) |
| false alarm, low-observability stratum (reported) | INSUFFICIENT_EVIDENCE, PROVISIONAL | 0 per supported min | one-sided 95% upper 0.3349 | 0 false reviewed, inclusion 1, 8.945 min; window 0 per min (upper 30.85, not gated) |
| false alarm, ember-positive stratum (reported) | INSUFFICIENT_EVIDENCE, PROVISIONAL | 0 per supported min | one-sided 95% upper 1.336 | 0 false reviewed, inclusion 1, 2.243 min; window 0 per min (upper 91.33, not gated) |
| implementation | PASSED | 728 passed, 0 failed |  | every given test run passed with no failure or error |
| phone non-regression | PASSED |  |  | phone_check.json pass |
| runtime (Linux container reference) | FAILED | paint median 13 fps, p5 11 fps, decision p95 n/a ms | >= 20 fps, >= 10 fps, <= 250 ms | paint_fps_median: FAILED (13.0); paint_fps_p5: PASSED (11.0); decision_publish_to_state_p95_ms: NOT_RUN (not measured); decision frames: the scorer is unavailable on profile live_downscaled (method_unavailable:profile_mismatch): no decision frames, model inference not measured |
| runtime (booth Mac) | NOT_RUN |  |  | the booth Mac is not measured in this task |
| reliability (soak) | FAILED |  |  | carried forward: the owner's overnight soak of 2026-10-16 is OVERALL FAIL and no new passing soak report is given |
| reliability (long soak) | NOT_RUN |  |  | no long soak was run |
| default promotion | NOT_RUN | not promoted |  | the high-precision verifier stays opt-in; the default is never promoted by this run |

## Evidence and populations

- Development: C5 only (agent labels). Frame-level comparison, rerun from reviewed source: legacy raw detections precision 0.133, accept_all 0.293, best candidate (temporal, threshold 0.98) 0.786 (dev/c5_dev_comparison.json). Development evidence only, never a confirmatory claim.
- Calibration: 13 recordings (C8 calibration fires, the Rough prefix, four C7 burns); 9 observable truth tracks. Calibration preview of 33 candidates (calibration/), blind review of 829 items (638 sampled tracks, 191 decoys excluded from scoring, 0 unresolved; review_calibration/).
- Sealed test: low-observability stratum (6 recordings plus the tracking-only C8_MAPL007_C1; 0 observable tracks; false-alarm evidence) and the ember-positive stratum (3 recordings of 2 fires chosen by the frozen rule before any method output existed; 9 observable tracks, under the 20 the recall gate needs). Blind review of 151 items (review_test/).
- Reviewers and labellers are agents. The calibration and sealed reviews used two independent reviewers per batch (reviewer A haiku, reviewer B sonnet) and a sonnet adjudicator; the protocol fixes the two-reviewer and adjudicator design, not the model.

## Separate records

- Phone non-regression: same-host release 4d0092c against the verifier code: PASS (phone_check.json). The Mac verification (the release's saved Mac reports) is a separate requirement: NOT_RUN.
- Mac and Linux C5 baseline: the Mac score (FP 168) and the Linux reproduction (FP 156, identical TP and FN) are kept separately; the cause is UNRESOLVED (c5_baseline_discrepancy.json; OpenCV optimized dispatch ruled out).
- Runtime: Linux container references only (runtime/). Legacy itself paints below the goal on this host, so the booth Mac measurement is needed.
- Failed and invalid runs, with logs and reasons: invalid_runs/README.md (the first C5 comparison, phone check attempts, the stopped and out-of-memory calibration attempts, and a calibration preview with every model silently unavailable).
- Amendments and what motivated them: protocol.yaml (amendment log).

## Needed next

1. An independently annotated ember-positive population with at least 20 observable tracks, from recordings and incidents not used here, before any recall claim.
2. A precision claim needs at least 10 reviewed true or false accepted tracks on an untouched population; the sealed test here is used up.
3. Rules calibrated for the live profile before the booth can use the mode.
4. The booth Mac runtime and the Mac phone check.
