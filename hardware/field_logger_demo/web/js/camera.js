// Adaptive map scale (spec section 3B). One module owns the overview fit, the close-up rule and F/R, for REPLAY and LIVE.
//  - Overview: fit every visible fix so far plus the current position into the safe area (90 px padding). The stats
//    card and the close-up sit in opposite corners; if the route would run under a card, shift the fit away from it
//    before zooming out further. Minimum span 60 m on the short side; no maximum.
//  - Change zoom only when a point would leave the safe area or the ideal zoom differs by more than 0.15 levels; eased
//    800 ms moves; never during a stop. Manual pan or zoom pauses auto-fit until F or R.
//  - Close-up: 80 m across (300 px card -> 3.75 px/m), shown only when the overview is below 1.5 px/m (2.5x rule).
import { pxPerMetre, zoomForPxPerMetre } from './mapview.js';
import { reducedMotion } from './util.js';

export const PAD = 90;
export const MIN_SPAN_M = 60;
export const HYSTERESIS = 0.15;
export const LENS_PPM = 300 / 80;           // close-up: 80 m across the 300 px card
export const LENS_RULE_PPM = 1.5;           // close-up only when the overview is below 1.5 px per metre
const R = 6371008.8;

const mx = (lon) => (lon + 180) / 360;
const my = (lat) => { const s = Math.sin(lat * Math.PI / 180); return 0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI); };
const lonOf = (x) => x * 360 - 180;
const latOf = (y) => { const n = Math.PI - 2 * Math.PI * y; return 180 / Math.PI * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n))); };

// Pure fit: points [[lon, lat]], size {w, h}, pads {l, t, r, b}. Returns {zoom, center}.
export function fitView(points, size, pads, minSpanM = MIN_SPAN_M) {
  const xs = points.map(p => mx(p[0])), ys = points.map(p => my(p[1]));
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const lat = latOf((y0 + y1) / 2);
  const ws = Math.max(40, size.w - pads.l - pads.r), hs = Math.max(40, size.h - pads.t - pads.b);
  const dx = Math.max(x1 - x0, 1e-12), dy = Math.max(y1 - y0, 1e-12);
  const zFit = Math.log2(Math.min(ws / (dx * 512), hs / (dy * 512)));
  const zMax = Math.log2(Math.min(ws, hs) * 2 * Math.PI * R * Math.cos(lat * Math.PI / 180) / (minSpanM * 512));
  const zoom = Math.min(zFit, zMax);
  const scale = 512 * 2 ** zoom;
  const cx = (x0 + x1) / 2 - (pads.l - pads.r) / 2 / scale;
  const cy = (y0 + y1) / 2 - (pads.t - pads.b) / 2 / scale;
  return { zoom, center: [lonOf(cx), latOf(cy)] };
}

// screen position of a point for a view that is not applied yet
export function projectAt(view, size, p) {
  const scale = 512 * 2 ** view.zoom;
  return { x: (mx(p[0]) - mx(view.center[0])) * scale + size.w / 2, y: (my(p[1]) - my(view.center[1])) * scale + size.h / 2 };
}

function hits(view, size, points, rect) {
  for (const p of points) {
    const q = projectAt(view, size, p);
    if (q.x >= rect.x - 24 && q.x <= rect.x + rect.w + 24 && q.y >= rect.y - 24 && q.y <= rect.y + rect.h + 24) return true;
  }
  return false;
}

// Fit avoiding the cards (rects in map pixels): try shifting away from each card before zooming out further.
export function fitAvoiding(points, size, cards) {
  const base = { l: PAD, t: PAD, r: PAD, b: PAD };
  const opts = [];
  const per = cards.map(c => {
    const left = c.x < size.w / 2, top = c.y < size.h / 2;
    const o = [{}];
    o.push(left ? { l: c.x + c.w + 16 } : { r: size.w - c.x + 16 });
    o.push(top ? { t: c.y + c.h + 16 } : { b: size.h - c.y + 16 });
    return o;
  });
  const combine = (i, acc) => {
    if (i === per.length) { opts.push(acc); return; }
    for (const o of per[i]) combine(i + 1, Object.assign({}, acc, o, mergeMax(acc, o)));
  };
  combine(0, {});
  let best = null;
  for (const o of opts) {
    const pads = Object.assign({}, base, o);
    const v = fitView(points, size, pads);
    const clear = cards.every(c => !hits(v, size, points, c));
    if (clear && (!best || v.zoom > best.zoom + 1e-9)) best = Object.assign(v, { pads });
  }
  if (best) return best;
  // nothing avoids both cards: zoom out with both cards as padding
  const pads = Object.assign({}, base);
  for (const c of cards) {
    if (c.x < size.w / 2) pads.l = Math.max(pads.l, c.x + c.w + 16); else pads.r = Math.max(pads.r, size.w - c.x + 16);
  }
  return Object.assign(fitView(points, size, pads), { pads });
}

function mergeMax(a, b) {
  const out = {};
  for (const k of Object.keys(b)) out[k] = Math.max(a[k] || 0, b[k]);
  return out;
}

