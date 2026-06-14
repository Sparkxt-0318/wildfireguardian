# `smoke_dispersion` — PM2.5 / smoke exposure

**Status**: scaffold only — a research scaffold, **not** part of the canonical
`spread_v2` pipeline and **not** a current deliverable (see `docs/architecture.md`).

**Purpose**: estimate downwind smoke concentration (PM2.5 µg/m³) from an
active fire perimeter, on the same time grid as the spread forecast, so the
routing module can avoid plumes that would harm elderly evacuees.

**Inputs**: fire perimeter time series (from the cellular automaton), an
emission factor (g PM2.5 per kg dry fuel consumed), and a 3D wind / stability
field (initially from KMA AWS interpolation, later from KMA NWP / ERA5).

**Outputs**: a per-hour PM2.5 raster on the same grid as the spread output.

**Algorithmic basis**: in the prototype, a Gaussian plume model with
Pasquill–Gifford stability classes is used for near-source dispersion. A
HYSPLIT (Stein et al. 2015) coupling for medium-range transport is planned
for the validation hindcast but not yet wired in.
