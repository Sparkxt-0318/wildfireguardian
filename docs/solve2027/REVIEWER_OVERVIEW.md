# WildfireGuardian: reviewer overview

**Research prototype.** "Planning aid only — not for live evacuation operations." This page describes `Main`; each number links to its source or to the card that cites it.

## Problem and who it serves

A forecast map does not tell a care-facility manager whether a vehicle journey would meet fire, or how late it can still leave. WildfireGuardian's intended use is "to support responders and caregivers planning assistance for residents who may need more time to evacuate, including older adults" ([README](../../README.md)). The [planner](../../planner/README.md) is a pre-season tool for "지자체 safety staff, 산림청 / fire departments and care facility managers".

## What it does

1. **Forecast.** Checkpoint c651 predicts the next-hour probability that each [375 m](../../planner/docs/ARCHITECTURE.md#1-fixed-facts-do-not-change) cell starts burning ([model card](MODEL_CARD.md)).
2. **Scenarios.** Each check uses [four scenario members](../../planner/docs/ARCHITECTURE.md#1-fixed-facts-do-not-change) drawn from that forecast, on top of the fire already burning. They are not simulations of the actual fire.
3. **Checked journeys.** Route search, then a check of the whole journey (driving, permitted waiting, required destination stay) against every member for flame contact, peak heat flux and cumulative dose, within a fixed [30 s budget](../../api/README.md#what-it-is) per request.
4. **Leave-by deadlines and plan sheets.** For every village and care facility, the planner shows **출발 마감**, "the latest departure offset with a checked route", with printable plan sheets and exports ([planner](../../planner/README.md#source-layout)).

There are exactly three verdicts: `checked_route` (a checked route within the model), `model_no_route` and `unresolved`. Unresolved is never safe and never counts toward a deadline ([decision card](DECISION_CARD.md)).

## Try it

- **Demo:** <https://sparkxt-0318.github.io/wildfireguardian/>. Live only once the static planner demo (proposed separately, below) is on `Main` and GitHub Pages is enabled.
- **Docker:** `docker compose up --build` is set up to start the planner at <http://127.0.0.1:8080> with the Route-Check API behind it. CI built and ran both images on `linux/amd64` for commit `2b1d54d1` ([run](https://github.com/Sparkxt-0318/wildfireguardian/actions/runs/41494735774); [reproduction guide](REPRODUCE.md)).
- **Linux or macOS with Python 3.12:** `make reproduce-linux` (Linux also needs GNU `time`).

## How we know it works

- **Routing benchmark** ([README](../../README.md#frozen-october-15-comparison), [independent report](../../research/routing/INDEPENDENT_REPORT.v1.md)). "20 missions across five Korean regional panels from four parent fires", 80 executions on the evaluated macOS host. The candidate resolved **20/20** missions in both repetitions, giving 15 checked routes and five scoped refusals. The reference resolved 13/20. Unresolved executions were 0/40 against 14/40. "The result is 100% verified on-time mission resolution on this panel, not 100% routing accuracy or 20 evacuation routes." No speed gain: median request time 8.006 s (candidate) versus 7.344 s (reference) in 26 jointly resolved route pairs.
- **October 29 replay of an opt-in kit** ([README](../../README.md#verified-october-29-request-window-update), [records](../../research/routing/request-window-20261029/README.md)). Its candidate was the opt-in request-window/check-first kit, not kit v3, which stays unchanged and runs in the API. All 80 executions completed again, and all 56 returned witnesses matched the historical routes. Independent programs checked 18 distinct returned journeys and 72/72 scenario-specific thermal thresholds.
- **Why checking matters** ([constraint ablation](../../research/routing/final-input-ablation/README.md)). Travel-time-only routing returned a route for all 20 missions, but only 12 passed the full rules. Eight travel-only routes encountered predicted flames. Flame avoidance found three checked detours, arriving 490, 527 and 531 seconds later.
- **Software checks** ([README](../../README.md#software-verification-after-integration)). 3,531 forecast/cross-track tests passed, and 177 radiation/export/scenario/SIPP/truth tests passed with no skips. 3,640 protected artifacts remained byte-identical.
- **On Linux, not the evaluated host** ([Linux VM report](../../api/reports/LINUX_VM_REPLAY_2026-10-17.md)). On a 4-vCPU VM with the unchanged 30 s budget, the Route-Check API matched the record for 17 of the 20 final-panel missions (16/20 on a re-run). The others ran out of time: "No mission returned a different answer".
- **Planner data.** Precomputed results for the planner's two 2025 demo regions come from a host that [planner/cache/INDEX.json](../../planner/cache/INDEX.json) records as `macOS-27.0.1-arm64-arm-64bit`, 15 CPUs, Python 3.12.1, purpose `booth`, live API.

## What is not established

- "Field effectiveness and evacuation safety have not been established." A checked route "is not a guarantee of real-world safety" ([README](../../README.md#reproducibility-attribution-and-intended-use)).
- **Forecast skill** ([model card](MODEL_CARD.md#metrics-exactly-as-recorded)). On held-out test cells, c651's Brier scores are only marginally below no-learning baselines'. Its Korean AP is below the global-neighbor baseline's, and its Korean F1 below the training-prevalence and global-neighbor baselines'. Its four-scale design "was not shown to outperform its smaller alternatives". Of the 15 benchmark routing windows, "eight contain no sampled new ignition in all four members" ([independent report](../../research/routing/INDEPENDENT_REPORT.v1.md#scientific-interface-and-limits)), so there the checked hazard came only from the fire already burning.
- **Physics.** Flame-front radiation v2 is under "**Physics HOLD**", and the heat model is not calibrated against measured flux ([README](../../README.md#current-research-status)).
- **Model scope.** Scenarios cover [one hour](../../planner/docs/ARCHITECTURE.md#1-fixed-facts-do-not-change) after each recorded input time. Roads assume "40km/h" with no field validation ([decision card](DECISION_CARD.md#outside-the-decisions-scope)). Destinations come from OpenStreetMap tags. Smoke, embers, accessibility and destination suitability are outside the check.
- **Hosts.** Only native macOS on an [Apple M5 Pro](../../research/routing/INDEPENDENT_REPORT.v1.md#exact-candidate-and-evaluation) was evaluated. Elsewhere, heavy missions can time out (`unresolved`). A slow or loaded host can leave the optimality proof unfinished even with a longer budget, because the frozen worker caps its first search stage at [6 s](../../integration/kit/phaseB/rda_worker_v1_1.py); the Linux replay reports this separately ([reproduction guide](REPRODUCE.md#replay-outcomes)).

## Roadmap

From [scientific next steps](../../README.md#scientific-next-steps) and [future extensions](../FUTURE_EXTENSIONS.md):

1. Physically validate the flame-front radiation model.
2. Complete and independently verify the v2 checker.
3. Address scenario support, causal forecast alignment and broader held-out evaluation.
4. Evaluate operationally with intended users and responders.

## Proposed separately

Proposed in November 2026 as separate pull requests (check the repository for their status): public static planner demo; explained deadlines; field-message kit; impact numbers (`research/solve2027-impact/`).
