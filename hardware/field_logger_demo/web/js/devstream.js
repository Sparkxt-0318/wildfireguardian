// The device stream (spec section 3C): every line the app sends (→) and receives (←), with a short note on the lines it
// understands, and the app's own lines (·). Poll replies are one short dimmed line each; identical replies in a row
// collapse into one line with a count. X shows the exact raw lines (position bytes stay masked on screen; the log file
// keeps them).
import { esc, comma, fixed, shortenShas, localClock } from './util.js';
import { t, modeName } from './i18n.js';

const MAX = 400;

export class DeviceStream {
  constructor(linesEl) {
    this.el = linesEl;
    this.raw = false;
    this.events = [];
    this.lastPoll = null;
    this.prevStatus = null;
    this.pollS = 1;
    this.cursor = document.createElement('div');
    this.cursor.className = 'ln cursor nw';
    this.cursor.innerHTML = '<span class="blk"></span>';
    this.el.appendChild(this.cursor);
    this.queue = [];
    this.raf = 0;
    // the newest line stays in view when the window or the panel changes size
    if (window.ResizeObserver) new ResizeObserver(() => { this.el.scrollTop = this.el.scrollHeight; }).observe(this.el);
  }

  setRaw(on) { this.raw = on; this.rebuild(); }

  // The session ended and its end zone hides more: lines already shown are masked again (never unmasked).
  remask(lines) {
    const byN = new Map(lines.map(l => [l.n, l.raw]));
    for (const ev of this.events) if (byN.has(ev.n)) ev.raw = byN.get(ev.n);
    for (const d of this.el.querySelectorAll('.ln[data-n]')) {
      const n = Number(d.dataset.n);
      if (!byN.has(n)) continue;
      const ev = this.events.find(e => e.n === n);
      if (ev) d.innerHTML = this._html(ev);
    }
  }

  load(events) { this.events = events.slice(-MAX); this.rebuild(); }

  rebuild() {
    this.el.innerHTML = '';
    this.el.appendChild(this.cursor);
    this.lastPoll = null;
    this.prevStatus = null;
    for (const ev of this.events) this._add(ev, false);
    this.el.scrollTop = this.el.scrollHeight;
  }

  add(ev) {
    this.events.push(ev);
    if (this.events.length > MAX * 1.5) this.events = this.events.slice(-MAX);
    this.queue.push(ev);
    if (!this.raf) this.raf = requestAnimationFrame(() => { this.raf = 0; const q = this.queue.splice(0); for (const e of q) this._add(e, true); });
  }

  _add(ev, anim) {
    if (ev.cls === 'poll' && !this.raw) {
      const kind = ev.poll;
      const last = this.cursor.previousElementSibling;
      if (ev.same && last && last.dataset.poll === kind && this.lastPoll && this.lastPoll.kind === kind) {
        this.lastPoll.n += 1;
        last.querySelector('.t').textContent = localClock(ev.ts);
        const c = last.querySelector('.cnt');
        c.textContent = `  ×${this.lastPoll.n}`;
        if (kind === 'STATUS') this.prevStatus = ev.fields;
        this.el.scrollTop = this.el.scrollHeight;
        return;
      }
    }
    const d = document.createElement('div');
    const html = this._html(ev);
    if (html === null) return;
    d.className = `ln ${ev.cls}${anim ? '' : ' noanim'}`;
    d.innerHTML = html;
    if (ev.cls === 'live' || ev.cls === 'nmea') d.dataset.n = ev.n;
    if (ev.cls === 'poll') { d.dataset.poll = ev.poll; this.lastPoll = { kind: ev.poll, n: 1 }; } else this.lastPoll = null;
    this.el.insertBefore(d, this.cursor);
    let extra = this.el.childElementCount - 1 - MAX;
    while (extra-- > 0) this.el.removeChild(this.el.firstChild);
    this.el.scrollTop = this.el.scrollHeight;
  }

  _prefix(ev) { return `<i class="t">${esc(localClock(ev.ts))}</i>  <i class="dir">${esc(ev.dir)}</i>  `; }

  _html(ev) {
    const pre = this._prefix(ev);
    if (this.raw) {
      if (ev.dir === '·') return pre + esc(appText(ev));
      return pre + esc(ev.raw);
    }
    switch (ev.cls) {
      case 'poll': return pre + this._poll(ev) + '<i class="cnt"></i>';
      case 'rec': return pre + this._rec(ev);
      case 'live': return pre + esc(liveText(ev.raw));
      case 'nmea': return pre + esc(ev.raw);
      default: break;
    }
    if (ev.dir === '·') {
      const ok = ev.cls === 'ok' ? '  <i class="g">✓</i>' : '';
      const text = appText(ev);
      // a LIVE stop: the green ▶ of the REPLAY console (spec 6.9)
      if (ev.code === 'live_stop' && text.startsWith('▶ ')) return `${pre}<i class="g">▶</i> ${esc(text.slice(2))}${ok}`;
      return pre + esc(text) + ok;
    }
    const note = ev.note ? noteText(ev.note, ev.args || [], this.pollS) : '';
    return pre + esc(shortenShas(ev.raw)) + (note ? `   <i class="nt">${esc(note)}</i>` : '');
  }

