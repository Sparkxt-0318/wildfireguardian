# Gates of precision_20261017

Computed 2026-10-18T05:23:51+08:00 from saved results by scripts/precision_gates.py (sha256 7955d110900273d0).

Statuses: PASSED, FAILED, NOT_RUN, INSUFFICIENT_EVIDENCE; PROVISIONAL marks every accuracy status that rests on agent-only annotation (all of them here). The gates are separate: none stands in for another.

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
