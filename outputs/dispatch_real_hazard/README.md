# `outputs/dispatch_real_hazard/` — dispatch sheets made on the REAL 영덕 spread surface

Generated 2026-09-12 on the author's laptop (NH-057: 「run the whole thing」) by

    python scripts/run_rescue_routing_real_hazard.py
    python scripts/generate_dispatch_outputs.py --full \
        --source data/processed/rescue_routing_real_hazard.json \
        --out-root outputs/dispatch_real_hazard

from `data/processed/rescue_routing_real_hazard.json`. Method, numbers and what they
do NOT show: `docs/rescue_routing_real_hazard.md`.

## What is real, what is not — printed on every sheet

> 본 출동 지시서는 2025년 영덕 산불의 실제 확산면(관측 기반 전방 시뮬레이션,
> routing_demo_canonical.npz)과 2026-07-24 도로망 스냅샷으로 만든 것입니다. 출발지는
> 실제 가구가 아니라 도로망에서 표본추출한 후보 지점이며, 보행 시간은 경사를 반영하지
> 않은 평지 속도입니다. 합성 확산면으로 만든 기존 지시서(outputs/dispatch_full/)와 수치를
> 합치거나 비교하지 마십시오.

- **Real:** the hazard (the leave-one-fire-out forward simulation of the 2025 영덕 fire,
  the same field every routing surface cites), the walk and drive networks, the refuges
  and the depots (2026-07-24 OSM snapshots in `data/snapshots/`, not `data/cache/`).
- **Not real:** the origins (walk-network candidates at stride 18, not households); the
  walk timing (flat elderly speed, no slope — the OSM loader carries no DEM); the vehicle
  side (config assumptions: cutoff 0.7, 40 km/h, dispatch delay, safety margin).
- **Nothing synthetic drives a number:** no synthetic terrain, no synthetic envelope,
  no synthetic coastline. Nothing was sent (SMS demo mode, no credentials).

## Relationship to the other dispatch directories

`outputs/dispatch/` and `outputs/dispatch_full/` were made on a **synthetic** hazard
over the same real roads. This directory is a **separate run** on a different hazard,
a different extent and a different origin set. Do not reconcile, average, subtract or
compare the counts. The 2026-08-01 sheets are kept byte-unchanged as the record.

## PDFs

Only the three largest clusters' `dispatch_a4.pdf` are tracked (`.gitignore`); every
cluster's `dispatch_a4.html`, broadcast script, SMS drafts and `points.json` are.
