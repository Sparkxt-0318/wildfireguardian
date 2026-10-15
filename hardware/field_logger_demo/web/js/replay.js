// REPLAY (booth screen): the backend sends the whole decoded session once; the page plays it, so seeking and pausing
// are exact and repeatable. Map with the adaptive scale, the close-up, the stats card, the timeline and the log stream.
import { esc, el, mmss, comma, shortSha, dateTime, clock, bus, reducedMotion, toast } from './util.js';
import { t, th, getLang, modeName } from './i18n.js';
import { get, post } from './api.js';
import { MapView, pxPerMetre } from './mapview.js';
import { Camera } from './camera.js';
import { renderTimeline } from './timeline.js';
import { LogConsole, recordLines } from './console.js';
import { buildTrack, interpolate, statsCardHTML, renderScale, Lens, watermarkHTML } from './trackview.js';

export const SPEEDS = [1, 5, 10, 15, 30, 60];
const HEX_EVERY = 25;
const NORTH = '<svg width="14" height="18" viewBox="-7 -10 14 18"><path d="M0,-10 L5.5,7 L0,3.5 L-5.5,7 Z"/></svg>';

export function sessionLabel(meta) {
  const m = /-(\d{6})$/.exec(meta.sid || '');
  return m ? `S${m[1]}` : (meta.name || '').replace(/\.wfg$/, '');
}

export function eyebrow(meta) {
  if (meta.sim) return { text: meta.sim_kind === 'double' ? t('double.label') : t('sim.label'), sim: true };
  if (meta.source === 'gpx') return { text: t('gpx.label'), sim: true };
  if (meta.device_test) return { text: t('devtest.eyebrow', { session: sessionLabel(meta) }), sim: false };
  return { text: t('stats.eyebrow', { session: sessionLabel(meta), mode: modeName(meta.mode), date: dateTime(meta.utc0, meta.tz, getLang()) }), sim: false };
}

export class Booth {
  constructor(root) {
    this.root = root;
    this.payload = null;
    this.tau = 0;
    this.playing = false;
    this.speed = 30;
    this.showAllHex = false;
    this.testLog = new URLSearchParams(location.search).has('test') ? (window.__cameraLog = []) : null;
    root.innerHTML = `
      <div class="left">
        <div class="mapwrap"><div class="ml"></div>
          <div class="card stats glass"></div>
          <div class="card lens glass off"><div class="lh"><b></b><span></span></div><div class="lmap"><div class="ml"></div><div class="scalebar"></div></div></div>
          <div class="north">${NORTH}</div>
          <div class="scalebar main"></div>
          <div class="attr"></div>
          <div class="maptoast hidden"></div>
          <div class="mapnote hidden"></div>
          <div class="wm hidden"></div>
        </div>
        <div class="tl"><div class="tlh"><span class="eyebrow2 tlt"></span><span class="leg"></span></div><div class="tlhost"></div><div class="tls"></div></div>
      </div>
      <section class="con">
        <div class="conh"><div><b class="ct"></b><span class="sub"></span></div><div><span class="chip sm recs"></span><span class="chip sm ok crc"></span></div></div>
        <div class="prog"><div></div></div>
        <div class="lines"></div>
        <div class="keys"></div>
        <div class="wm hidden"></div>
      </section>`;
    const q = (s) => root.querySelector(s);
    this.$ = { map: q('.mapwrap > .ml'), stats: q('.stats'), lens: q('.lens'), scale: q('.scalebar.main'), attr: q('.attr'),
      toast: q('.maptoast'), note: q('.mapnote'), wmL: q('.mapwrap .wm'), wmR: q('.con .wm'), tlt: q('.tlt'), leg: q('.leg'),
      tl: q('.tlhost'), tls: q('.tls'), ct: q('.ct'), sub: q('.conh .sub'), recs: q('.recs'), crc: q('.crc'), prog: q('.prog div'),
      lines: q('.lines'), keys: q('.keys') };
    this.view = new MapView(this.$.map, {});
    this.lens = new Lens(this.$.lens);
    this.camera = new Camera(this.view, { testLog: this.testLog, onPause: () => this._mapToast(t('autofit.paused')) });
    this.console = new LogConsole(this.$.lines);
    this.view.map.on('move', () => this._scale());
    this.view.map.on('moveend', () => this.view.declutter());
    this._raf = 0;
    this._last = 0;
    this._lastTrack = -1;
    bus.on('lang', () => { if (this.payload) this._relabel(true); });
    window.addEventListener('resize', () => { this.view.resize(); this.lens.resize(); this._timeline(); });
  }

