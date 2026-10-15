// The white summary (spec section 9): shown at the end of a replay and, in export mode (?export=summary&key=..&lang=..),
// rendered at 1600 x 1000 for headless Chromium to save as summary_ko.png / summary_en.png (3200 x 2000). Every number
// comes from the same payload the backend writes to summary.json.
import { esc, mmss, comma, fixed, shortSha, clock, dateTimeLong } from './util.js';
import { t, getLang, modeName } from './i18n.js';
import { MapView, pxPerMetre } from './mapview.js';
import { fitView } from './camera.js';
import { renderTimeline } from './timeline.js';
import { buildTrack, renderScale, watermarkHTML } from './trackview.js';
import { sessionLabel, keyFooter, zoneLabels } from './replay.js';

const NORTH = '<svg width="14" height="18" viewBox="-7 -10 14 18"><path d="M0,-10 L5.5,7 L0,3.5 L-5.5,7 Z"/></svg>';
const MAX_ROWS = 8;

// The footer says what the map hides: the start and end areas, places marked private, both, or nothing.
function privacyNote(zones) {
  const auto = zones.some(z => z.kind === 'start' || z.kind === 'end');
  const named = zones.some(z => z.kind === 'named');
  if (auto && named) return t('privacy.note_both');
  if (auto) return t('privacy.note');
  if (named) return t('privacy.note_named');
  return t('privacy.note_off');
}

export class Summary {
  constructor(root, opts = {}) {
    this.root = root;
    this.exportMode = !!opts.exportMode;
    root.innerHTML = `<div class="sumwrap"><div class="summary"></div><div class="sumbar"></div></div>`;
    this.page = root.querySelector('.summary');
    this.bar = root.querySelector('.sumbar');
    this.view = null;
    window.addEventListener('resize', () => this.fit());
  }

  fit() {
    if (this.exportMode) return;
    const w = this.root.clientWidth, h = this.root.clientHeight;
    const s = Math.min(w / 1600, (h - 20) / 1000, 1.4);
    this.page.style.transform = `scale(${s.toFixed(4)})`;
  }

  title(p) {
    const lang = getLang();
    const m = p.meta;
    return (lang === 'ko' ? m.title_ko : m.title_en) || `${modeName(m.mode)} · ${sessionLabel(m)}`;
  }

