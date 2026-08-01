# Network-drift sensitivity: what moves when only the road network moves

**Artifact:** [`data/processed/network_drift_experiment.json`](../data/processed/network_drift_experiment.json)
**Script:** `scripts/run_network_drift_experiment.py`
**Measured:** 2026-08-01

## Headline

> A **0.05 %** change in the walk network moved the binary reachability verdict by
> **33 %** — 24 origins with no surviving vehicle ingress became 32 — while the
> responder-exposure reduction moved **0.56 percentage points**, from 72.03 % to
> 72.59 %. **Binary verdicts are sensitive to network topology; paired contrasts
> are robust to it.**

## Why this experiment exists

It was not planned. `data/processed/rescue_routing.json` was written 2026-07-19;
the OSM graphs it consumed were overwritten 2026-07-24 and cannot be recovered
([`DATA_LOSS_2026-07-24.md`](DATA_LOSS_2026-07-24.md)). Re-running it today
cannot reproduce the committed numbers.

That loss is also, accidentally, a clean controlled experiment. Everything else
is pinned:

| held constant | varied |
|---|---|
| seed (20250603) | **the OSM walk + drive network — and nothing else** |
| every `RescueConfig` assumed parameter | |
| synthetic hazard envelope | |
| synthetic terrain / land–sea mask | |
| pipeline code | |
| refuge (50) and depot (4) POI layers | |

So the arm-to-arm difference measures exactly one thing: **how sensitive each
reported quantity is to road-network topology.**

## Method

| | arm A | arm B |
|---|---|---|
| label | committed | re-run |
| run | 2026-07-19 08:53 UTC | 2026-08-01 |
| network | OSM graph ≤ 2026-07-19 — **overwritten, unrecoverable** | OSM graph 2026-07-24, preserved in `data/snapshots/` |
| network sha256 | — (lost) | `osm-walk_…2bff8d85`, `osm-drive_…f537bdf5` |
| `config_hash` | — (predates `config/`) | `35349edc…` |
| walk nodes | 8439 | 8443 (+4, **+0.047 %**) |
| walk edges (collapsed) | 11015 | 11020 (+5, **+0.045 %**) |

Arm A's parameter values were proven bit-identical to the current config in
PHASE 1-A (30/30 `RescueConfig` defaults, 4001/4001 Tobler sample points), so the
absence of a stored `config_hash` for arm A does not leave the comparison open.

## Results

| metric | arm A | arm B | Δ | Δ % |
|---|---:|---:|---:|---:|
| origins scanned | 439 | 441 | +2 | +0.46 % |
| saved by rescue-reachable refuge | 10 | 12 | +2 | +20.00 % |
| already safe | 262 | 255 | −7 | −2.67 % |
| no safe pedestrian route | 143 | 142 | −1 | −0.70 % |
| **no surviving vehicle ingress** | **24** | **32** | **+8** | **+33.33 %** |
| needs rescuer | 167 | 174 | +7 | +4.19 % |
| dispatch | 143 | 142 | −1 | −0.70 % |
| shortest path enters hazard | 57 | 59 | +2 | +3.51 % |
| refuges | 50 | 50 | 0 | 0.00 % |
| refuges rescue-reachable | 24 | 24 | 0 | 0.00 % |
| responder exposure, shortest path (prob·min) | 6.1173 | 6.1487 | +0.0314 | +0.51 % |
| responder exposure, survival-aware (prob·min) | 1.7112 | 1.6855 | −0.0257 | −1.50 % |
| **responder exposure reduction** | **72.03 %** | **72.59 %** | **+0.56 pp** | +0.78 % |

## Interpretation

**Binary verdicts amplify.** `no_surviving_vehicle_ingress` moved 33 % on a
0.05 % network change — roughly a 700× amplification. This is structural, not a
bug: reachability is a threshold on a shortest-path survival time. An origin
sitting near the threshold flips when one edge appears, disappears, or changes
length. Nothing about the fire model changed.

**Paired contrasts absorb it.** Both routing policies traverse the *same*
perturbed network, so the perturbation largely cancels in the ratio. Each arm's
exposure mean moved ~0.5–1.5 % and the reduction moved 0.56 pp.

**What this licenses, and what it does not.** It supports the standing claim that
"contrasts are the robust result; absolute magnitudes are illustrative" — that
was previously an argument, and is now a measurement. It does **not** show the
routing method is right, nor that 72 % generalises beyond this fire, this
synthetic hazard, and these assumptions. One perturbation, one direction, one
fire.

## Reporting rules

* Quote counts (439 / 143 / 24 / 167) **only** with their arm and vintage, e.g.
  "24 origins (committed 2026-07-19 network)". They are not stable to a network
  refresh.
* Arm B does **not** supersede arm A. Neither network is "right" — OSM is a
  living dataset. Never substitute one arm for the other, and never average them.
* Registered in [`NUMBERS.json`](NUMBERS.json) under
  `network_drift_*`, each carrying the caveat that it is a 2026-07-24-network
  re-run and separate from the committed values.

## What would sharpen it

A single perturbation cannot separate "this network is 0.05 % different" from
"this *particular* 0.05 % happened to sit near thresholds". Re-fetching OSM at
several dates, or bootstrapping edge dropouts, would turn one point into a
distribution. Not done — recorded as the obvious next step.