  // ------------------------------------------------------------------ loading
  async load(query) {
    this.pause();
    this._mapToast(t('replay.loading'));
    let p;
    try { p = await get(`/api/session?${query}`); }
    catch (e) { this._mapToast(t('replay.missing', { file: query })); throw e; }
    this.query = query;
    this.payload = p;
    this._prepare(p);
    const area = await this.view.setArea(p.meta.area, p.bounds);
    await this.lens.setArea(p.meta.area, p.bounds);
    this.areaMeta = area;
    this.view.setZones(p.zones);
    this.view.setLabels(zoneLabels(p.zones));
    this._relabel(false);
    this.restart(false);
    this._mapToast(null);
    return p;
  }

  _prepare(p) {
    const tEnd = Math.max(p.meta.t_end || 0, ...p.rows.map(r => r.t));
    this.tEnd = tEnd;
    this.span = p.span;
    // distance so far: prefix sums of the moving steps
    this.steps = p.steps;
    this.cum = [];
    let acc = 0;
    for (const [, d] of p.steps) { acc += d; this.cum.push(acc); }
    // the stream: records, then the detector's lines at the time they happen
    const items = [];
    // a record without a readable time (CORRUPT, or the END a boot recovery wrote) keeps its place in the file: it is
    // shown right after the record before it
    let lastT = p.rows.length ? p.rows[0].t : 0;
    this.recT = p.records.map((r) => {
      if (r.t !== null && r.t !== undefined) lastT = r.t;
      return lastT;
    });
    this.recT.forEach((tt, i) => items.push({ tt, k: 0, i }));
    p.stops.forEach((s, i) => { items.push({ tt: s.td, k: 1, i }); items.push({ tt: s.t1 + 1, k: 2, i }); });
    items.sort((a, b) => a.tt - b.tt || a.k - b.k || a.i - b.i);
    this.items = items;
    // row -> stop (a stop shows on the timeline once it has been detected)
    this.rowStop = p.rows.map(r => { const k = p.stops.findIndex(s => r.t >= s.t0 && r.t <= s.t1); return k; });
    // default speed: the step that plays the analysed span in about 40 s
    const L = p.span ? p.span[1] - p.span[0] + 1 : tEnd;
    let best = SPEEDS[0];
    for (const s of SPEEDS) if (Math.abs(L / s - 40) < Math.abs(L / best - 40)) best = s;
    this.speed = best;
    bus.emit('speed', this.speed);
  }

