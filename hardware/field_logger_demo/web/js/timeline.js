// Timeline under the map (dark) and on the summary (light): moving / stopped / position gap / not analysed, stop
// numbers above their spans, clock ticks in the session's time zone, and a playhead while replaying.
import { esc, hhmm, clock, mmss } from './util.js';

const NS = 'http://www.w3.org/2000/svg';
let uid = 0;

function niceTick(spanS) {
  const cands = [10, 15, 30, 60, 120, 240, 300, 600, 900, 1800, 3600, 7200];
  for (const c of cands) if (spanS / c <= 7) return c;
  return 7200;
}

// rows: [{t, s}] (s: lead | move | stop | gap), stops: [{n, t0, t1}], tEnd: last t, upto: replay time or null
export function renderTimeline(host, { rows, stops, tEnd, upto = null, utc0 = null, tz, width, height = 86 }) {
  const W = Math.max(200, width || host.clientWidth || 900);
  const H = height;
  const yb = 40, hb = 8;
  const total = Math.max(1, tEnd + 1);
  const sx = (t) => W * Math.min(Math.max(t, 0), total) / total;
  const lim = upto === null ? total : upto;
  const id = `tl${++uid}`;
  const o = [];
  o.push(`<defs><pattern id="${id}g" width="4" height="8" patternUnits="userSpaceOnUse"><rect width="4" height="8" class="tlf"/><rect width="2" height="8" class="tlgp"/></pattern>`
    + `<clipPath id="${id}c"><rect x="0" y="${yb}" width="${W}" height="${hb}" rx="4"/></clipPath></defs>`);
  o.push(`<rect x="0" y="${yb}" width="${W}" height="${hb}" rx="4" class="tlf"/>`);
  o.push(`<g clip-path="url(#${id}c)">`);
  // runs of states up to the playhead
  let i = 0;
  while (i < rows.length && rows[i].t <= lim) {
    const st = rows[i].s;
    let j = i;
    while (j + 1 < rows.length && rows[j + 1].s === st && rows[j + 1].t <= lim) j++;
    const a = rows[i].t;
    const b = Math.min(j + 1 < rows.length ? rows[j + 1].t : total, lim);
    const x = sx(a), w = Math.max(0.6, sx(b) - x);
    if (st === 'gap') o.push(`<rect x="${x.toFixed(1)}" y="${yb}" width="${w.toFixed(1)}" height="${hb}" fill="url(#${id}g)"/>`);
    else o.push(`<rect x="${x.toFixed(1)}" y="${yb}" width="${w.toFixed(1)}" height="${hb}" class="tl-${st}"/>`);
    i = j + 1;
  }
  o.push('</g>');
  for (const s of stops) {
    if (s.t0 > lim) continue;
    const cx = (sx(s.t0) + sx(Math.min(s.t1, lim))) / 2;
    o.push(`<text x="${cx.toFixed(1)}" y="${yb - 9}" class="tln">${esc(s.n)}</text>`);
  }
  const step = niceTick(total);
  if (utc0 !== null && utc0 !== undefined) {
    const first = Math.ceil((utc0 / 1000) / step) * step;
    for (let u = first; (u - utc0 / 1000) <= total; u += step) {
      const t = u - utc0 / 1000;
      const x = sx(t);
      if (x < 18 || x > W - 18) continue;
      o.push(`<text x="${x.toFixed(1)}" y="${yb + hb + 20}" class="tick">${esc(step < 60 ? clock(u * 1000, tz) : hhmm(u * 1000, tz))}</text>`);
    }
  } else {
    for (let t = step; t < total; t += step) {
      const x = sx(t);
      if (x > W - 18) continue;
      o.push(`<text x="${x.toFixed(1)}" y="${yb + hb + 20}" class="tick">+${esc(mmss(t))}</text>`);
    }
  }
  if (upto !== null && upto < total) {
    const px = sx(upto);
    const lab = utc0 !== null && utc0 !== undefined ? clock(utc0 + upto * 1000, tz) : `+${mmss(upto)}`;
    const bx = Math.min(Math.max(px + 6, 0), W - 70);
    o.push(`<line x1="${px.toFixed(1)}" y1="${yb - 14}" x2="${px.toFixed(1)}" y2="${yb + hb + 6}" class="ph"/>`);
    o.push(`<rect x="${bx.toFixed(1)}" y="${yb - 32}" width="66" height="20" rx="10" class="phb"/>`);
    o.push(`<text x="${(bx + 33).toFixed(1)}" y="${yb - 18}" class="pht">${esc(lab)}</text>`);
  }
  host.innerHTML = `<svg class="tlsvg" xmlns="${NS}" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${o.join('')}</svg>`;
}
