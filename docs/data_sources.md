# Data sources

WildfireGuardian relies entirely on **public** data. The repository does not
distribute any of it; users download datasets into `data/raw/` at run time
using the ingestion helpers (to be implemented in `wildfireguardian.data_io`
and `wildfireguardian.fire_detection`).

## Satellite

| Dataset                                  | Provider     | Use                              | Access                                              | Auth         |
|------------------------------------------|--------------|----------------------------------|-----------------------------------------------------|--------------|
| VIIRS S-NPP / NOAA-20 375 m active fire  | NASA FIRMS   | Real-time ignition detection     | <https://firms.modaps.eosdis.nasa.gov/api/>         | MAP_KEY      |
| MODIS Aqua/Terra MCD14ML                 | NASA FIRMS   | Cross-check & historic ignitions | Same                                                | MAP_KEY      |
| Sentinel-2 L2A surface reflectance       | Copernicus   | LFMC retrieval                   | <https://browser.dataspace.copernicus.eu/>          | CDS account  |
| Sentinel-3 SLSTR L2 FRP                  | Copernicus   | Fire radiative power, optional   | Same                                                | CDS account  |

## Meteorology

| Dataset                                  | Provider     | Use                          | Access                          | Auth         |
|------------------------------------------|--------------|------------------------------|---------------------------------|--------------|
| KMA AWS hourly wind, RH, T               | KMA          | Spatial wind field for CA    | <https://data.kma.go.kr/>       | service key  |
| ERA5 single levels (10 m winds, 2 m T/q) | Copernicus C3S| Reanalysis fallback         | CDS API                         | CDS account  |
| GDAPS / KIM regional NWP                 | KMA          | Short-range forecast wind     | KMA (data.kma.go.kr)            | service key  |

## Terrain & land cover

| Dataset                                  | Provider                 | Use              | Access                                   |
|------------------------------------------|--------------------------|------------------|------------------------------------------|
| DEM 30 m / 10 m                          | NGII (국토지리정보원)    | Slope, aspect    | <https://map.ngii.go.kr/>                |
| 환경부 토지피복지도 (Land cover)         | ME (환경부)              | Fuel-model raster| <https://egis.me.go.kr/>                 |
| 산림청 임상도 (Forest type map)          | KFS (산림청)             | Fuel-model raster (refined) | <https://www.forest.go.kr/>     |

## Roads & population

| Dataset                                  | Provider                 | Use                              | Access                                   |
|------------------------------------------|--------------------------|----------------------------------|------------------------------------------|
| OSM road network                         | OpenStreetMap            | Evacuation routing graph         | <https://www.openstreetmap.org/>         |
| 행정안전부 주민등록 연령별 인구 통계     | MOIS                     | Elderly density per village      | <https://mois.go.kr/>                    |
| SK Telecom Floating Population (sample)  | KOSIS                    | Diurnal exposure adjustment      | <https://kosis.kr/>                      |

## Ground-truth validation

| Dataset                                            | Provider | Use                                  | Access                              |
|----------------------------------------------------|----------|--------------------------------------|-------------------------------------|
| KFS official perimeter polygons (영덕 산불 2025)  | KFS      | Retrospective skill scoring          | KFS post-event report               |
| MOIS casualty reports (March 2025 event)          | MOIS     | Outcome variables for evaluation     | Government white paper              |

## Licensing & attribution

All datasets listed here are public for non-commercial research. Each
ingestion helper in `wildfireguardian.data_io` will emit the proper
attribution line in the output product metadata. **Never** redistribute raw
NASA FIRMS or Sentinel imagery; redistribute *derived products only*, with
provenance.
