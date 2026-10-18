/**
 * Small custom polygon editor for user-drawn spread zones on MapLibre GL (no extra dependency).
 *
 * Pointer: click adds a vertex while drawing; double-click, Enter or clicking the first vertex
 * closes the polygon; drag a vertex to move it; click (or drag) a midpoint handle to insert a
 * vertex; click a vertex to select it.
 * Keyboard (map focused, or anywhere outside text fields): Space adds a vertex at the map centre
 * crosshair while drawing, Enter closes, Esc cancels / deselects, Delete or Backspace removes the
 * selected vertex, [ and ] select the previous / next vertex, arrow keys move it (Shift: ×4),
 * Ctrl/⌘+Z undoes the last edit.
 *
 * Rendering is monochrome ink only (green stays reserved for checked routes): the 5 h zone is a
 * cross-hatched fill with a solid outline, the 8 h zone a sparse single hatch with a dashed outline,
 * each labelled "5시간" / "8시간". Zones are drawn only in drawn-zone mode.
 *
 * State lives in the zustand store (src/state/zoneActions.ts); this class only translates map
 * events into those actions and renders the store into MapLibre sources.
 */
import maplibregl, { type GeoJSONSource, type Map as MLMap, type MapMouseEvent, type MapTouchEvent, type PointLike } from 'maplibre-gl';
import type { Feature, FeatureCollection, LineString, Point, Polygon } from 'geojson';
import { closeRing, labelAnchor, validateZones, vertexAt, ZONE_KEYS, type DrawnZone, type LonLat, type VertexRef, type ZoneKey } from '../domain/zones';
import { regionBBox } from '../state/selectors';
import { DRAWN_SCENARIO, getState, useStore, type PlannerState } from '../state/store';
import * as za from '../state/zoneActions';

const INK = '#0B0B0C';
const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] };

export const ZONE_FILL_LAYERS = ['wfg-zone8-fill', 'wfg-zone8-line', 'wfg-zone5-fill', 'wfg-zone5-line'] as const;
const HANDLE_LAYERS = ['wfg-zone-first', 'wfg-zone-vertex', 'wfg-zone-mid'] as const;
const HIT_PX = 8;
/** Midpoint handles are drawn only up to this many vertices in the active zone. */
const MAX_MIDPOINTS = 1500;

function canvasImage(size: number, draw: (ctx: CanvasRenderingContext2D, s: number) => void): ImageData {
  const c = document.createElement('canvas');
  c.width = size;
  c.height = size;
  const ctx = c.getContext('2d')!;
  draw(ctx, size);
  return ctx.getImageData(0, 0, size, size);
}

/** Fill patterns (pixel ratio 2): 5 h = cross-hatch, 8 h = sparse single hatch. */
export function addZoneImages(map: MLMap): void {
  const px = 2;
  if (!map.hasImage('wfg-z5'))
    map.addImage(
      'wfg-z5',
      canvasImage(8 * px, (ctx, s) => {
        ctx.fillStyle = 'rgba(11,11,12,0.10)';
        ctx.fillRect(0, 0, s, s);
        ctx.strokeStyle = 'rgba(11,11,12,0.55)';
        ctx.lineWidth = 0.8 * px;
        for (const dir of [1, -1]) {
          for (let k = -s; k <= s; k += 4 * px) {
            ctx.beginPath();
            if (dir > 0) {
              ctx.moveTo(k, s);
              ctx.lineTo(k + s, 0);
            } else {
              ctx.moveTo(k, 0);
              ctx.lineTo(k + s, s);
            }
            ctx.stroke();
          }
        }
      }),
      { pixelRatio: px },
    );
  if (!map.hasImage('wfg-z8'))
    map.addImage(
      'wfg-z8',
      canvasImage(10 * px, (ctx, s) => {
        ctx.fillStyle = 'rgba(11,11,12,0.035)';
        ctx.fillRect(0, 0, s, s);
        ctx.strokeStyle = 'rgba(11,11,12,0.38)';
        ctx.lineWidth = 0.8 * px;
        for (let k = -s; k <= s; k += 5 * px) {
          ctx.beginPath();
          ctx.moveTo(k, s);
          ctx.lineTo(k + s, 0);
          ctx.stroke();
        }
      }),
      { pixelRatio: px },
    );
  if (!map.hasImage('wfg-zone-x'))
    map.addImage(
      'wfg-zone-x',
      canvasImage(18 * px, (ctx, s) => {
        ctx.beginPath();
        ctx.arc(s / 2, s / 2, s / 2 - 1.5 * px, 0, Math.PI * 2);
        ctx.fillStyle = '#fff';
        ctx.fill();
        ctx.lineWidth = 2 * px;
        ctx.strokeStyle = INK;
        ctx.stroke();
        ctx.beginPath();
        const a = s * 0.33;
        const b = s * 0.67;
        ctx.moveTo(a, a);
        ctx.lineTo(b, b);
        ctx.moveTo(b, a);
        ctx.lineTo(a, b);
        ctx.lineWidth = 2.2 * px;
        ctx.lineCap = 'round';
        ctx.stroke();
      }),
      { pixelRatio: px },
    );
}

