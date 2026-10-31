# Decisions

Dated, one line of reason each. Interface changes also bump `hazard_contract.CONTRACT_VERSION`.

- **2026-10-31** — Program started in a Claude Code cloud container, not on the Mac.
  Reason: the session was launched in the cloud; work that needs no Mac data proceeds here,
  data-dependent work is flagged as blocked rather than replaced with synthetic data.
- **2026-10-31** — `claude/ecstatic-keller-fm31to` mirrors `next/integration`.
  Reason: the cloud session must push its designated branch; Siyeong's branch layout is kept.
- **2026-10-31** — Bench lock = Python `fcntl.flock` on `<main checkout>/program/.bench.lock`
  via `program/benchlock.py`. Reason: stock macOS lacks `flock(1)`; one file shared by all
  worktrees.
- **2026-10-31** — Per-folder `.gitignore` files instead of editing the root `.gitignore`.
  Reason: the root is part of the frozen release.
- **2026-10-31** — No torch in the cloud venvs for now. Reason: the CPU wheel index is blocked
  and the PyPI Linux wheel set is over 1 GB (needs approval); c651 needs Mac data anyway.
- **2026-10-31** — `hazard_contract` v1 (`CONTRACT_VERSION = "1.0"`) published on `next/integration`.
  Reason: shared interface before track agents start.
- **2026-10-31** — `SegmentHazard` gains `dose_lower`/`dose_upper` (kJ/m²) beyond the specified
  fields. Reason: peak-flux bounds alone cannot certify a cumulative-exposure violation.
- **2026-10-31** — Reference flux law = the `wfg_latest` finite-cell sheet law (`sheet_solid_angle_v1`),
  with `HeatSource` adding `consumed_fraction` and emission/receiver heights. Reason: the oracle
  must reuse the router's physics; the law caps flux at q_rad/2 = 0.70 kW/m², so with the
  repo's parameters the 10 kW/m² peak budget never binds and contact + dose decide.
- **2026-10-31** — Contact uses closed cells (the existing checker's "whole-road" rule);
  `segment_uniform` adds the router's uniform-motion occupancy. Reason: the API already requires
  whole-road CLEAR for a checked route; it is the stricter of the two rules.
- **2026-10-31** — `from_wfg_packet` applies rule 4 with no opt-out: missing native probability or
  unknown burned state ⇒ unsupported. Reason: the user's rule; it leaves 32–100% of Korean road
  cells unsupported (question for Siyeong whether a labeled "packet policy" mode is wanted).
- **2026-10-31** — Geometry touching the grid's outside or a query past `horizon_s` ⇒ unsupported;
  sources outside the grid are not modelled. Reason: unknown is not unburned; producers pad grids.
- **2026-10-31** — `hazard_contract` 1.0.1 (format unchanged, `CONTRACT_VERSION` stays 1.0): fixes from an
  independent adversarial review (12 confirmed findings, each now a regression test). Reason: two
  false-safe paths (polygon holes filled; float time drift in `query_uniform`) and ten smaller
  honesty gaps. Behaviour changes: polygons use GeoJSON nesting with holes kept; `from_wfg_packet`
  default `present_fire="enclosure"` (what the router used) and also reads
  `mask__unknown_cumulative_state`; geographic / Web Mercator CRSs refused (interface tightening —
  needs Siyeong's confirmation); interval policy treats unknown emission as unbounded.
