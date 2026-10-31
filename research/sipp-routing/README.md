# Exact contact interval routing, native evidence

52/52 paired executions match in verdict and arrival second across 26 missions (two repetitions). The fresh random census agrees on 10000/10000 abstract instances, including 8312 legal returned witnesses. The native study has 104 executions and no unresolved output. This is contact-relaxation evidence, not a complete thermal-routing benchmark.

The median complete-child interval/sweep time ratio is 0.633025. The interval implementation is slower in 4/52 pairs. The largest complete-child time is 5.209567 s and maximum sampled child RSS 487.344 MiB. These are measurements on this host only.

## Reproduce

Use the fresh Python 3.12 routing environment installed with `pip install -c constraints-routing.txt './integration[packets]'` and pytest 8.3.4, Hypothesis 6.170.13, matplotlib 3.9.2. Commands from repository root:

```sh
python research/sipp-routing/run_native_panel.py --korean-jobs KOREAN_JOBS --caldor-jobs CALDOR_JOBS --out FRESH_RUN
python research/sipp-routing/verify_custody.py --jobs KOREAN_JOBS --jobs CALDOR_JOBS --run FRESH_RUN
python research/sipp-routing/analyze_native.py --run FRESH_RUN
python research/sipp-routing/property_census.py --out research/sipp-routing/PROPERTY_CENSUS.json
PYTHONPATH=experimental/sipp-routing/src:experimental/scenario-members/src:experimental/synthetic-truth/src python -m pytest experimental/sipp-routing/tests
```

The original producer is retained at native-panel-20261030/ORIGINAL_CONTROLLER.py. After the run, review found that a child exiting between deadline polls could bypass the final time check. The current controller adds final-after-exit elapsed/RSS admission and boundary tests. All original rows were far below either cap, so this defect does not change their recorded gate outcomes; they were not replaced or pooled with another campaign. The original execution source hash binds its snapshot. Fresh reruns use the corrected controller.

The 156 source/input fields match their original sealed-job expectations, with 0 mismatches. Actual runtime data reads are graph, request, REPORT.json and constructed_arrays.npz. NATIVE_METADATA.json and HAZARD.json are additionally pinned. No external native history files are read by this contact-only adapter. Code identity is commit e8a492aef, with the original controller snapshot and prior-source reuse manifest. No frozen kit source is edited.

The random census uses dense seeds 0 through 4999 and a deterministic Hypothesis half-census without a database. It found 1688 no-journey cases; blocked intervals change the travel-only answer in 1244 cases. Repetitions are verification repeats, not independent missions. Korean panels represent four parent fires, with the two Gyeongbuk panels sharing one parent.

## Figures

Figure 1, fig01_time_vs_sweep_paired (PNG 300 dpi and SVG), plots complete child time for paired contact-relaxation runs, including imports, input validation/loading and cold preparation. The diagonal is equal time; the host, fixed member packets and exact missions are unchanged within each pair. This does not measure the full thermal-checking request.

Figure 3, fig03_caldor_breakdown (PNG and SVG), shows the complete child time for each Caldor/Rim mission and repetition under the two contact planners. It retains pairs where the interval implementation is slower. It is an execution-cost breakdown by mission, not a decomposition of thermal-checking cost.

## Scope and limits

The hybrid retains all admitted arrival runs at nonwaitable nodes and extracts destination goals before dominance. Classic earliest-arrival dominance alone is invalid there. See experimental/sipp-routing/docs/SIPP_EQUIVALENCE.md and JOURNEY_SAFETY_PREDICATE.md. The contact geometry and frozen sweep are copied with source hashes; the reference time-expanded abstract search shares the declared instance format but uses no interval search or dominance. Finite agreement is not a machine-checked general theorem.

This is a model-relative contact relaxation. Peak and dose still require the complete journey checker; source support must be known for a global no-route claim. The requested trajectory-member K-scaling and new-bridge packet equivalence are separate gates. They are not established by the fixed four-member native panel. There is no field validation, physical-accuracy claim or universal speedup.

