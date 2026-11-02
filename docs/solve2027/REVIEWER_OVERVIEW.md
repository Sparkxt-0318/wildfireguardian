# WildfireGuardian: reviewer overview

**Research prototype.** "Planning aid only — not for live evacuation operations." This page describes what is on `Main`; every number links to the file it comes from.

## Problem and who it serves

A wildfire forecast map does not tell a care-facility manager or a local safety officer whether a specific vehicle journey would meet fire, or how late it can still leave. WildfireGuardian's intended use is "to support responders and caregivers planning assistance for residents who may need more time to evacuate, including older adults" ([README](../../README.md)). The [planner](../../planner/README.md), the product-like surface, is a pre-season tool for "지자체 safety staff, 산림청 / fire departments and care facility managers".

## What it does

1. **Forecast.** Checkpoint c651 predicts the next-hour probability that each 375 m cell starts burning ([model card](MODEL_CARD.md)).
2. **Scenarios.** Each check uses four scenario members drawn from that forecast, on top of the fire already burning. They are not simulations of the actual fire.
3. **Checked journeys.** Route search, then a whole-journey check against every member. It covers driving, permitted waiting and the required destination stay, and tests flame contact, peak heat flux and cumulative dose. Each request has a fixed 30 s budget.
4. **Leave-by deadlines.** For every village and care facility, the planner shows **출발 마감**, "the latest departure offset with a checked route". Each time comes "with the evidence behind it: the route, per-scenario heat exposure, compute time and full provenance".
5. **Plan sheets.** Printable A4/PDF plan sheets and data exports ([planner](../../planner/README.md#source-layout)).

There are exactly three verdicts: `checked_route`, `model_no_route` and `unresolved`. Unresolved is never safe and never counts toward a deadline ([decision card](DECISION_CARD.md)).

## Try it

- **Demo:** <https://sparkxt-0318.github.io/wildfireguardian/>. Placeholder: it goes live only after the static demo (under review, below) is merged and GitHub Pages is enabled.
- **Docker:** `docker compose up --build` starts the planner at <http://127.0.0.1:8080> with the Route-Check API behind it ([reproduction guide](REPRODUCE.md)).
- **Linux or macOS with Python 3.12:** `make reproduce-linux` (Linux also needs GNU `time`).

## How we know it works

- **Routing benchmark** ([README](../../README.md#frozen-october-15-comparison), [independent report](../../research/routing/INDEPENDENT_REPORT.v1.md)). "20 missions across five Korean regional panels from four parent fires", 80 executions on the evaluated native macOS host. The candidate resolved **20/20** missions in both repetitions, giving 15 checked routes and five scoped refusals. The reference resolved 13/20. Unresolved executions were 0/40 against 14/40. "The result is 100% verified on-time mission resolution on this panel, not 100% routing accuracy or 20 evacuation routes." There is no speed gain: the median request time in 26 jointly resolved route pairs was 8.006 s for the candidate and 7.344 s for the reference.
- **Fresh replay and independent checks** ([README](../../README.md#verified-october-29-request-window-update)). All 80 executions completed again, and all 56 returned witnesses matched the historical routes. Independent programs checked 18 distinct returned journeys, 72/72 scenario-specific thermal thresholds and the five candidate no-route missions.
- **Why checking matters** ([constraint ablation](../../research/routing/final-input-ablation/README.md)). Travel-time-only routing returned a route for all 20 missions, but only 12 passed the full rules. Eight travel-only routes encountered predicted flames. Flame avoidance found three checked detours, arriving 490, 527 and 531 seconds later.
- **Software checks** ([README](../../README.md#software-verification-after-integration)). 3,531 forecast/cross-track tests passed, and 177 radiation/export/scenario/SIPP/truth tests passed with no skips. 3,640 protected artifacts remained byte-identical.
- **Runs anywhere.** A Linux CI job ([workflow](../../.github/workflows/reproduce-linux.yml)) and a [local run](reproduce/RECEIPT_2026-11-02_linux_2vcpu.json) replay the recorded Uljin request with an **extended budget**. They assert the recorded arrival of 3,119 s, 512 road legs, 120 s stay, route hash and independent verdict. This is a Linux reproduction, not the evaluated 30 s macOS benchmark. On the local run's 2-vCPU host, the same request at the evaluated 30 s budget returned `unresolved`. An earlier 4-vCPU Linux VM timed out in four of five runs ([Linux VM report](../../api/reports/LINUX_VM_REPLAY_2026-10-17.md)). Such outcomes are reported, never shown as safe.
- **Planner data.** The planner ships results precomputed on the evaluated macOS host for its two 2025 demo regions ([planner/cache/INDEX.json](../../planner/cache/INDEX.json) lists host, checks and verdicts per file).

## What is not established

- "Field effectiveness and evacuation safety have not been established." A checked route "is not a guarantee of real-world safety" ([README](../../README.md#reproducibility-attribution-and-intended-use)).
- **Forecast skill.** c651's four-scale design "was not shown to outperform its smaller alternatives". A later forecast model failed its frozen primary superiority criterion, so no checkpoint was promoted ([model card](MODEL_CARD.md)).
- **Physics.** Flame-front radiation v2 is under "**Physics HOLD**", and the heat model is not calibrated against measured flux.
- **Model scope.** Scenarios cover one hour after each recorded input time. Roads assume "40km/h" with no field validation ([decision card](DECISION_CARD.md#outside-the-decisions-scope)). Destinations come from OpenStreetMap tags. Smoke, embers, accessibility and destination suitability are outside the check.
- **Hosts.** Only native macOS on an Apple M5 Pro was evaluated. Elsewhere, heavy missions can time out.

## Roadmap

From [scientific next steps](../../README.md#scientific-next-steps) and [future extensions](../FUTURE_EXTENSIONS.md):

1. Physically validate the flame-front radiation model under a frozen protocol.
2. Complete and independently verify the v2 checker for driving, waiting and destination stays.
3. Address scenario support, causal forecast alignment and broader held-out evaluation.
4. Run an operational evaluation with intended users and responders.

## Under review for Solve 2027 (not yet merged)

Names only, as of 3 November 2026; none is on `Main` and no results are claimed for them:

- Public static planner demo
- Explainable deadlines
- Field-message kit for caregivers and village heads
- Impact numbers
- This reproduction and reviewer-documents package
