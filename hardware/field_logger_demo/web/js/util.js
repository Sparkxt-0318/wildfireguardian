// Small helpers shared by every module: DOM building, formatting, time zones, the event bus.

export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

export function $(sel, root = document) { return root.querySelector(sel); }
export function $$(sel, root = document) { return Array.from(root.querySelectorAll(sel)); }

export function el(tag, attrs = {}, html = '') {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k.startsWith('on') && typeof v === 'function') e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  if (html) e.innerHTML = html;
  return e;
}

// ------------------------------------------------------------------ numbers and durations
export function comma(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return '-';
  return Math.round(n).toLocaleString('en-US');
}

export function fixed(n, d = 2) {
  if (n === null || n === undefined || Number.isNaN(n)) return '-';
  return Number(n).toFixed(d);
}

// 1:22, 22:51, 1:04:07 (seconds rounded down: durations are whole rows)
export function mmss(s) {
  if (s === null || s === undefined || Number.isNaN(s)) return '-';
  s = Math.max(0, Math.floor(s + 1e-6));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}` : `${m}:${String(sec).padStart(2, '0')}`;
}

export function km(m) { return m >= 1000 ? `${fixed(m / 1000, 2)} km` : `${Math.round(m)} m`; }

export function shortSha(sha) { return sha && sha.length > 12 ? `${sha.slice(0, 6)}…${sha.slice(-4)}` : (sha || '-'); }

export function shortenShas(text) { return text.replace(/\b([0-9a-f]{64})\b/g, (m) => shortSha(m)); }

// ------------------------------------------------------------------ time zones (times are shown in the session's own zone)
const fmtCache = new Map();
function fmt(tz, opts, lang) {
  const key = `${tz}|${lang}|${JSON.stringify(opts)}`;
  if (!fmtCache.has(key)) {
    try { fmtCache.set(key, new Intl.DateTimeFormat(lang === 'ko' ? 'ko-KR' : 'en-US', Object.assign({ timeZone: tz }, opts))); }
    catch (e) { fmtCache.set(key, new Intl.DateTimeFormat(lang === 'ko' ? 'ko-KR' : 'en-US', opts)); }
  }
  return fmtCache.get(key);
}

export function parts(ms, tz) {
  const p = {};
  for (const x of fmt(tz, { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }, 'en').formatToParts(new Date(ms))) p[x.type] = x.value;
  return { y: +p.year, mo: +p.month, d: +p.day, h: +p.hour % 24, mi: +p.minute, s: +p.second };
}

export function clock(ms, tz) {
  if (ms === null || ms === undefined) return '--:--:--';
  const p = parts(ms, tz);
  return `${String(p.h).padStart(2, '0')}:${String(p.mi).padStart(2, '0')}:${String(p.s).padStart(2, '0')}`;
}

export function hhmm(ms, tz) {
  if (ms === null || ms === undefined) return '--:--';
  const p = parts(ms, tz);
  return `${String(p.h).padStart(2, '0')}:${String(p.mi).padStart(2, '0')}`;
}

const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
// "10월 14일 16:05" / "Oct 14, 16:05"
export function dateTime(ms, tz, lang) {
  if (ms === null || ms === undefined) return '-';
  const p = parts(ms, tz);
  const t = `${String(p.h).padStart(2, '0')}:${String(p.mi).padStart(2, '0')}`;
  return lang === 'ko' ? `${p.mo}월 ${p.d}일 ${t}` : `${MON[p.mo - 1]} ${p.d}, ${t}`;
}
// "2026년 10월 14일 16:05" / "Oct 14, 2026, 16:05"
export function dateTimeLong(ms, tz, lang) {
  if (ms === null || ms === undefined) return '-';
  const p = parts(ms, tz);
  const t = `${String(p.h).padStart(2, '0')}:${String(p.mi).padStart(2, '0')}`;
  return lang === 'ko' ? `${p.y}년 ${p.mo}월 ${p.d}일 ${t}` : `${MON[p.mo - 1]} ${p.d}, ${p.y}, ${t}`;
}
export function dateOnly(ms, tz, lang) {
  if (ms === null || ms === undefined) return '-';
  const p = parts(ms, tz);
  return lang === 'ko' ? `${p.mo}월 ${p.d}일` : `${MON[p.mo - 1]} ${p.d}`;
}
export function localClock(ms) {
  const d = new Date(ms);
  return [d.getHours(), d.getMinutes(), d.getSeconds()].map(v => String(v).padStart(2, '0')).join(':');
}

// ------------------------------------------------------------------ geometry (Web Mercator, 512 px tiles)
export const R_EARTH = 6371008.8;
export function haversine(lat1, lon1, lat2, lon2) {
  const r = Math.PI / 180;
  const dp = (lat2 - lat1) * r, dl = (lon2 - lon1) * r;
  const a = Math.sin(dp / 2) ** 2 + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(dl / 2) ** 2;
  return 2 * R_EARTH * Math.asin(Math.min(1, Math.sqrt(a)));
}
// circle as a GeoJSON ring (for privacy zones; no symbol layers needed)
export function circleRing(lon, lat, radiusM, n = 96) {
  const out = [];
  const ky = Math.PI * R_EARTH / 180, kx = ky * Math.cos(lat * Math.PI / 180);
  for (let i = 0; i <= n; i++) {
    const a = 2 * Math.PI * i / n;
    out.push([lon + radiusM * Math.cos(a) / kx, lat + radiusM * Math.sin(a) / ky]);
  }
  return out;
}

// ------------------------------------------------------------------ tiny event bus
const handlers = new Map();
export const bus = {
  on(ev, fn) { if (!handlers.has(ev)) handlers.set(ev, new Set()); handlers.get(ev).add(fn); return () => handlers.get(ev).delete(fn); },
  emit(ev, data) { for (const fn of handlers.get(ev) || []) { try { fn(data); } catch (e) { console.error(ev, e); } } },
};

export function reducedMotion() { return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches; }

export function cssVar(name, root = document.body) { return getComputedStyle(root).getPropertyValue(name).trim(); }

let toastTimer = null;
export function toast(text, err = false, ms = 3500) {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = text;
  t.className = 'toast' + (err ? ' err' : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add('off'), ms);
}