export class Camera {
  constructor(view, opts = {}) {
    this.view = view;
    this.mode = 'overview';            // overview | follow
    this.paused = false;
    this.lastMove = 0;
    this.testLog = opts.testLog || null;
    view.onUserMove = () => { this.paused = true; opts.onPause && opts.onPause(); };
  }

  closeZoom(lat) { return zoomForPxPerMetre(LENS_PPM, lat); }
  ppm() { const c = this.view.getCenter(); return pxPerMetre(this.view.getZoom(), c[1]); }
  lensVisible() { return this.mode === 'overview' && this.ppm() < LENS_PPM / 2.5 + 1e-9; }

  reset() { this.paused = false; this.view.userMoved = false; }

  toggleFollow() { this.mode = this.mode === 'overview' ? 'follow' : 'overview'; this.paused = false; return this.mode; }

  _move(center, zoom, reason, t, duration = 800, pads = null) {
    const d = reducedMotion() ? 0 : duration;
    const from = this.view.getZoom();
    if (d) this.view.ease(center, zoom, d); else this.view.jump(center, zoom);
    this.lastMove = performance.now();
    if (this.testLog) {
      this.testLog.push({ t, zoom: +zoom.toFixed(4), center: center.map(v => +v.toFixed(6)), reason, from: +from.toFixed(4),
        size: this.view.size(), pads });
    }
  }

  // Fit, and if the close-up will show at that scale, fit again keeping clear of it too.
  fitWithCards(pts, size, stats, lens) {
    let ideal = fitAvoiding(pts, size, stats ? [stats] : []);
    const lat = ideal.center[1];
    if (lens && pxPerMetre(ideal.zoom, lat) < LENS_PPM / 2.5) ideal = fitAvoiding(pts, size, (stats ? [stats] : []).concat([lens]));
    return ideal;
  }

  // points: visible fixes so far + current position; cards: {stats, lens} rects (map pixels); stopped: a stop is in
  // progress
  update({ points, me, cards, stopped, t, force = false }) {
    if (!points.length && !me) return;
    if (this.paused && !force) return;
    if (this.view.isMoving() && !force) return;
    const size = this.view.size();
    if (this.mode === 'follow') {
      if (!me) return;
      const z = this.closeZoom(me[1]);
      const p = this.view.project(me);
      const off = Math.hypot(p.x - size.w / 2, p.y - size.h / 2);
      if (force || Math.abs(this.view.getZoom() - z) > 0.01 || off > Math.min(size.w, size.h) * 0.18) {
        if (stopped && !force && Math.abs(this.view.getZoom() - z) < 0.01) return;
        this._move(me, z, 'follow', t, force ? 800 : 600);
      } else if (off > 2 && !stopped) {
        this.view.jump(me, z);
      }
      return;
    }
    const pts = me ? points.concat([me]) : points;
    if (!pts.length) return;
    const ideal = Array.isArray(cards) ? fitAvoiding(pts, size, cards) : this.fitWithCards(pts, size, cards.stats, cards.lens);
    if (force) { this._move(ideal.center, ideal.zoom, 'force', t, 800, ideal.pads); return; }
    if (stopped) return;   // during a stop the camera does not move
    const z = this.view.getZoom();
    const pads = ideal.pads;
    let leaves = false;
    for (const p of pts) {
      const q = this.view.project(p);
      if (q.x < pads.l * 0.5 || q.x > size.w - pads.r * 0.5 || q.y < pads.t * 0.5 || q.y > size.h - pads.b * 0.5) { leaves = true; break; }
    }
    if (Math.abs(ideal.zoom - z) > HYSTERESIS) {
      this._move(ideal.center, ideal.zoom, leaves ? 'leave' : 'zoom', t, 800, pads);
    } else if (leaves) {
      // a point is leaving but the ideal zoom is within the hysteresis: pan at the same zoom when the ideal zoom is not
      // lower (everything fits), otherwise zoom out by the full 0.15 (more than needed), so no zoom change is smaller
      const zoom = ideal.zoom >= z ? z : z - HYSTERESIS;
      this._move(ideal.center, zoom, 'leave', t, 800, pads);
    }
  }

  // the end of a replay: one smooth move out to the whole route
  final(points, cards, t) {
    if (!points.length) return;
    const size = this.view.size();
    const ideal = Array.isArray(cards) ? fitAvoiding(points, size, cards) : this.fitWithCards(points, size, cards.stats, null);
    this._move(ideal.center, ideal.zoom, 'final', t, 1200, ideal.pads);
  }

  // corners of the close-up's extent (for the thin white rectangle on the overview)
  lensCorners(me) {
    if (!me) return null;
    const halfW = 150 / LENS_PPM, halfH = 98 / LENS_PPM;     // 300 x 196 px card
    const ky = Math.PI * R / 180, kx = ky * Math.cos(me[1] * Math.PI / 180);
    const dx = halfW / kx, dy = halfH / ky;
    return [[me[0] - dx, me[1] - dy], [me[0] + dx, me[1] - dy], [me[0] + dx, me[1] + dy], [me[0] - dx, me[1] + dy]];
  }
}
