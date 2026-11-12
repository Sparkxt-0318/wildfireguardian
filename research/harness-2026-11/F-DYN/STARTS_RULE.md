# F-DYN start-time rule (fixed before any reach or fire-set share is computed on the new starts)

Decided by the orchestrator, 2026-11-12, option (a). This file is committed before any synthetic start is computed.

- **Starts:** every 3 h from t0 + 24 h to t0 + 108 h, with t0 = 2025-03-22 02:24 UTC, **each floored to the whole
  UTC hour**. That is 29 starts: 2025-03-23 02:00 UTC, 05:00, …, 2025-03-26 14:00 UTC.
- **Amendment** (committed before any computation on these starts): the contract binding accepts only whole-hour
  cutoffs (`contract.normalize_cutoff`: `CLOCK_CUTOFF_NOT_WHOLE_HOUR`), so the :24 times of the original text are
  floored to the hour.
- **Coverage check (by construction):** the Yeongdeok coastal run on the evening of 25 March KST (about 09–15 UTC
  on 25 March, i.e. t0 + 78.6 h to t0 + 84.6 h) contains the rule starts 2025-03-25 08:00, 11:00 and 14:00 UTC.
- **Regions:** every start is built for both regions (uiseong_andong_2025, yeongdeok_2025).
- **Horizons:** 5 h and 8 h.
- **Arrival:** `kriged_mean`, central member, Q = 300 s. Other variants are run on the same starts.
- **Reporting:** reach (road cells igniting; places whose entry cell ignites; places within 1 km) is reported for
  **every** start, quiet ones included. No start is dropped after seeing results.
- **Recorded starts:** the 6 recorded input times remain in the workload and keep their recorded c651 exports.
- **Rule starts:** each uses a SYNTHETIC present-fire export generated from the TOA (`fdyn/synthetic_export.py`).
  - The record, the packet settings (`fdyn.present_fire_source`) and the identity
    (`checkpoint_sha256 = "SYNTHETIC-fdyn-present-fire-from-TOA:<toa sha>"`) all say so.
  - The scenario ids differ because the export SHA differs.
  - A test checks that the generator reproduces the recorded exports' burned, active and remaining fields at the 6
    recorded starts.

The commit that adds this file is the rule commit.

## Build criterion and scoring set (fixed before any deadline is computed; orchestrator/Iris decision 2026-11-12)

- **Scoring set:** {`kriged_mean`, `firms_early`, `envelope`} × built starts × {5 h, 8 h}.
  - `envelope` = each cell burning from its bracket start until its bracket end plus the burning duration (the F-9.3
    interval member).
  - Bracket start = `firms_early`. Bracket end = `firms_constrained`, i.e. min(kriged, first detection).
  - Cells without a detection have a zero-width bracket at the kriged mean.
- **Built starts:** a rule start (or recorded start) is **built** for a region when at least one routed road cell
  ignites or burns within the **8 h** horizon in **any** of the three variants (the union). This is computed from the
  fire inputs and the road cells only, never from routing results. Starts below the criterion appear in every results
  table as "no fire reaches the routed network in the horizon", without a packet. No start is excluded for any other
  reason.
- **Comparison rows:** per-village differences between `kriged_mean` and `firms_early` deadlines are reported as a
  result (how much the timing source matters).