  _relabel(rerender) {
    const p = this.payload;
    const meta = p.meta;
    this.$.lens.querySelector('.lh b').textContent = t('lens.title');
    this.$.lens.querySelector('.lh span').textContent = t('lens.sub');
    this.$.tlt.textContent = t('timeline');
    this.$.leg.innerHTML = `<i class="sw m"></i>${esc(t('tl.moving'))}<i class="sw s"></i>${esc(t('tl.stopped'))}<i class="sw g"></i>${esc(t('tl.gap'))}<i class="sw l"></i>${esc(t('tl.lead'))}`;
    this.$.ct.textContent = t('console.title');
    // the device's own name for the file, as in the mockup (S000014.wfg); the full file name is in the summary footer
    const label = meta.source === 'wfg' ? `${sessionLabel(meta)}.wfg` : meta.name;
    this.$.sub.textContent = label + (meta.source === 'csv' ? ` · ${t('source.csv')}` : '');
    this.$.sub.title = meta.name;
    this.$.keys.innerHTML = keyFooter(t('keys.footer'));
    let attr = t('attrib');
    if (!meta.area || !this.areaMeta) attr = t('attrib.grid');
    else if (this.areaMeta.synthetic) attr = t('attrib.synthetic');
    this.$.attr.textContent = attr;
    const wm = meta.sim ? (meta.sim_kind === 'double' ? t('double.label') : t('sim.label')) : (meta.source === 'gpx' ? t('gpx.label') : null);
    for (const w of [this.$.wmL, this.$.wmR]) { w.classList.toggle('hidden', !wm); if (wm) w.innerHTML = watermarkHTML(wm); }
    const nofix = !p.rows.some(r => r.f);
    this.$.note.classList.toggle('hidden', !nofix);
    if (nofix) this.$.note.textContent = `${t('nopos.note')} ${p.rows.some(r => r.nr === 'RECEIVER_NO_FIX') ? t('indoor.note') : ''}`;
    if (rerender) { this._rebuildConsole(); this._render(true); }
  }

  // ------------------------------------------------------------------ controls
  play() {
    if (!this.payload) return;
    if (this.tau >= this.tEnd) this.restart(false);
    this.playing = true;
    this._last = performance.now();
    if (!this._raf) this._raf = requestAnimationFrame((ts) => this._frame(ts));
    bus.emit('replay-state', 'playing');
  }
  pause() { this.playing = false; bus.emit('replay-state', 'paused'); }
  toggle() { if (this.playing) this.pause(); else this.play(); }
  restart(autoplay = true) {
    if (!this.payload) return;
    this.tau = this.payload.rows.length ? Math.max(0, this.payload.rows[0].t) : 0;
    this.camera.reset();
    this.camera.mode = 'overview';
    this.ended = false;
    this._rebuildConsole();
    this._render(true, true);
    if (autoplay) this.play();
  }
  seek(dt) {
    if (!this.payload) return;
    this.tau = Math.min(this.tEnd, Math.max(0, this.tau + dt));
    this.ended = false;
    this._rebuildConsole();
    this._render(true, true);
  }
  faster() { const i = SPEEDS.indexOf(this.speed); this.speed = SPEEDS[Math.min(SPEEDS.length - 1, i + 1)]; bus.emit('speed', this.speed); }
  slower() { const i = SPEEDS.indexOf(this.speed); this.speed = SPEEDS[Math.max(0, i - 1)]; bus.emit('speed', this.speed); }
  toggleHex() {
    this.showAllHex = !this.showAllHex;
    this._mapToast(this.showAllHex ? t('x.on') : t('x.off'), 1500);
    this._rebuildConsole();
  }
  toggleFollow() {
    const m = this.camera.toggleFollow();
    this._mapToast(m === 'follow' ? t('follow.on') : t('follow.off'), 1500);
    this._render(true, true);
  }