Queue scope: this additional contact study uses per-mission ABBA pairs in first-appearance mission order, not the original full-request campaign controller queue. The Caldor/Rim missions are appended as a separate panel. Exact input identities and scientific mission settings are retained.

Timing identity: the measured overlay source is commit e8a492aef. This branch later hardens final deadline admission and unsupported-source handling. The fixed timing table is not silently relabeled as a fresh timing of every later edit.

The mandatory fig02_states_vs_members remains unproduced after the bounded closure audit. All existing native searches use K = 4; the actual stored counters are now extracted without reruns in member-scaling-closure-20261030-v2/NATIVE_FIXED_K_COUNTERS.csv. The existing K-labelled C1-C4 records have no search counters. A separate read-only first-K audit checks 20 Korean missions at K = 4/8/16/32 with exact clocks/grids and already-recorded regional integer windows: 0/80 candidates pass the current adapter's contact-support predicate, so no state-count series is available. Those admission refusals are not measured search costs or risk rates. Full-N masks and other selectors were not assessed. See MEMBER_SCALING_FEASIBILITY.md and the exact-hash RESULTS.json; no figure, algorithm run or solver campaign was fabricated. A supported contact-only study does not require the unresolved Track 1A physics gate, while a different local/pessimistic support contract would need its own justification.

A subsequent separate all-saved-member census closes the other-selector admission question left open by the first-32 audit. FULL_MEMBER_SUPPORT_CENSUS.md and full-member-support-census-20261030/ retain all 1,024 original members on each of 15 exact domains covering the 20 missions: 0 supported members over 15,360 domain-member checks, with byte-identical unknown masks across N in every domain. Any nonempty selection from these saved pools therefore fails the existing whole-domain contact-support predicate. This is NOT_RUN_CONTACT_ADMISSION, not measured scaling performance or a risk rate; fig02 remains unproduced. The source-bound streaming census changes no policy or frozen input and does not rule out a future justified local/pessimistic support contract. All first-32 and initial strict-grid-failure artifacts remain immutable.
## Proposed local contact support and read-only topology census

The subsequent known-footprint census makes the conservative default's scope concrete. It audits all 20 original Korean missions and 15 exact source domains, finding six spatially known, turn-aware issue-to-destination topologies. All 14 failures have an unknown issue or destination cell under this restriction. These are source-support findings, not timed safe routes or a replacement for the strict zero-of-15,360 whole-domain result. No source/default was changed and no adapter or timed K campaign was run.

See KNOWN_FOOTPRINT_TOPOLOGY_RESULT.md for the exact table and receipts, and KNOWN_FOOTPRINT_CONTACT_PLAN.md for the proposed locality proof, original-data witness checks, finite clock support and restricted-failure-to-unresolved protocol. The five bounded graph children released HEAVY between graphs and left no owned process groups. The 512-mask fixture and exact producer/input/flag hashes are retained separately. KNOWN_FOOTPRINT_SOURCE_SCOPE.md explains why the actual one-hour source duration cannot be assumed to demonstrate increasing edge-interval fragmentation with K. The mandatory fig02 still awaits a separately reviewed opt-in adapter and an actual paired K study; static reachability counts cannot supply its data. Radiation, full-policy and risk gates remain closed.

## Implemented contact-only opt-in, software fixture scope

The separately reviewed implementation stage now supplies
experimental/sipp-routing/src/wfg_sipp/known_footprint.py and a separately
versioned support-restricted copied sweep. Both use identical exact support
barriers and represented contact activity. The independent raw-data checker
does not trust planner flags, intervals or event caches. The strict bridge,
frozen sweep/geometry and all earlier source/census evidence remain unchanged.
This later implementation does not alter the historical proposal/static-audit
statements above. No native timed journey or K campaign has run at this stage.

The exact contract and explicit omission of thermal history from the private
contact relaxation are documented in
experimental/sipp-routing/docs/KNOWN_FOOTPRINT_CONTACT.md. Public results retain
the original request/history verbatim and leave peak, dose and risk unknown.
Only independent raw-data checking can return the typed contact result;
restricted exhaustion remains unresolved about the original unknown domain.