  _poll(ev) {
    const f = ev.fields || {};
    if (ev.poll === 'STATUS') {
      const p = this.prevStatus || {};
      const b = (k, txt) => (p[k] !== f[k] ? `<b>${esc(txt)}</b>` : esc(txt));
      this.prevStatus = f;
      return `STATUS  ${b('state', f.state)} · ${b('session', f.session || '-')} · ${b('seq', `seq ${f.seq}`)} · ${b('free', `free ${comma(f.free)}`)}`;
    }
    const mv = f.vbat_mv !== undefined && f.vbat_mv !== null && f.vbat_mv >= 0 ? `${comma(f.vbat_mv)} mV` : t('tile.no_value');
    return `VBAT  <b>${esc(mv)}</b> · pin ${esc(comma(f.pin_mv))} mV · cal ${esc(f.cal || '-')}`;
  }

  _rec(ev) {
    const r = ev.rec || {};
    if (r.type === 'TORN') {
      const tx = (ev.raw.split(' ')[1] || '');
      return `T     <i class="hx">${esc(tx.slice(0, 8))} ${esc(tx.slice(8, 16))} …</i>  ${esc(t('recnote.TORN', { n: r.n_bytes }))}`;
    }
    const m = /^R (\d+) ([0-9a-fx]+)/.exec(ev.raw);
    const idx = m ? m[1] : r.i;
    const hx = m ? m[2] : '';
    const head = `R ${String(idx).padEnd(3, ' ')} <i class="hx">${esc(hx.slice(0, 8))} ${esc(hx.slice(8, 16))} …</i>  `;
    return head + esc(recNote(r));
  }
}

export function recNote(r) {
  switch (r.type) {
    case 'START': return t('recnote.START', { mode: modeName(r.mode) });
    case 'FIX': return t('recnote.FIX', { ft: r.ft || '' });
    case 'NOFIX': return t('recnote.NOFIX', { reason: t(`nofix.${r.nr || 'UNKNOWN'}`) });
    case 'EVENT': return t('recnote.EVENT', { n: r.n, loc: r.loc ? t('test.loc_yes') : t('test.loc_no') });
    case 'STATUS': return r.vb ? t('recnote.STATUS', { mv: comma(r.vb), n: comma(r.nmea) }) : t('recnote.STATUS_nobatt', { n: comma(r.nmea) });
    case 'END': return t('recnote.END', { reason: r.er || '-' });
    case 'CLOCK': return t('recnote.CLOCK', { kind: r.kind || '' });
    case 'CORRUPT': return t('recnote.CORRUPT');
    default: return t('recnote.UNKNOWN');
  }
}

export function appText(ev) {
  const a = Object.assign({}, ev.args || {});
  if (ev.code === 'cc_restart_other' && a.what) a.what = t(`what.${a.what}`);
  if (ev.code === 'cc_done') { a.method = a.method && a.method !== '-' ? t(`cc.method.${a.method}`) : '-'; }
  if (ev.code === 'port_likely' && !a.chip) return t('stream.port_likely', a).replace(' ·  · ', ' · ');
  const key = `stream.${ev.code}`;
  const s = t(key, a);
  return s === key ? (ev.text || ev.code) : s;
}

export function noteText(code, g, pollS = 1) {
  const strip = (s) => String(s || '').replace(/\.wfg$/, '');
  switch (code) {
    case 'rec': return t('note.rec', { s: strip(g[0]), m: modeName(g[1]) });
    case 'event': return g[1] === 'marked' ? t('note.event_marked', { n: g[0] }) : t('note.event_nopos', { n: g[0] });
    case 'mode': return t('note.mode', { m: modeName(g[0]) });
    case 'resume_decision': return t('note.resume_decision', { d: g[0] });
    case 'recovered_detail': return t('note.recovered_detail', { s: strip(g[0]) });
    case 'basic': return t('note.basic', { s: pollS });
    default: {
      const k = `note.${code}`;
      const s = t(k);
      return s === k ? '' : s;
    }
  }
}

// '#J {...}' in short form (X shows the raw line)
export function liveText(raw) {
  let o;
  try { o = JSON.parse(raw.slice(3)); } catch (e) { return raw; }
  switch (o.t) {
    case 'ep': {
      const fix = o.fix ? `FIX ${o.ft || ''} · ${t('sats')} ${o.su ?? '-'} · HDOP ${o.hd ?? '-'}` : `${t('fix.none')} · ${t(`nofix.${o.nr || 'UNKNOWN'}`)}`;
      return `#J ep  ${fix} · ${o.rs}`;
    }
    case 'rec': return `#J rec  #${o.seq} · ${recTypeName(o.ty)} · ${comma(o.b)} B`;
    case 'st': return `#J st  ${o.vb ? `${comma(o.vb)} mV` : t('tile.no_value')} · ${fixed((o.ff || 0) / 1e6, 2)} MB`;
    case 'ev': return `#J ev  ${o.loc ? t('event.mark_loc', { k: o.n }) : t('event.mark_noloc', { k: o.n })}`;
    case 'ss': return `#J ss  S${String(o.ss).padStart(6, '0')} · ${modeName(o.md)} · ${o.sr}`;
    case 'se': return `#J se  S${String(o.ss).padStart(6, '0')} · ${o.er} · ${comma(o.n)}`;
    case 'drop': return `#J drop  ${o.n}`;
    default: return raw;
  }
}

function recTypeName(ty) { return { 1: 'SESSION_START', 2: 'FIX', 3: 'NOFIX', 4: 'EVENT', 5: 'CLOCK', 6: 'SESSION_END', 7: 'STATUS' }[ty] || String(ty); }
