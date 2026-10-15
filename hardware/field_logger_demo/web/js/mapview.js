// One MapLibre map (vendored, offline): a monochrome basemap from GeoJSON (no tiles, no glyphs), the green route,
// the no-fix gaps, privacy zones and HTML markers that keep their screen size at every zoom. Colours come from the
// tokens (css variables) of the current theme. Without map data the route is drawn on a plain grid.
import { cssVar, circleRing, R_EARTH, esc } from './util.js';

const areaCache = new Map();
async function loadArea(area) {
  if (!area) return null;
  if (areaCache.has(area)) return areaCache.get(area);
  const p = (async () => {
    const meta = await fetch(`mapdata/${area}/meta.json`).then(r => (r.ok ? r.json() : null)).catch(() => null);
    if (!meta) return null;
    const layers = {};
    for (const name of meta.layers || ['water', 'blocks', 'parks', 'buildings', 'roads']) {   // only the layers it has
      try {
        const r = await fetch(`mapdata/${area}/${name}.geojson`);
        if (r.ok) layers[name] = await r.json();
      } catch (e) { /* a missing layer is simply not drawn */ }
    }
    return { meta, layers };
  })();
  areaCache.set(area, p);
  return p;
}

// pixels per metre at a zoom level and latitude (MapLibre: 512 px world at zoom 0)
export function pxPerMetre(zoom, lat) { return 512 * 2 ** zoom / (2 * Math.PI * R_EARTH * Math.cos(lat * Math.PI / 180)); }
export function zoomForPxPerMetre(ppm, lat) { return Math.log2(ppm * 2 * Math.PI * R_EARTH * Math.cos(lat * Math.PI / 180) / 512); }

const EMPTY = { type: 'FeatureCollection', features: [] };

