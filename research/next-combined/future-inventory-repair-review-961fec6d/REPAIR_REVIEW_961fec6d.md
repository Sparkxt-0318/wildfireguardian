# Independent repair recheck, 961fec6d

Reviewed immutable `961fec6d43bd8f89433c183f973805de3a228444` in `work/audit-1b`. Adapter SHA256 `50d4c848ef796ed83c3f2fb7de74b4b615c14a3665a427fba0c4d5ff1bc5bbad`. Original review, reproduction script, result JSON and fixtures were preserved; separate controls and newly generated fixtures are adjacent to this report.

**Recommendation: one targeted custody repair remains before adopting/wiring this adapter into a preregistration command.** The original three findings are repaired at their reviewed mechanisms. The added canonical-raster dependency guard leaves optional weather quality rasters outside its scope, permitting an unpinned dependency to change actual model-input validity.

## Confirmed remaining P1: optional quality-raster dependency closure

`research/forecast-v2/scripts/blind_inventory.py:336-353` checks the actual GDAL driver and dependencies only for the six `CHANNELS` canonical rasters. The later `dataset[0]` at line 380 also reads optional weather quality rasters through `forecast/wildfire/data.py:449-455`. Those optional rasters do not receive the new driver/dependency check.

Tiny synthetic reproduction:

1. Ordinary pinned canonical sources validate two cases.
2. Add a regular GeoTIFF at `environment/quality_flags/SYNTHETIC_A/temperature_2m_quality_flags_375m.tif`, with 97 aligned bands of zero quality flags. Pin and validate: two cases are admitted.
3. Move that quality GeoTIFF to `input_root/borrowed-quality.tif` outside environment, then replace the original `.tif` path with a GDAL VRT referring to the borrowed file. Repin the environment. The VRT is pinned, but its external source is absent from all environment pins. Validation still returns `LOCAL_INVENTORY_VALIDATED_EXTERNAL_RELEASE_UNVERIFIED` and two cases.
4. Change every quality flag in the unpinned borrowed GeoTIFF from zero to one without changing the manifest. Validation returns the same admitted result. A direct label-free read of the same tiny sample proves the dependency is consumed: valid feature entries fall from 54 to 45.

Apply the same actual-driver and complete dependency-custody guard to every optional quality raster the loader can open, retaining the valid ordinary quality-GeoTIFF control. Include dependencies/sidecars in that guard. This can be repaired in the adapter without changing frozen forecasting/scoring code. Do not treat missing-value non-exclusion as permission for unpinned quality-input bytes to vary.

## Repairs independently confirmed

- The original internal directory symlink is refused before and after its target is mutated, following an ordinary successful validation.
- Appended complete DBF records and double EOF bytes are refused. Exact DBF payloads with no EOF or one 0x1A EOF retain the three raw records and two admitted cases.
- A `.tgz` containing a second complete incident bundle is refused by the explicit member-format allowlist. Disguising its binary contents as `.txt` is also refused. Ordinary allowlisted TXT/MD/matching SHP.XML metadata remains admissible and authenticated.
- A VRT disguised as a canonical `.tif` is refused after a successful ordinary-source control. The remaining finding above concerns the separately opened optional quality raster.
- All successful controls still report `NOT_READY_FOR_2026_EXECUTION`. The source remains unwired, and no software result authenticates release identity or preregistration chronology.

Seventeen separate positive/negative observations are recorded in `repaired_controls_961fec6d.json`. Reproduce using:

```
PYTHONDONTWRITEBYTECODE=1 work/venv-forecast/bin/python work/future-inventory-review/repaired_controls_961fec6d.py
```

The controls write new tiny synthetic fixture directories only beneath `work/future-inventory-review/`. They do not alter the original evidence. No real raw, 2026/future study or heldout data was accessed; no forecasts, heavy experiment, timing claim, source modification, push or merge occurred. The audited checkout remained clean. The owner's 69-test suite was read at its changed sections, not independently rerun.

The entire repaired 552-line adapter was directly read because graph project `wfg-next-1b-audit-961fec6d-20261030`, generation `2026-10-30T05:22:21Z`, excludes its scripts subtree. Indexed test discovery returned 57 entities with no next page. The tests and referenced environmental loader source were metadata-matching with no recorded coverage gap. The original nonchanged tests and reference-loader behavior were retained from the earlier bounded review. This remains a software/protocol review, not certification of real release completeness, dependency-runtime correctness, public-release authenticity or pre-access registration.
