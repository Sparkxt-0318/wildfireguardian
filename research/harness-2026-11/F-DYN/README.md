# F-DYN: multi-hour dynamic routing workload from the 2025 KFS_01 arrival-time reconstruction

> **SCENARIO, not what happened, not a forecast.**
>
> - The fire comes from a retrospective kriging reconstruction of arrival times: Choi, Seo & Cha 2026, Zenodo
>   10.5281/zenodo.21788344, CC-BY-4.0. It is built from VIIRS and Himawari detections inside the final perimeter.
> - Its kriging sd is 16.6–19.5 h (about 17 h median), and independent checks suggest even that is too small.
> - It is a realistic dynamic fire for testing routing. It says nothing reliable about when fire reached any place.

## Why

The frozen 1-hour workload is close to routing around a static obstacle:

- 15 of 522 deadlines are set by the fire.
- Each member has only 0–9 new ignitions per hour.

F-DYN gives the routing streams a workload where moving fire, not the 1-hour window, drives outcomes. Measured new
ignitions inside the routing window per start, central member:

| Start (UTC) | 5 h | 8 h |
|---|---:|---:|
| Uiseong 03-23 01:00 | 82 | 131 |
| Uiseong 03-24 09:00 | 76 | 133 |
| Uiseong 03-25 17:00 | 1,099 | 1,137 |
| Yeongdeok 03-25 19:00 | 307 | 372 |
| Yeongdeok 03-25 23:00 | 109 | 150 |
| Yeongdeok 03-26 08:00 | 29 | 29 |

## How it is built (the F-9.3 hazard interface, first case: an arrival-time field)

The **unchanged** packet writer (`integration/src/wfg_latest/packets.write_regional_packet`) is driven through the
same two extension points `api/adapters/_zone_packet_child.py` uses:

- `bridge.draw_ignitions` returns the F-DYN ignition schedule on the full KFS_01 event grid instead of random draws.
- `bridge.settings_for` sets `horizon_s` (5 h or 8 h) and adds an `fdyn` entry. The settings digest, construction id
  and scenario ids therefore identify the F-DYN output.

Nothing else changes: present fire, radiation, flame semantics, the router validator and the routing kit are all as
before.

- **Start times** are the six recorded input times. At each one, the recorded c651 export's present fire, burned state
  and remaining burn time **equal this arrival field thresholded at the start**, cell for cell (test
  `test_recorded_export_is_the_field_thresholded`). So the packet continues the same reconstruction.
- **Ignitions.** A cell with arrival `a` (hours since t0 = 2025-03-22 02:24 UTC) ignites at
  `floor_300s(s_k * (a - h) * 3600 - shift_k)`, clamped at 0, if `a > h` and the time is within the horizon. Rounding
  down is the earlier reading, which is the conservative one.

  | Member | Name | Rule |
  |---|---|---|
  | m0 | central | as reconstructed |
  | m1 | faster 1.33x | s = 0.75 |
  | m2 | faster 2x | s = 0.5 |
  | m3 | 1 h earlier | shift = 3600 s |

  Members are never later than the reconstruction. They are speed and offset variants, **not sd quantiles and not
  probabilities**. The sd (about 17 h) is larger than the horizon, so absolute timing is not identified. The members
  probe sensitivity to faster or earlier fire, the direction that matters for safety. The 2025 front was reported at
  up to 8.2 km/h, against roughly 4 km/h overall.
- **Fire outside the reconstruction** (NaN arrival, outside the final perimeter) never ignites. That is the observed
  event, not an assumption.
- **Source domain.** Ignitions are on the full event grid. The packet keeps each region's recorded window, which
  contains every routed road (0 graph nodes outside the window). Fire outside the window appears only through the
  writer's own omitted-source radiation bounds (`BUILD_SUMMARY.json` → `omitted`). No routed road lies in an omitted
  cell.

## Files (large; outside git)

`fdyn/build.py` writes `packets/<region>/<start>_h<5|8>/`:

- `HAZARD.json`: `wfg.routing.edgegrid/1`, `valid_until` = 18000 or 28800, 4 members. About 56 MB for Yeongdeok
  03-25 23:00 at 5 h.
- `NATIVE_METADATA.json`, `REPORT.json`, `constructed_arrays.npz`.
- `BUILD_SUMMARY.json`: includes the `fdyn` plan metadata, the sd at ignited cells, and the omitted-source bounds.
- `<start>_h<H>.plan.npz`: the ignition schedule.

`fdyn/instance.py` writes `INSTANCE.json` (schema `wfg.fdyn.instance/1`). It holds 12 instances: 6 starts × 2
horizons. Each instance has:

- **Origins:** the planner's 174 places (84 Uiseong-Andong, 90 Yeongdeok) at their road entry nodes.
- **Destinations:** each origin's 3 recorded candidates, with a 120 s stay.
- **Departures:** every 30 min over the horizon.
- **Destination window:** [0, H].
- **Limits:** peak 10 kW/m², dose 100 kJ/m², as in every recorded request.

Requests are built with `api.requests_build.build_request`, as the API does.

## Reproduce

```
python3 tools/fetch_routing_inputs.py                       # data/routing (SHA-checked)
git show origin/daniel/data-fetch:research/harness-2026-11/data-fetch/small/choi2026_kfs01/KFS_01_pswt_ok_toa.tif > research/harness-2026-11/F-DYN/_data/KFS_01_pswt_ok_toa.tif
git show origin/daniel/data-fetch:research/harness-2026-11/data-fetch/small/choi2026_kfs01/KFS_01_pswt_ok_std.tif > research/harness-2026-11/F-DYN/_data/KFS_01_pswt_ok_std.tif
pip install numpy scipy rasterio pyproj
python3 research/harness-2026-11/F-DYN/fdyn/build.py --region yeongdeok_2025 --start 20250325T230000Z --horizon-h 5 \
   --toa research/harness-2026-11/F-DYN/_data/KFS_01_pswt_ok_toa.tif --sd research/harness-2026-11/F-DYN/_data/KFS_01_pswt_ok_std.tif \
   --out research/harness-2026-11/F-DYN/_data/packets/yeongdeok_2025/20250325T230000Z_h5        # about 1 min
python3 research/harness-2026-11/F-DYN/fdyn/instance.py --out research/harness-2026-11/F-DYN/_data/INSTANCE.json
python3 -m pytest -q research/harness-2026-11/F-DYN/tests
```

## Status and known issues

- **Built so far:** one packet, Yeongdeok 03-25 23:00 at 5 h. The router validator accepts it, and the written
  ignitions equal the plan.
- **Kit smoke test** (`fdyn/smoke_check.py`, arm RDA_CAND, unchanged kit, 30 s booth budget): 4 of 4 checks timed out
  as UNRESOLVED/LATE_RESULT, with RSS 3.0–4.6 GB. The host was also running another 3-process job at the time, so this
  is not a timing claim. Re-timing with free CPU and larger budgets is pending. The multi-hour, many-interval packet is
  heavy for the evaluated path; that is a finding for the routing streams.
- **Packet rebuild check:** rebuilding a recorded 1-hour packet with the unchanged writer in this container gives the
  same scenario ids, breakpoints, flame and support. Flux differs by at most 1.1e-15 kW/m² (numpy 2.5 here vs the
  pinned 1.26.4). The identity differs only in the absolute module path. Byte-identity holds between rebuilds in one
  environment, not across hosts.