export class MapView {
  constructor(container, opts = {}) {
    this.container = container;
    this.opts = Object.assign({ interactive: true, lens: false, exportMode: false }, opts);
    this.markers = { stops: [], me: null, labels: [] };
    this.area = null;
    this.lat0 = 35;
    this.ready = new Promise(res => { this._resolve = res; });
    const c = (n) => cssVar(n);
    this.map = new maplibregl.Map({
      container, style: { version: 8, sources: {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': c('--map-land') } }] },
      center: [126.839, 35.147], zoom: 15, attributionControl: false, interactive: this.opts.interactive,
      dragRotate: false, pitchWithRotate: false, touchPitch: false, boxZoom: false, keyboard: false,
      fadeDuration: 0, renderWorldCopies: false, maxPitch: 0, preserveDrawingBuffer: !!this.opts.exportMode,
    });
    this.map.on('load', () => { this._initLayers(); this._resolve(); });
    this.userMoved = false;
    if (this.opts.interactive) {
      for (const ev of ['dragstart', 'zoomstart', 'wheel']) {
        this.map.on(ev, (e) => { if (e.originalEvent) { this.userMoved = true; this.onUserMove && this.onUserMove(); } });
      }
    }
  }

  _initLayers() {
    const m = this.map, c = (n) => cssVar(n);
    const add = (id, data = EMPTY) => m.addSource(id, { type: 'geojson', data });
    for (const id of ['grid', 'water', 'blocks', 'parks', 'buildings', 'roads', 'zones', 'gaps', 'track', 'lensbox', 'cloud']) add(id);
    m.addLayer({ id: 'grid', type: 'line', source: 'grid', paint: { 'line-color': ['case', ['==', ['get', 'major'], 1], c('--map-grid-major'), c('--map-grid')], 'line-width': 1 } });
    m.addLayer({ id: 'blocks', type: 'fill', source: 'blocks', paint: { 'fill-color': c('--map-block') } });
    m.addLayer({ id: 'parks', type: 'fill', source: 'parks', paint: { 'fill-color': c('--map-park') } });
    m.addLayer({ id: 'water', type: 'fill', source: 'water', filter: ['==', ['geometry-type'], 'Polygon'], paint: { 'fill-color': c('--map-water') } });
    m.addLayer({ id: 'water-line', type: 'line', source: 'water', filter: ['==', ['geometry-type'], 'LineString'],
      layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': c('--map-water'), 'line-width': 1 } });
    m.addLayer({ id: 'buildings', type: 'fill', source: 'buildings', paint: { 'fill-color': c('--map-bldg'), 'fill-outline-color': c('--map-bldg-line') } });
    m.addLayer({ id: 'roads-case', type: 'line', source: 'roads', layout: { 'line-cap': 'butt', 'line-join': 'round' },
      paint: { 'line-color': c('--map-casing'), 'line-width': 1 } });
    m.addLayer({ id: 'roads', type: 'line', source: 'roads', layout: { 'line-cap': 'butt', 'line-join': 'round' },
      paint: { 'line-color': ['match', ['get', 'kind'], 'minor', c('--map-minor'), 'art', c('--map-art'), 'arterial', c('--map-art'), c('--map-major')], 'line-width': 1 } });
    m.addLayer({ id: 'zones-fill', type: 'fill', source: 'zones', paint: { 'fill-color': c('--map-zone-fill') } });
    m.addLayer({ id: 'zones-line', type: 'line', source: 'zones', paint: { 'line-color': c('--map-zone-line'), 'line-width': 1.2, 'line-dasharray': [4, 5] } });
    m.addLayer({ id: 'gaps', type: 'line', source: 'gaps', layout: { 'line-cap': 'round' },
      paint: { 'line-color': c('--map-gap'), 'line-width': 2.5, 'line-dasharray': [0.1, 2.6] } });
    const lw = this.opts.lens ? 5 : 4;
    m.addLayer({ id: 'track-glow', type: 'line', source: 'track', layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': c('--map-route-glow'), 'line-width': 12, 'line-blur': 4 } });
    m.addLayer({ id: 'track', type: 'line', source: 'track', layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': c('--map-route'), 'line-width': lw } });
    m.addLayer({ id: 'cloud', type: 'circle', source: 'cloud', paint: { 'circle-radius': 2.4, 'circle-color': c('--map-jitter') } });
    m.addLayer({ id: 'lensbox', type: 'line', source: 'lensbox', paint: { 'line-color': c('--map-lens-box'), 'line-width': 1 } });
  }

  _set(id, data) { const s = this.map.getSource(id); if (s) s.setData(data || EMPTY); }

  // area: name of mapdata/<area>/, or null for the grid. bounds: [w, s, e, n] of the session (for the grid).
  async setArea(area, bounds) {
    await this.ready;
    this.area = area;
    const a = await loadArea(area);
    const lat = bounds ? (bounds[1] + bounds[3]) / 2 : (a && a.meta.center ? a.meta.center[1] : 35);
    this.lat0 = lat;
    if (a) {
      for (const name of ['water', 'blocks', 'parks', 'buildings', 'roads']) this._set(name, a.layers[name]);
      this._set('grid', EMPTY);
      // road widths in metres, drawn to scale at every zoom (exponential base 2 between zoom 10 and 22)
      const s10 = pxPerMetre(10, lat), s22 = pxPerMetre(22, lat);
      const w = (s, extra) => ['+', ['*', ['coalesce', ['get', 'w'], 8], s], extra];
      this.map.setPaintProperty('roads', 'line-width', ['interpolate', ['exponential', 2], ['zoom'], 10, w(s10, 0), 22, w(s22, 0)]);
      this.map.setPaintProperty('roads-case', 'line-width', ['interpolate', ['exponential', 2], ['zoom'], 10, w(s10, 1.6), 22, w(s22, 1.6)]);
      this.map.setPaintProperty('water-line', 'line-width', ['interpolate', ['exponential', 2], ['zoom'], 10, w(s10, 0), 22, w(s22, 0)]);
      this.meta = a.meta;
    } else {
      for (const name of ['water', 'blocks', 'parks', 'buildings', 'roads']) this._set(name, EMPTY);
      this._set('grid', bounds ? gridLines(bounds) : EMPTY);
      this.meta = null;
    }
    return a ? a.meta : null;
  }

  setTrack(segments) {
    this._set('track', { type: 'FeatureCollection', features: segments.filter(s => s.length > 1).map(s => ({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: s } })) });
  }

  setGaps(gaps) {
    this._set('gaps', { type: 'FeatureCollection', features: gaps.filter(g => g.a && g.b).map(g => ({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: [g.a, g.b] } })) });
  }

  setZones(zones) {
    this._set('zones', { type: 'FeatureCollection', features: zones.map(z => ({ type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [circleRing(z.lo, z.la, z.r)] } })) });
  }

  setLensBox(corners) {
    this._set('lensbox', corners ? { type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [corners.concat([corners[0]])] } } : EMPTY);
  }

  setCloud(points) {
    this._set('cloud', { type: 'FeatureCollection', features: points.map(p => ({ type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: p } })) });
  }

  // ------------------------------------------------------------------ HTML markers
  _marker(elm, lngLat, anchor = 'center') {
    return new maplibregl.Marker({ element: elm, anchor }).setLngLat(lngLat).addTo(this.map);
  }

  setStops(stops) {
    // stops: [{n, lo, la, pill}] (pill: duration text or null)
    for (const mk of this.markers.stops) mk.remove();
    this.markers.stops = [];
    for (const s of stops) {
      if (s.la === null || s.lo === null || s.la === undefined) continue;
      const w = document.createElement('div');
      w.className = 'mk-stopwrap';
      w.innerHTML = `<div class="mk-stop">${esc(s.n)}</div>` + (s.pill ? `<div class="mk-dpill">${esc(s.pill)}</div>` : '');
      const mk = this._marker(w, [s.lo, s.la]);
      mk._stop = s;
      this.markers.stops.push(mk);
    }
    this.declutter();
  }

  // When two duration pills would overlap, hide the pill and keep the number.
  declutter() {
    const placed = [];
    for (const mk of this.markers.stops) {
      const pill = mk.getElement().querySelector('.mk-dpill');
      if (!pill) continue;
      const p = this.map.project(mk.getLngLat());
      const box = { x0: p.x + 18, x1: p.x + 18 + 60, y0: p.y - 12, y1: p.y + 12 };
      const hit = placed.some(b => !(box.x1 < b.x0 || box.x0 > b.x1 || box.y1 < b.y0 || box.y0 > b.y1))
        || this.markers.stops.some(o => o !== mk && (() => { const q = this.map.project(o.getLngLat()); return q.x > box.x0 - 12 && q.x < box.x1 + 12 && Math.abs(q.y - p.y) < 24; })());
      pill.classList.toggle('hide', hit);
      if (!hit) placed.push(box);
    }
  }

  setMe(lonlat, pillText = null) {
    if (!lonlat) { if (this.markers.me) { this.markers.me.remove(); this.markers.me = null; } return; }
    if (!this.markers.me) {
      const w = document.createElement('div');
      w.className = 'mk-me';
      this.markers.me = this._marker(w, lonlat);
    }
    this.markers.me.setLngLat(lonlat);
    const e = this.markers.me.getElement();
    let pill = e.querySelector('.mk-cpill');
    if (pillText) {
      if (!pill) { pill = document.createElement('div'); pill.className = 'mk-cpill'; e.appendChild(pill); }
      pill.textContent = pillText;
    } else if (pill) pill.remove();
  }

  setLabels(labels) {
    // labels: [{lo, la, text, cls}]
    for (const mk of this.markers.labels) mk.remove();
    this.markers.labels = labels.filter(l => l.la !== null && l.la !== undefined).map(l => {
      const d = document.createElement('div');
      d.className = l.cls || 'mk-label';
      d.textContent = l.text;
      return this._marker(d, [l.lo, l.la], l.anchor || 'left');
    });
  }

  // ------------------------------------------------------------------ camera
  size() { const c = this.map.getContainer(); return { w: c.clientWidth, h: c.clientHeight }; }
  getZoom() { return this.map.getZoom(); }
  getCenter() { const c = this.map.getCenter(); return [c.lng, c.lat]; }
  project(lonlat) { return this.map.project(lonlat); }
  unproject(xy) { const p = this.map.unproject(xy); return [p.lng, p.lat]; }
  jump(center, zoom) { this.map.jumpTo({ center, zoom }); }
  ease(center, zoom, duration = 800) {
    this.map.easeTo({ center, zoom, duration, easing: (t) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2) });
  }
  isMoving() { return this.map.isMoving(); }
  resize() { this.map.resize(); }
  remove() { this.map.remove(); }
  idle() { return new Promise(res => { if (this.map.loaded() && !this.map.isMoving()) { this.map.once('idle', res); this.map.triggerRepaint(); } else this.map.once('idle', res); }); }
}

// plain grid when there is no map data: 1-2-5 spacing at about an eighth of the session's span
function gridLines(b) {
  const lat = (b[1] + b[3]) / 2;
  const ky = Math.PI * R_EARTH / 180, kx = ky * Math.cos(lat * Math.PI / 180);
  const spanM = Math.max((b[2] - b[0]) * kx, (b[3] - b[1]) * ky, 60);
  const steps = [5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000];
  const s = steps.find(v => v >= spanM / 8) || 5000;
  const padM = spanM * 2 + 200;
  const x0 = (b[0] * kx) - padM, x1 = (b[2] * kx) + padM, y0 = (b[1] * ky) - padM, y1 = (b[3] * ky) + padM;
  const f = [];
  for (let x = Math.floor(x0 / s) * s; x <= x1; x += s) {
    f.push({ type: 'Feature', properties: { major: Math.round(x / s) % 5 === 0 ? 1 : 0 }, geometry: { type: 'LineString', coordinates: [[x / kx, y0 / ky], [x / kx, y1 / ky]] } });
  }
  for (let y = Math.floor(y0 / s) * s; y <= y1; y += s) {
    f.push({ type: 'Feature', properties: { major: Math.round(y / s) % 5 === 0 ? 1 : 0 }, geometry: { type: 'LineString', coordinates: [[x0 / kx, y / ky], [x1 / kx, y / ky]] } });
  }
  return { type: 'FeatureCollection', features: f };
}

// scale bar in 1-2-5 steps from 5 m to 5 km, at most about 120 px long
export function scaleBar(ppm, maxPx = 120) {
  const steps = [5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000];
  let v = steps[0];
  for (const s of steps) if (s * ppm <= maxPx) v = s;
  return { metres: v, px: v * ppm, label: v >= 1000 ? `${v / 1000} km` : `${v} m` };
}
