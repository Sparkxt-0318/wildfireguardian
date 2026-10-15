# Asset provenance and boundaries

Created for the user-requested standalone exhibition website, 2026-10-11. The inventory was bounded to the named reference directories and locally shipped assets. It did not consume experiments, intermediate results, scientific histories, or the full archive. No network assets, tiles, geocoding, or runtime CDN requests are needed for these visual assets.

## Rendered data

- **Terrain:** an original deterministic mathematical height field in `src/data.mjs`, in arbitrary visual units. It is not a Korean DEM, measured landscape, or terrain truth.
- **Roads:** authored smooth curves. Both route displays reuse exactly the same coordinate sequences as their roads. They are not surveyed, OpenStreetMap, or imported real Korean roads.
- **Fire:** scripted radial visual and particle art. It is not a forecast, observation, perimeter measurement, uncertainty field, or propagation model.
- **Routes:** two scripted paths for spatial comparison. No optimality, safety, improved exposure, causal effect, or superiority claim is made. A line near a visual fire does not establish real hazard or tenability.
- **Track:** the built-in track is scripted. A local recorded-track adapter accepts a user's source assertion and displays it on illustrative terrain with fire hidden; recording authenticity is unverified. It is not a computed escape route.
- **Device:** actual owner CAD housing meshes, with exhibition materials. It is a housing design study, not proof of a built or tested device. No sensor, PCB, battery, thermal mechanism, or antenna internals are shown. The dark-glass window and its small DEMO route animation are illustrative proposed interface art, not a supplied firmware screen or live telemetry. Failure to load CAD leaves a simple outline, not an invented substitute assembly.

## Owner CAD

Exact source folder:
`/Users/jp/Documents/Codex/2026-09-24/fu/outputs/field_route_logger_planning_20261003_v1/prearrival_20261003_v2/baseline/CAD`

The CAD README describes a housing v1.1 study for Heltec Wireless Tracker V2 and binary STLs in their assembly positions. DIMENSION_LEDGER.md gives an 81.1 × 30.0 × 22.9 mm design envelope; this is a design dimension, not a measurement of physical fit. The meshes are copied byte-for-byte, recoloured for the exhibition, and rigidly reoriented/uniformly scaled to approximately 6.66 × 18 × 5.08 scene units. Only bottom housing, top housing, and short user plunger are included. No assembly internals or vendor board mesh are copied. The copied files retain their original `_v1` names despite the source README describing v1.1.

Source render `renders/01_assembled_iso_front.png` was visually inspected for exterior alignment. Source README.md and DIMENSION_LEDGER.md were read for orientation and status. No Blender regeneration, CAD experiment, or physical check was run. No separate CAD redistribution license was found in the bounded CAD folder; these owner-provided assets are used for this owner's requested website. This document does not grant rights to redistribute other owner's or vendor files.

## Fonts

IBM Plex Sans KR (Regular, SemiBold) and IBM Plex Mono (Regular, SemiBold) were copied from the owner's `wildfireguardian/web/assets/fonts` directory. The supplied `LICENSE-IBMPlex.txt` states copyright IBM Corp. and SIL Open Font License 1.1. Font binaries are unmodified; the license is bundled. No other font or brand image is copied. The wordmark is website text.

## Bounded availability checks

The named logger-planning directory contains the exterior CAD used above. The connected desktop demo's app directory did not yield an appropriate packaged image/font/mesh in the bounded asset inventory. The owner's repository contains DEM and geographical cache filenames, but their contents were not inspected, processed, or reused; the website must keep its illustrative terrain/road labels.

`outputs/final_forecast_routing_integration_20261011_v1` exists. Its top-level listing at this check contained work/input/environment/raw-style directories and an ownership note, but no final-ready public manifest. None of those intermediate directories or results were read. No final scientific artifact is integrated, and there was no waiting for that investigation.

## Exact packaged asset hashes

The machine-readable inventory is `public/assets/ASSET_MANIFEST.json`. SHA-256 is used for byte identity only; it does not establish scientific truth or license authority.

| Packaged path | SHA-256 | Origin |
|---|---|---|
| `public/assets/device/WFG_logger_housing_bottom_v1.stl` | `ffe93241d51f71424dfb29c0cf0096942d4300e5eebaab13f46d74466110422f` | Owner CAD exact copy |
| `public/assets/device/WFG_logger_housing_top_v1.stl` | `6c43a4ae177f626200ba0645b04dfe80a0f342fff455f2a7c70a1be285d8df95` | Owner CAD exact copy |
| `public/assets/device/WFG_logger_plunger_user_v1.stl` | `38e47754d903b02e11fb37221f19d413555b8549dcb29956294c97aa2e4f4aa3` | Owner CAD exact copy |
| `public/assets/fonts/IBMPlexMono-Regular.woff2` | `08949f728dc52d528e69b1667d15c89a5686a4ee9a296ff90983985f99c380f7` | IBM font/license exact copy |
| `public/assets/fonts/IBMPlexMono-SemiBold.woff2` | `0d1f0b8d0722224e32e9f28261bdc86c79115be73444ae5eceb73976a1bcdf83` | IBM font/license exact copy |
| `public/assets/fonts/IBMPlexSansKR-Regular.woff2` | `f44b788da57c4717d6eb3a9cc4441204d81c476b9edcf0d3f9aff32b638fd600` | IBM font/license exact copy |
| `public/assets/fonts/IBMPlexSansKR-SemiBold.woff2` | `aca77c5de668158f3f12e5b4f2f0eef242e974310e04665bc6a57a1287cefb00` | IBM font/license exact copy |
| `public/assets/fonts/LICENSE-IBMPlex.txt` | `7e6b2818edbd8f6a01ae80641cc8f16a51080d08fb4e532be3a0b6f74adb07da` | IBM font/license exact copy |
| `public/assets/illustrative-scene.json` | `a549003a3d6f297f10b88478ad1aec6eb59ba86686bb41ace8b7f9e7dfd20378` | Authored fixture |
