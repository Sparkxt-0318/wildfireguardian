# Final-input routing constraint ablation — frozen design

Status: protocol declared before scored execution. No new optimization or forecast fit.

## Question and sample
What does each hazard constraint contribute on the exact final 20 missions, five regional panels / four parent fires? Same latest c651 checkpoint identity and final packet freeze as the accepted 80-attempt study. No claim of 20 independent fires or real-fire accuracy.

## Five policies
A0 travel-only: no flame, peak, or dose constraint. A1 contact: flame only. A2 contact+peak. A3 contact+dose. A4 full: flame+peak+dose. Every arm retains road directions, turns, waiting permission, 1-second decisions, support requirements, destination openings, required stay, clocks, horizon, and exposure_scope. Incurred exposure is retained in every request. When dose is disabled its limit is replaced by 1e12, including the departure incurred-budget check. Peak-disabled limit also 1e12. Both-disabled centre flux is zeroed; A0 additionally clears planning flame arrays and source-derived contact intervals. Exact physical source arrays are immutable, used unchanged for independent/full-policy checks.

The sentinel is proved nonbinding on centre and whole-road physics for every mission. Nonoverlapping planar source rectangles subtend total solid angle <=2*pi, so total received flux <= radiative emission density/2 (W/m²), divided by1000 for kW/m². Maximum cumulative dose <= that cap times horizon-minus-departure plus incurred. Every per-mission bound is more than1000-fold below1e12. Bounds and all transformations recorded in POLICY_TRANSFORMS.json.

## Algorithm and implementation
Same proposed algorithm as final kit v3: reviewed fast cold graph preparation, exact contact sweep Z, same stage allocations and lower/upper road-bound searches/refinement, same final publication logic and adaptive road checker. No production code edited. A minimal isolated worker supplies the selected policy and omits inapplicable end checks: A0 checks mission grammar; A1 adds exact source contact; A2–A4 use adaptive road checker with only disabled budgets neutralized. Thermal prefilter bypassed when no thermal limit enabled. A4 full-policy logic and packet/requests equal the original final implementation; source checker return is unwrapped identically. WORKER.patch shows changes. Raw certificates in weak arms are policy-relative, never full-policy certificates.

## Execution and freeze
20 missions ×5 policies ×2 repetitions=200 independent fresh native macOS request processes. Each has original max-label/expansion/frontier caps,30-second complete-request deadline and3072MiB sampled family guard. Forecast inference excluded; graph preparation and mandatory own-policy checking included. Deterministic cyclic five-policy order rotates across missions; repetition2 reverses each order. Original interleaved mission order preserved. Queue frozen before scores. Six proven lifecycle controls plus five unscored real policy preflights, same first mission, once only. Any failed attempt/control is retained; no silent retries. Scored queue starts only after independent bounded protocol review and preflight PASS. Shared advisory lock+lease and caffeinate required; power recorded.

## Independent assessment and metrics
Each returned route is checked outside timed scope against both its selected policy and the unchanged full policy. Independently implemented source-based mission grammar, centre exposure and exact road-contact calculations; project's adaptive whole-road checker for radiation, with independent continuous-road radiation enclosure explicitly not established. Own-policy success requires complete in-deadline own-policy certificate and no independent contradiction. Full-policy pass requires independent centre/contact pass and whole-road certificate; unresolved radiation remains unresolved. Refusals are scoped separately, with independent source-based relaxation verification if available. Timeouts/label caps/rejections not silently treated as infeasible.

Report stable mission outcomes (agreement and success in both reps), execution outcomes, full-policy passing routes, constraint violations, arrival differences versus travel-only when defined, latency, CPU and RSS scopes. Do not pool historical300-run ablation or final80-run campaign. No threshold tuning or mission reselection after outcomes.
