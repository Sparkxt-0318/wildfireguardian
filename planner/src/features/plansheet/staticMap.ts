/**
 * Static route maps for the plan sheet.
 *
 * A non-interactive MapLibre map (offline basemap from src/map/basemapStyle) is rendered off-screen
 * with preserveDrawingBuffer, converted to an image on 'idle' and removed again, so a sheet prints
 * reliably and many sheets never hold many WebGL contexts (maps render one at a time through a
 * serial queue; results are cached by content key). When WebGL is unavailable, or rendering fails
 * or times out, the caller falls back to an inline SVG of the route geometry (RouteSvg).
 *
 * maplibre-gl and the basemap module are imported lazily, so tests (jsdom) never load them.
 */
import type { FeatureCollection } from 'geojson';
import { COLORS } from '../shared/VerdictIcon';

export interface StaticMapSpec {
  key: string;
  regionId: string;
  widthPx: number;
  heightPx: number;
  pixelRatio?: number;
  /** [w, s, e, n]; a degenerate box (single point) is shown at `pointZoom` */
  bounds: [number, number, number, number];
  checked: [number, number][][];
  travelOnly: [number, number][][];
  origin: [number, number] | null;
  shelters: [number, number][];
  pointZoom?: number;
  timeoutMs?: number;
}

let webglCache: boolean | null = null;

/** Whether WebGL can be used (probed once; the probe context is released immediately). */
export function webglAvailable(): boolean {
  if (webglCache !== null) return webglCache;
  if (typeof document === 'undefined') return false;
  try {
    // jsdom has no canvas implementation: getContext is a stub that returns null (and may log).
    if (typeof navigator !== 'undefined' && /jsdom/i.test(navigator.userAgent)) return (webglCache = false);
    const c = document.createElement('canvas');
    const gl = (c.getContext('webgl2') || c.getContext('webgl')) as WebGLRenderingContext | null;
    webglCache = Boolean(gl);
    gl?.getExtension('WEBGL_lose_context')?.loseContext();
  } catch {
    webglCache = false;
  }
  return webglCache;
}

/** Frees a canvas' WebGL context right away (browsers cap live contexts at ~16). */
function loseContext(canvas: HTMLCanvasElement | null): void {
  if (!canvas) return;
  try {
    const gl = (canvas.getContext('webgl2') || canvas.getContext('webgl')) as WebGLRenderingContext | null;
    gl?.getExtension('WEBGL_lose_context')?.loseContext();
  } catch {
    /* ignore */
  }
}

export function overlayCollection(spec: Pick<StaticMapSpec, 'checked' | 'travelOnly' | 'origin' | 'shelters'>): FeatureCollection {
  const features: FeatureCollection['features'] = [];
  for (const coords of spec.travelOnly) {
    features.push({ type: 'Feature', properties: { kind: 'travel_only' }, geometry: { type: 'LineString', coordinates: coords } });
  }
  for (const coords of spec.checked) {
    features.push({ type: 'Feature', properties: { kind: 'checked' }, geometry: { type: 'LineString', coordinates: coords } });
  }
  for (const s of spec.shelters) features.push({ type: 'Feature', properties: { kind: 'shelter' }, geometry: { type: 'Point', coordinates: s } });
  if (spec.origin) features.push({ type: 'Feature', properties: { kind: 'origin' }, geometry: { type: 'Point', coordinates: spec.origin } });
  return { type: 'FeatureCollection', features };
}

const SRC = 'wfgf-sheet-overlay';

function overlayLayers(): any[] {
  return [
    {
      id: 'wfgf-travel-only',
      type: 'line',
      source: SRC,
      filter: ['==', ['get', 'kind'], 'travel_only'],
      layout: { 'line-join': 'round', 'line-cap': 'butt' },
      paint: { 'line-color': COLORS.ink, 'line-width': 2, 'line-opacity': 0.6, 'line-dasharray': [2.2, 1.6] },
    },
    {
      id: 'wfgf-checked-casing',
      type: 'line',
      source: SRC,
      filter: ['==', ['get', 'kind'], 'checked'],
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': '#FFFFFF', 'line-width': 7.5 },
    },
    {
      id: 'wfgf-checked',
      type: 'line',
      source: SRC,
      filter: ['==', ['get', 'kind'], 'checked'],
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': COLORS.accent, 'line-width': 4 },
    },
    {
      id: 'wfgf-shelter',
      type: 'circle',
      source: SRC,
      filter: ['==', ['get', 'kind'], 'shelter'],
      paint: { 'circle-radius': 7, 'circle-color': '#FFFFFF', 'circle-stroke-color': COLORS.accent, 'circle-stroke-width': 3.2 },
    },
    {
      id: 'wfgf-shelter-dot',
      type: 'circle',
      source: SRC,
      filter: ['==', ['get', 'kind'], 'shelter'],
      paint: { 'circle-radius': 2.4, 'circle-color': COLORS.accentHover },
    },
    {
      id: 'wfgf-origin',
      type: 'circle',
      source: SRC,
      filter: ['==', ['get', 'kind'], 'origin'],
      paint: { 'circle-radius': 6.5, 'circle-color': COLORS.ink, 'circle-stroke-color': '#FFFFFF', 'circle-stroke-width': 2.5 },
    },
  ];
}