  async render(p) {
    this.p = p;
    const m = p.meta, M = p.metrics;
    const lang = getLang();
    const pct = M && M.pct_added !== null ? Math.round(M.pct_added * 100) : null;
    const stops = p.stops;
    const tiles = M ? [
      [`${fixed(M.distance / 1000, 2)} km`, t('distance')], [mmss(M.moving), t('moving')],
      [`${M.avg_speed === null ? '-' : fixed(M.avg_speed, 2)} m/s`, t('avg')],
      [t('stats.count', { n: stops.length, d: mmss(M.stopped) }), t('stops')], [mmss(M.longest), t('longest')], [mmss(M.gap), t('gap')],
    ] : [];
    const tz = m.tz;
    const at = (tt) => (m.utc0 !== null && m.utc0 !== undefined ? clock(m.utc0 + tt * 1000, tz) : `+${mmss(tt)}`);
    const shown = stops.slice(0, MAX_ROWS);
    const rows = shown.map(s => `<tr><td><span class="num">${esc(s.n)}</span></td><td>${esc(at(s.t0))}${s.h ? ` <span class="zt">· ${esc(t('zone.stop'))}</span>` : ''}</td>`
      + `<td><b>${esc(mmss(s.dur))}</b></td><td class="${s.me ? 'okt' : ''}">${esc(p.validation ? (s.me ? t('summary.match', { k: s.me }) : t('summary.nomatch')) : '-')}</td></tr>`).join('');
    const more = stops.length > MAX_ROWS ? `<tr><td colspan="4" class="more">+${stops.length - MAX_ROWS}</td></tr>` : '';
    const par = p.params;
    const v = p.validation;
    const sens = p.sensitivity;
    const gpx = m.source === 'gpx';                       // no record bytes, so no CRC to claim
    const nBad = gpx ? 0 : m.n_rec - m.crc_ok;
    let source;
    if (gpx) source = t('summary.source_gpx', { file: m.name, hash: shortSha(m.sha256), n: comma(m.n_rec) });
    else if (nBad) source = t('summary.source_bad', { file: m.name, hash: shortSha(m.sha256), dev: m.device, n: comma(m.n_rec), bad: comma(nBad) });
    else source = t('summary.source', { file: m.name, hash: shortSha(m.sha256), dev: m.device, n: comma(m.n_rec) });
    if (m.seq_breaks) source += ` · ${t('summary.source_seq', { g: comma(m.seq_breaks), n: comma(m.seq_missing) })}`;
    const span = p.span ? mmss(p.span[1] - p.span[0] + 1) : '-';
    const simMark = m.sim ? t('summary.sim_mark') : (gpx ? t('summary.gpx_mark') : '');
    const wmText = m.sim ? (m.sim_kind === 'double' ? t('double.label') : t('sim.label')) : (gpx ? t('gpx.label') : null);
    this.page.innerHTML = `
      <div class="head">
        <div><div class="eyebrow-l">${esc(t('summary.eyebrow'))}</div><h1>${esc(this.title(p))}</h1>
          <div class="sub-l">${esc(t('summary.sub', { date: dateTimeLong(m.utc0, tz, lang), session: sessionLabel(m), a: span }))}</div></div>
        <div class="herom"><div class="pct">${pct === null ? '-' : `+${pct}%`}</div><div class="hc">${esc(t('summary.hero'))}</div>
          <div class="hs">${M ? esc(t('summary.hero_sub', { s: mmss(M.stopped), m: mmss(M.moving) })) : ''}</div></div>
      </div>
      <div class="body">
        <div class="mapcard"><div class="ml"></div><div class="north">${NORTH}</div><div class="scalebar"></div><div class="attr"></div></div>
        <div class="side">
          <div class="tiles">${tiles.map(([a, b]) => `<div class="tile"><b>${esc(a)}</b><span>${esc(b)}</span></div>`).join('')}</div>
          <table class="st"><tr><th>${esc(t('summary.th_no'))}</th><th>${esc(t('summary.th_start'))}</th><th>${esc(t('summary.th_dur'))}</th><th>${esc(t('summary.th_mark'))}</th></tr>${rows}${more}</table>
          <div class="method"><div class="eyebrow-l">${esc(t('summary.method'))}</div>
            <p>${esc(t('summary.rule', { v: par.v_stop, t: par.t_min, r: par.r_max }))}</p>
            <p>${esc(v ? t('validation', { m: v.presses, d: v.detected, k: v.matched, g: v.median_gap === null ? '-' : Math.round(Math.abs(v.median_gap)) }) : t('validation.none'))}</p>
            <p>${esc(!sens ? '' : (sens.stops_min === sens.stops_max && Math.floor(sens.stopped_min) === Math.floor(sens.stopped_max)
              ? t('sensitivity.same', { a: sens.stops_min, c: mmss(sens.stopped_min) })
              : t('sensitivity', { a: sens.stops_min, b: sens.stops_max, c: mmss(sens.stopped_min), d: mmss(sens.stopped_max) })))}</p></div>
        </div>
      </div>
      <div class="tlw"><div class="tlh-l"><span class="eyebrow-l">${esc(t('timeline'))}</span><span class="leg-l"><i class="sw m"></i>${esc(t('tl.moving'))}<i class="sw s"></i>${esc(t('tl.stopped'))}<i class="sw g"></i>${esc(t('tl.gap'))}<i class="sw l"></i>${esc(t('tl.lead'))}</span></div><div class="tlhost"></div></div>
      <div class="foot"><span>${esc(source)}</span><span>${esc(t('n1.note'))}</span><span>${esc(privacyNote(p.zones))}</span><span class="mk">${esc(simMark)}</span></div>
      ${wmText ? `<div class="wm">${watermarkHTML(wmText)}</div>` : ''}`;
    this.bar.innerHTML = keyFooter(t('keys.summary'));
    renderTimeline(this.page.querySelector('.tlhost'), { rows: p.rows.map(r => ({ t: r.t, s: r.s })), stops: p.stops,
      tEnd: Math.max(m.t_end, ...p.rows.map(r => r.t)), upto: null, utc0: m.utc0, tz, width: 1504, height: 78 });
    this.fit();
    await this._map(p);
  }

  async _map(p) {
    const host = this.page.querySelector('.mapcard .ml');
    if (this.view) { try { this.view.remove(); } catch (e) { /* already gone */ } }
    this.view = new MapView(host, { interactive: false, exportMode: this.exportMode });
    const meta = await this.view.setArea(p.meta.area, p.bounds);
    const attr = this.page.querySelector('.attr');
    attr.textContent = !meta ? t('attrib.grid') : (meta.synthetic ? t('attrib.synthetic') : t('attrib'));
    const tr = buildTrack(p.rows, Infinity);
    this.view.setTrack(tr.segments);
    this.view.setGaps(p.gaps.filter(g => g.a && g.b));
    this.view.setZones(p.zones);
    const labels = zoneLabels(p.zones);
    for (const g of p.gaps) if (g.a && g.b) labels.push({ lo: (g.a[0] + g.b[0]) / 2, la: (g.a[1] + g.b[1]) / 2, text: `   ${t('gap.label', { dur: mmss(g.dur) })}` });
    this.view.setLabels(labels);
    this.view.setStops(p.stops.map(s => ({ n: s.n, lo: s.lo, la: s.la, pill: mmss(s.dur) })));
    const pts = tr.visible.concat(p.stops.filter(s => s.la !== null).map(s => [s.lo, s.la]));
    if (pts.length) {
      const v = fitView(pts, { w: 902, h: 618 }, { l: 70, t: 70, r: 70, b: 70 });
      this.view.jump(v.center, v.zoom);
      renderScale(this.page.querySelector('.mapcard .scalebar'), pxPerMetre(v.zoom, v.center[1]));
    }
    this.view.resize();
    await this.view.idle();
    this.view.declutter();
  }
}
