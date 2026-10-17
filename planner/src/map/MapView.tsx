/**
 * Centre map: offline basemap (local PMTiles, grayscale, Korean labels), forecast cells
 * (monochrome ink by p_new_burn_1h — never green), origins, shelters, the selected checked route
 * (solid green with white casing), the travel-time-only comparison (ink dashed) and a vehicle
 * marker that follows the route's per-vertex times as the scenario clock moves.
 */
import { hoverEdgeClass } from './hoverEdge';
import { useEffect, useMemo, useRef, useState } from 'react';
import maplibregl, { type GeoJSONSource, type Map as MLMap, type MapLayerMouseEvent } from 'maplibre-gl';
import type { Feature, FeatureCollection, LineString, Point } from 'geojson';
import { CONFIG } from '../config/env';
import { positionAt } from '../domain/plan';
import type { Place, RouteDetail } from '../domain/types';
import { translate, useLang, useLangStore, useT } from '../i18n';
import { selectOrigin } from '../state/controller';
import { travelOnlyDetail, useRegionEntry, useRoute, useScenarioPlaces, useShownAttempt } from '../state/selectors';
import { DRAWN_SCENARIO, getState, setState, useStore } from '../state/store';
import { categoryLabel, errorText, placeName, sourceTag } from '../components/format';
import { ChevronIcon, OriginGlyph } from '../components/Icons';
import { BASEMAP_ATTRIBUTION, LOCAL_IDEOGRAPH_FONT, basemapStyle, ensurePmtilesProtocol, hasRegionBasemap, paperStyle, vworldRasterSource } from './basemapStyle';
import { ZONE_KEYS, zoneBounds } from '../domain/zones';
import { ZoneEditor } from './zoneEditor';
import { DrawCrosshair, ZoneToolbar } from './ZoneToolbar';

const INK = '#0B0B0C';
const GREEN = '#1A9E55';
const GREY = '#9A9AA0';
const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] };

/** Forecast classes (discrete, no gradient): upper bounds and ink opacity. */
export const FORECAST_CLASSES: { label: string; min: number; opacity: number }[] = [
  { label: '< 1%', min: 0, opacity: 0.1 },
  { label: '1–2%', min: 0.01, opacity: 0.18 },
  { label: '2–5%', min: 0.02, opacity: 0.28 },
  { label: '5–10%', min: 0.05, opacity: 0.4 },
  { label: '≥ 10%', min: 0.1, opacity: 0.55 },
];

