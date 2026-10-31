# Targeted final custody repair recheck

Reviewed immutable `d031b72b86d4f9089c87ab3e8d706ca74423c31f` at `work/audit-1b`. Adapter SHA256: `6358a96d55f18f61c01a89caaba5fbe4e8fd5cfda01c5cab0f62a0e8e88ca330`.

**Scoped software clearance: the owner may wire this reviewed adapter into a preregistration command.** No remaining actionable finding was found in the targeted quality-raster and reported mask-sidecar custody repair. This clearance neither authorizes future study execution nor establishes release authenticity, registration chronology, real archive completeness or physical correctness. `NOT_READY_FOR_2026_EXECUTION` and the independent documentary gates must remain enforced. Any subsequent command wiring still needs its own source/pinning and software checks.

## Source assessment

The shared `_raster_custody` helper at `research/forecast-v2/scripts/blind_inventory.py:331-353` checks actual GeoTIFF driver, lexical path symlinks, resolved environmental containment and membership in complete snapshot pins. It recursively applies the same check to reported raster sidecars (`.tif`, `.tiff`, `.msk`, `.ovr`) with a seen set.

The availability path list at lines 361-374 now includes all three optional weather-quality rasters actually read by the selected six-channel loader, alongside the six canonical sources. Thus the previously demonstrated optional quality VRT no longer bypasses driver/dependency checks. The earlier symlink, DBF payload and archive-format repairs are unchanged in this diff; their prior independent recheck remains applicable.

## Independent targeted controls

Twenty observations passed in `repaired_controls_d031b72b.json`:

- For each of temperature, eastward wind and northward wind, an ordinary fixture and an ordinary pinned quality GeoTIFF both admit the expected two cases with three raw records and no exclusions.
- Replacing each quality GeoTIFF with a VRT referencing an unpinned file outside `environment/` is refused at the specific quality path. Mutating that external file from zero to one with the exact manifest unchanged is refused again. This directly closes the mechanism that previously changed 54 valid feature entries to 45.
- Ordinary pinned external GeoTIFF masks attached to a quality raster and to a canonical source raster remain admissible. The quality case uses nonzero quality values, confirming those values do not become a cohort exclusion.
- Replacing either reported `.msk` with a VRT referencing an unpinned external source is refused at the specific mask path, both before and after external mutation with unchanged manifest.
- Every successful control retains `NOT_READY_FOR_2026_EXECUTION`. Expected GDAL warnings about standalone mask georeferencing do not affect the assertions.

Reproduction from the task directory:

```
PYTHONDONTWRITEBYTECODE=1 work/venv-forecast/bin/python work/future-inventory-review/repaired_controls_d031b72b.py
```

The script constructs only tiny synthetic inputs in new `repair-d031b72b-*` directories beneath this review folder. Original a6d15519 and 961fec6d reports, controls, results and fixtures remain unchanged. No real raw archive, future/2026 study data or heldout data was accessed. No forecasts, heavy/timed experiment, track-source change, push or merge occurred. The audited checkout remained clean. The owner's 74-test suite was not independently rerun; this review executed the separate fixed controls above and read the changed tests.

## Evidence scope and limits

The full repaired 573-line adapter was read directly because graph project `wfg-next-1b-audit-d031b72b-20261030`, generation `2026-10-30T05:29:57Z`, excludes its scripts subtree. The project was confirmed ready. Indexed test discovery returned 61 entities with no further page; test coverage was metadata-matching with no recorded gap. Coverage signals are best effort, not proof of completeness.

This is a bounded source-and-fixture recheck of the confirmed custody mechanism and its reported raster sidecars. It is not a universal filesystem/GDAL proof, concurrent-mutation defense, platform census, full format-security audit or certification of every possible dependency/reporting behavior. Exact source/dependency registration, first-public-release identity/time, authoritative grid extent and real source completeness remain independent gates. The adapter's current unwired and NOT_READY status is accurately retained.
