# F-3.4 multi-hour profile and F-4.2 margins on F-DYN v3: fixed request set

Written before any F-DYN routing run (12 Nov, ~10:10 UTC). F-DYN v3 is Leo's `7eb3691` on
`leo/f-c1-see-before-leave`, passed by Nora with notes.

## Packets (4)

Both recorded starts that are also rule starts, 5 h horizon, central member, Q = 300, full KFS_01 grid, interim
graph:

| Region | Start (UTC) | Variants |
|---|---|---|
| uiseong_andong_2025 | 20250325T170000Z | kriged_mean, firms_early |
| yeongdeok_2025 | 20250325T230000Z | kriged_mean, firms_early |

Each packet is built by its exact `MANIFEST_v3.json` command and its hashes are recorded. The envelope variant is
excluded: it has a single implementation and is not independently checked.

## Requests (12)

Per region, taken from `INSTANCE.json` (`fdyn/instance.py`): the **first 3 places in file order**, departure 0, each
place's **first** listed destination, with the instance's limits (10 kW/m², 100 kJ/m²), 120 s stay and destination
window [0, H]. That gives 3 requests × 2 variants × 2 regions = 12. The same 12 are used for every budget and for the
margins.

## Runs

- **Profile.** Instrumented (`run_profile.py`-style job through the unchanged controller, request-window kit,
  `RDA_CAND`), cold preparation, sequential, quiet host. Budgets: **30 s** (the evaluated budget, outcome record only),
  then **300 s** and **900 s** (extended, reported separately), 1 repetition each. Memory guard 3,072 MiB as in the kit.
  If a run stops on the memory guard, it is repeated once with the guard raised to 12,288 MiB (host has 15 GiB), to
  locate the phase that grows. That repeat is labelled non-evaluated.
- **Reported per run.** Outcome; wall time by phase; per-phase RSS high-water; family peak RSS; host (stated; timings
  are host-relative).
- **Margins.** `clearance.py` on the same 12 requests: published-route clearance (where a route is published), margin
  bracket, ≤ +60/+300/+600 s trade-off, and crop/domain flag.
- **Carried notes (Nora).** Roads are the clipped recorded windows, so 45% of burned cells have no modelled roads.
  Dose binds over 5–8 h. This is a scenario, not what happened.

## Label correction (Leo, c79c510, received after the plan was fixed)

`firms_early` uses the FIRMS bracket start, which is **not a lower bound** on arrival. It stays in the fixed set,
because timing results are unaffected. Every result on it is labelled **"firms bracket-start (not a lower bound)"** and
is never described as early or conservative. Leo's sound envelope variant (`envelope_sound`) is not part of this plan.

## Version update (Leo 11:43 UTC; orchestrator decision): F-DYN v3.1

The plan runs on **v3.1**: `MANIFEST_v3_1.json` (sha `1c2e73db…`) at `3f1fa15`, with packets under
`_data/packets_v31/`. The 4 packets and 12 requests are unchanged in definition. The v3.1 data changes touch only the
23T23, 24T02 and 24T05 starts, not this plan's 0325T17 and 0325T23 starts; identity digests change. Each manifest
command is run as an argv list. Every packet hash is recorded in `fdyn_prepare.log`.

## Amendment A1 — 12 Nov 2026, committed 13:00:28 UTC (033e7f0) before the run it describes (run started ~13:01 UTC)

**Deviation 1: the 900 s / 12,288 MiB controller-only repeat was stopped** at 12:59:06 UTC, after 1 of 12 rows
(orchestrator decision). It cannot show search behaviour, for the reason below. The one completed row (Uiseong
kriged …323: UNRESOLVED, 151.9 s, 9,766 MiB) is kept and labelled "stopped repeat".

**Why.** The plan's memory repeat raised only the controller's guard. The kit's solver has a second memory gate,
which the plan did not cover: `phaseB/road_core.py:751-757`, the same code as `routing/core.py:605-611` in the
routing package. Every 64 expansions it compares the **process-lifetime maximum RSS** (`getrusage ru_maxrss`) with
`limits.rss_limit_mb`. The default is 3,072 because the requests do not set it.

On these packets, bound construction has already raised the lifetime maximum above 3 GiB, so the LO and HI stages
stop with `RSS_LIMIT` at 0 expansions. In the 300 s / 12,288 MiB repeat, 9 of 9 unresolved requests did this.

**Deviation 2: one more repeat.** It is labelled **non-evaluated, amendment A1**.
- The request carries `limits.rss_limit_mb = 12288`, a field the kit validates (`routing/validation.py:421`).
- So both gates are at 12,288 MiB: controller `--memory-guard-mib 12288`, and the solver via the request.
- Budget 300 s; the same 12 requests; one repetition; quiet host.
- Command: `fdyn_profile.py --budget 300 --memory-guard-mib 12288 --rss-limit-mb 12288`, output `fdyn_b300_g12k_rss12k`.

**Reported, descriptive only (no pass/fail threshold, per the orchestrator):** per request,
- outcome and terminal reason;
- per stage (Z, LO, LO2, HI): wall cap, elapsed, status, reason, labels and expansions;
- complete wall;
- family peak RSS, and resident vs lifetime-peak RSS at the end of the bound model, the EA bound and search.

Also reported beside it: the count of the 9 requests unresolved in the 300 s / 12,288 MiB repeat that reach
FEASIBLE or OPTIMUM_PROVEN with a completed whole-road check (Iris's question), as a number, not a pass rule.

**Findings recorded with this amendment (from existing rows; measured).**
1. **The gate measures lifetime peak, not current use.** Any large transient precompute therefore disables every
   later search stage for the rest of the process, even when resident memory has fallen back. On Uiseong:
   - RoadBoundModel construction peaks at 9.0–9.5 GiB, but resident RSS at its end is 0.40 GiB;
   - resident RSS at the end of `road_core.solve` is 2.09 GiB, below 3 GiB;
   - search was nevertheless stopped by the gate.
   On Yeongdeok the EarliestArrivalBound stays resident (4.4 GiB at its end and during search), so that memory is
   genuinely held.
2. **The terminal reason under-reports memory.** Gate-stopped runs end as `UNRESOLVED / SEARCH_TIMEOUT`, with
   search status `TIMEOUT`. `RSS_LIMIT` appears only in the per-stage records of `SEARCH_RESULT.json`. This is a
   reporting defect in the kit's terminal reason (observation; the frozen kit is not changed).
3. **Open item: Z overran its 6 s cap on Uiseong** (Z elapsed 20.0–22.4 s, wall cap 6 s). Not investigated.
4. **The 2 feasible results at 900 s / 3,072 MiB** (Yeongdeok firms_early, origins …207 and …168) came from **Z**:
   - Z timed out at its 6 s cap with a checked incumbent (`WALL_CLOCK_AFTER_CHECK`);
   - the whole-road check certified that incumbent, and it was published (`WHOLE_ROAD_CERTIFIED_NO_OPTIMALITY_CLAIM`);
   - so the EA bound was never built and the peak stayed at 2.3 GiB.
   At 300 s / 3,072 MiB, the same requests reached EA, which needs 4.4 GiB, and were stopped by the guard. The
   difference is whether Z had a certified incumbent when its fixed 6 s cap expired. That is a run-to-run timing
   effect at the Z cap, not an effect of the larger budget (hypothesis; 1 repetition each).