const regionHasBasemap = new Map<string, Promise<boolean>>();

/** One off-screen map reused for consecutive renders of a region (style, sprites, glyphs and tiles
 *  load once); released after a short idle period so it never holds a WebGL context for long. */
interface Renderer {
  regionId: string;
  pixelRatio: number;
  map: any;
  container: HTMLDivElement;
}

let renderer: Renderer | null = null;
let releaseTimer: ReturnType<typeof setTimeout> | null = null;
const RELEASE_AFTER_MS = 8000;

function releaseRenderer(): void {
  if (releaseTimer) clearTimeout(releaseTimer);
  releaseTimer = null;
  const r = renderer;
  renderer = null;
  if (!r) return;
  const canvas: HTMLCanvasElement | null = r.map ? r.map.getCanvas() : null;
  try {
    r.map?.remove();
  } catch {
    /* already gone */
  }
  loseContext(canvas);
  r.container.remove();
}

function waitIdle(map: any, timeoutMs: number): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const onError = (ev: any) => {
      // tile/glyph errors still end in 'idle'; only a lost WebGL context is fatal
      if (String(ev?.error?.message ?? '').includes('WebGL')) {
        cleanup();
        reject(ev.error);
      }
    };
    const onIdle = () => {
      cleanup();
      resolve();
    };
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error('static map timed out'));
    }, timeoutMs);
    function cleanup() {
      clearTimeout(timer);
      map.off('idle', onIdle);
      map.off('error', onError);
    }
    map.on('idle', onIdle);
    map.on('error', onError);
    map.triggerRepaint();
  });
}

function camera(spec: StaticMapSpec): { center?: [number, number]; zoom?: number; bounds?: [[number, number], [number, number]] } {
  const [w, s, e, n] = spec.bounds;
  if (Math.abs(e - w) < 1e-6 && Math.abs(n - s) < 1e-6) return { center: [w, s], zoom: spec.pointZoom ?? 13 };
  return { bounds: [[w, s], [e, n]] };
}

const FIT_PADDING = { top: 34, bottom: 34, left: 40, right: 40 };

async function getRenderer(spec: StaticMapSpec): Promise<Renderer> {
  const pixelRatio = spec.pixelRatio ?? 2;
  if (renderer && renderer.regionId === spec.regionId && renderer.pixelRatio === pixelRatio) return renderer;
  releaseRenderer();
  const [mlMod, bm] = await Promise.all([import('maplibre-gl'), import('../../map/basemapStyle')]);
  const maplibregl: any = (mlMod as any).default ?? mlMod;
  bm.ensurePmtilesProtocol();
  let has = regionHasBasemap.get(spec.regionId);
  if (!has) {
    has = bm.hasRegionBasemap(spec.regionId);
    regionHasBasemap.set(spec.regionId, has);
  }
  const base: any = (await has) ? bm.basemapStyle(spec.regionId, { flavor: 'grayscale' }) : bm.paperStyle();
  const style = {
    ...base,
    sources: { ...base.sources, [SRC]: { type: 'geojson', data: overlayCollection(spec) } },
    layers: [...base.layers, ...overlayLayers()],
  };
  const container = document.createElement('div');
  container.setAttribute('aria-hidden', 'true');
  container.style.cssText = `position:fixed;left:-30000px;top:0;width:${spec.widthPx}px;height:${spec.heightPx}px;pointer-events:none;`;
  document.body.appendChild(container);
  const cam = camera(spec);
  const map = new maplibregl.Map({
    container,
    style,
    interactive: false,
    attributionControl: false,
    fadeDuration: 0,
    pixelRatio,
    canvasContextAttributes: { preserveDrawingBuffer: true, antialias: true },
    localIdeographFontFamily: bm.LOCAL_IDEOGRAPH_FONT,
    ...(cam.bounds ? { bounds: cam.bounds, fitBoundsOptions: { padding: FIT_PADDING, maxZoom: 15.5 } } : { center: cam.center, zoom: cam.zoom }),
  });
  renderer = { regionId: spec.regionId, pixelRatio, map, container };
  return renderer;
}

