# Synthetic-truth scoring: strict support admission remains unresolved

The strict campaign admission study made 428 configuration-level attempts on 20 fixed Korean missions over 15 cutoffs. All were unresolved because the trajectory exports contain unknown global sources. The requested false-safe and false-refusal rates are unidentified, not zero. There are no scored truth cases and no population uncertainty claim.

| Campaign | Retained case records | Result |
|---|---:|---|
| C1, matched-support independent versus trajectory members | 6000 | unresolved admission, null truth scores |
| C2, rate and baseline diagnostics | 12000 | unresolved admission, joint-known-cell Brier only |
| C3, member count and acceptance rules | 24000 | unresolved admission, no acceptance trade-off identified |
| C4, the two Gyeongbuk regional panels | 8 | unresolved admission, retrospective truth scoring not run |

Each holdout configuration retains 100 trajectory indices per cutoff, indices 512 through 611, excluded from the planning pool 0 through 511. Truth draws are reused across missions/configurations. This is a repeated conditional case design, not 2,000 independent fires. The two Gyeongbuk panels share one parent incident. No repetition is counted as an independent mission. Wilson intervals cannot be computed for null truth scores; if risk scores become identifiable, case-wise Wilson intervals would still be descriptive under this clustered design.

## What was implemented

`wfg_synthetic_truth.score_decision` enforces the three outcome states, rejects truth/planning identity leakage and refuses a contact-only clairvoyant reference masquerading as a full-policy optimum. Unknown check support produces null scores. A refusal with a checked full-policy clairvoyant route is flagged false-refusal; a checked journey violating known truth contact is false-safe. Unit tests exercise those rules. A copy of the frozen independent centre checker provides full journey grammar, turns, waits, history, dwell, peak and linear dose checks. Its scope is the cell-centre surrogate; it is not the continuous-road checker.

The decision wrapper proposes contact routes, checks each member, and permits only checked witnesses. Rejected candidates remain unresolved. Bounded heuristic lazy cuts never produce a global no-route certificate after eliminating alternatives. Exhaustion of the all-member relaxation cannot certify a k-of-m refusal. Weighted subset search is not implemented and is not disguised as post-hoc optimality.

The strict admission policy requires known global emitting sources: an unknown emitting cell can contribute flux at a known receiver. The present exports cannot discharge that condition. The runner therefore records unsupported admission rather than inventing complete hazards or clairvoyant optima. This is an executed admission study, not a completed OSSE routing-risk study. It does not supply a numerical answer to the forecast-quality-versus-decision-value question.

## Reproduce

```sh
python research/synthetic-truth/run_strict_support_campaigns.py --exports EXPORTS_V3 --cases research/sipp-routing/native-panel-20261030/CASES.json --data-root DATA_ROOT --out FRESH_SUPPORT_RUN
python research/synthetic-truth/analyze_strict.py --run FRESH_SUPPORT_RUN
PYTHONPATH=experimental/synthetic-truth/src:experimental/scenario-members/src:experimental/sipp-routing/src python -m pytest experimental/synthetic-truth/tests
```

`strict-support-20261030/` retains JSON lines per campaign, SUMMARY.csv and RESULTS.json. Each record keeps null true_contact, true_peak, true_dose, arrival, clairvoyant arrival, false-safe, false-refusal and regret when unscorable. Candidate Brier scores use only the recorded joint-known, initially unburned cells; their denominator is stored per case and they are not complete-domain scores. Seed 20261008; actual c651 trajectory exports use seed 0 and 1,024 trajectories. Input and script hashes, host, Python and configuration identities are recorded in RESULTS.json and the export audit.

## Figures

Figure 1, fig01_truth_score_availability (PNG 300 dpi and SVG), displays unscorable C1 cases for each matched-support member configuration. It visualizes missing evidence, not a zero injury or error rate.

Figure 2, fig02_decision_vs_forecast_quality (PNG and SVG), plots the diagnostic Brier score on joint known cells against the unresolved admission fraction for the C2 configurations. All truth-risk rates remain null. The chart cannot establish a decision-quality frontier.

## Scope and limits

Truths are model or reconstruction based, not observed evacuations. Results are conditional on the represented road graph, lattice, horizon, source domain and construction policy. There is no field validation. Complete C1/C2 risk scoring, C3 acceptance trade-offs, retrospective route maps and the Caldor c651 alignment remain open. Independent reconstructed-arrival, NIROPS GeoJSON and stored external-simulator readers are now implemented and tested. Their units, georeferencing, missingness and source identity remain distinct from full-policy truth scorability; see experimental/synthetic-truth/README.md and REAL_READERS_SMOKE.json. No physical-fatality or real casualty attribution is made.

Radiation law v2 is deliberately NOT_RUN. Track 1A's physics and enclosure gate remains unresolved, and the explicit `radiation_law="v2"` seam raises NotImplementedError. No synthetic fronts or guessed present-fire phases bypass that gate. The prior remote campaign's error-rate headlines are not reused: its missingness assumptions differ from the strict contract in this run.

The global-support refusal used here is a conservative admission choice. It is not proof that every local checker or a checker with pessimistic bounds on unknown sources would fail. Those alternative bounds and their effect on case scorability have not been established in this track.

A separate own-members regression passed the copied complete centre checker for all four Uljin members at arrival 3,119 s, with zero rejected members. See ULJIN_TRUTH_MEMBERS_REGRESSION.json and check_uljin_truth_members.py. It is not a withheld-truth risk estimate or a new clairvoyant proof.

REAL_READERS_SMOKE.json records three source-identified real-file checks at software commit a1fb31a4e. KFS_01 reconstruction plus aligned SD retains 10,955 supported cells and 7,768 unknown cells and remains unscorable as an exact truth. CedarCreek has eight invalid original geometry records, retained with source_record_id and validity reasons; the reader refuses the complete 10,640-cell collection without repair. A cached Wapiti FARSITE file yields a complete 11,655-cell deterministic arrival model on its explicitly covered grid. The latter is MODEL_RELATIVE_ARRIVAL_ONLY, lacks independent flaming phases and thermal inputs, and is not an observed or full-policy truth certificate. Extracted file digests are verified against the existing extraction and perimeter ledgers. Current native FARSITE installation availability remains unconfirmed; no native run or historical performance-metric inspection occurred.

POST_REPAIR_CORE_AUDIT.json records the independent audit's 9/9 repaired core interfaces. Old campaign outputs and their exact producing source remain historical evidence. The current readers and guards have separate source hashes, tests and receipts. No null risk record was reclassified as safe, and the requested retrospective and risk campaigns remain gated.
