# The walk network does not cover the whole predicted fire

**Status: WORSE than first reported. Re-measured 2026-08-02 on the canonical
hazard field.** Found while designing the multi-region extension; it describes
what was already shipped, and the canonical field makes it larger, not smaller.

## The measurement (canonical hazard field)

| | |
|---|---|
| Yeongdeok walk bbox | 129.25 – 129.55 °E (27.5 × 33.8 km, 931 km²) |
| predicted fire core, p ≥ 0.5, final slice | **1,036 cells, 45.0 × 25.5 km** |
| core cells inside the walk bbox | **338 of 1,036 — 32.6 %** |

The bbox did not move. The core **quadrupled**: 244 cells on the reverted run's
field, 1,036 on the canonical one
([`routing_demo_divergence.json`](../data/processed/routing_demo_divergence.json)).
So the earlier 50.4 % was not merely superseded — it was measured against a fire
four times too small.

### Coverage across the three regions

| region | walk bbox | area | **core coverage** |
|---|---|---:|---:|
| 영덕 2025 | committed, hand-drawn | 931 km² | **32.6 %** |
| 의성·안동 2025 | ignition-centred | 919 km² | **99.2 %** |
| 울진·삼척 2022 | ignition-centred | 924 km² | **81.5 %** |

**Yeongdeok is now a different kind of sample from the other two, not a
noisier one.** Uiseong-Andong effectively scans its whole fire; Uljin-Samcheok
scans four fifths of it; Yeongdeok scans a third. In
[`multi_region.md`](multi_region.md) this is the single largest covariate
imbalance in the table, and it lands on the region whose row the submission
documents cite.

Concretely, Yeongdeok's 44 origins whose fire-blind route is unsafe — and the
95.5 % of them the future-aware router rescues — are drawn from **a third of the
predicted fire**. The other two thirds contain an unmeasured number of origins
whose behaviour is unknown. The rescue rate is not an estimate of the
region-wide rate; it is the rate **on the covered third**, and nothing here
bounds the difference.

