# Completed hourly forecast-to-routing integration

Date: 8 October 2026, Asia/Shanghai. Delivery: `forecast_routing_hourly_integration_20261008_v1`.

**Engineering complete.** The original saved hourly model runs through a separately versioned hazard constructor and adapter into the maintained router. Strict mode retains missing-information `UNSUPPORTED`; opt-in research mode supplies declared finite scenarios and produces checked conditional routes. Replay preserves incurred exposure and rejects unsupported history gaps. No mentor implementation or response is required to launch the delivered workflow.

**Real-fire and physical-safety validation remain unavailable.** The research constructor supplies assumptions where observations are absent. The route results concern its finite scenario, interval-enclosure, cell-center, graph and lattice contract. They do not demonstrate actual thermal exposure, operational road passability, ensemble coverage or evacuation safety.

## Run it

From the extracted directory, use Python 3.12:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -c constraints.txt
.venv/bin/python -B candidate/hourly.py native-run --mode research --repeats 2 --output-dir results/my_native_run
```

The last command reruns the original safely loaded checkpoint on portable numeric original-loader inputs, constructs the research fields, prepares the provisional matching Uljin graph, searches and checks the frozen simple query. Use `--mode strict` for the missing-information pathway. A zero process exit means a report was produced; inspect each row's `result.status` and `proof_level`.

`REPRODUCE.md` gives strict, precomputed forecast, custom assumption, tests, replay and original raster-loader commands. `python -B tools/verify_delivery.py` verifies the portable file manifest. `python -B candidate/hourly.py tests` runs the 181 release software tests. Matplotlib is needed only to regenerate the optional figure.

## What changed and what was preserved

- `candidate/native_forecast.py` invokes the preserved model and exports numeric fields with original support and hashes. Three supplied historical snapshots reproduce all 25 exported numeric arrays exactly, including NaNs (18 legacy outputs plus raw score and six support-diagnosis masks), through both raster-loader and portable numeric paths.
- `candidate/hazard_constructor.py` defines strict and research channels. The baseline uses four equal-weight scenarios, seed 20261008, independent Bernoulli occurrences, conditional uniform within-hour timing, illustrative current burning and unknown future-source assignments. Twelve 300-second intervals enclose a native 3600-second horizon. Every report retains the original forecast separately from the constructed fields.
- `candidate/forecast_bridge.py` admits version-two interval metadata with the named `RESEARCH_CONSTRUCTION` evidence class; version-one compatibility remains tested. It verifies masks, orientation, units, clocks, revisions and provenance.
- `candidate/hourly.py` and `candidate/replay_with_provenance.py` connect prepared geometry, routing, exposure history, update rejection and reporting. The native hour is never repeated to cover a longer mission.
- The isolated router patch only adds the research evidence class to `routing/validation.py`. Search, geometry, numerical exposure, support and budget semantics are unchanged. The inherited old seal is retained and intentionally detects this compatibility edit; `FILE_MANIFEST.json` is the new release's integrity authority.

All 13,263 original extracted files (5,144,081,683 bytes), original archive and original checkpoint remain unchanged. Fifty-three bundled runtime/checkpoint entries match the originals. Of 266 copied routing baseline files, only the explicit compatibility whitelist file differs. Original forecasts, scientific eligibility, protected labels and frozen studies were not modified. No retraining, GitHub push/merge, deployment or messaging occurred.

Original archive SHA256: `2541d820e22cf8e65d3ae5dc56e6f2e603f0cc0509422adf5dcef3f9a8e39e28`.
Original checkpoint SHA256: `5ef66e06842eeecd9272ba47d12ba577e71bd5d004b179dc11c37e7c49a723e8`.

## Diagnosis and assumptions

The actual endpoint is next-hour crossing of a retrospective kriging arrival estimate, using full-event histories/final perimeters and satellite detections. It is not directly observed first flame ignition. The research endpoint-to-flame mapping is explicit and unvalidated.

The original local burned-neighbor prediction population and missing environmental/current-state inputs explain sparse support; no loader error that would justify widening eligibility was demonstrated. Known original probability cells number 25/249/376 of 3596 at the three cutoffs; complete original expected-flux support is zero at all receiver cells. No physically justified non-emitter mask was available. No NaN was silently changed into evidence of zero hazard.

Research mode assumes unknown future probability 0.5, known previously burned cells active for 300 seconds, unknown current-state cells initially cold, and fixed illustrative combustion/receiver parameters. These assignments make the declared finite construction evaluable; they do not resolve original observation gaps. `ASSUMPTIONS.md` supplies the exact laws, parameter table, temporal positivity proof, current phase-energy consistency and sensitivity alternatives. `SUPPORT_DIAGNOSIS.md` preserves disjoint missingness counts and target provenance.

The temporal union covers interior flux maxima by summing nonnegative contributions from every source active anywhere in a bin. It can overestimate simultaneous flux or flag future within-bin contact at issue. Receiver values are cell-center spatial surrogates, not continuous-road spatial bounds. The FFT guard and direct numerical checks are not a formal floating-point enclosure proof.

## Frozen development panel

Master ledger: `results/frozen_panel_release_v2/ROWS.json`. Aggregate: `results/PANEL_SUMMARY.json`. Three Uljin cutoffs × thirteen variants × two fixed queries gives 78 unique cases. Six extra warm baseline calls give 84 saved calls.

| Primary case outcome | Cases | Meaning |
|---|---:|---|
| CONDITIONAL_OPTIMUM | 27 | Exact search completed within the supplied finite represented contract; saved witness separately checked |
| TIMEOUT | 27 | Difficult query unresolved at unchanged 30-second search limit |
| AT_ISSUE_FAILURE | 24 | Query refuses admission under the constructed first-bin contact/peak/exposure contract |

All 27 conditional cases use the frozen simple query; every difficult query that passes admission times out. `missing_one`, `comonotone`, `timing_early` and `current_unknown_active` produce admission failures for both queries at all cutoffs. The other nine variants yield one conditional simple route and one unresolved difficult query per cutoff. There is no demonstrated difficult-route success or general forecast-value advantage.

The original twelve variants, queries, budgets and seeds were frozen before routing outcomes. The thirteenth `current_unknown_active` variant was added after an engineering smoke route and before the comparative panel; it is exploratory. `evidence/PROTOCOL_TIMELINE_CORRECTION.json` discloses the timestamp ordering. No query/budget tuning followed results. Original freezes remain preserved.

Six completed cases with passing individual source guards were retained from an earlier prefix. A lifecycle bookkeeping repair followed; independent AST and whole-file checks establish unchanged numerical functions. Failed-seal cases were excluded and rerun. The master ledger explicitly records source runs and report paths; do not aggregate directory scans of retained failed attempts.

## Concrete route example

The preselected 03:00 baseline simple query traverses `w33431422:s1:f` from `osm:380419070` to `osm:380419072` in 10 seconds and dwells for 120 seconds. Total modeled per-member doses are 4.105429, 0.224057, 1.579121 and 0.264822 kJ/m². Maximum represented peak is 0.031580224 kW/m². Supplied study budgets remain 100 kJ/m² per member and 10 kW/m² peak; these are not medical/firefighter limits.

The example has positive thermal exposure and nonzero dwell. It is a single-edge engineering example, not evidence of long-distance evacuation performance. Saved details are in `results/ROUTE_EXAMPLES.json`; `results/ROUTE_EXAMPLE.png` shows original sparse support, the constructed field and the route distinctly. The baseline was not selected from outcomes to manufacture a route.

## Independent review and replay

The release CLI passes 91 original router tests, 18 bridge regressions, 20 constructor tests, 12 integration/history tests and 40 independent tests: 181 total. The original mentor suite freshly passes 436 tests. These counts refer to separate suites, not 617 independent field validations.

The reviewer implements its own rectangular radiation sum, area quadrature, rational route/grid integration and tiny timed-walk reference. All 78 cases satisfy the frozen ledger/config/source checks. All 30 saved finite cold/warm witnesses pass independent geometry, arrival, peak, dose and dwell checks. All 3744 member/bin radiation checks pass across 12,528 receiver evaluations. Extra checks at every witness route/dwell cell are transparently labelled post-outcome diagnostics. `INDEPENDENT_REVIEW.md` and `evidence/independent_native_checks_20261007T174823640886Z.json` give scope and raw residuals.

The documented replay checks a modeled stationary ten-second prefix and records its nonzero dose. Each new future receives an upward encoded maximum accepted old incurred dose, representing a conservative finite Cartesian recombination of accepted pasts and new futures. Reusing a seed or ID is not treated as physical trajectory correspondence. Assumption changes are prospective. The 03:00→06:00 historical gap is `UNSUPPORTED`; exposure remains charged, older pending completion cannot commit, and graph reset is explicit. The prefix is modeled, not observed movement. Successful update controls are separate generated fixtures.

## Latency, resources and portable scope

`results/LATENCY_MEMORY_RAW.json` preserves every stage measurement. On the actual Apple M5 Pro/macOS arm64 host with 24 GiB memory, the 78 precomputed-forecast cases have median construction/adapter 9.21 seconds and graph preparation 4.61 seconds. The constructor itself is about 0.061 seconds median; adapter/metadata processing dominates construction-stage time. Search includes the router checker; simple finite searches are about 0.10 seconds and unresolved difficult searches reach about 30 seconds. Cold first-query totals range 13.84–44.62 seconds; process totals including extra warm baseline searches reach 74.06 seconds. These are local measurements, not speed guarantees.

Peak process RSS ranges 164.05–336.38 MiB; it is a lifetime high-water mark. Serialized hazard payloads range 2.80–5.76 MB. Warm reuse avoids construction/preparation but does not remove difficult-query timeouts. Raw versus prepared equivalent hazards agree; their one-shot timings provide no universal speed claim. Native-model runs measure loading/inference/export separately; panel rows using precomputed exports do not count old inference timing as current CPU work.

The ZIP contains runnable code, the original safely loaded checkpoint, three numeric original-loader samples, native forecast samples, matching provisional historical OSM graph/provenance, tests, schemas, evidence and results. It excludes `work/`, complete environments, caches and credentials. Dependencies are pinned in `requirements.txt` with the tested transitive lock in `constraints.txt`. A minimal isolated 30-distribution Python3.12.1/macOS-arm64 environment was exercised with fresh code imports and exact original-output checks; this was an offline dependency-closure audit, not a fresh network installation or validation on every platform. Final extracted-ZIP smoke evidence is `evidence/FRESH_PORTABLE_SMOKE.json`.

## Failures retained and remaining limits

The rejected 900-second current phase would spend three copies of the stated 300-second energy budget; it was replaced before route outcomes. Strict launch initially lacked its mandatory assumption identifier and was repaired. A history-gap refusal initially failed to advance session generation; independent regression prompted the bookkeeping fix. A constructor test launcher initially ran no tests; it now executes all 20. Source-guard interruptions, an interpreter-dependent AST comparison failure, incorrect working-directory check, fixture-provenance error, a fresh-smoke checker that initially compared 18 legacy keys against the 25-field enriched export, and overly strong bitwise FFT reproducibility assertion remain in raw evidence and correction records. None is silently presented as a successful gate.

Still unavailable: causal same-fire current activity, direct flame/thermal observations, calibrated endpoint-to-ignition mapping, uncertain exterior emission, ensemble coverage, measured combustion geometry, continuous road spatial bounds, operational passability and deployment/physical-safety validation. The Uljin graph is provisional historical OSM with documented speed/oneway/restriction assumptions. Existing recorded-return and partial-edge limitations remain. There is no claim of universal routing performance or real-fire safety.

`VERIFICATION.json`, `FILE_MANIFEST.json`, the adjacent ZIP SHA256 file and the canonical-context append record make this release inspectable. `MENTOR_OPTIONAL_REVIEW.md` lists optional scientific feedback; no mentor action is required to run the complete software.
