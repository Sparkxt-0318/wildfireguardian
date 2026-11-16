# Historical evidence for the v8 corridor experiment

These records summarize one historical experiment performed on 15 November 2026. They make its reported numbers inspectable. The package refactor is a new code artifact. The historical campaign used separately frozen worker and numerical dependency hashes, not this package checkout. These records do not establish a new benchmark of the refactored package.

## Dataset and methods

The population comprised 273 routing requests from 18 region and revision groups covering five physical fires. The forecast revisions were reconstructed retrospectively from observations at successive cutoffs. The two Uiseong–Andong focus missions informed development.

The worker had a 30-second complete-request deadline and a 3,072 MiB sampled memory guard for the worker process family and controller. It executed once per request, serially on one Mac, with an operating-system awake assertion. The independent reviewer verified original-road journey checks, the claimed optimum and no-route bounds, resource samples and the frozen inputs. No external guard stopped a request. All launch-to-cleanup UTC intervals were below 30 seconds.

| Measure | Historical v7 protected run | Historical v8 run |
| --- | ---: | ---: |
| Checked journeys | 189 | 189 |
| Proved modeled no-route | 84 | 84 |
| Unresolved feasibility | 0 | 0 |
| Total request time | 540.417 s | 568.667 s |
| Median request time | 1.101 s | 1.156 s |
| Maximum request time | 15.998 s | 28.244 s |
| Peak sampled process-family memory | 1,413.25 MiB | 1,679.203 MiB |

These are single runs on one host. Timing differences include host variation. Sampling can miss short memory spikes.

Of the v8 results, 187 checked routes had independently verified earliest-arrival proofs. Minimum driving at that arrival was independently verified for 168 routes. Two feasible Uiseong–Andong routes had no earliest proof. The independent review obtained lower arrival bounds after the timed experiment.

| Uiseong–Andong mission | Checked arrival | Independent lower bound | Gap | Complete request |
| --- | ---: | ---: | ---: | ---: |
| FN1 | 3,187 s | 3,180 s | 7 s | 28.244 s |
| FT1 | 3,074 s | 3,070 s | 4 s | 23.683 s |

Arrivals are measured from the 01:00 UTC forecast issue, 23 March 2025. The missions depart at 01:10 UTC. Each route includes the required two-minute destination stay, passes the modeled checks for all four fire histories and occupies supported forecast cells throughout. The new worker's fine checker was adapted from the earlier reviewer implementation and shares geometry and MPFR components. The original adaptive checker independently accepted the two scored witnesses in offline checking-only runs. The new post-run lower bounds used an independent turn-aware relaxation with fractional activity and were not included in the timed request.

A separate Yeongdeok FW2 result illustrates timing-sensitive refinement. Its arrival remained unchanged and it passed the journey check, while driving rose from 1,011 s to 1,197 s when the candidate refinement check did not complete. Minimum driving was unproved in both runs.

## Included records

- `receipts.csv` records all 273 case outcomes, resource measurements, verification flags and recorded source hashes.
- `proofs.json` contains the reviewer's case-level route checks and proof summaries. Route hashes and records are evidence pointers, not a replacement for the source graphs, forecasts, paths, worker receipts or verifier.
- `summary.json` records the audit totals and the Yeongdeok regression.
- `turn_trials3.json` and `turn_trials4.json` contain the post-run FT1 and FN1 bound trials, including unsuccessful tests. `turn_selfcheck.json` records 125 exhaustive tiny-graph turn checks.
- `utc_clock_audit.json` records the separate launch-to-cleanup check.
- `packaged_smokes.json` and the two `packaged_*_resource.json` files record two guarded tests of the refactored worker on original FN1 and FT1 data with authenticated warm graph caches. They record arrivals, timing, sampled memory and output hashes. They are not an independent review or a full-census rerun.
- `SHA256SUMS` hashes the copied historical records and packaged smoke records. The hashes identify these copies; they do not independently authenticate the underlying data.