Reproduce fixture/regression counts and unchanged-artifact hashes with:

```sh
python research/sipp-routing/verify_known_footprint_adapter.py --out FRESH_RECEIPT.json
```

KNOWN_FOOTPRINT_ADAPTER_RECEIPT.json records the actual command, host, versions,
source hashes, test counts and preserved prior evidence. No timing chart is
created from software fixture runtimes. The fixed native paired K protocol,
all thermal/full-policy checks and scientific risk remain on hold pending
independent review and their separate execution gates.

## Contact adapter source and clock repair

Independent review of fd8bf2e7 identified three additional tiny API boundaries:
contradictory active/unburned cutoff data was discarded, fractional member
support could silently change the earliest-arrival problem, and datetime
precision truncation could alias distinct source/request clocks. The repair
restores consumed canonical source invariants and explicitly rejects unsupported
clock precision and fractional member bounds. Exclusive terminal mode requires
integer dwell; inclusive mode retains exact fractional dwell checking.

The original contact fixture, producer, receipt and contact-contract document
are byte-preserved. Their original test results remain historical evidence;
the new boundary tests and repair receipt supersede their admission coverage.
Run `python research/sipp-routing/verify_known_footprint_repair.py --out FRESH_RECEIPT.json`
to reproduce the full overlay regression and custody checks. Exact counts,
reference hashes and supported clock rules are recorded in
KNOWN_FOOTPRINT_ADAPTER_REPAIR_RECEIPT.json. Native contact/K execution remains
closed pending independent recheck. No prior static/strict evidence or timing
record is replaced.

## Fixed known-footprint contact K campaign, executed stage

The fixed opt-in study is now retained in known-footprint-contact-K-20261030/.
It has 320 records over the 20 original missions, K4/8/16/32, both methods and
two ABBA repetitions. All 48 searchable paired outcomes agree: 36 matched
checked contact arrivals and 12 matched restricted exhaustions. The remaining
112 pairs are presearch unknown-endpoint admission, with 224 null solver-cost
records. Every one of the 72 returned contact-route records passed a separate
fresh original-source/mask/geometry recheck through full dwell.

The measured source phase is 095b8d174d2f203ea67bea5fdd8c69eb0633b2a0.
The protocol and controller were committed before any native row, after the
root's independent core-700 source/clock recheck; 13 tiny controller/source-pin
controls and all 20 exact original-input preflights passed. Every child released
HEAVY; all controller guards admitted and owned groups were absent after exit.
The maximum complete child time was 5.520812 s and peak RSS was 454.4375 MiB.
These are bounded host measurements, not physical or operational guarantees.

The median SIPP/sweep planner-call ratio was 0.561111 across all 48 completed
search pairs, including restricted exhaustion; the complete-child ratio was
0.671574. Endpoint admission times are excluded from solver costs. At K32,
Uiseong FX2 and Uljin FW2 changed from smaller-K contact routes to restricted
exhaustion. State counts can rise, fall or remain flat; the actual fig02 is now
produced with SIPP expansions and sweep states in separate panels. No increasing
multi-interval fragmentation claim follows under T>H. The artifact README has
commands, seeds, hashes, host, exact outcomes and captions for PNG300dpi/SVG.

This later stage supersedes the earlier pending-known-footprint-study status
only. Strict default admission and all earlier first32/fullN/topology evidence
remain unchanged. The 115 original input files, 35 prior evidence paths and four
fd8 reviewed artifacts retain their hashes. The result is local represented
contact on the support-restricted problem: original issued histories remain
verbatim and thermal fields are privately omitted without rebinding. Peak,
dose, full-policy acceptance and scientific risk remain unknown. Restricted
exhaustion is unresolved about the original unknown domain, and no physical or
global original-domain optimum/refusal is asserted. Independent output audit
remains separate from executing and checking this bounded study.
