# Camera arrival-time proof of concept — stopped at Step 0

**Status: the feasibility gate failed. Steps 1–7 (images, camera pose, flame
segmentation, ground projection, GOFER validation, figures, animation) were
not run. There are no arrival-time results, validated or otherwise, in this
folder.**

The goal was to turn fixed HPWREN wildfire-camera images into a
fire-arrival-time map and check it against GOFER hourly perimeters. The plan
required a gate first: at least one GOFER fire with an HPWREN camera within
60 km that sees at least 10% of the burn by terrain line of sight, with
1-minute archive images available for the fire dates. Full details, tables and
the independent audit are in [FEASIBILITY.md](FEASIBILITY.md).

## What was done

- Downloaded GOFER v0.2 from its publisher (Zenodo record 14642378; md5
  verified). The archive was **not** present in this repository. Listed all 28
  fires with dates and bounding boxes (`outputs/gofer_fires.csv`,
  `outputs/gofer_layout.md`).
- Built an inventory of 82 HPWREN sites and 503 cameras with position, view
  azimuth and horizontal field of view from the HPWREN camera page
  (`outputs/hpwren_cameras.csv`), and recorded HPWREN's usage notice
  (`outputs/hpwren_access_notice.md`).
- Computed terrain line of sight (30 m DEM, earth curvature, refraction
  k = 0.13) from every site within 60 km to every burned cell of each fire's
  final GOFER perimeter (`src/s0_feasibility.py`, `src/viewshed.py`,
  `outputs/feasibility_table.csv`).
- Probed the HPWREN archive for the fire dates, sequentially and throttled
  (`outputs/hpwren_archive_probe.md`, `outputs/feasibility_archive.json`).
- A second, independent implementation re-checked coordinates, distances,
  visible fractions and archive status (`src/audit_s0_independent.py`,
  `outputs/audit_s0_independent.json`).

## The numbers

| Item | Result |
|---|---|
| GOFER fires with any HPWREN site within 60 km | 6 of 28 (Bobcat, Kincade, Glass, LNU, CZU, SCU) |
| Best single fixed camera, ground-level visible burn | 7.7% (`chino-n-mobo-c` and `wilson-e-mobo-c`, Bobcat 2020) — below the 10% gate |
| Same cameras, independent audit | 7.4% and 7.0% (95% upper bounds 8.4% and 8.0%) |
| Same cameras, target 20 m above ground (not the gate criterion) | 10.7% and 11.1% |
| Mount Wilson north + east cameras combined, ground (not the gate criterion) | 10.8% |
| Kincade 2019 / Glass 2020 best camera (`ihvy`) | 4.8% / 4.0% |
| LNU, CZU, SCU | 0% |
| 1-minute images retrievable for any 2019–2021 date | None |

## What failed

1. **Line of sight.** No single fixed camera sees 10% of any GOFER burn at
   ground level. The miss is narrow for Bobcat, and the gate would pass under
   looser definitions (flames 20 m above ground, or two cameras combined), but
   those are not the criterion that was set.
2. **Image archive.** HPWREN deletes 1-minute JPEGs after about 90 days, and
   image lists for 2019–2022 return HTTP 403. For Mount Wilson, three-hour MP4
   videos of the Bobcat dates exist but sit in cold storage (S3 Deep Archive);
   downloads return 403 until HPWREN restores them on request. For Chino Hills
   and Iron Horse Vineyards nothing was found for the dates probed.

No fire outside GOFER was substituted.

## What it would take to continue

- A decision to relax the 10% single-camera ground-level criterion for Bobcat
  with `wilson-e-mobo-c` (optionally plus `wilson-n-mobo-c`).
- A request to HPWREN to restore specific three-hour video blocks.
  `outputs/restore_plan_bobcat_wilson.csv` ranks blocks by newly burned area
  visible from Mount Wilson. Whether those videos hold one frame per minute is
  unverified.
- Note that Bobcat's largest growth day (2020-09-18) is almost entirely hidden
  from Mount Wilson: 1.4 of 165 km² of that day's new burn is visible.

## Limits

- Camera positions, azimuths and fields of view come from HPWREN's current
  (2026) metadata; 2019–2021 positions and pointing may have differed, and
  sites removed since then are not in the search.
- Visibility is terrain-only and horizontal field of view only. Vegetation,
  buildings, smoke, haze, vertical field of view and image resolution are not
  modelled. Pan-tilt-zoom cameras were excluded from the gate.
- Visible fractions are relative to the GOFER footprint, which differs from
  official fire areas (Bobcat: 584 km² in GOFER versus 469 km² official).
- GOFER hourly labels are nominal end-of-hour stamps from roughly 2 km
  geostationary pixels, not measured arrival times.
- Archive probing was sparse (selected three-hour blocks per camera), and an
  HTTP 403 cannot distinguish a missing file from a forbidden one.
- This work makes no claim about any region outside the fires examined.

## Reproduce

```bash
python3 src/s0_gofer_inventory.py
```

```bash
python3 src/s0_hpwren_inventory.py
```

```bash
python3 src/s0_feasibility.py
```

```bash
python3 src/test_viewshed.py
```

Downloads go to `cache/`, which is not committed. Note that
`src/s0_write_feasibility_md.py` regenerates FEASIBILITY.md and would drop the
appended audit section.

## Credits

- Camera metadata and archive: HPWREN (hpwren.ucsd.edu), UC San Diego;
  archived data CC BY-NC 4.0. HPWREN data are not intended to be used as a
  decision-making tool, or as a replacement for such tools.
- Fire perimeters: GOFER v0.2, Liu et al., doi:10.5281/zenodo.14642378.
- Elevation: AWS Terrain Tiles (1 arc-second, SRTM / USGS derived).
