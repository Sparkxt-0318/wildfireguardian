# The walk network does not cover the whole predicted fire

**Status: a property of the committed 459-origin result, found 2026-08-02.**
Surfaced while designing the multi-region extension, but it is not a
multi-region finding — it describes what was already shipped.

## The measurement

| | |
|---|---|
| Yeongdeok walk bbox | 129.25 – 129.55 °E (27.5 × 33.8 km, 931 km²) |
| predicted fire core, p ≥ 0.5, final slice | 128.966 – 129.456 °E (43.5 × 22.5 km, 244 cells) |
| core cells inside the walk bbox | **123 of 244 — 50.4 %** |
| unmodelled span | the western **25.1 km** of the core has no road network at all |

Measured by **cell count**, not bounding-box overlap, so a long thin envelope is
not flattered by a box that merely touches both ends
(`check_envelope_coverage`, `src/wildfireguardian/spread_v2/extent.py`).

## What the existing check verified, and what it did not

`real_roads_real_hazard.json` records `n_nodes_outside_hazard_extent: 0`, and
`check_routing_clearance` reports 20.4 km of margin on the tightest side. Both
are true. Both answer the same question:

> **Is the road network inside the hazard GRID?** — Yes, comfortably.

Neither answers:

> **Does the road network cover the FIRE?** — No. Half of it.

The grid is 73.5 × 90.5 km; the fire core occupies a 43.5 × 22.5 km strip within
it; the walk bbox is a different 27.5 × 33.8 km rectangle that overlaps that
strip only partially. Every existing check passed because each was asking about
the grid.

## Consequence

The 459 origins were drawn from the eastern portion of the predicted fire.
**This is a spatially biased sample, not a random one.**

**It does not make the results wrong.** The routing, the classification and the
459 / 438 / 18 / 3 counts are correct for the origins that were scanned. What is
unsupported is treating those origins as representative of the whole fire area.

**The direction of the bias has not been measured.** The western half might be
easier terrain or harder, better connected or worse; nothing here establishes
which. Anyone tempted to guess should note that the walk bbox follows
administrative convenience (`regions.py`: "approximate bbox covering the
affected area in northern Yeongdeok-gun"), not any property of the fire, so
there is no reason to expect the omission to be systematic in either direction.

## Why the walk bbox is not being redrawn

Re-acquiring Yeongdeok's road network on an envelope-derived bbox would break
continuity with every committed 439- and 459-series number, which the submission
documents cite and which must still be explainable. The cost of that outweighs
the benefit of a tidier extent.

So coverage is **measured and reported as a covariate** rather than controlled.
The multi-region comparison carries a coverage column for exactly this reason
([`multi_region.md`](multi_region.md)). This is a deliberate trade, and it is not
the ideal design: the ideal is that every region covers its whole fire.

## The check that now exists

```yaml
grid:
  boundary_check:
    envelope_coverage_min: 0.80
```

`check_envelope_coverage(routing_bbox, surface, grid, p_cut=0.5)` reports the
covered fraction and warns below the threshold. **Applied to Yeongdeok it warns
at 50.4 %.** That is the intended behaviour — the warning is the finding, not a
misconfiguration.

## Coverage across the three regions

| region | walk bbox | area | core coverage | min. grid clearance |
|---|---|---:|---:|---:|
| Yeongdeok 2025 | committed, hand-drawn | 931 km² | **50.4 %** | 20.4 km |
| Uiseong-Andong 2025 | ignition-centred | 919 km² | **98.9 %** | 5.81 km (south) |
| Uljin-Samcheok 2022 | ignition-centred | 924 km² | **84.8 %** | 5.73 km (south) |

The two new regions reach ≥ 5 km clearance on every side only because their
simulation canvas was extended southward (`docs/forward_sim_regions.md`); the
extension left both envelopes bit-identical.

Comparable areas, very different coverage. Read every cross-region number with
this column beside it.
