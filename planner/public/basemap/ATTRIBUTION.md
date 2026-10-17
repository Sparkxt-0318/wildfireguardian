# Basemap attribution

- **Map data:** © OpenStreetMap contributors, available under the Open Database License (ODbL 1.0),
  https://www.openstreetmap.org/copyright. The `*.pmtiles` files are byte-for-byte copies of tiles from the
  Protomaps daily build `20261016` (https://build.protomaps.com/20261016.pmtiles), cut to each region's
  road-graph bounding box (z0–15) plus a South Korea context box (z0–8). See `SOURCES.json` for hashes.
- **Tile schema and style:** Protomaps Basemap (https://github.com/protomaps/basemaps), BSD-3-Clause code.
- **Fonts:** Noto Sans glyph PBFs from `protomaps/basemaps-assets`, SIL Open Font License 1.1. Unused ranges are
  replaced with empty glyph files (see `SOURCES.json` → `fonts.trim`). Korean labels use Pretendard (SIL OFL 1.1),
  bundled with the app, through MapLibre's `localIdeographFontFamily`.
- **Sprites:** `protomaps/basemaps-assets` sprites v4.

No raster tiles were downloaded from tile.openstreetmap.org (its usage policy forbids bulk or offline prefetching).
The app never fetches tiles from the internet; an optional VWorld base layer is used only when `VWORLD_API_KEY`
is set in a local `.env`.
