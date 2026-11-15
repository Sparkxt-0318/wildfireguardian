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

The original local experiment also includes the complete historical job outputs, the frozen absolute-path input and source manifest, and native checker receipts. Those artifacts are not distributed with this package. A clean clone cannot reproduce the 273-case campaign from the records above. Public-source rights and access for the underlying forecast, graph and third-party data need to be resolved for any redistribution. The repository's existing data terms apply.

Under the historical benchmark's permissive missing-input policy, 163 of 189 returned routes occupied at least one cell-hour without native forecast support. A model-scoped no-route decision concerns the configured roads, destination, horizon and hazard inputs. The evaluations do not establish physical safety or operational effectiveness.
