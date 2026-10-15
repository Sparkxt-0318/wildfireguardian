// LIVE (firmware 0.3.0, spec sections 5 and 8): the device sends '#J' lines while it records; the map draws the live
// track with the same adaptive scale as REPLAY. Indoors there is no fix: the note explains why and the satellites with
// signal are counted from the GSV sentences. I shows the device page over the map.
import { mmss, bus, esc, comma } from './util.js';
import { t, modeName } from './i18n.js';
import { get } from './api.js';
import { MapView, pxPerMetre } from './mapview.js';
import { Camera } from './camera.js';
import { buildTrack, statsCardHTML, renderScale, Lens } from './trackview.js';
import { circled } from './replay.js';

const NORTH = '<svg width="14" height="18" viewBox="-7 -10 14 18"><path d="M0,-10 L5.5,7 L0,3.5 L-5.5,7 Z"/></svg>';

export class LiveView {
  constructor() {
    this.el = null;
    this.rows = [];
    this.stops = new Map();
    this.metrics = null;
    this.session = null;
    this.mode = 'UNKNOWN';
    this.sats = null;
    this.area = undefined;
    this.zones = [];
    this.builds = 0;                    // maps made: stays 1 (tests/test_web.py)
    bus.on('ws:live', (ev) => this.onEvent(ev));
  }

  // container: the device segment's left pane; snap: the device snapshot
  render(container, snap) {
    if (!this.el) this._build(container);
    else if (!container.contains(this.el)) this._attach(container);
    const lv = snap.live || {};
    this.deviceStatus = snap.status || {};
    this.activity = lv.activity || {};
    this.simulated = !!(snap.conn && snap.conn.simulated);
    if (lv.rows && lv.session !== undefined && (this.session !== lv.session || this.rows.length < lv.rows.length)) {
      this.session = lv.session;
      this.mode = lv.mode;
      this.rows = lv.rows.filter(r => r.t !== null);
      this.stops = new Map((lv.stops || []).map(s => [s.n, s]));
      this.zones = lv.zones || [];
    }
    if (lv.zones) { this.zones = lv.zones; if (this.view) this.view.setZones(this.zones); }
    if (lv.sats_signal !== undefined && lv.sats_signal !== null) this.sats = lv.sats_signal;
    this.recording = !!lv.recording || this.deviceStatus.state === 'RECORDING';
    this.ended = lv.ended;
    this._draw();
  }

  _build(container) {
    container.innerHTML = `<div class="mapwrap" style="position:absolute;inset:0"><div class="ml"></div>
      <div class="card stats glass"></div>
      <div class="card lens glass off"><div class="lh"><b></b><span></span></div><div class="lmap"><div class="ml"></div><div class="scalebar"></div></div></div>
      <div class="north">${NORTH}</div><div class="scalebar main"></div><div class="attr"></div><div class="mapnote hidden"></div>
      <div class="maptoast hidden"></div></div>`;
    this.el = container.firstElementChild;
    this.builds += 1;
    const q = (s) => this.el.querySelector(s);
    this.$ = { map: q('.ml'), stats: q('.stats'), lens: q('.lens'), scale: q('.scalebar.main'), attr: q('.attr'), note: q('.mapnote'),
      toast: q('.maptoast') };
    this.view = new MapView(this.$.map, {});
    this.lens = new Lens(this.$.lens);
    this.camera = new Camera(this.view, { onPause: () => this._mapToast(t('autofit.paused')) });
    this.view.map.on('move', () => renderScale(this.$.scale, pxPerMetre(this.view.getZoom(), this.view.getCenter()[1])));
    this.area = undefined;
  }

  // F and R work as in REPLAY (spec section 3B): F switches overview and follow, R resumes the auto-fit that a manual
  // pan or zoom paused. Both move the camera at once.
  toggleFollow() {
    if (!this.camera) return null;
    const m = this.camera.toggleFollow();
    this._mapToast(m === 'follow' ? t('follow.on') : t('follow.off'), 1500);
    this._draw(true);
    return m;
  }

  resetCamera() {
    if (!this.camera) return;
    this.camera.reset();
    this._mapToast(t('autofit.on'), 1500);
    this._draw(true);
  }

  _mapToast(text, ms = 0) {
    const e = this.$ && this.$.toast;
    if (!e) return;
    clearTimeout(this._mt);
    if (!text) { e.classList.add('hidden'); return; }
    e.textContent = text;
    e.classList.remove('hidden');
    if (ms) this._mt = setTimeout(() => e.classList.add('hidden'), ms);
  }

