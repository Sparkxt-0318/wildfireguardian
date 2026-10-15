// The log stream on the right (REPLAY): the records as they pass, decoded by the backend from the .wfg bytes, plus the
// detector's lines. At most 400 lines in the page; updates are batched per animation frame so x60 stays smooth.
import { esc, comma, fixed, clock, mmss } from './util.js';
import { t, modeName } from './i18n.js';

export const MAX_LINES = 400;

export class LogConsole {
  constructor(linesEl) {
    this.el = linesEl;
    this.queue = [];
    this.raf = 0;
    this.cursor = document.createElement('div');
    this.cursor.className = 'ln cursor nw';
    this.cursor.innerHTML = '<span class="blk"></span>';
    this.el.appendChild(this.cursor);
  }

  clear() {
    this.queue = [];
    this.el.innerHTML = '';
    this.el.appendChild(this.cursor);
  }

  push(html, cls = '', wrap = true) { this.queue.push([html, cls, wrap]); this._schedule(); }

  _schedule() {
    if (this.raf) return;
    this.raf = requestAnimationFrame(() => { this.raf = 0; this.flush(); });
  }

  flush() {
    if (!this.queue.length) return;
    const items = this.queue.splice(0, this.queue.length).slice(-MAX_LINES);
    const frag = document.createDocumentFragment();
    for (const [html, cls, wrap] of items) {
      const d = document.createElement('div');
      d.className = `ln ${cls}${wrap ? '' : ' nw'}`;
      d.innerHTML = html;
      frag.appendChild(d);
    }
    this.el.insertBefore(frag, this.cursor);
    let extra = this.el.childElementCount - 1 - MAX_LINES;
    while (extra-- > 0) this.el.removeChild(this.el.firstChild);
  }
}

// ------------------------------------------------------------------ one record of the replay as console lines
export function timeCell(r, meta) {
  if (r.u !== null && r.u !== undefined) return clock(r.u, meta.tz);
  return r.t !== null && r.t !== undefined ? `+${mmss(r.t)}`.padStart(8, ' ') : '--:--:--';
}

export function hexLines(hx) {
  if (!hx) return [];
  const g = [];
  for (let i = 0; i < 96; i += 8) g.push(hx.slice(i, i + 8));
  return [`      ${g.slice(0, 6).join(' ')}`, `      ${g.slice(6).join(' ')}  crc32 ${hx.slice(88, 96).match(/../g).reverse().join('')}`];
}

// rec: payload record; row: payload row (for FIX/NOFIX); ev: payload event; returns [[html, cls], ...]
export function recordLines(rec, payload, showHex) {
  const meta = payload.meta;
  const tc = `<i class="t">${esc(timeCell(rec, meta))}</i>`;
  const sq = `<i class="q">#${String(rec.sq ?? rec.i).padStart(4, '0')}</i>`;
  const out = [];
  if (rec.sg) {             // [last readable seq, this seq, records missing]: reported, never repaired
    const [a, b, n] = rec.sg;
    const txt = n > 0 ? t('console.seq_gap', { a: `#${String(a).padStart(4, '0')}`, b: `#${String(b).padStart(4, '0')}`, n: comma(n) })
      : t('console.seq_order', { a: `#${String(a).padStart(4, '0')}`, b: `#${String(b).padStart(4, '0')}` });
    out.push([`${tc}  ${esc(txt)}`, 'corrupt seqgap']);
  }
  if (!rec.ok) {
    out.push([`${tc}  <i class="q">#${String(rec.i).padStart(4, '0')}</i>  ${esc(t('console.corrupt'))}`, 'corrupt']);
    for (const h of hexLines(rec.hx)) out.push([esc(h), 'corrupt']);
    return out;
  }
  if (rec.ty === 'FIX' || rec.ty === 'NOFIX') {
    const row = rec.row !== undefined && rec.row !== null ? payload.rows[rec.row] : null;
    if (rec.ty === 'FIX' && row) {
      const coords = row.h ? esc(t('console.hidden')) : `${fixed(row.la, 7)}, ${fixed(row.lo, 7)}`;
      const sats = row.n === null || row.n === undefined ? '--' : String(row.n).padStart(2, ' ');
      const hd = row.hd === null || row.hd === undefined ? '--' : fixed(row.hd, 1);
      const sp = row.v === null || row.v === undefined ? '' : `  ${fixed(row.v, 2)} m/s`;
      const ok = meta.has_crc === false ? '' : '  <i class="g">✓</i>';      // the CRC tick; a GPX point has none
      out.push([`${tc}  ${sq}  <i class="g">FIX ${esc(row.ft || '')}</i>  ${esc(t('console.sats'))} ${sats}  HDOP ${hd}  ${coords}${sp}${ok}`, 'fix']);
    } else {
      const reason = t(`nofix.${(row && row.nr) || 'UNKNOWN'}`);
      out.push([`${tc}  ${sq}  ${esc(t('console.nofix', { reason }))}`, 'nofix']);
    }
  } else if (rec.ty === 'STATUS') {
    const mb = rec.ff !== null && rec.ff !== undefined ? fixed(rec.ff / 1e6, 2) : '-';
    const txt = rec.vb ? t('status.line', { mv: comma(rec.vb), mb }) : t('status.line_nobatt', { mb });
    out.push([`${tc}  ${sq}  STATUS  ${esc(txt)}`, 'status']);
  } else if (rec.ty === 'EVENT') {
    const ev = rec.ev !== undefined && rec.ev !== null ? payload.events[rec.ev] : null;
    const k = ev ? ev.en : '?';
    const txt = ev && ev.lc ? t('event.mark_loc', { k }) : t('event.mark_noloc', { k });
    out.push([`${tc}  ${sq}  EVENT   ${esc(txt)}`, 'event']);
  } else if (rec.ty === 'START') {
    out.push([`${tc}  ${sq}  ${esc(t('console.start', { mode: modeName(meta.mode), reason: t(`start.${meta.start_reason || 'OWNER_BUTTON'}`) }))}`, 'status']);
  } else if (rec.ty === 'END') {
    out.push([`${tc}  ${sq}  ${esc(t('console.end', { reason: meta.end_reason || '-' }))}`, 'status']);
  } else if (rec.ty === 'CLOCK') {
    const txt = rec.ck === 'JUMP' ? t('console.clock_jump', { d: comma(rec.cd) }) : t('console.clock');
    out.push([`${tc}  ${sq}  ${esc(txt)}`, 'status']);
  }
  if (showHex) for (const h of hexLines(rec.hx)) out.push([esc(h), 'hex']);
  return out;
}
