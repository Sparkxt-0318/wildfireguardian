/**
 * Offline basemap style (planner/public/basemap, see its README.md).
 *
 * - Vector tiles come only from the region's local PMTiles file (`/basemap/<region>.pmtiles`);
 *   the app never requests internet tiles. The optional VWorld raster (VWORLD_API_KEY) is a
 *   separate, explicitly enabled layer (see `vworldRasterSource`).
 * - Labels are Korean (`lang: 'ko'`). MapLibre draws Hangul client-side; styles/map-hangul-fonts.css maps
 *   the basemap's "Noto Sans …" stacks to the bundled Pretendard for Hangul, Latin glyphs come from the
 *   bundled Noto Sans PBF ranges.
 * - Village/neighbourhood labels are moved beside their point, because the planner draws its own origin
 *   markers on the same OSM place nodes and a centred label would sit under the marker.
 *
 * Shared with the feature builder (plan sheet mini maps): keep the signatures stable.
 */
import maplibregl from 'maplibre-gl';
import type { LayerSpecification, StyleSpecification } from 'maplibre-gl';
import { Protocol } from 'pmtiles';
import { layers as protomapsLayers, namedFlavor } from '@protomaps/basemaps';

export type BasemapFlavor = 'light' | 'white' | 'grayscale';

export const BASEMAP_ATTRIBUTION = '© OpenStreetMap contributors · Protomaps';

/** CSS font stack MapLibre uses for Hangul / CJK labels (no glyph download needed). */
export const LOCAL_IDEOGRAPH_FONT =
  "'Pretendard Variable', Pretendard, 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', sans-serif";

let protocolInstalled = false;

/** Registers the `pmtiles://` protocol with MapLibre once (safe to call many times). */
export function ensurePmtilesProtocol(): void {
  if (protocolInstalled) return;
  const protocol = new Protocol();
  maplibregl.addProtocol('pmtiles', protocol.tile);
  protocolInstalled = true;
}

/** Absolute same-origin URL; template tokens such as {fontstack} stay unescaped. */
function abs(path: string): string {
  if (typeof window === 'undefined' || !window.location) return path;
  return `${window.location.origin}${path.startsWith('/') ? '' : '/'}${path}`;
}

/** URL of a region's local PMTiles archive. */
export function pmtilesUrl(regionId: string): string {
  return abs(`/basemap/${encodeURIComponent(regionId)}.pmtiles`);
}

/**
 * MapLibre style for a region's offline vector basemap (Protomaps schema, Korean labels).
 * Default flavor: grayscale — the map stays monochrome so status colours carry meaning.
 */
export function basemapStyle(regionId: string, opts?: { flavor?: BasemapFlavor }): StyleSpecification {
  const flavor: BasemapFlavor = opts?.flavor ?? 'grayscale';
  const layers = (protomapsLayers('protomaps', namedFlavor(flavor), { lang: 'ko' }) as LayerSpecification[]).map(
    offsetPlaceLabels,
  );
  return {
    version: 8,
    glyphs: abs('/basemap/fonts/{fontstack}/{range}.pbf'),
    sprite: abs(`/basemap/sprites/v4/${flavor}`),
    sources: {
      protomaps: {
        type: 'vector',
        url: 'pmtiles://' + pmtilesUrl(regionId),
        attribution: BASEMAP_ATTRIBUTION,
      },
    },
    layers,
  };
}

/** Village-level place labels: anchor beside the point (right first) instead of on it. */
function offsetPlaceLabels(layer: LayerSpecification): LayerSpecification {
  if (layer.type !== 'symbol' || (layer.id !== 'places_locality' && layer.id !== 'places_subplace')) return layer;
  const layout = { ...(layer.layout ?? {}) } as Record<string, unknown>;
  delete layout['text-anchor'];
  delete layout['text-offset'];
  layout['text-variable-anchor'] = ['left', 'right', 'top', 'bottom'];
  layout['text-radial-offset'] = 0.85;
  layout['text-justify'] = 'auto';
  return { ...layer, layout } as LayerSpecification;
}

/** Plain paper style used when a region's PMTiles file is missing (no tiles at all). */
export function paperStyle(): StyleSpecification {
  return {
    version: 8,
    glyphs: abs('/basemap/fonts/{fontstack}/{range}.pbf'),
    sources: {},
    layers: [{ id: 'paper', type: 'background', paint: { 'background-color': '#FAFAFA' } }],
  };
}

/** True when the region's PMTiles archive is served (HEAD/range probe, no tile decoding). */
export async function hasRegionBasemap(regionId: string, signal?: AbortSignal): Promise<boolean> {
  try {
    const r = await fetch(pmtilesUrl(regionId), { headers: { Range: 'bytes=0-15' }, signal });
    if (!(r.ok || r.status === 206)) return false;
    const type = r.headers.get('content-type') ?? '';
    // Vite's SPA fallback answers unknown paths with index.html; that is not a tile archive.
    if (type.includes('text/html')) return false;
    const buf = new Uint8Array(await r.arrayBuffer());
    // PMTiles v3 magic "PMTiles"
    return buf.length >= 7 && String.fromCharCode(...buf.slice(0, 7)) === 'PMTiles';
  } catch {
    return false;
  }
}

/**
 * Optional VWorld raster background (국토교통부 VWorld WMTS). Only used when VWORLD_API_KEY is set
 * AND the user turns it on; it is an internet service, so it is never the default.
 */
export function vworldRasterSource(apiKey: string): maplibregl.RasterSourceSpecification {
  return {
    type: 'raster',
    tiles: [`https://api.vworld.kr/req/wmts/1.0.0/${encodeURIComponent(apiKey)}/gray/{z}/{y}/{x}.png`],
    tileSize: 256,
    minzoom: 6,
    maxzoom: 18,
    attribution: '© VWorld (국토교통부)',
  };
}
