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
