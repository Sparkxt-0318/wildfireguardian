# Forecast-conditioned, time-expanded routing for household-level wildfire evacuation and rescue in rural Korea

## Abstract

[GAP: abstract to be written from registered numbers once Results 4.1–4.4 are final; the student rewrites it in their own words before any submission]

## 1. Introduction

The March 2025 Gyeongbuk wildfires killed 27 people, most of them residents in their sixties to eighties, in a region where satellite detection and provincial fire-danger forecasts were already operating [@wwa2025korea]. The failure was not detection. It was the last kilometre: telling a specific household which way to walk, and telling a rescue crew which homes it can still reach and until when. Korea's national forecast answers "how likely is a fire in this district"; a household needs "where will this fire be in the next hours, and is my road still open".

This paper describes WildfireGuardian, a system that couples a data-driven wildfire-spread model to household-level evacuation and rescue routing, evaluated on six real Korean fires with the fire held out, and reports its results through an auditable registry in which every number is re-derived from a committed artifact. The contribution is not the spread model, which is deliberately simple, but (i) the coupling of an event-held-out, calibrated ignition-probability field into a time-expanded pedestrian router with a rescue-ingress term and operator-facing outputs, and (ii) the evaluation design for a six-fire dataset, including the claims that were withdrawn along the way.

## 2. Related work

Learned next-day fire-spread models are trained on hundreds of fires on other continents [@wildfirespreadts2025]; six Korean fires cannot compete on that axis and this paper does not try. [GAP: related-work table (WFG-026): time-expanded evacuation routing, WUI evacuation simulation, shelter placement, geostationary detection latency; every entry opened at its URL before it is cited]

## 3. Data and methods

### 3.1 Study fires and public inputs

Detections from NASA FIRMS [@firms], reanalysis weather from ERA5 [@era5], terrain from SRTM, land cover from ESA WorldCover and road networks and building footprints from OpenStreetMap. Six fires: Gangneung 2023, Hongseong 2023, Miryang 2022, Uiseong-Andong 2025, Uljin-Samcheok 2022 and Yeongdeok 2025.

![System overview. Public inputs feed a per-cell ignition-probability model; its time-sliced hazard field drives a time-expanded pedestrian router and a rescue-ingress calculation; the outputs are operator documents. Every reported number is re-derived from its committed artifact by the registry gate.](figures/F1_system.png)

### 3.2 Spread model and evaluation protocol

A gradient-boosted classifier predicts, for each grid cell, the probability of detection at the next satellite overpass. Evaluation is leave-one-fire-out: the model is trained on five fires and scored on the sixth, so no cell of the held-out fire is seen in training. The mean of the six held-out ROC-AUC values is reported as the generalisation figure; the pooled out-of-fold AUC is reported only as such.

### 3.3 Time-expanded routing and rescue ingress

[GAP: Methods 3.3 prose from docs/rescue_routing.md, docs/routing_limitations.md and docs/decision_shift.md: edge costs from the time-sliced field, the closure time of a corridor, the rescue-ingress survival term, and the three-way partition of origins]

### 3.4 Sensitivity and controls

[GAP: walking-speed and pre-movement-delay sweeps (WFG-025) and the network-drift control; until then only the committed forecast-robustness and dilation perturbation results are cited]

## 4. Results

### 4.1 Held-out spread skill

![Held-out ROC-AUC per fire under leave-one-fire-out cross-validation. The dashed line is the mean of folds; the dotted line is the pooled out-of-fold AUC, a different quantity.](figures/F2_lofo_auc.png)

[GAP: Results 4.1 prose with the registered mean-of-folds and pooled values and the small-fold caveat for Gangneung 2023]

### 4.2 What the forecast changes about who can walk out

[GAP: Results 4.2 from real_roads_real_hazard_canonical.json and docs/decision_shift.md: the three-way partition on the canonical Yeongdeok field with the walk-coverage caveat, and the three-region table]

### 4.3 Operating point

[GAP: operating-point table from data/processed/operating_point/ once WFG-019's figure is drawn in paper style]

### 4.4 Rescue ingress and dispatch ordering

[GAP: Results (dispatch ordering) from docs/dispatch_ordering.md and docs/ordering_boundary.md, including the negative result that the deadline-first ordering does not beat the alternatives]

### 4.5 Leak-free fold and hindsight oracle

[GAP: leak-free Yeongdeok fold and hindsight-oracle arm (WFG-032)]

## 5. Discussion

[GAP: discussion: what the coupling adds over a spread map alone; why n = 6 forbids a threshold guarantee; the withdrawn severity-versus-direction claim; the 32.6 % coverage caveat; expert consultation quotes with consent (NH-009)]

## 6. Limitations

[GAP: limitations from docs/routing_limitations.md and the model card: ERA5 resolution, six fires, sampled origins rather than households, OSM refuge semantics, no live weather]

## 7. Conclusion

[GAP: conclusion after 4.1–4.4 are final]

## Data and code availability

The code, committed artifacts, evidence registry and this manuscript are at https://github.com/Sparkxt-0318/wildfireguardian. Raw geospatial inputs are public and are re-acquired by the scripts in `scripts/`; the repository distributes no raw data.