  async exportSummary() {
    const p = this.payload;
    if (!p) return;
    if (!p.metrics) { toast(t('summary.no_export'), true); return; }
    toast(t('summary.exporting'), false, 60000);
    try {
      const body = p.meta.key ? { key: p.meta.key } : { file: p.meta.file };
      const r = await post('/api/export', Object.assign(body, { langs: ['ko', 'en'] }));
      toast(t('summary.exported', { path: r.dir.replace(/^.*\/out\//, 'out/') }), false, 6000);
    } catch (e) { toast(t('summary.export_failed', { err: e.message }), true, 8000); }
  }

  // ------------------------------------------------------------------ the frame loop
  _frame(ts) {
    this._raf = 0;
    if (!this.payload) return;
    const dt = Math.min(0.5, (ts - this._last) / 1000);
    this._last = ts;
    if (this.playing) {
      this.tau = Math.min(this.tEnd, this.tau + dt * this.speed);
      this._render(false);
      if (this.tau >= this.tEnd) this._end();
    }
    if (this.playing) this._raf = requestAnimationFrame((x) => this._frame(x));
  }

  _end() {
    this.playing = false;
    this.ended = true;
    bus.emit('replay-state', 'ended');
    const tr = buildTrack(this.payload.rows, this.tEnd);
    this.camera.paused = false;
    this.camera.final(tr.visible, this._cards(), this.tau);
    this.lens.show(false);
    this.view.setLensBox(null);
    setTimeout(() => { if (this.ended) bus.emit('replay-ended', this.payload); }, reducedMotion() ? 200 : 1700);
  }

  // the two cards as rects in map pixels (the close-up's rect is used only when it will show)
  _cards() {
    const mapR = this.$.map.getBoundingClientRect();
    const r1 = this.$.stats.getBoundingClientRect();
    const r2 = this.$.lens.getBoundingClientRect();
    return { stats: { x: r1.left - mapR.left, y: r1.top - mapR.top, w: r1.width, h: r1.height },
      lens: { x: r2.left - mapR.left, y: r2.top - mapR.top, w: r2.width, h: r2.height } };
  }

  _rowIndex(tau) {
    const rows = this.payload.rows;
    let lo = 0, hi = rows.length - 1, ans = -1;
    while (lo <= hi) { const m = (lo + hi) >> 1; if (rows[m].t <= tau) { ans = m; lo = m + 1; } else hi = m - 1; }
    return ans;
  }

  _activeStop(tau) {
    for (const s of this.payload.stops) if (s.td <= tau && tau <= s.t1 + 1) return s;
    return null;
  }

  _metrics(tau) {
    const p = this.payload;
    if (!p.span || !p.metrics) return null;
    const [A0, A1] = p.span;
    const elapsed = Math.min(Math.max(tau - A0 + (tau >= A0 ? 1 : 0), 0), A1 - A0 + 1);
    let n = 0, stopped = 0;
    for (const s of p.stops) if (s.td <= tau) { n++; stopped += Math.min(s.t1, tau) - s.t0 + 1; }
    let gap = 0;
    for (const g of p.gaps) if (g.t0 < tau) gap += Math.min(Math.max(tau - g.t0, 0), g.dur);
    let k = -1;
    for (let i = 0; i < p.steps.length && p.steps[i][0] <= tau; i++) k = i;
    const dist = k >= 0 ? this.cum[k] : 0;
    const moving = Math.max(0, elapsed - stopped - gap);
    return { elapsed, total: A1 - A0 + 1, dist, avg: moving > 0 ? dist / moving : null, n, stopped,
      pct: moving > 0 ? stopped / moving : null, leadin: tau < A0 };
  }

  _render(force = false, jump = false) {
    const p = this.payload;
    const tau = this.tau;
    const idx = this._rowIndex(tau);
    // stream
    this._advanceConsole(tau);
    // stats
    const m = this._metrics(tau);
    const eb = eyebrow(p.meta);
    const nofix = !p.rows.some(r => r.f);
    this.$.stats.innerHTML = statsCardHTML(m ? Object.assign({ eyebrow: eb.text, eyebrowSim: eb.sim }, m)
      : { eyebrow: eb.text, eyebrowSim: eb.sim, nomove: true, nopos: nofix });
    // track, gaps, stops (throttled to ~10 Hz while playing)
    const now = performance.now();
    if (force || now - this._lastTrack > 100) {
      this._lastTrack = now;
      const tr = buildTrack(p.rows, tau);
      this.view.setTrack(tr.segments);
      this.view.setGaps(p.gaps.filter(g => g.t1 <= tau && g.a && g.b));
      this.view.setStops(p.stops.filter(s => s.td <= tau && tau > s.t1).map(s => ({ n: s.n, lo: s.lo, la: s.la, pill: mmss(s.dur) })));
      const gl = p.gaps.filter(g => g.t1 <= tau && g.a && g.b).map(g => ({ lo: (g.a[0] + g.b[0]) / 2, la: (g.a[1] + g.b[1]) / 2, text: `   ${t('gap.label', { dur: mmss(g.dur) })}` }));
      this.view.setLabels(zoneLabels(p.zones).concat(gl));
      this._track = tr;
    }
    this._timeline();
    // current position (interpolated on screen only) and the stop in progress
    const me = idx >= 0 ? interpolate(p.rows, idx, tau) : null;
    const act = this._activeStop(tau);
    const pill = act && tau <= act.t1 ? t('stop.inprogress', { n: circled(act.n), dur: mmss(tau - act.t0 + 1) }) : null;
    const showMe = me;
    this.view.setMe(showMe, pill);
    // camera
    const stopped = !!(act && tau <= act.t1);
    const cards = this._cards();
    let pts = (this._track || { visible: [] }).visible;
    if (!pts.length && !showMe && p.zones.length) {            // nothing shown yet: frame the start zone
      const start = p.zones.filter(z => z.kind === 'start');
      pts = zoneBoxes(start.length ? start : p.zones);
    }
    if (!this.ended) this.camera.update({ points: pts, me: showMe, cards, stopped, t: tau, force: jump });
    // close-up
    const lensOn = !!showMe && this.camera.lensVisible() && !this.ended;
    if (this.testLog && lensOn !== this._lensWas) {      // test mode: every change of the close-up, with the scale it saw
      this.testLog.push({ t: tau, reason: 'lens', on: lensOn, ppm: this.camera.ppm(), me: !!showMe, mode: this.camera.mode });
      this._lensWas = lensOn;
    }
    this.lens.show(lensOn);
    if (lensOn) {
      const recent = buildTrack(p.rows, tau, tau - 90, false);
      const cloud = act && tau <= act.t1 ? p.rows.filter(r => r.f && !r.h && r.la !== null && r.t >= act.t0 && r.t <= tau).map(r => [r.lo, r.la]) : [];
      this.lens.update(showMe, recent.segments, cloud);
      this.view.setLensBox(this.camera.lensCorners(showMe));
    } else this.view.setLensBox(null);
    // header counters and progress
    const nRec = p.records.filter((r, i) => this.recT[i] <= tau).length;
    const okRec = p.records.filter((r, i) => this.recT[i] <= tau && r.ok).length;
    this.$.recs.textContent = `${t('records')} ${comma(nRec)} / ${comma(p.records.length)}`;
    if (!p.meta.has_crc) {                               // a GPX file has no record bytes: nothing to check
      this.$.crc.textContent = t('crc.none');
      this.$.crc.className = 'chip sm crc';
    } else {
      this.$.crc.textContent = `CRC ${comma(okRec)}/${comma(nRec)} ${okRec === nRec ? '✓' : '✕'}`;
      this.$.crc.className = `chip sm crc ${okRec === nRec ? 'ok' : 'bad'}`;
    }
    this.$.prog.style.width = `${(100 * tau / Math.max(1, this.tEnd)).toFixed(2)}%`;
    this._scale();
  }

  _timeline() {
    const p = this.payload;
    if (!p) return;
    const tau = this.tau;
    const rows = p.rows.map((r, i) => {
      const k = this.rowStop[i];
      let s = r.s;
      if (s === 'stop' && k >= 0 && p.stops[k].td > tau) s = 'move';
      return { t: r.t, s };
    });
    const stops = p.stops.filter(s => s.td <= tau).map(s => ({ n: s.n, t0: s.t0, t1: s.t1 }));
    const w = this.$.tl.clientWidth || this.root.clientWidth * 0.62 - 48;
    renderTimeline(this.$.tl, { rows, stops, tEnd: this.tEnd, upto: this.ended ? null : tau, utc0: p.meta.utc0, tz: p.meta.tz, width: w });
    const m = this._metrics(tau);
    if (!m) this.$.tls.textContent = t('tl.nomove');
    else if (!m.n) this.$.tls.textContent = t('tl.summary0');
    else this.$.tls.innerHTML = th(m.n === 1 ? 'tl.summary1' : 'tl.summary', { n: m.n, dur: mmss(m.stopped), pct: m.pct === null ? '-' : Math.round(m.pct * 100) });
  }

  _scale() {
    const c = this.view.getCenter();
    renderScale(this.$.scale, pxPerMetre(this.view.getZoom(), c[1]));
  }

  _mapToast(text, ms = 0) {
    const e = this.$.toast;
    clearTimeout(this._mt);
    if (!text) { e.classList.add('hidden'); return; }
    e.textContent = text;
    e.classList.remove('hidden');
    if (ms) this._mt = setTimeout(() => e.classList.add('hidden'), ms);
  }

  // ------------------------------------------------------------------ the stream
  _itemLines(it) {
    const p = this.payload;
    if (it.k === 0) {
      const r = p.records[it.i];
      return recordLines(r, p, this.showAllHex || (r.i % HEX_EVERY === 0) || !r.ok);
    }
    const s = p.stops[it.i];
    const utc0 = p.meta.utc0;
    if (it.k === 1) {
      const time = utc0 !== null && utc0 !== undefined ? clock(utc0 + s.t0 * 1000, p.meta.tz) : `+${mmss(s.t0)}`;
      const out = [[`<i class="g">▶</i> ${esc(t('stop.detected', { n: circled(s.n), time, v: p.params.v_stop, t: p.params.t_min }).replace(/^▶ /, ''))}`, 'det']];
      if (s.me) out.push([`   ${esc(t('stop.match', { k: s.me, d: Math.round(Math.abs(s.mg ?? 0)) }))}`, 'det2']);
      else if (p.validation) out.push([`   ${esc(t('stop.nomatch'))}`, 'det2']);
      return out;
    }
    return [[esc(t('stop.ended', { n: circled(s.n), dur: mmss(s.dur) })), 'det']];
  }

  _rebuildConsole() {
    this.console.clear();
    const tau = this.tau;
    let k = 0;
    while (k < this.items.length && this.items[k].tt <= tau) k++;
    this.itemPtr = k;
    const lines = [];
    for (let i = Math.max(0, k - 160); i < k; i++) for (const ln of this._itemLines(this.items[i])) lines.push(ln);
    for (const [h, c] of lines.slice(-400)) this.console.push(h, c);
  }

  _advanceConsole(tau) {
    if (this.itemPtr === undefined) this._rebuildConsole();
    let k = this.itemPtr;
    let n = 0;
    while (k < this.items.length && this.items[k].tt <= tau) {
      for (const [h, c] of this._itemLines(this.items[k])) { this.console.push(h, c); n++; }
      k++;
    }
    this.itemPtr = k;
    return n;
  }
}

// one label per group of overlapping privacy zones, inside the lower part of the circle
export function zoneLabels(zones) {
  const out = [];
  for (const z of zones) {
    if (out.some(o => Math.hypot((o.lo - z.lo) * 111320 * Math.cos(z.la * Math.PI / 180), (o.zla - z.la) * 111320) < z.r)) continue;
    out.push({ lo: z.lo, la: z.la - z.r * 0.55 / 111320, zla: z.la, text: t('zone'), cls: 'mk-zone', anchor: 'center' });
  }
  return out;
}

// corners of the zones' bounding boxes (to frame the map when every fix so far is hidden)
export function zoneBoxes(zones) {
  const out = [];
  for (const z of zones) {
    const dy = z.r / 111320, dx = z.r / (111320 * Math.cos(z.la * Math.PI / 180));
    out.push([z.lo - dx, z.la - dy], [z.lo + dx, z.la + dy]);
  }
  return out;
}

export function circled(n) {
  const c = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳';
  return n >= 1 && n <= 20 ? c[n - 1] : String(n);
}

// "Space 재생 · R 처음 · ..." -> keycaps: the key is the text before the first space of each item
export function keyFooter(text) {
  return text.split(' · ').map(item => {
    const i = item.indexOf(' ');
    const k = i > 0 ? item.slice(0, i) : item, l = i > 0 ? item.slice(i + 1) : '';
    return `<span class="k"><span class="kc">${esc(k)}</span>${esc(l)}</span>`;
  }).join('');
}

export { el, shortSha };
