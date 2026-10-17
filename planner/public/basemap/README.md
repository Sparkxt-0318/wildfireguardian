# Offline basemap

Built by `planner/tools/build_basemap.py` (HTTP Range requests against a Protomaps daily build; no re-encoding).

| File | Region | Notes |
|---|---|---|
| `uiseong_andong_2025.pmtiles` | 의성·안동 | demo region |
| `yeongdeok_2025.pmtiles` | 영덕 | demo region |
| `uljin_2022.pmtiles`, `miryang_2022.pmtiles`, `hongseong_2023.pmtiles` | 울진, 밀양, 홍성 | |

Each file holds z0–15 for the padded road-graph bbox plus z0–8 for South Korea, so the map works with no internet.

Use from the app (MapLibre GL JS 5 + `pmtiles` + `@protomaps/basemaps` 5):

```ts
import maplibregl from 'maplibre-gl';
import { Protocol } from 'pmtiles';
import { layers, namedFlavor } from '@protomaps/basemaps';

maplibregl.addProtocol('pmtiles', new Protocol().tile);
const abs = (p: string) => new URL(p, window.location.href).href;
const style = {
  version: 8,
  glyphs: abs('/basemap/fonts/{fontstack}/{range}.pbf'),
  sprite: abs('/basemap/sprites/v4/light'),
  sources: { protomaps: { type: 'vector', url: 'pmtiles://' + abs(`/basemap/${regionId}.pmtiles`),
                          attribution: '© OpenStreetMap contributors · Protomaps' } },
  layers: layers('protomaps', namedFlavor('light'), { lang: 'ko' }),
};
new maplibregl.Map({ container, style,
  localIdeographFontFamily: "'Pretendard Variable', Pretendard, 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif" });
```

Flavors with sprites here: `light`, `white`, `grayscale`. Attribution: see `ATTRIBUTION.md`.