The bbox follows administrative convenience (`regions.py`: "approximate bbox
covering the affected area in northern Yeongdeok-gun"), not any property of the
fire, so there is no reason to expect the omission to be systematic in either
direction — but "unbiased in expectation" is not "small".

---

# ── EARLIER READING (reverted hazard field) ──────────────────────

Retained because the 50.4 % figure is quoted in committed prose, and because the
contrast shows how much a hazard field can move a spatial-bias statistic.

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

> ⚠ **제출 시점 기록입니다.** 459 / 438 / 18 / 3 은 제출 시점의 값이며, 정본 위험면
> 위 재산출값은 **458 — 414 / 42 / 2** 입니다
> ([`HANDOFF_ROUND3.md`](HANDOFF_ROUND3.md) §2-A,
> [`real_roads_real_hazard_canonical.json`](../data/processed/real_roads_real_hazard_canonical.json)).
> 위 문장의 논지 — 주사된 출발지에 대해서는 옳고, 그것을 화재 전역의 대표로 보는 것이
> 근거 없다 — 는 재산출값에도 그대로 적용됩니다. 커버리지 32.6 %는 두 값 모두의 분모입니다.

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

## Coverage across the three regions (superseded figures)

| region | walk bbox | area | core coverage | min. grid clearance |
|---|---|---:|---:|---:|
| Yeongdeok 2025 | committed, hand-drawn | 931 km² | **50.4 %** | 20.4 km |
| Uiseong-Andong 2025 | ignition-centred | 919 km² | **98.9 %** | 5.81 km (south) |
| Uljin-Samcheok 2022 | ignition-centred | 924 km² | **84.8 %** | 5.73 km (south) |

All three moved on 2026-08-02 — the two new regions when their DEMs were
corrected, Yeongdeok when it moved onto the canonical field. Current figures are
at the top of this document.


---

# What re-drawing the bbox would cost — ESTIMATE ONLY

**Artifact:** [`yeongdeok_bbox_reacquisition_estimate.json`](../data/processed/yeongdeok_bbox_reacquisition_estimate.json)
**Script:** `scripts/estimate_yeongdeok_bbox_reacquisition.py` — performs **no
network I/O** and imports no OSM client. Nothing was acquired.

## The bbox that would actually cover the fire

Rule: the canonical p ≥ 0.5 final-slice core, plus 5 km on every side — the same
`walk_margin_km` the two acquired regions used.

| | current | proposed |
|---|---|---|
| bbox (W, S, E, N) | 129.250, 36.300, 129.550, 36.600 | **128.893, 36.323, 129.513, 36.634** |
| area | 931 km² | **1,993 km² (2.14×)** |
| coverage of the canonical core | 32.6 % | 100 % by construction |

## Projected cost, extrapolated from current density

| | current | projected |
|---|---:|---:|
| walk nodes | 8,443 | **~18,100** |
| directed edges | 22,276 | **~47,700** |
| road length | 1,614 km | **~3,450 km** |
| refuge POIs | 50 | **~107** |
| origins at stride 18 | 458 | **~980** |
| walk graphml | 12.1 MB | **~26 MB** |

Overpass reference: the two 2026-08-02 walk fetches at ~920 km² took **4.4 s**
(Uiseong-Andong) and **83.6 s** (Uljin-Samcheok). The spread is server-side
variance, not size, so a 2.14× bbox is minutes, not hours. Download volume is
the real cost, and it is modest.

⚠ **The projections are biased HIGH.** Densities come from the current bbox,
which is coastal and contains Yeongdeok town; the proposal extends ~25 km west
into the Taebaek range, where settlement and road density are lower. Every
projected count is an upper bound, by an amount that cannot be measured without
doing the acquisition.

## ⚠ It does not fit the current simulation grid

| side | clearance |
|---|---:|
| west | **−1.5 km** |
| south | +25.0 km |
| east | +24.5 km |
| north | +30.0 km |

The proposed walk bbox extends **1.5 km beyond the western edge of the canonical
simulation grid**, which is already extended 0.05° west. Meeting the 5 km
`routing_clearance_km` requirement needs a further **~6.5 km (~0.073°)** of
canvas.

That is not a detail. Extending the canvas means **re-simulating the hazard
field**, which means a new `routing_demo_canonical.npz`, which means re-running
the 459 scan, the slope sweep, the objective 2×2, the budget sweep and the
multi-region table — the entire step 1–3 chain, again, against a field that may
itself differ. The bbox and the canvas are coupled, and the coupling runs the
expensive way.

## What re-acquiring would break

| broken | why |
|---|---|
| **continuity with the committed 439 series** | 439/167/24, walk-failure 11.4 %, the 72.0 % exposure reduction and the dispatch outputs all rest on the current walk graph and bbox. A different bbox is a different origin population, so none of them could be quoted beside the new ones. |
| **the committed 459 series** | 459 = 438 + 18 + 3 is already unreproducible (its 2026-07-23 network is gone). Re-drawing the bbox would make it unreproducible *in principle* as well as in practice. |
| **every Round-3 result** | the slope sweep, the objective 2×2, the budget sweep, the canonical 459 scan and the Yeongdeok row of the multi-region table are all on 458 origins from the current bbox. All would need re-running on ~980. |
| **the multi-region comparison** | its whole design is "identical parameters, identical rule, three regions". Yeongdeok would become the one region whose bbox was drawn by a *different* rule — envelope-derived rather than the 0.30° × 0.30° ignition-centred footprint — which is the comparability the phase was built to protect. |
| **submission figures** | anything citing 439, 459, 407, 143/24, 72.0 %, 11.4 %, or the dispatch counts. |

## The alternative: keep 32.6 % and state it

Not re-acquiring costs nothing computationally and weakens exactly one thing:
**any claim that a Yeongdeok number describes the Yeongdeok fire rather than the
covered third of it.**

What still stands without qualification:

* every **paired contrast** — fire-blind vs future-aware, flat vs slope,
  distance vs time objective, budget A vs budget B. Both arms are computed on
  the same origins, so the sampling frame cancels. This is most of what the
  project reports.
* every **network and terrain** quantity: the +26.594 % traversal time, the 150
  changed routes, the 91.3-minute longest-walk saving. None depends on the fire.

What needs a caveat every time it is quoted:

* **absolute rates.** `w`, the FA-only share, the 95.5 % rescue rate — all are
  rates *on the covered third*. They are not estimates of a region-wide rate,
  and the direction of the bias is unmeasured.
* **the Yeongdeok row of the multi-region table.** It carries 32.6 % coverage
  against 99.2 % and 81.5 %. Any statement of the form "Yeongdeok differs from
  Uiseong-Andong because …" must clear the coverage difference first, and at
  n = 3 it cannot.

The honest form of the caveat, for reuse:

> 영덕 수치는 정본 화재 핵심의 **32.6 %만 덮는** 보행망에서 산출되었습니다.
> 나머지 3분의 2에 있는 출발지들의 거동은 측정되지 않았으며, 편향의 방향도
> 알려져 있지 않습니다. 지역 간 비교에서 영덕 행을 인용할 때는 이 열을 반드시
> 함께 제시하십시오.

**This document does not recommend either course.** The estimate exists so the
choice can be made on numbers rather than on discomfort.