The original local experiment also includes the complete historical job outputs, the frozen absolute-path input and source manifest, and native checker receipts. Those artifacts are not distributed with this package. A clean clone cannot reproduce the 273-case campaigns from the records above. Public-source rights and access for the underlying forecast, graph and third-party data need to be resolved for any redistribution. The repository's existing data terms apply.

Under the historical benchmark's permissive missing-input policy, 163 of 189 returned routes occupied at least one cell-hour without native forecast support. A model-scoped no-route decision concerns the configured roads, destination, horizon and hazard inputs. The evaluations do not establish physical safety or operational effectiveness.

## Packaged worker full-census rerun

The refactored packaged worker was run locally against all 273 original frozen requests at package commit `61b3a4c8464e6c5499578d4d4acae7f1354b6122`. The worker used the original inputs and separate authenticated graph cache copies, preserving the benchmark's setup boundary and limits. The five `packaged_273_*` files contain the independently reconstructed case ledger, proof summaries, timing measurements, target rechecks and aggregate results. Relative to historical v8, every authoritative status matched and all 189 returned arrivals and driving durations matched.

The verifier confirmed 189 feasible journeys, 84 modeled refusals, 187 earliest-arrival proofs and 168 minimum-driving proofs. Both target paths were also rechecked using the distinct original adaptive thermal checker. The longest guarded worker request was 28.950 seconds and largest sampled process-family/supervisor memory 1,642 MiB. Guard CLI startup and cleanup are additionally recorded; its maximum was 29.009 seconds. Adding preparation adapter time gives a maximum 29.035 seconds. Cache copy and forecast generation remain outside these timings. A sample may miss a shorter memory peak.

The timed run's adapter initially preserved the historical template's worker hash. The campaign separately bound the actual packaged-worker hash before each scored call and pinned the package and dependencies. The subsequent PR change fixes this metadata in the adapter and validates the worker entrypoint in the supervisor. The immutable source identity for the experiment remains the original package commit above. A post-run fix does not retroactively change the measured software.

## Native-support full-census rerun

The support_273 files record the final support-aware, tie-preserving rerun of the 273 original requests and its independent audit. Inputs, warm-cache preparation and the 30-second / 3,072 MiB sampled guards match the historical benchmark. The support-aware policy changes which routes may be published. The timed jobs explicitly selected strict policy, which is also the default.

- 28 supported checked journeys, including 26 independently proved earliest among supported journeys and 23 independently verified minimum-driving claims.
- 78 independently proved model-scoped no-route decisions and 167 unresolved.
- Zero of the 28 returned journeys touched a cell-hour missing native forecast support.
- Two of the 163 previously unsupported journeys received supported alternatives, with +71 and +2 seconds to arrival. The other 161 are unresolved. Of those 161, 153 have at least one endpoint in a missing native cell.
- The 26 previously supported journeys retained the same arrival and driving times. Six prior model refusals became unresolved under strict processing.

The all-18-packet source-crop validity audit is sanitized to omit local paths. The source input and campaign machinery remain external, so these records do not by themselves reproduce the study. The independent verifier's initial integer-clock type error and its complete rerun are documented in the local independent report. The support lattice self-test records 150 exhaustive small-graph checks.

The policy cannot create missing input or validate off-route thermal-source coverage. An unresolved result is not a no-route proof. A supported route is not a field safety guarantee.

## Forecast-input recovery on all 273 requests

After recovering forecast inputs for 16 of 18 windows, we reran every original request with the same router and limits. Independent checks found **35 supported routes, 114 model-scoped no-route proofs and 124 unresolved cases**, compared with 28, 78 and 167 before recovery. All returned journeys had native forecast support throughout driving, permitted waits and destination stays.

Of the 153 cases that previously had a missing endpoint, 11 now have complete endpoint coverage and 7 have a checked route. 17 others gained partial coverage and 125 gained no fully supported endpoint cells. Across the whole cohort, the archive supplied 4,442 additional supported road-grid cell-hours. All previously supported probabilities and scenario ignition draws were preserved.

[Case ledger, sensor sources and independent checks](forecast_input_recovery/README.md)
