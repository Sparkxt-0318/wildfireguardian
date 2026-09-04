# Buildings as fuel at the wildland–urban interface — the FireDX pipeline, and why WildfireGuardian does not adopt it before the finals

*Knowledge note · written 2026-09-04 (laptop lap) · status: **decision recorded — do not implement before 2026-10-16 freeze; post-finals / IEEE direction** · maintained by the research routine (CHARTER §11)*

## 1. The source

Theodori, M., Zamanialaei, M., Purnomo, D. M. J., Qin, Y., Lautenberger, C., Gollner, M. J. — *A pipeline for buildings as fuels in wildland–urban fire spread and risk modeling* (FireDX). Preprint PDF supplied by the author on 2026-09-04 (year inferred as 2026 from the newest cited work; no DOI printed). Code: `https://github.com/berkeley-firelab/firedx` (announced "upon publication" — not yet opened, treat as unverified). Data: Zenodo deposit announced, ~3 GB of GeoTIFF + parquet for California.

## 2. What FireDX actually does

FireDX is a **data-engineering pipeline**, not a fire model. It converts open building data into simulation-ready fuel layers for a coupled wildland–urban spread solver (ELMFIRE-WU-E).

1. **Inputs.** Microsoft US Building Footprints (+ OpenStreetMap infill), parcel records (year built, occupancy), National Structure Inventory (fallback attributes), LANDFIRE FBFM40 fuel raster, California Fire Hazard Severity Zones (FHSZ).
2. **Per-structure enrichment.** Footprint area, occupancy class, stories (from LiDAR height), construction year, hardened flag (Chapter 7A: year built ≥ 2008 AND inside an FHSZ polygon).
3. **Building Fuel Model (BFM).** Seven classes: BFM1–3 unprotected (small / moderate / large by potential fire energy), BFM4–6 hardened, BFM7 small footprint (< 85 m²). Assignment is a deterministic rule set; the authors call it "a flexible structural typology rather than a fixed statewide taxonomy".
4. **Fuel load.** Per structure, F_load = ρ_fuel · A_bldg · (N_stories + 1) / 1000 GJ; summed per cell it yields a continuous urban fire-load energy density map (GJ/ha).
5. **Hybrid raster.** On the LANDFIRE grid, the single "developed / non-burnable" class is split into burnable structure cells (BFM-coded), explicitly non-burnable paved cells (code 256) and preserved vegetative fuels; companion rasters give footprint fraction, characteristic building area and minimum structure-separation distance. Same pipeline runs at 10 m or 30 m.
6. **Validation is internal only** — attribute coverage per county, raster/vector conservation, bit-identical reruns. The authors state plainly that the release is **not calibrated or validated against observed spread or structure loss**.

The statewide California run classifies about 11.5 million structures; the large majority are unprotected, and the hardened share is well under one percent because the rule needs both a documented post-2008 build year and an FHSZ overlay.

## 3. Is it useful for WildfireGuardian's forecasting? — the decision

**Conceptually yes, operationally no before the finals.** Recorded reasons:

| # | Reason it is not adopted now | Weight |
|---|---|---|
| 1 | FireDX feeds a **physics spread solver**. WildfireGuardian forecasts per-cell ignition probability with a trained classifier and then routes/dispatches on that field; there is no spread solver to feed, and the freeze rules (docs/HANDOFF_ROUND3.md §5, CHARTER §3) forbid a new spread model or a retrain before 2026-10-16. | blocking |
| 2 | The BFM rules need **structure attributes we do not hold** for Korea: construction year, stories, occupancy, hazard-zone overlay. Korean equivalents exist (건축물대장 via 공공데이터포털 open API — needs an API key, which is a credential and therefore an author task; 도로명주소 건물DB footprints), but ingesting them is a data programme, not a lap. | blocking before freeze |
| 3 | Even for California the product is **uncalibrated against loss**; adopting it would add an unvalidated layer to a system we are trying to make more, not less, defensible in front of judges. | strong |
| 4 | Our motivating event (2025 의성→영덕 chain) was a fast wind-driven forest fire that entered settlements; the routing objective cares about *when the front reaches the road*, which FireDX does not predict. | strong |

**What we take immediately (no model change, no new dependency):**

- **Framing for the paper.** Developed land is not inert: the related-work / limitations text should say that WildfireGuardian treats settlements as exposure (origins, refuges, homes to rescue) rather than as fuel, cite FireDX and the structure-loss literature it rests on (Syphard & Keeley 2019; Zamanialaei et al. 2025; Purnomo et al. 2024; Young et al. 2025), and name that as a limitation.
- **Vocabulary and descriptors** for WFG-013 (open footprints for 영덕): report *footprint fraction per cell* and *minimum structure-separation distance* the way FireDX does, so a later comparison is straightforward.
- **A judge answer** (for docs/auto/JUDGE_QA.md): "Why don't you model houses burning?" → "Because no open Korean structure inventory carries the attributes the state of the art needs, and an uncalibrated building-fuel layer would weaken rather than strengthen the evidence; we treat buildings as exposure and say so."

## 4. Post-finals / IEEE direction (backlog WFG-059)

1. **Korean BFM-lite.** From 건축물대장 (사용승인일, 층수, 주용도, 구조) joined to 건물DB footprints: footprint fraction, mean separation distance, construction era, structure type (목구조 vs 철근콘크리트) per 30 m cell for the six study fires.
2. **Feature ablation (a retrain, hence post-finals).** Does footprint fraction or separation distance improve held-out ignition discrimination in the leave-one-fire-out protocol, or only in the two fires that entered settlements?
3. **Exposure raster for routing.** Use the structure density as a *demand* layer (where people are) rather than a fuel layer — that fits our objective and needs no spread solver.
4. **Loss comparison** if 산림청 / 행정안전부 publish parcel-level damage for 2025 의성·영덕: the first honest test of whether a Korean BFM-lite predicts loss.

## 5. Sources (DOIs as printed in the FireDX reference list; not yet opened — verify before citing in the manuscript)

- Radeloff, V. C. et al. (2023) Rising wildfire risk to houses in the United States. *Science* 382, 702–707. doi:10.1126/science.ade9223
- Schug, F. et al. (2023) The global wildland–urban interface. *Nature* 621, 94–99. doi:10.1038/s41586-023-06320-0
- Syphard, A. D. & Keeley, J. E. (2019) Factors associated with structure loss in the 2013–2018 California wildfires. *Fire* 2(3), 49–64.
- Zamanialaei, M. et al. (2025) Fire risk to structures in California's wildland–urban interface. *Nature Communications* 16, 8041. doi:10.1038/s41467-025-63386-2
- Purnomo, D. M. J. et al. (2024) Reconstructing modes of destruction in wildland–urban interface fires using a semi-physical level-set model. *Proc. Combust. Inst.* 40, 105755. doi:10.1016/j.proci.2024.105755
- Young, B. et al. (2025) Modeling neighborhoods as fuel for wildfire: a review. *Fire Technology*. doi:10.1007/s10694-025-01773-3
- Microsoft US Building Footprints — https://github.com/microsoft/USBuildingFootprints
- 건축물대장 정보 서비스 (국토교통부) — https://www.data.go.kr (search "건축물대장"; API key required → author)
- 도로명주소 건물DB — https://business.juso.go.kr (open download, no key)