async function renderOne(spec: StaticMapSpec): Promise<string> {
  if (releaseTimer) clearTimeout(releaseTimer);
  releaseTimer = null;
  const fresh = !renderer || renderer.regionId !== spec.regionId || renderer.pixelRatio !== (spec.pixelRatio ?? 2);
  const r = await getRenderer(spec);
  try {
    if (!fresh) {
      r.container.style.width = `${spec.widthPx}px`;
      r.container.style.height = `${spec.heightPx}px`;
      r.map.resize();
      r.map.getSource(SRC)?.setData(overlayCollection(spec));
      const cam = camera(spec);
      if (cam.bounds) r.map.fitBounds(cam.bounds, { padding: FIT_PADDING, maxZoom: 15.5, animate: false, duration: 0 });
      else r.map.jumpTo({ center: cam.center, zoom: cam.zoom });
    }
    await waitIdle(r.map, spec.timeoutMs ?? 25000);
    const canvas: HTMLCanvasElement = r.map.getCanvas();
    // JPEG keeps a 90-page PDF small; at 2× pixel ratio and q 0.9 lines and labels stay crisp in print
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob((b) => resolve(b), 'image/jpeg', 0.9));
    if (blob && typeof URL.createObjectURL === 'function') return URL.createObjectURL(blob);
    return canvas.toDataURL('image/jpeg', 0.9);
  } catch (e) {
    releaseRenderer();
    throw e;
  } finally {
    if (renderer) releaseTimer = setTimeout(releaseRenderer, RELEASE_AFTER_MS);
  }
}

let chain: Promise<unknown> = Promise.resolve();
const cache = new Map<string, Promise<string>>();

/** Renders (or returns the cached) image URL of a static map; maps render one at a time. */
export function renderStaticMap(spec: StaticMapSpec): Promise<string> {
  const hit = cache.get(spec.key);
  if (hit) return hit;
  const p = chain.then(() => renderOne(spec));
  chain = p.catch(() => undefined);
  cache.set(spec.key, p);
  p.catch(() => cache.delete(spec.key));
  return p;
}

/** Already rendered (synchronously known) image for a key, used to avoid a loading flash. */
export function cachedStaticMap(key: string): Promise<string> | undefined {
  return cache.get(key);
}

/* ---------- SVG fallback geometry ---------- */

export interface SvgProjection {
  width: number;
  height: number;
  project: (lon: number, lat: number) => [number, number];
  metresPerPx: number;
}

/** Equirectangular projection (cos φ scaled) of a lon/lat box into width×height with padding. */
export function fitProjection(
  bounds: [number, number, number, number],
  width: number,
  height: number,
  pad = 24,
  minSpanM = 1500,
): SvgProjection {
  let [w, s, e, n] = bounds;
  const lat0 = ((s + n) / 2) * (Math.PI / 180);
  const kx = Math.cos(lat0);
  const mPerDegLat = 111320;
  // ensure a minimum span so a single point or a very short route is not over-zoomed
  const spanXm = (e - w) * kx * mPerDegLat;
  const spanYm = (n - s) * mPerDegLat;
  if (spanXm < minSpanM) {
    const d = (minSpanM - spanXm) / 2 / (kx * mPerDegLat);
    w -= d;
    e += d;
  }
  if (spanYm < minSpanM * (height / width)) {
    const d = (minSpanM * (height / width) - spanYm) / 2 / mPerDegLat;
    s -= d;
    n += d;
  }
  const dx = (e - w) * kx;
  const dy = n - s;
  const scale = Math.min((width - 2 * pad) / dx, (height - 2 * pad) / dy);
  const ox = (width - dx * scale) / 2;
  const oy = (height - dy * scale) / 2;
  return {
    width,
    height,
    project: (lon, lat) => [ox + (lon - w) * kx * scale, oy + (n - lat) * scale],
    metresPerPx: mPerDegLat / scale,
  };
}

/** A "nice" scale-bar length (m) close to `targetPx` pixels. */
export function niceScale(metresPerPx: number, targetPx: number): { metres: number; px: number; label: string } {
  const target = metresPerPx * targetPx;
  const steps = [50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000, 20000, 25000, 50000];
  let best = steps[0]!;
  for (const st of steps) if (Math.abs(st - target) < Math.abs(best - target)) best = st;
  return { metres: best, px: best / metresPerPx, label: best >= 1000 ? `${best / 1000} km` : `${best} m` };
}