  // Back from the device page (I) or after a reconnect: the same maps go back in, never new ones. Every map holds a
  // WebGL context and the browser keeps only a few, so new maps would at last blank the REPLAY map.
  _attach(container) {
    container.replaceChildren(this.el);
    requestAnimationFrame(() => { try { this.view.resize(); this.lens.resize(); } catch (e) { /* not laid out yet */ } });
  }

  onEvent(ev) {
    if (ev.ev === 'session') { this.session = ev.ss; this.mode = ev.md; this.last = null; this.rows = []; this.stops = new Map(); this.metrics = null; this.ended = null; this.recording = true; }
    else if (ev.ev === 'session_end') { this.recording = false; this.ended = { er: ev.er, n: ev.n }; }
    else if (ev.ev === 'ep') { if (ev.recording && ev.row && ev.row.t !== null) this.rows.push(ev.row); this.last = ev.row; }
    else if (ev.ev === 'stop_detected' || ev.ev === 'stop_ended') this.stops.set(ev.n, Object.assign(this.stops.get(ev.n) || {}, ev, { open: ev.ev === 'stop_detected' && (this.stops.get(ev.n) || {}).open !== false }));
    else if (ev.ev === 'stop_removed') this.stops.delete(ev.n);
    else if (ev.ev === 'rezone') {        // the session ended: its end zone hides the last part of the track too
      this.rows = (ev.rows || []).filter(r => r.t !== null);
      this.zones = ev.zones || [];
      this.stops = new Map((ev.stops || []).map(s => [s.n, s]));
      if (this.view) this.view.setZones(this.zones);
    }
    else if (ev.ev === 'zones') { this.zones = ev.zones || []; if (this.view) this.view.setZones(this.zones); }
    else if (ev.ev === 'activity') this.activity = ev;
    else if (ev.ev === 'metrics') this.metrics = ev;
    else if (ev.ev === 'sats') this.sats = ev.n;
    if (this.el && document.body.contains(this.el)) this._draw();
  }

  async _ensureArea(p) {
    if (this.area !== undefined || !p) return;
    this.area = null;
    try { const r = await get(`/api/area_for?lat=${p[1]}&lon=${p[0]}&sim=${this.simulated ? 1 : 0}`); this.area = r.area; } catch (e) { this.area = null; }
    const b = [p[0] - 0.003, p[1] - 0.003, p[0] + 0.003, p[1] + 0.003];
    const meta = await this.view.setArea(this.area, b);
    await this.lens.setArea(this.area, b);
    this.$.attr.textContent = !meta ? t('attrib.grid') : (meta.synthetic ? t('attrib.synthetic') : t('attrib'));
    this.view.setZones(this.zones);
  }

