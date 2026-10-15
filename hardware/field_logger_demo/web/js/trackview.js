// Pieces shared by REPLAY and LIVE: building the drawn line from real fixes only, the stats card, the close-up card,
// the scale bar and the SIM watermark.
import { esc, fixed, mmss, comma } from './util.js';
import { t } from './i18n.js';
import { MapView, pxPerMetre, scaleBar } from './mapview.js';
import { LENS_PPM, zoomForLens } from './lensmath.js';

export const BRIDGE_S = 3.0;   // no-fix runs up to 3 s belong to what surrounds them (spec section 6)

// rows: [{t, f, la, lo, h, s}] up to the current time. Returns {segments, gaps, visible}: the line uses only real
// points; a run without a fix longer than 3 s ends the line and is drawn as a dotted gap; lead-in and lead-out rows and
// rows inside privacy zones are not drawn.
export function buildTrack(rows, upto, from = -Infinity, skipLead = true) {
  const segments = [];
  const gaps = [];
  const visible = [];
  let cur = [];
  let last = null;
  for (const r of rows) {
    if (r.t > upto) break;
    if (r.t < from) continue;
    if (!r.f) continue;
    if (r.h || r.la === null || r.la === undefined) { if (cur.length) segments.push(cur); cur = []; last = null; continue; }
    if (skipLead && r.s === 'lead') { if (cur.length) segments.push(cur); cur = []; last = null; continue; }
    const p = [r.lo, r.la];
    if (last && r.t - last.t - 1 > BRIDGE_S) {
      if (cur.length) segments.push(cur);
      cur = [];
      gaps.push({ a: [last.lo, last.la], b: p, t0: last.t, t1: r.t });
    }
    cur.push(p);
    visible.push(p);
    last = r;
  }
  if (cur.length) segments.push(cur);
  return { segments, gaps, visible };
}

// marker position between two real fixes (screen only), or the last fix
export function interpolate(rows, idx, upto) {
  let a = null, b = null;
  for (let i = idx; i >= 0; i--) { const r = rows[i]; if (r.t <= upto && r.f && r.la !== null && r.la !== undefined && !r.h) { a = r; break; } if (r.h) return null; }
  if (!a) return null;
  for (let i = idx + 1; i < rows.length; i++) { const r = rows[i]; if (r.f) { if (r.la !== null && r.la !== undefined && !r.h) b = r; break; } }
  if (b && b.t - a.t - 1 <= BRIDGE_S && b.t > a.t) {
    const f = Math.min(1, Math.max(0, (upto - a.t) / (b.t - a.t)));
    return [a.lo + (b.lo - a.lo) * f, a.la + (b.la - a.la) * f];
  }
  return [a.lo, a.la];
}

// ------------------------------------------------------------------ stats card
export function statsCardHTML(st) {
  // st: {eyebrow, eyebrowSim, elapsed, total, dist, avg, n, stopped, pct, nomove, nopos}
  const head = `<div class="eyebrow${st.eyebrowSim ? ' sim' : ''}">${esc(st.eyebrow)}</div>`;
  if (st.nomove) {
    return `${head}<div class="nomove">${esc(st.nopos ? t('nopos.note') : t('stats.nomove'))}</div>`;
  }
  const cnt = t('stats.count', { n: st.n, d: mmss(st.stopped) });
  const lab = st.pct === null ? t('stops') : t('stats.pct', { label: t('stops'), p: Math.round(st.pct * 100) });
  return `${head}
    <div class="hero"><span class="big">${esc(mmss(st.elapsed))}</span><span class="of"> / ${esc(mmss(st.total))}</span></div>
    <div class="cap">${esc(st.leadin ? t('stats.leadin') : t('stats.hero_cap'))}</div>
    <div class="grid3">
      <div><b>${esc(fixed(st.dist / 1000, 2))} km</b><span>${esc(t('distance'))}</span></div>
      <div><b>${st.avg === null ? '-' : esc(fixed(st.avg, 2))} m/s</b><span>${esc(t('avg'))}</span></div>
      <div><b>${esc(cnt)}</b><span>${esc(lab)}</span></div>
    </div>`;
}

// ------------------------------------------------------------------ scale bar
export function renderScale(elm, ppm) {
  const s = scaleBar(ppm);
  elm.innerHTML = `<div class="lab">${esc(s.label)}</div><div class="bar" style="width:${s.px.toFixed(1)}px"></div>`;
}

// ------------------------------------------------------------------ close-up card
export class Lens {
  constructor(cardEl, opts = {}) {
    this.card = cardEl;
    this.host = cardEl.querySelector('.ml');
    this.scale = cardEl.querySelector('.scalebar');
    this.view = new MapView(this.host, { interactive: false, lens: true, exportMode: opts.exportMode });
    this.visible = false;
  }
  async setArea(area, bounds) { await this.view.setArea(area, bounds); }
  show(on) {
    if (on === this.visible) return;
    this.visible = on;
    this.card.classList.toggle('off', !on);
  }
  update(me, segments, cloud) {
    if (!me) return;
    const z = zoomForLens(me[1]);
    this.view.jump(me, z);
    this.view.setTrack(segments);
    this.view.setCloud(cloud || []);
    this.view.setMe(me);
    renderScale(this.scale, pxPerMetre(z, me[1]));
  }
  resize() { this.view.resize(); }
}

export function watermarkHTML(text) {
  const rows = [];
  for (let i = 0; i < 7; i++) rows.push(`<span>${esc(text)}   ${esc(text)}   ${esc(text)}</span>`);
  return `<div>${rows.join('')}</div>`;
}

export function fmtCount(n) { return comma(n); }
export { LENS_PPM };
