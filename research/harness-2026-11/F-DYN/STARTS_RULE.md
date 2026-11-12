# F-DYN start-time rule (fixed before any reach or fire-set share is computed on the new starts)

Decided by the orchestrator, 2026-11-12, option (a). This file is committed before any synthetic start is computed.

- **Starts:** every 3 h from t0 + 24 h to t0 + 108 h, with t0 = 2025-03-22 02:24 UTC. That is 29 starts:
  2025-03-23 02:24 UTC, 05:24, …, 2025-03-26 14:24 UTC.
- **Coverage check (by construction):** the Yeongdeok coastal run on the evening of 25 March KST (about 09–15 UTC
  on 25 March, i.e. t0 + 78.6 h to t0 + 84.6 h) contains the rule starts t0 + 78 h (08:24 UTC), + 81 h (11:24 UTC)
  and + 84 h (14:24 UTC).
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