function canvasImage(size: number, draw: (ctx: CanvasRenderingContext2D, s: number) => void): ImageData {
  const c = document.createElement('canvas');
  c.width = size;
  c.height = size;
  const ctx = c.getContext('2d')!;
  draw(ctx, size);
  return ctx.getImageData(0, 0, size, size);
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function addImages(map: MLMap) {
  const px = 2; // pixelRatio
  if (!map.hasImage('wfg-facility'))
    map.addImage(
      'wfg-facility',
      canvasImage(13 * px, (ctx, s) => {
        roundRect(ctx, 1.6 * px, 1.6 * px, s - 3.2 * px, s - 3.2 * px, 3 * px);
        ctx.fillStyle = '#fff';
        ctx.fill();
        ctx.lineWidth = 1.8 * px;
        ctx.strokeStyle = INK;
        ctx.stroke();
      }),
      { pixelRatio: px },
    );
  // shelters: white disc, ink ring and ink "+" — never the checked-route green (green = checked route only)
  if (!map.hasImage('wfg-shelter'))
    map.addImage(
      'wfg-shelter',
      canvasImage(14 * px, (ctx, s) => {
        ctx.beginPath();
        ctx.arc(s / 2, s / 2, s / 2 - 1.4 * px, 0, Math.PI * 2);
        ctx.fillStyle = '#fff';
        ctx.fill();
        ctx.lineWidth = 1.8 * px;
        ctx.strokeStyle = INK;
        ctx.stroke();
        const arm = s * 0.22;
        ctx.beginPath();
        ctx.moveTo(s / 2 - arm, s / 2);
        ctx.lineTo(s / 2 + arm, s / 2);
        ctx.moveTo(s / 2, s / 2 - arm);
        ctx.lineTo(s / 2, s / 2 + arm);
        ctx.lineWidth = 1.6 * px;
        ctx.lineCap = 'round';
        ctx.stroke();
      }),
      { pixelRatio: px },
    );
  if (!map.hasImage('wfg-research'))
    map.addImage(
      'wfg-research',
      canvasImage(14 * px, (ctx, s) => {
        ctx.beginPath();
        ctx.moveTo(s / 2, 1.5 * px);
        ctx.lineTo(s - 1.5 * px, s / 2);
        ctx.lineTo(s / 2, s - 1.5 * px);
        ctx.lineTo(1.5 * px, s / 2);
        ctx.closePath();
        ctx.fillStyle = '#fff';
        ctx.fill();
        ctx.lineWidth = 1.8 * px;
        ctx.strokeStyle = INK;
        ctx.stroke();
      }),
      { pixelRatio: px },
    );
  if (!map.hasImage('wfg-nc'))
    map.addImage(
      'wfg-nc',
      canvasImage(12 * px, (ctx, s) => {
        ctx.beginPath();
        ctx.arc(s / 2, s / 2, s / 2 - 1.5 * px, 0, Math.PI * 2);
        ctx.setLineDash([2 * px, 1.6 * px]);
        ctx.lineWidth = 1.5 * px;
        ctx.strokeStyle = GREY;
        ctx.stroke();
      }),
      { pixelRatio: px },
    );
  if (!map.hasImage('wfg-hatch'))
    map.addImage(
      'wfg-hatch',
      canvasImage(8 * px, (ctx, s) => {
        ctx.strokeStyle = INK;
        ctx.lineWidth = 0.9 * px;
        for (let k = -s; k <= s; k += 4 * px) {
          ctx.beginPath();
          ctx.moveTo(k, s);
          ctx.lineTo(k + s, 0);
          ctx.stroke();
        }
      }),
      { pixelRatio: px },
    );
}

function opacityExpr(): maplibregl.ExpressionSpecification {
  const steps: (number | maplibregl.ExpressionSpecification)[] = [];
  for (const c of FORECAST_CLASSES.slice(1)) steps.push(c.min, c.opacity);
  return ['case', ['<=', ['coalesce', ['get', 'p'], 0], 0], 0, ['step', ['coalesce', ['get', 'p'], 0], FORECAST_CLASSES[0]!.opacity, ...steps]] as unknown as maplibregl.ExpressionSpecification;
}

function addOverlays(map: MLMap) {
  addImages(map);
  const src = (id: string) => {
    if (!map.getSource(id)) map.addSource(id, { type: 'geojson', data: EMPTY });
  };
  ['wfg-forecast', 'wfg-travel', 'wfg-route', 'wfg-shelters', 'wfg-origins', 'wfg-selection', 'wfg-vehicle'].forEach(src);
  const add = (layer: maplibregl.LayerSpecification) => {
    if (!map.getLayer(layer.id)) map.addLayer(layer);
  };
  add({ id: 'wfg-forecast-fill', type: 'fill', source: 'wfg-forecast', filter: ['!', ['get', 'burning']], paint: { 'fill-color': INK, 'fill-opacity': opacityExpr() } });
  add({ id: 'wfg-burning-fill', type: 'fill', source: 'wfg-forecast', filter: ['get', 'burning'], paint: { 'fill-pattern': 'wfg-hatch', 'fill-opacity': 0.55 } });
  add({ id: 'wfg-burning-line', type: 'line', source: 'wfg-forecast', filter: ['get', 'burning'], paint: { 'line-color': INK, 'line-width': 0.8, 'line-opacity': 0.7 } });
  add({ id: 'wfg-travel-line', type: 'line', source: 'wfg-travel', layout: { 'line-cap': 'butt', 'line-join': 'round' }, paint: { 'line-color': INK, 'line-width': 2.5, 'line-dasharray': [2, 1.6] } });
  add({ id: 'wfg-route-casing', type: 'line', source: 'wfg-route', layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': '#FFFFFF', 'line-width': 8 } });
  add({ id: 'wfg-route-line', type: 'line', source: 'wfg-route', layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': GREEN, 'line-width': 4.5 } });
  add({ id: 'wfg-shelters-nc', type: 'symbol', source: 'wfg-shelters', filter: ['!', ['get', 'checkable']], layout: { 'icon-image': 'wfg-nc', 'icon-size': 0.8, 'icon-allow-overlap': true } });
  add({
    id: 'wfg-shelters',
    type: 'symbol',
    source: 'wfg-shelters',
    filter: ['get', 'checkable'],
    layout: { 'icon-image': 'wfg-shelter', 'icon-size': ['interpolate', ['linear'], ['zoom'], 9, 0.6, 13, 0.9], 'icon-allow-overlap': true },
  });
  add({
    id: 'wfg-origins-village',
    type: 'circle',
    source: 'wfg-origins',
    filter: ['==', ['get', 'kind'], 'village'],
    paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 9, 3.8, 13, 6], 'circle-color': '#FFFFFF', 'circle-stroke-color': INK, 'circle-stroke-width': 1.8 },
  });
  add({ id: 'wfg-origins-nc', type: 'symbol', source: 'wfg-origins', filter: ['==', ['get', 'kind'], 'nc'], layout: { 'icon-image': 'wfg-nc', 'icon-allow-overlap': true } });
  add({ id: 'wfg-origins-facility', type: 'symbol', source: 'wfg-origins', filter: ['==', ['get', 'kind'], 'facility'], layout: { 'icon-image': 'wfg-facility', 'icon-allow-overlap': true } });
  add({ id: 'wfg-origins-research', type: 'symbol', source: 'wfg-origins', filter: ['==', ['get', 'kind'], 'research'], layout: { 'icon-image': 'wfg-research', 'icon-allow-overlap': true } });
  add({
    id: 'wfg-selection',
    type: 'circle',
    source: 'wfg-selection',
    paint: {
      'circle-radius': ['case', ['==', ['get', 'role'], 'hover'], 10, 12],
      'circle-color': 'rgba(0,0,0,0)',
      'circle-stroke-color': ['case', ['==', ['get', 'role'], 'shelter'], GREEN, INK],
      'circle-stroke-width': ['case', ['==', ['get', 'role'], 'hover'], 1.5, 2.5],
    },
  });
  add({ id: 'wfg-vehicle', type: 'circle', source: 'wfg-vehicle', paint: { 'circle-radius': 6.5, 'circle-color': INK, 'circle-stroke-color': '#FFFFFF', 'circle-stroke-width': 2.5 } });
}

const ORIGIN_LAYERS = ['wfg-origins-village', 'wfg-origins-nc', 'wfg-origins-facility', 'wfg-origins-research'];
/** hover only (name, category, source tag); a shelter click never selects anything */
const SHELTER_LAYERS = ['wfg-shelters', 'wfg-shelters-nc'];

function setData(map: MLMap | null, id: string, data: FeatureCollection) {
  const s = map?.getSource(id) as GeoJSONSource | undefined;
  s?.setData(data);
}

function originKind(p: Place): string {
  if (!p.checkable) return 'nc';
  if (p.role === 'research_origin') return 'research';
  return p.vulnerable ? 'facility' : 'village';
}

function lineFC(r: RouteDetail | null): FeatureCollection {
  if (!r?.coordinates || r.coordinates.length < 2) return EMPTY;
  const f: Feature<LineString> = { type: 'Feature', geometry: { type: 'LineString', coordinates: r.coordinates }, properties: {} };
  return { type: 'FeatureCollection', features: [f] };
}

function Legend() {
  const t = useT();
  const drawn = useStore((s) => s.scenarioId === DRAWN_SCENARIO);
  const forecastOn = useStore((s) => s.showForecast && s.forecast.state === 'ready' && s.scenarioId !== DRAWN_SCENARIO);
  // collapsed by default so it does not hide villages in the top-left corner; one click opens it
  const [open, setOpen] = useState(false);
  if (!open) {
    return (
      <div className="map-overlay map-legend collapsed" data-testid="map-legend">
        <button type="button" className="lg-toggle" aria-expanded={false} onClick={() => setOpen(true)}>
          {t('map.legend.title')}
          <ChevronIcon dir="down" size={12} />
        </button>
      </div>
    );
  }
  return (
    <div className="map-overlay map-legend" data-testid="map-legend">
      <button type="button" className="lg-toggle" aria-expanded={true} onClick={() => setOpen(false)}>
        {t('map.legend.title')}
        <ChevronIcon dir="up" size={12} />
      </button>
      {forecastOn ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span className="small-note" style={{ color: 'var(--ink)' }}>{t('map.legend.forecast')}</span>
          <div className="lg-swatches">
            {FORECAST_CLASSES.map((c) => (
              <span key={c.label} title={c.label} style={{ background: `rgba(11,11,12,${c.opacity})` }} />
            ))}
          </div>
          <div className="lg-scale" style={{ width: 'auto', justifyContent: 'flex-start', gap: 2 }}>
            {FORECAST_CLASSES.map((c) => (
              <span key={c.label} style={{ width: 24, textAlign: 'center', fontSize: 9 }}>
                {c.label.replace('%', '')}
              </span>
            ))}
            <span style={{ fontSize: 9, marginLeft: 2 }}>%</span>
          </div>
          <span className="lg-row">
            <span className="lg-burn" />
            {t('map.legend.burning')}
          </span>
        </div>
      ) : null}
      {drawn ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }} data-testid="legend-zones">
          <span className="lg-row">
            <span className="zone-swatch z5" />
            {t('map.legend.zone5')}
          </span>
          <span className="lg-row">
            <span className="zone-swatch z8" />
            {t('map.legend.zone8')}
          </span>
        </div>
      ) : null}
      <div className="lg-grid">
        <span className="lg-row">
          <OriginGlyph kind="village" />
          {t('map.legend.village')}
        </span>
        <span className="lg-row">
          <OriginGlyph kind="facility" />
          {t('map.legend.facility')}
        </span>
        <span className="lg-row">
          <OriginGlyph kind="research" />
          {t('map.legend.research')}
        </span>
        <span className="lg-row">
          <OriginGlyph kind="not_checkable" />
          {t('map.legend.notCheckable')}
        </span>
        <span className="lg-row">
          <OriginGlyph kind="shelter" />
          {t('map.legend.shelter')}
        </span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <span className="lg-row">
          <span className="lg-line" />
          {t('map.legend.route')}
        </span>
        <span className="lg-row">
          <span className="lg-line dashed" />
          {t('map.legend.travel')}
        </span>
      </div>
    </div>
  );
}