/** Zone fills and outlines (under routes and points). */
export function addZoneLayers(map: MLMap, beforeId?: string): void {
  addZoneImages(map);
  if (!map.getSource('wfg-zones')) map.addSource('wfg-zones', { type: 'geojson', data: EMPTY });
  const add = (layer: maplibregl.LayerSpecification) => {
    if (!map.getLayer(layer.id)) map.addLayer(layer, beforeId && map.getLayer(beforeId) ? beforeId : undefined);
  };
  add({ id: 'wfg-zone8-fill', type: 'fill', source: 'wfg-zones', filter: ['==', ['get', 'zone'], 'h8'], paint: { 'fill-pattern': 'wfg-z8' } });
  add({
    id: 'wfg-zone8-line',
    type: 'line',
    source: 'wfg-zones',
    filter: ['==', ['get', 'zone'], 'h8'],
    layout: { 'line-join': 'round' },
    paint: { 'line-color': INK, 'line-width': ['case', ['get', 'active'], 2.2, 1.6], 'line-dasharray': [2.2, 1.4] },
  });
  add({ id: 'wfg-zone5-fill', type: 'fill', source: 'wfg-zones', filter: ['==', ['get', 'zone'], 'h5'], paint: { 'fill-pattern': 'wfg-z5' } });
  add({
    id: 'wfg-zone5-line',
    type: 'line',
    source: 'wfg-zones',
    filter: ['==', ['get', 'zone'], 'h5'],
    layout: { 'line-join': 'round' },
    paint: { 'line-color': INK, 'line-width': ['case', ['get', 'active'], 2.6, 2] },
  });
}