  _draw(force = false) {
    const rows = this.rows;
    const lastFix = [...rows].reverse().find(r => r.f && r.la !== null);
    const me = lastFix ? [lastFix.lo, lastFix.la] : null;
    const last = rows.length ? rows[rows.length - 1] : this.last;
    const hiddenNow = !!(last && last.f && last.h);
    if (me) this._ensureArea(me);
    else if (this.zones.length) this._ensureArea([this.zones[0].lo, this.zones[0].la]);
    const tr = buildTrack(rows, Infinity, -Infinity, false);
    this.view.setTrack(tr.segments);
    this.view.setGaps(tr.gaps);
    const stops = [...this.stops.values()];
    const open = stops.find(s => s.ev === 'stop_detected');
    this.view.setStops(stops.filter(s => s.ev === 'stop_ended' && s.la !== null).map(s => ({ n: s.n, lo: s.lo, la: s.la, pill: mmss(s.dur) })));
    const tNow = rows.length ? rows[rows.length - 1].t : 0;
    this.view.setMe(me, open ? t('stop.inprogress', { n: circled(open.n), dur: mmss(tNow - open.t0 + 1) }) : null);
    const M = this.metrics && this.metrics.metrics;
    const sessionLabel = this.session ? `S${String(this.session).padStart(6, '0')}` : '-';
    const eyebrow = t('live.eyebrow', { session: sessionLabel, mode: modeName(this.mode) });
    const activityData = this.activity || {};
    const currentFix = typeof activityData.fix === 'boolean' ? activityData.fix : !!(last && last.f);
    const fixLabel = !last && activityData.fix == null ? t('live.activity.waiting') : currentFix ? t('live.activity.fix') : t('live.activity.nofix');
    const st = this.deviceStatus || {};
    const sameSession = String(st.session || '').replace(/\.wfg$/, '') === sessionLabel;
    const n = this.ended && this.ended.n != null ? this.ended.n : activityData.count != null ? activityData.count : sameSession && st.seq != null ? Number(st.seq) : null;
    const span = activityData.count != null ? activityData.span : rows.length ? rows[rows.length - 1].t - rows[0].t : 0;
    const label = this.recording ? t('live.activity.rec') : this.ended ? t('live.activity.stopped') : t('live.activity.idle');
    const detail = !this.recording ? t('live.activity.start') : !last && activityData.fix == null ? t('live.activity.awaiting') :
      currentFix ? (hiddenNow ? t('live.activity.private') : t('live.activity.positions')) :
      activityData.reason === 2 || activityData.reason === 3 || (last && (last.nr === 'NO_NMEA_DATA' || last.nr === 'CHECKSUM_ERRORS_ONLY')) ? t('live.activity.no_data') : t('live.activity.indoor');
    const activity = `<div class="live-activity" role="status" aria-label="${esc(t('live.activity.title'))}">
      <div class="activity-head"><span class="dot ${this.recording ? 'live' : 'grey'}"></span><b>${esc(label)}</b><span class="activity-fix">${esc(fixLabel)}</span></div>
      <div class="grid3 activity-values"><div><b class="activity-records">${n === null ? '-' : esc(comma(n))}</b><span>${esc(t('live.activity.records'))}</span></div>
      <div><b class="activity-span">${esc(mmss(Math.max(0, span)))}</b><span>${esc(t('live.activity.span'))}</span></div>
      <div><b>${esc(comma(activityData.samples ?? rows.length))}</b><span>${esc(t('live.activity.samples'))}</span></div></div>
      <p class="activity-detail">${esc(detail)}</p></div>`;
    this.$.stats.innerHTML = activity + (M ? statsCardHTML({ eyebrow, elapsed: M.elapsed, total: M.elapsed, dist: M.distance, avg: M.avg_speed,
      n: M.n_stops, stopped: M.stopped, pct: M.pct_added }) : `<div class="eyebrow">${esc(eyebrow)}</div>`);
    const nofix = !me && !hiddenNow;
    this.$.note.classList.toggle('hidden', !nofix && !hiddenNow && this.recording);
    // positions are shown only while recording, and never inside a privacy zone (live.py)
    if (!this.recording) this.$.note.textContent = this.ended ? t('live.ended') : t('live.waiting');
    else if (hiddenNow) this.$.note.textContent = `${t('zone')} · ${t('console.hidden')}`;
    else if (nofix) this.$.note.textContent = `${t('indoor.note')}${this.sats !== null && this.sats !== undefined ? `  ${t('live.sats', { n: this.sats })}` : ''}`;
    if (!me && this.zones.length) {                        // nothing shown yet: frame the start zone
      const pts = [];
      const start = this.zones.filter(z => z.kind === 'start');
      for (const z of (start.length ? start : this.zones)) { const dy = z.r / 111320, dx = z.r / (111320 * Math.cos(z.la * Math.PI / 180)); pts.push([z.lo - dx, z.la - dy], [z.lo + dx, z.la + dy]); }
      const mapR = this.$.map.getBoundingClientRect(), r1 = this.$.stats.getBoundingClientRect();
      this.camera.update({ points: pts, me: null, cards: { stats: { x: r1.left - mapR.left, y: r1.top - mapR.top, w: r1.width, h: r1.height }, lens: null }, stopped: false, t: 0, force });
    }
    if (me) {
      const mapR = this.$.map.getBoundingClientRect(), r1 = this.$.stats.getBoundingClientRect();
      const r2 = this.$.lens.getBoundingClientRect();
      this.camera.update({ points: tr.visible, me, cards: { stats: { x: r1.left - mapR.left, y: r1.top - mapR.top, w: r1.width, h: r1.height },
        lens: { x: r2.left - mapR.left, y: r2.top - mapR.top, w: r2.width, h: r2.height } }, stopped: !!open, t: tNow, force });
      const lensOn = this.camera.lensVisible();
      this.lens.show(lensOn);
      if (lensOn) this.lens.update(me, buildTrack(rows, Infinity, tNow - 90, false).segments, []);
      this.view.setLensBox(lensOn ? this.camera.lensCorners(me) : null);
    }
    this.$.lens.querySelector('.lh b').textContent = t('lens.title');
    this.$.lens.querySelector('.lh span').textContent = t('lens.sub');
  }
}