export function MapView() {
  const t = useT();
  const lang = useLang();
  const container = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MLMap | null>(null);
  const editorRef = useRef<ZoneEditor | null>(null);
  const [mapObj, setMapObj] = useState<MLMap | null>(null);
  const [styleKey, setStyleKey] = useState(0);
  const [noBasemap, setNoBasemap] = useState(false);
  const [hover, setHover] = useState<{ x: number; y: number; id: string } | null>(null);

  const region = useRegionEntry();
  const regionId = region?.id ?? null;
  const { origins, destinations, byId } = useScenarioPlaces();
  const scenarioId = useStore((s) => s.scenarioId);
  const forecast = useStore((s) => s.forecast);
  const showForecast = useStore((s) => s.showForecast);
  const showVworld = useStore((s) => s.showVworld);
  const selectedId = useStore((s) => s.selectedOriginId);
  const hoverOriginId = useStore((s) => s.hoverOriginId);
  const clockS = useStore((s) => s.clockS);
  // the comparison of the origin's CURRENT best checked attempt only (never another run's)
  const travelDetail = useStore((s) => travelOnlyDetail(s, selectedId));
  const travelFor = useStore((s) => (selectedId ? s.travelOnly[selectedId]?.forJobId ?? null : null));
  const recomputeRunning = useStore((s) => s.recompute?.state === 'running' && s.recompute.originId === selectedId);
  const { attempt } = useShownAttempt();
  const route = useRoute(attempt?.jobId);
  // the dashed line is drawn only together with the green route it was computed for
  const travel =
    route?.verdict === 'checked_route' && attempt?.jobId && travelFor === attempt.jobId && travelDetail?.coordinates && !recomputeRunning ? travelDetail : null;

  // create the map once
  useEffect(() => {
    if (!container.current) return;
    ensurePmtilesProtocol();
    const map = new maplibregl.Map({
      container: container.current,
      style: paperStyle(),
      center: [128.7, 36.44],
      zoom: 10,
      attributionControl: false,
      localIdeographFontFamily: LOCAL_IDEOGRAPH_FONT,
      dragRotate: false,
      pitchWithRotate: false,
      maxPitch: 0,
    });
    map.touchZoomRotate.disableRotation();
    map.addControl(new maplibregl.AttributionControl({ compact: false, customAttribution: BASEMAP_ATTRIBUTION }), 'bottom-right');
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: 'metric' }), 'bottom-left');
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');
    const editor = new ZoneEditor(map, { label: (key) => translate(useLangStore.getState().lang, `zones.label.${key}`) });
    editorRef.current = editor;
    map.on('style.load', () => {
      addOverlays(map);
      editor.install('wfg-travel-line');
      setStyleKey((k) => k + 1);
    });
    const onClick = (e: MapLayerMouseEvent) => {
      if (editor.capturesClicks()) return; // drawing or handling a zone handle
      const id = e.features?.[0]?.properties?.id;
      if (typeof id === 'string') selectOrigin(id);
    };
    // one map-level hover for origins and shelters; origins win where they overlap (they are drawn on top)
    const onMove = (e: maplibregl.MapMouseEvent) => {
      if (getState().drawn.edit.drawing && getState().scenarioId === DRAWN_SCENARIO) {
        setHover(null); // no place tooltips while drawing a zone
        return;
      }
      const layers = [...ORIGIN_LAYERS, ...SHELTER_LAYERS].filter((l) => map.getLayer(l));
      if (!layers.length) return;
      const feats = map.queryRenderedFeatures(e.point, { layers });
      const hit = feats.find((f) => ORIGIN_LAYERS.includes(f.layer.id)) ?? feats.find((f) => SHELTER_LAYERS.includes(f.layer.id));
      const id = hit?.properties?.id;
      if (typeof id === 'string') {
        map.getCanvas().style.cursor = ORIGIN_LAYERS.includes(hit!.layer.id) ? 'pointer' : 'default';
        setHover({ x: e.point.x, y: e.point.y, id });
      } else {
        map.getCanvas().style.cursor = '';
        setHover(null);
      }
    };
    const onLeave = () => {
      map.getCanvas().style.cursor = '';
      setHover(null);
    };
    for (const l of ORIGIN_LAYERS) map.on('click', l, onClick);
    map.on('mousemove', onMove);
    map.on('mouseout', onLeave);
    mapRef.current = map;
    setMapObj(map);
    (window as unknown as { __wfgMap?: MLMap }).__wfgMap = map;
    return () => {
      editor.destroy();
      editorRef.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // zone labels follow the UI language
  useEffect(() => {
    editorRef.current?.relabel();
  }, [lang]);

  // frame the zones when a recorded-footprint preset is copied in
  const presetAt = useStore((s) => (s.drawn.notice?.key === 'zones.notice.preset' ? s.drawn.notice.at : null));
  useEffect(() => {
    const map = mapRef.current;
    if (!map || presetAt === null) return;
    const zones = getState().drawn.zones;
    const bs = ZONE_KEYS.map((k) => zoneBounds(zones[k])).filter((b): b is [number, number, number, number] => b !== null);
    if (!bs.length) return;
    const [w, s, e, n] = [Math.min(...bs.map((b) => b[0])), Math.min(...bs.map((b) => b[1])), Math.max(...bs.map((b) => b[2])), Math.max(...bs.map((b) => b[3]))];
    // frame every zone whole (the region window is drawn separately); keep them clear of the
    // legend (top-left) and the zone toolbar (top-right, 292 px)
    const el = map.getContainer();
    const wide = el.clientWidth > 900;
    map.fitBounds(
      [
        [w, s],
        [e, n],
      ],
      { padding: wide ? { top: 48, bottom: 40, left: 240, right: 320 } : { top: 56, bottom: 40, left: 48, right: 48 }, duration: 600, maxZoom: 13 },
    );
  }, [presetAt]);

  // basemap per region (local PMTiles only; paper fallback + notice when missing)
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !regionId) return;
    let cancelled = false;
    const ctrl = new AbortController();
    void hasRegionBasemap(regionId, ctrl.signal).then((ok) => {
      if (cancelled) return;
      setNoBasemap(!ok);
      map.setStyle(ok ? basemapStyle(regionId, { flavor: 'grayscale' }) : paperStyle(), { diff: false });
    });
    if (region?.bbox) {
      const [w, s, e, n] = region.bbox;
      map.fitBounds([[w, s], [e, n]], { padding: 40, duration: 0 });
    }
    return () => {
      cancelled = true;
      ctrl.abort();
    };
  }, [regionId, region?.bbox]);

  // optional VWorld raster (explicit opt-in; internet service)
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleKey) return;
    const key = CONFIG.vworldKey;
    if (showVworld && key) {
      if (!map.getSource('vworld')) map.addSource('vworld', vworldRasterSource(key));
      if (!map.getLayer('vworld')) map.addLayer({ id: 'vworld', type: 'raster', source: 'vworld', paint: { 'raster-saturation': -1 } }, 'wfg-forecast-fill');
    } else if (map.getLayer('vworld')) {
      map.removeLayer('vworld');
      map.removeSource('vworld');
    }
  }, [showVworld, styleKey]);

  // forecast cells
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleKey) return;
    const on = showForecast && forecast.state === 'ready' && forecast.data && scenarioId !== DRAWN_SCENARIO;
    setData(map, 'wfg-forecast', on ? (forecast.data!.cells as FeatureCollection) : EMPTY);
  }, [forecast, showForecast, styleKey, scenarioId]);

  // origins + shelters
  const originFC = useMemo<FeatureCollection<Point>>(
    () => ({
      type: 'FeatureCollection',
      features: (scenarioId === DRAWN_SCENARIO ? origins.filter((p) => p.role === 'origin') : origins).map((p) => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
        properties: { id: p.id, kind: originKind(p) },
      })),
    }),
    [origins, scenarioId],
  );
  const shelterFC = useMemo<FeatureCollection<Point>>(
    () => ({
      type: 'FeatureCollection',
      features: destinations.map((p) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [p.lon, p.lat] }, properties: { id: p.id, checkable: p.checkable } })),
    }),
    [destinations],
  );
  useEffect(() => {
    if (!styleKey) return;
    setData(mapRef.current, 'wfg-origins', originFC);
    setData(mapRef.current, 'wfg-shelters', shelterFC);
  }, [originFC, shelterFC, styleKey]);

  // selection rings
  useEffect(() => {
    if (!styleKey) return;
    const feats: Feature<Point>[] = [];
    const sel = selectedId ? byId.get(selectedId) : null;
    if (sel) feats.push({ type: 'Feature', geometry: { type: 'Point', coordinates: [sel.lon, sel.lat] }, properties: { role: 'origin' } });
    const dest = attempt ? byId.get(attempt.destinationId) : null;
    if (dest) feats.push({ type: 'Feature', geometry: { type: 'Point', coordinates: [dest.lon, dest.lat] }, properties: { role: 'shelter' } });
    const hov = hoverOriginId && hoverOriginId !== selectedId ? byId.get(hoverOriginId) : null;
    if (hov) feats.push({ type: 'Feature', geometry: { type: 'Point', coordinates: [hov.lon, hov.lat] }, properties: { role: 'hover' } });
    setData(mapRef.current, 'wfg-selection', { type: 'FeatureCollection', features: feats });
  }, [selectedId, attempt, hoverOriginId, byId, styleKey]);

  // routes
  useEffect(() => {
    if (!styleKey) return;
    setData(mapRef.current, 'wfg-route', route?.verdict === 'checked_route' ? lineFC(route) : EMPTY);
  }, [route, styleKey]);
  useEffect(() => {
    if (!styleKey) return;
    setData(mapRef.current, 'wfg-travel', travel && travel.coordinates ? lineFC(travel) : EMPTY);
  }, [travel, route, attempt, recomputeRunning, styleKey]);

  // frame the selection when its route arrives
  const framed = useRef<string | null>(null);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedId) return;
    const sel = byId.get(selectedId);
    if (!sel) return;
    const key = `${selectedId}|${route?.jobId ?? ''}`;
    if (framed.current === key) return;
    framed.current = key;
    const pts: [number, number][] = [[sel.lon, sel.lat]];
    for (const c of route?.coordinates ?? []) pts.push(c);
    for (const c of travel?.coordinates ?? []) pts.push(c);
    if (pts.length === 1) {
      const b = map.getBounds();
      if (!b.contains([sel.lon, sel.lat])) map.easeTo({ center: [sel.lon, sel.lat], duration: 500 });
      return;
    }
    const lons = pts.map((p) => p[0]);
    const lats = pts.map((p) => p[1]);
    map.fitBounds(
      [
        [Math.min(...lons), Math.min(...lats)],
        [Math.max(...lons), Math.max(...lats)],
      ],
      { padding: { top: 60, bottom: 60, left: 270, right: 60 }, duration: 600, maxZoom: 14 },
    );
  }, [selectedId, route, travel, byId]);

  // vehicle marker along the route by per-vertex times
  useEffect(() => {
    if (!styleKey) return;
    const pos = route?.verdict === 'checked_route' && route.coordinates && route.timesS ? positionAt(route.coordinates, route.timesS, clockS) : null;
    setData(mapRef.current, 'wfg-vehicle', pos ? { type: 'FeatureCollection', features: [{ type: 'Feature', geometry: { type: 'Point', coordinates: pos }, properties: {} }] } : EMPTY);
  }, [route, clockS, styleKey]);

  const hoverPlace = hover ? byId.get(hover.id) : null;
  const forecastNotice =
    scenarioId === DRAWN_SCENARIO
      ? null
      : forecast.state === 'unavailable'
        ? t('map.forecastUnavailable')
        : forecast.state === 'error'
          ? t('map.forecastError', { code: errorText(forecast.error, t) })
          : null;

  return (
    <div className="map-wrap">
      <div ref={container} className="map" data-testid="map" />
      <Legend />
      {scenarioId === DRAWN_SCENARIO ? (
        <>
          <ZoneToolbar map={mapObj} />
          <DrawCrosshair />
        </>
      ) : (
        <div className="map-overlay map-tools">
          <button type="button" className="btn" aria-pressed={showForecast} onClick={() => setState({ showForecast: !showForecast })} disabled={forecast.state !== 'ready'}>
            {t('map.forecastToggle')}
          </button>
          {CONFIG.vworldKey ? (
            <button type="button" className="btn" aria-pressed={showVworld} onClick={() => setState({ showVworld: !showVworld })}>
              {t('map.vworldToggle')}
            </button>
          ) : null}
        </div>
      )}
      {noBasemap || forecastNotice ? (
        <div className="map-overlay map-notice" role="status">
          {[noBasemap ? t('map.noBasemap') : null, forecastNotice].filter(Boolean).join(' · ')}
        </div>
      ) : null}
      {hover && hoverPlace ? (
        <div
          className={`map-overlay map-hover${hoverEdgeClass(hover, container.current?.clientWidth ?? 0)}`}
          style={{ left: hover.x, top: hover.y }}
          data-testid="map-hover"
        >
          <span>{placeName(hoverPlace, t, lang)}</span>
          <span className="map-hover-sub">
            {categoryLabel(hoverPlace, t)} · <span className="mono">{sourceTag(hoverPlace)}</span>
          </span>
        </div>
      ) : null}
    </div>
  );
}