/** Draft line, problem markers and handles (on top of everything). */
export function addZoneHandleLayers(map: MLMap): void {
  addZoneImages(map);
  for (const id of ['wfg-zone-draft', 'wfg-zone-handles', 'wfg-zone-issues']) if (!map.getSource(id)) map.addSource(id, { type: 'geojson', data: EMPTY });
  const add = (layer: maplibregl.LayerSpecification) => {
    if (!map.getLayer(layer.id)) map.addLayer(layer);
  };
  add({ id: 'wfg-zone-draft-fill', type: 'fill', source: 'wfg-zone-draft', filter: ['==', ['get', 'kind'], 'preview'], paint: { 'fill-color': INK, 'fill-opacity': 0.06 } });
  add({ id: 'wfg-zone-draft-line', type: 'line', source: 'wfg-zone-draft', filter: ['==', ['get', 'kind'], 'draft'], layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': INK, 'line-width': 2.2 } });
  add({
    id: 'wfg-zone-rubber',
    type: 'line',
    source: 'wfg-zone-draft',
    filter: ['==', ['get', 'kind'], 'rubber'],
    layout: { 'line-cap': 'round' },
    paint: { 'line-color': INK, 'line-width': 1.4, 'line-dasharray': [2, 2], 'line-opacity': 0.75 },
  });
  // handles are ink-filled (villages are white-filled circles), the selected one gets a ring
  add({
    id: 'wfg-zone-mid',
    type: 'circle',
    source: 'wfg-zone-handles',
    filter: ['==', ['get', 'kind'], 'mid'],
    paint: { 'circle-radius': 3.4, 'circle-color': '#FFFFFF', 'circle-opacity': 0.95, 'circle-stroke-color': INK, 'circle-stroke-width': 1.2, 'circle-stroke-opacity': 0.75 },
  });
  add({
    id: 'wfg-zone-selring',
    type: 'circle',
    source: 'wfg-zone-handles',
    filter: ['all', ['==', ['get', 'kind'], 'vertex'], ['get', 'selected']],
    paint: { 'circle-radius': 10, 'circle-color': '#FFFFFF', 'circle-opacity': 0.55, 'circle-stroke-color': INK, 'circle-stroke-width': 2 },
  });
  add({
    id: 'wfg-zone-vertex',
    type: 'circle',
    source: 'wfg-zone-handles',
    filter: ['any', ['==', ['get', 'kind'], 'vertex'], ['==', ['get', 'kind'], 'draft']],
    paint: {
      'circle-radius': ['case', ['get', 'selected'], 5.5, 4.6],
      'circle-color': INK,
      'circle-stroke-color': '#FFFFFF',
      'circle-stroke-width': 1.6,
    },
  });
  add({
    id: 'wfg-zone-first',
    type: 'circle',
    source: 'wfg-zone-handles',
    filter: ['==', ['get', 'kind'], 'first'],
    paint: { 'circle-radius': ['case', ['get', 'closable'], 8.5, 7], 'circle-color': '#FFFFFF', 'circle-stroke-color': INK, 'circle-stroke-width': ['case', ['get', 'closable'], 3.2, 2.4] },
  });
  add({ id: 'wfg-zone-issue', type: 'symbol', source: 'wfg-zone-issues', layout: { 'icon-image': 'wfg-zone-x', 'icon-allow-overlap': true, 'icon-ignore-placement': true } });
}

type Hit =
  | { kind: 'first' }
  | { kind: 'vertex'; ref: VertexRef }
  | { kind: 'mid'; ref: VertexRef; lngLat: LonLat }
  | { kind: 'draft' };

function setData(map: MLMap, id: string, data: FeatureCollection): void {
  (map.getSource(id) as GeoJSONSource | undefined)?.setData(data);
}

export interface ZoneEditorOptions {
  /** label text of a zone ("5시간" / "8시간" or English) */
  label: (key: ZoneKey) => string;
}

export class ZoneEditor {
  private readonly map: MLMap;
  private readonly opts: ZoneEditorOptions;
  private drag: { ref: VertexRef; moved: boolean; inserted: boolean } | null = null;
  private suppressClick = false;
  private mouse: LonLat | null = null;
  private cursorSet = false;
  private labels = new Map<ZoneKey, maplibregl.Marker>();
  private unsub: (() => void) | null = null;
  private nudgeAt = 0;
  private nudgeTimer: ReturnType<typeof setTimeout> | null = null;
  private installed = false;

  constructor(map: MLMap, opts: ZoneEditorOptions) {
    this.map = map;
    this.opts = opts;
    map.on('mousedown', this.onDown);
    map.on('mousemove', this.onMove);
    map.on('mouseup', this.onUp);
    map.on('click', this.onClick);
    map.on('moveend', this.onMoveEnd);
    map.on('dblclick', this.onDbl);
    map.on('touchstart', this.onTouchStart);
    map.on('touchmove', this.onTouchMove);
    map.on('touchend', this.onTouchEnd);
    window.addEventListener('keydown', this.onKey, true);
    this.unsub = useStore.subscribe((s, prev) => {
      if (s.drawn !== prev.drawn || s.scenarioId !== prev.scenarioId || s.apiRegions !== prev.apiRegions || s.regionIndex !== prev.regionIndex) this.render();
    });
  }

  /** Call after every style load (setStyle wipes sources and layers). */
  install(beforeId?: string): void {
    addZoneLayers(this.map, beforeId);
    addZoneHandleLayers(this.map);
    this.installed = true;
    this.render();
  }

  destroy(): void {
    this.unsub?.();
    window.removeEventListener('keydown', this.onKey, true);
    window.removeEventListener('mouseup', this.onWindowUp);
    for (const m of this.labels.values()) m.remove();
    this.labels.clear();
  }

  /** True while drawing, or while a handle press is being handled (origin clicks are ignored then). */
  capturesClicks(): boolean {
    return this.enabled() && (getState().drawn.edit.drawing || this.suppressClick || this.drag !== null);
  }

  relabel(): void {
    for (const [key, m] of this.labels) m.getElement().textContent = this.opts.label(key);
  }

  private enabled(): boolean {
    return getState().scenarioId === DRAWN_SCENARIO;
  }

  // ------------------------------------------------------------------ rendering

  render(): void {
    if (!this.installed || !this.map.getSource('wfg-zones')) return;
    const s = getState();
    if (s.scenarioId !== DRAWN_SCENARIO) {
      for (const id of ['wfg-zones', 'wfg-zone-draft', 'wfg-zone-handles', 'wfg-zone-issues']) setData(this.map, id, EMPTY);
      this.updateLabels(null);
      this.setCursor(null);
      return;
    }
    const d = s.drawn;
    const zoneFeatures: Feature<Polygon>[] = [];
    for (const key of ['h8', 'h5'] as ZoneKey[]) {
      d.zones[key].polygons.forEach((poly, pi) => {
        const rings = poly.filter((r) => r.length >= 3).map((r) => closeRing(r));
        if (!rings.length) return;
        zoneFeatures.push({ type: 'Feature', geometry: { type: 'Polygon', coordinates: rings }, properties: { zone: key, poly: pi, active: key === d.edit.active } });
      });
    }
    setData(this.map, 'wfg-zones', { type: 'FeatureCollection', features: zoneFeatures });
    setData(this.map, 'wfg-zone-handles', this.handleFeatures(s));
    this.renderDraft(s);
    const issues = validateZones(d.zones, regionBBox(s));
    const pts: Feature<Point>[] = [];
    for (const i of issues) {
      if (i.code !== 'self_intersection' && i.code !== 'rings_cross') continue;
      for (const p of i.points ?? []) pts.push({ type: 'Feature', geometry: { type: 'Point', coordinates: p }, properties: { code: i.code } });
    }
    setData(this.map, 'wfg-zone-issues', { type: 'FeatureCollection', features: pts });
    this.updateLabels(s);
  }

  private handleFeatures(s: PlannerState): FeatureCollection<Point> {
    const d = s.drawn;
    const feats: Feature<Point>[] = [];
    if (d.edit.drawing) {
      d.edit.draft.forEach((p, i) => {
        feats.push({ type: 'Feature', geometry: { type: 'Point', coordinates: p }, properties: i === 0 ? { kind: 'first', closable: d.edit.draft.length >= 3 } : { kind: 'draft', selected: false } });
      });
      return { type: 'FeatureCollection', features: feats };
    }
    const zone = d.zones[d.edit.active];
    const total = zone.polygons.reduce((n, p) => n + p.reduce((m, r) => m + r.length, 0), 0);
    zone.polygons.forEach((poly, pi) =>
      poly.forEach((ring, ri) => {
        ring.forEach((p, i) => {
          const sel = d.edit.selected;
          const selected = Boolean(sel && sel.zone === zone.key && sel.poly === pi && sel.ring === ri && sel.index === i);
          feats.push({ type: 'Feature', geometry: { type: 'Point', coordinates: p }, properties: { kind: 'vertex', zone: zone.key, poly: pi, ring: ri, index: i, selected } });
          if (total <= MAX_MIDPOINTS && ring.length >= 2) {
            const q = ring[(i + 1) % ring.length]!;
            feats.push({ type: 'Feature', geometry: { type: 'Point', coordinates: [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2] }, properties: { kind: 'mid', zone: zone.key, poly: pi, ring: ri, index: i } });
          }
        });
      }),
    );
    // keep the selected vertex on top
    feats.sort((a, b) => Number(Boolean(a.properties?.selected)) - Number(Boolean(b.properties?.selected)));
    return { type: 'FeatureCollection', features: feats };
  }

  private renderDraft(s: PlannerState = getState()): void {
    const d = s.drawn;
    if (!d.edit.drawing || !this.map.getSource('wfg-zone-draft')) {
      setData(this.map, 'wfg-zone-draft', EMPTY);
      return;
    }
    const draft = d.edit.draft;
    const feats: Feature[] = [];
    if (draft.length >= 2) feats.push({ type: 'Feature', geometry: { type: 'LineString', coordinates: draft } as LineString, properties: { kind: 'draft' } });
    if (draft.length >= 1 && this.mouse) {
      const last = draft[draft.length - 1]!;
      feats.push({ type: 'Feature', geometry: { type: 'LineString', coordinates: [last, this.mouse] }, properties: { kind: 'rubber' } });
      if (draft.length >= 2) feats.push({ type: 'Feature', geometry: { type: 'LineString', coordinates: [this.mouse, draft[0]!] }, properties: { kind: 'rubber' } });
    }
    const ring = this.mouse ? [...draft, this.mouse] : draft;
    if (ring.length >= 3) feats.push({ type: 'Feature', geometry: { type: 'Polygon', coordinates: [closeRing(ring)] }, properties: { kind: 'preview' } });
    setData(this.map, 'wfg-zone-draft', { type: 'FeatureCollection', features: feats });
  }

  /**
   * Label anchor on screen: the 8 h label sits above the northernmost visible vertex of the zone's
   * outer rings, the 5 h label below the southernmost one, avoiding the map edges and the overlay
   * cards (legend, toolbar). Falls back to the geographic extreme when nothing is visible.
   */
  private labelPoint(zone: DrawnZone, side: 'north' | 'south'): LonLat | null {
    const container = this.map.getContainer();
    const box = container.getBoundingClientRect();
    const blocked = [...(container.parentElement?.querySelectorAll('.map-overlay') ?? [])].map((el) => el.getBoundingClientRect());
    const margin = 36;
    let best: { p: LonLat; y: number } | null = null;
    for (const poly of zone.polygons) {
      for (const p of poly[0] ?? []) {
        const sp = this.map.project(p);
        if (sp.x < margin || sp.y < margin || sp.x > box.width - margin || sp.y > box.height - margin) continue;
        const cx = sp.x + box.left;
        const cy = sp.y + box.top;
        if (blocked.some((r) => cx > r.left - 40 && cx < r.right + 40 && cy > r.top - 24 && cy < r.bottom + 24)) continue;
        if (!best || (side === 'north' ? sp.y < best.y : sp.y > best.y)) best = { p, y: sp.y };
      }
    }
    return best?.p ?? labelAnchor(zone, side);
  }

  private updateLabels(s: PlannerState | null): void {
    for (const key of ZONE_KEYS) {
      const zone = s ? s.drawn.zones[key] : null;
      const at = zone && zone.polygons.length ? this.labelPoint(zone, key === 'h8' ? 'north' : 'south') : null;
      const cur = this.labels.get(key);
      if (!at) {
        cur?.remove();
        this.labels.delete(key);
        continue;
      }
      if (cur) {
        cur.setLngLat(at);
        continue;
      }
      const el = document.createElement('div');
      el.className = `zone-label ${key === 'h5' ? 'z5' : 'z8'}`;
      el.textContent = this.opts.label(key);
      el.setAttribute('aria-hidden', 'true');
      const m = new maplibregl.Marker({ element: el, anchor: key === 'h8' ? 'bottom' : 'top', offset: key === 'h8' ? [0, -6] : [0, 6] }).setLngLat(at).addTo(this.map);
      this.labels.set(key, m);
    }
  }

  // ------------------------------------------------------------------ hit testing / cursor

  private hit(point: { x: number; y: number }): Hit | null {
    const layers = HANDLE_LAYERS.filter((l) => this.map.getLayer(l));
    if (!layers.length) return null;
    const box: [PointLike, PointLike] = [
      [point.x - HIT_PX, point.y - HIT_PX],
      [point.x + HIT_PX, point.y + HIT_PX],
    ];
    const fs = this.map.queryRenderedFeatures(box, { layers: [...layers] });
    if (!fs.length) return null;
    // nearest handle wins; vertices get a small preference over midpoints, the closing vertex a larger one
    const bias = (k: unknown) => (k === 'first' ? -6 : k === 'vertex' || k === 'draft' ? 0 : 3);
    let best = fs[0]!;
    let bestScore = Infinity;
    for (const f of fs) {
      const g = f.geometry as Point;
      const sp = this.map.project(g.coordinates as [number, number]);
      const dist = Math.hypot(sp.x - point.x, sp.y - point.y);
      const score = dist + bias(f.properties?.kind);
      if (score < bestScore) {
        bestScore = score;
        best = f;
      }
    }
    const p = best.properties ?? {};
    if (p.kind === 'first') return { kind: 'first' };
    if (p.kind === 'draft') return { kind: 'draft' };
    const ref: VertexRef = { zone: p.zone as ZoneKey, poly: Number(p.poly), ring: Number(p.ring), index: Number(p.index) };
    if (p.kind === 'vertex') return { kind: 'vertex', ref };
    const c = (best.geometry as Point).coordinates;
    return { kind: 'mid', ref, lngLat: [Number(c[0]), Number(c[1])] };
  }

  private setCursor(c: string | null): void {
    const canvas = this.map.getCanvas();
    if (c === null) {
      if (this.cursorSet) canvas.style.cursor = '';
      this.cursorSet = false;
      return;
    }
    canvas.style.cursor = c;
    this.cursorSet = true;
  }

  // ------------------------------------------------------------------ pointer events

  private startDrag(hit: Hit): boolean {
    if (hit.kind === 'vertex') {
      za.selectVertex(hit.ref);
      this.drag = { ref: hit.ref, moved: false, inserted: false };
      return true;
    }
    if (hit.kind === 'mid') {
      const ref = za.insertVertexAt(hit.ref, hit.lngLat);
      this.drag = { ref, moved: false, inserted: true };
      return true;
    }
    return false;
  }

  private onDown = (e: MapMouseEvent): void => {
    if (!this.enabled() || e.originalEvent.button !== 0) return;
    const d = getState().drawn;
    if (d.edit.drawing) return;
    const h = this.hit(e.point);
    if (!h || !this.startDrag(h)) return;
    e.preventDefault(); // no drag-pan for this gesture
    this.suppressClick = true;
    this.setCursor('grabbing');
    window.addEventListener('mouseup', this.onWindowUp);
  };

  private moveTo(lngLat: maplibregl.LngLat): void {
    if (!this.drag) return;
    if (!this.drag.moved) {
      this.drag.moved = true;
      if (!this.drag.inserted) za.beginChange();
    }
    za.moveVertexLive(this.drag.ref, [lngLat.lng, lngLat.lat]);
  }

  private onMove = (e: MapMouseEvent): void => {
    if (!this.enabled()) {
      this.setCursor(null);
      return;
    }
    if (this.drag) {
      this.moveTo(e.lngLat);
      this.setCursor('grabbing');
      return;
    }
    const d = getState().drawn;
    if (d.edit.drawing) {
      this.mouse = [e.lngLat.lng, e.lngLat.lat];
      this.renderDraft();
      const h = this.hit(e.point);
      this.setCursor(h?.kind === 'first' && d.edit.draft.length >= 3 ? 'pointer' : 'crosshair');
      return;
    }
    const h = this.hit(e.point);
    this.setCursor(h?.kind === 'vertex' ? 'move' : h?.kind === 'mid' ? 'copy' : null);
  };

  private finishDrag(): void {
    if (!this.drag) return;
    const moved = this.drag.moved;
    this.drag = null;
    window.removeEventListener('mouseup', this.onWindowUp);
    if (moved) za.endChange();
    this.setCursor(null);
  }

  private onUp = (): void => {
    this.finishDrag();
  };

  private onWindowUp = (): void => {
    this.finishDrag();
  };

  private onMoveEnd = (): void => {
    if (this.enabled() && this.installed) this.updateLabels(getState());
  };

  private onClick = (e: MapMouseEvent): void => {
    if (!this.enabled()) return;
    if (this.suppressClick) {
      this.suppressClick = false;
      return;
    }
    const d = getState().drawn;
    if (d.edit.drawing) {
      const h = this.hit(e.point);
      if (h?.kind === 'first' && d.edit.draft.length >= 3) {
        za.closeDrawing();
        this.mouse = null;
        return;
      }
      const last = d.edit.draft[d.edit.draft.length - 1];
      if (last) {
        const lp = this.map.project(last);
        if (Math.hypot(lp.x - e.point.x, lp.y - e.point.y) < 5) return; // second click of a double-click
      }
      za.addDraftVertex([e.lngLat.lng, e.lngLat.lat]);
      return;
    }
    if (!this.hit(e.point)) za.selectVertex(null);
  };

  private onDbl = (e: MapMouseEvent): void => {
    if (!this.enabled()) return;
    const d = getState().drawn;
    if (d.edit.drawing) {
      e.preventDefault();
      if (za.closeDrawing()) this.mouse = null;
      return;
    }
    if (this.hit(e.point)) e.preventDefault();
  };

  private onTouchStart = (e: MapTouchEvent): void => {
    if (!this.enabled() || e.points.length !== 1 || getState().drawn.edit.drawing) return;
    const h = this.hit(e.point);
    if (!h || !this.startDrag(h)) return;
    e.preventDefault();
    this.suppressClick = true;
  };

  private onTouchMove = (e: MapTouchEvent): void => {
    if (!this.drag) return;
    e.preventDefault();
    this.moveTo(e.lngLat);
  };

  private onTouchEnd = (): void => {
    this.finishDrag();
  };

  // ------------------------------------------------------------------ keyboard

  private onKey = (e: KeyboardEvent): void => {
    if (!this.enabled()) return;
    const t = e.target as HTMLElement | null;
    if (t && (t.tagName === 'INPUT' || t.tagName === 'SELECT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
    if (document.querySelector('[aria-modal="true"]')) return; // a dialog is open
    const onButton = t?.tagName === 'BUTTON';
    const onMap = Boolean(t && this.map.getContainer().contains(t));
    const d = getState().drawn;
    const stop = () => {
      e.preventDefault();
      e.stopPropagation();
    };
    const k = e.key;
    if (k === 'Escape') {
      if (d.edit.drawing) {
        za.cancelDrawing();
        this.mouse = null;
        stop();
      } else if (d.edit.selected) {
        za.selectVertex(null);
        stop();
      }
      return;
    }
    if ((k === 'z' || k === 'Z') && (e.ctrlKey || e.metaKey) && !e.shiftKey) {
      za.undo();
      stop();
      return;
    }
    if (d.edit.drawing) {
      if (k === 'Enter' && !onButton) {
        if (za.closeDrawing()) this.mouse = null;
        stop();
      } else if ((k === ' ' || k === 'Spacebar') && (onMap || t === document.body)) {
        const c = this.map.getCenter();
        za.addDraftVertex([c.lng, c.lat]);
        stop();
      } else if (k === 'Backspace' && !onButton && d.edit.draft.length) {
        za.undo(); // removes the last draft vertex
        stop();
      }
      return;
    }
    if ((k === 'Delete' || k === 'Backspace') && d.edit.selected) {
      za.deleteSelectedVertex();
      stop();
      return;
    }
    if (k === '[' || k === ']') {
      za.cycleVertex(k === ']' ? 1 : -1);
      const v = vertexAt(getState().drawn.zones, getState().drawn.edit.selected);
      if (v && !this.map.getBounds().contains(v)) this.map.easeTo({ center: v, duration: 300 });
      stop();
      return;
    }
    if (d.edit.selected && k.startsWith('Arrow') && (onMap || t === document.body)) {
      const v = vertexAt(d.zones, d.edit.selected);
      if (!v) return;
      const step = e.shiftKey ? 20 : 5;
      const p = this.map.project(v);
      if (k === 'ArrowLeft') p.x -= step;
      else if (k === 'ArrowRight') p.x += step;
      else if (k === 'ArrowUp') p.y -= step;
      else if (k === 'ArrowDown') p.y += step;
      const ll = this.map.unproject(p);
      const now = Date.now();
      if (now - this.nudgeAt > 1200) za.beginChange();
      this.nudgeAt = now;
      za.moveVertexLive(d.edit.selected, [ll.lng, ll.lat]);
      if (this.nudgeTimer) clearTimeout(this.nudgeTimer);
      this.nudgeTimer = setTimeout(() => za.endChange(), 700);
      stop();
    }
  };
}
