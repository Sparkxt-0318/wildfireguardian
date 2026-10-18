'use strict';
// scene units: every region is drawn at the same size (SF scene units per km), so camera, fog and lights are shared
const [W, S, E, N] = B.bbox, [KXr, KYr] = B.km, SF = 27.6 / Math.max(KXr, KYr), KX = KXr * SF, KY = KYr * SF;
const LON_C = (W + E) / 2, LAT_C = (S + N) / 2;
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
const $ = id => document.getElementById(id);

// ---------------- time ----------------
const T0 = Math.min(...B.footprints.map(f => Date.parse(f.time)), ...B.input_times.map(t => Date.parse(t)));
const hOf = iso => (Date.parse(iso) - T0) / 3.6e6;
const REC = B.footprints.map(f => hOf(f.time));            // recorded footprint times (h)
const INP = B.input_times.map(hOf);                         // model input times (h)
const TMAX = Math.ceil(Math.max(...REC, ...INP.map(h => h + 1), ...B.routes.filter(r => r.arr != null).map(r => hOf(r.input_time) + r.arr / 3600)) + 1);
const H0 = (new Date(T0).getUTCHours() + 9) % 24;          // KST hour at t = 0
const kst = h => new Date(T0 + (h + 9) * 3.6e6);
const p2 = n => String(n).padStart(2, '0');
const fmt = (h, withDate = true) => { const d = kst(h); return (withDate ? `${p2(d.getUTCMonth() + 1)}-${p2(d.getUTCDate())} ` : '') + `${p2(d.getUTCHours())}:${p2(d.getUTCMinutes())}`; };
const recIdx = t => { let k = -1; REC.forEach((r, i) => { if (r <= t + 1e-6) k = i; }); return k; };
const inpIdx = t => { let k = -1; INP.forEach((r, i) => { if (r <= t + 1e-6) k = i; }); return k; };
$('dateRange').textContent = `${kst(0).getUTCFullYear()}-${fmt(0)} – ${fmt(TMAX)} KST`;

// ---------------- noise ----------------
function h2(x, y) { let h = (Math.imul(x | 0, 374761393) + Math.imul(y | 0, 668265263)) | 0; h = Math.imul(h ^ (h >>> 13), 1274126177); return ((h ^ (h >>> 16)) >>> 0) / 4294967296; }
function vn(x, y) { const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi, u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
  const a = h2(xi, yi), b = h2(xi + 1, yi), c = h2(xi, yi + 1), d = h2(xi + 1, yi + 1); return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v; }
function fbm(x, y, o) { let s = 0, a = .5, f = 1, n = 0; for (let i = 0; i < o; i++) { s += a * vn(x * f, y * f); n += a; f *= 2.03; a *= .5; } return s / n; }
let seed = 7; const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const mix3 = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
const hexRgb = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));

// ---------------- DEM ----------------
// phones and #lite=1 (slower booth machines, projectors): no bloom, fewer trees, smaller shadow map and context texture
const LITE = /(^#|&)lite=1(&|$)/.test(location.hash), isPhone = matchMedia('(max-width: 860px)').matches || LITE;
const GX = B.dem.w, GY = B.dem.h, H = new Float32Array(GX * GY);
{ const bin = atob(B.dem.b64), u8 = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
  const u16 = new Uint16Array(u8.buffer); for (let i = 0; i < H.length; i++) H[i] = u16[i] * B.dem.scale; }
let HMIN = Infinity, HMAX = -Infinity, HSUM = 0; for (const v of H) { HMIN = Math.min(HMIN, v); HMAX = Math.max(HMAX, v); HSUM += v; }
const HMEAN = HSUM / H.length;
const K300 = Math.max(0, H.findIndex(v => Math.abs(v - 300) < 4));
// surrounding terrain (context ring), same projection scale and centre as the analysis box
const CXB = B.context, [CW, CS, CE, CN] = CXB.bbox, [CKXr, CKYr] = CXB.km, CKX = CKXr * SF, CKY = CKYr * SF, CDEC = isPhone ? 2 : 1;
const CGX = Math.floor((CXB.w - 1) / CDEC) + 1, CGY = Math.floor((CXB.h - 1) / CDEC) + 1, CH = new Float32Array(CGX * CGY);
{ const bin = atob(CXB.b64), u8 = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
  const u16 = new Uint16Array(u8.buffer); for (let y = 0; y < CGY; y++) for (let x = 0; x < CGX; x++) CH[y * CGX + x] = u16[(y * CDEC) * CXB.w + x * CDEC] * CXB.scale; }
function celevUV(u, v) { const gx = clamp(u * (CGX - 1), 0, CGX - 1.0001), gy = clamp(v * (CGY - 1), 0, CGY - 1.0001), x0 = gx | 0, y0 = gy | 0, fx = gx - x0, fy = gy - y0, i = y0 * CGX + x0;
  return CH[i] * (1 - fx) * (1 - fy) + CH[i + 1] * fx * (1 - fy) + CH[i + CGX] * (1 - fx) * fy + CH[i + CGX + 1] * fx * fy; }
let CMAX = 0; for (const v of CH) CMAX = Math.max(CMAX, v);
// hourly cumulative new-burn probability F(h) from the recursive Monte Carlo rollout (optional bundle part)
const HR = B.hourly || null, HH = HR ? HR.meta.hours.length : 0;
const decB = s => { const b = atob(s), a = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) a[i] = b.charCodeAt(i); return a; };
const HP = HR ? HR.p.map(decB) : [], HSE = HR ? HR.se.map(decB) : [], HV = HR ? HR.valid.map(decB) : [];
const HCUT = HR ? HR.meta.cutoffs.map(c => (Date.parse(c) - T0) / 3.6e6) : [];
function elevG(gx, gy) { gx = clamp(gx, 0, GX - 1.0001); gy = clamp(gy, 0, GY - 1.0001); const x0 = gx | 0, y0 = gy | 0, fx = gx - x0, fy = gy - y0, i = y0 * GX + x0;
  return H[i] * (1 - fx) * (1 - fy) + H[i + 1] * fx * (1 - fy) + H[i + GX] * (1 - fx) * fy + H[i + GX + 1] * fx * fy; }
const elevUV = (u, v) => elevG(u * (GX - 1), v * (GY - 1));       // metres; u east 0..1, v south 0..1
const uOf = lon => (lon - W) / (E - W), vOf = lat => (N - lat) / (N - S);
const sxU = u => (u - .5) * KX, szV = v => (v - .5) * KY;
const DXM = KXr * 1000 / (GX - 1), DYM = KYr * 1000 / (GY - 1);
const SL = new Float32Array(GX * GY), AS = new Float32Array(GX * GY), GE = new Float32Array(GX * GY), GN = new Float32Array(GX * GY);
for (let y = 0; y < GY; y++) for (let x = 0; x < GX; x++) {
  const xl = Math.max(x - 1, 0), xr = Math.min(x + 1, GX - 1), yt = Math.max(y - 1, 0), yb = Math.min(y + 1, GY - 1);
  const dzdx = (H[y * GX + xr] - H[y * GX + xl]) / ((xr - xl) * DXM), dzdn = (H[yt * GX + x] - H[yb * GX + x]) / ((yb - yt) * DYM);
  const i = y * GX + x; GE[i] = dzdx; GN[i] = dzdn;
  SL[i] = Math.atan(Math.hypot(dzdx, dzdn)) * 180 / Math.PI;
  AS[i] = (Math.atan2(-dzdx, -dzdn) * 180 / Math.PI + 360) % 360;   // direction the slope faces
}
const gIdx = (u, v) => clamp(Math.round(v * (GY - 1)), 0, GY - 1) * GX + clamp(Math.round(u * (GX - 1)), 0, GX - 1);
const ASPECT = EN ? ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'] : ['북', '북북동', '북동', '동북동', '동', '동남동', '남동', '남남동', '남', '남남서', '남서', '서남서', '서', '서북서', '북서', '북북서'];
const aspName = a => ASPECT[Math.round(a / 22.5) % 16];

// ---------------- cells (375 m grid) ----------------
const C = B.cells, NR = C.nr, NC = C.nc, NCELL = NR * NC, LAT = C.lattice;
const lat_ = (r, c) => { const i = (r * (NC + 1) + c) * 2; return [LAT[i], LAT[i + 1]]; };
const first = Uint8Array.from(C.first), valid = Uint8Array.from(C.valid);
const QF = C.q.map(a => Float32Array.from(a));
const BURNING = C.burning.map(a => new Set(a));
const cellCenter = i => { const r = (i / NC) | 0, c = i % NC; const a = lat_(r, c), b = lat_(r + 1, c + 1); return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]; };
const LON0 = LAT[0], LATB0 = LAT[1], DLON = (LAT[NC * 2] - LAT[0]) / NC, DLAT = (LAT[NR * (NC + 1) * 2 + 1] - LAT[1]) / NR;
function inQuad(lon, lat, r, c) {
  const p = [lat_(r, c), lat_(r, c + 1), lat_(r + 1, c + 1), lat_(r + 1, c)]; let inside = false;
  for (let i = 0, j = 3; i < 4; j = i++) { const [xi, yi] = p[i], [xj, yj] = p[j]; if ((yi > lat) !== (yj > lat) && lon < (xj - xi) * (lat - yi) / (yj - yi) + xi) inside = !inside; }
  return inside;
}
function cellOf(lon, lat) {
  const c0 = Math.floor((lon - LON0) / DLON), r0 = Math.floor((lat - LATB0) / DLAT);
  for (let dr = -2; dr <= 2; dr++) for (let dc = -2; dc <= 2; dc++) { const r = r0 + dr, c = c0 + dc; if (r >= 0 && r < NR && c >= 0 && c < NC && inQuad(lon, lat, r, c)) return r * NC + c; }
  return -1;
}
const CELL_KM2 = 0.140625;
const hourIdx = t => { let k = -1; HCUT.forEach((h, i) => { if (h <= t + 1e-6) k = i; }); return k; };
const hourStep = (t, k) => clamp(Math.ceil(t - HCUT[k] - 1e-6), 1, HH);
const Fh = (k, i, h) => { const v = HP[k][(h - 1) * NCELL + i] / 255; return v * v; };
const SEh = (k, i, h) => { const v = HSE[k][(h - 1) * NCELL + i] / 255; return v * v; };
// recorded routing hazard: 4 fire scenarios, piecewise-constant incident flux (kW/m²) and flame contact per interval
const HZ = (B.hazard || []).map(h => {
  const t0 = (Date.parse(h.input_time) - T0) / 3.6e6;
  const members = h.members.map(m => { const b = atob(m.flux), u8 = new Uint8Array(b.length); for (let i = 0; i < b.length; i++) u8[i] = b.charCodeAt(i);
    const u16 = new Uint16Array(u8.buffer), f = new Float32Array(u16.length); for (let i = 0; i < f.length; i++) f[i] = u16[i] ? Math.pow(10, u16[i] / 65535 * 11 - 8) : 0;
    return { bp: m.bp, flux: f, flame: m.flame.map(a => new Set(a)) }; });
  return { ...h, t0, members };
});
const hzSig = t => { const k = hzK(t); if (k < 0) return '-'; const s = (t - HZ[k].t0) * 3600; return k + ':' + state.member + ':' + HZ[k].members.map(m => hzInterval(m, s)).join(','); };
const hzK = t => HZ.findIndex(h => t >= h.t0 - 1e-9 && t < h.t0 + h.valid_until / 3600);
const hzInterval = (m, s) => { let j = 0; while (j < m.bp.length - 2 && s >= m.bp[j + 1]) j++; return j; };
const hzFlux = (k, mi, i, s) => { const m = HZ[k].members[mi]; return m.flux[hzInterval(m, s) * NCELL + i]; };
const hzFlame = (k, mi, i, s) => { const m = HZ[k].members[mi]; return m.flame[hzInterval(m, s)].has(i); };
function hzField(k, s, sel) {          // sel −1: maximum over the four scenarios
  const f = new Float32Array(NCELL), fl = new Set(), ms = sel < 0 ? [0, 1, 2, 3] : [sel];
  for (const mi of ms) { const m = HZ[k].members[mi], j = hzInterval(m, s), off = j * NCELL; for (let i = 0; i < NCELL; i++) if (m.flux[off + i] > f[i]) f[i] = m.flux[off + i]; m.flame[j].forEach(i => fl.add(i)); }
  return { f, flame: fl };
}
const INFERNO = ['#000004', '#160b39', '#420a68', '#6a176e', '#932667', '#bc3754', '#dd513a', '#f37819', '#fca50a', '#f6d746', '#fcffa4'].map(hexRgb);
function inferno(v) { v = clamp(v, 0, 1) * 10; const i = Math.min(9, Math.floor(v)); return mix3(INFERNO[i], INFERNO[i + 1], v - i); }
const fluxV = F => F > 0 ? clamp((Math.log10(F) + 6) / 6, 0, 1) : 0;      // 1e-6 … 1 kW/m², log scale
const POLICY = { full: { n: tr('전체 조건', 'Full constraints'), c: 0x2f8a57, css: '#2f8a57' }, flame_dose: { n: tr('불길 + 누적 노출', 'Flame + dose'), c: 0x4f86c6, css: '#4f86c6' }, flame_peak: { n: tr('불길 + 순간 열유속', 'Flame + peak flux'), c: 0x8a6fc0, css: '#8a6fc0' }, flame_only: { n: tr('불길만', 'Flame only'), c: 0x8d8d8d, css: '#8d8d8d' }, travel_only: { n: tr('이동시간만', 'Travel time only'), c: 0xe8862a, css: '#e8862a' } };
const POLICY_ORDER = ['full', 'flame_dose', 'flame_peak', 'flame_only', 'travel_only'];
const MEMBER_CSS = ['#d9472b', '#e8a33a', '#7a5cc4', '#2f8fb3'];
const A50 = HP.map((_, k) => { const a = new Uint8Array(NCELL).fill(255); for (let i = 0; i < NCELL; i++) { if (!HV[k][i]) continue; for (let h = 1; h <= HH; h++) if (Fh(k, i, h) >= .5) { a[i] = h; break; } } return a; });

// ---------------- canvases ----------------
const TW = 2048, TH = Math.round(2048 * KY / KX), MW = 1024, MH = Math.round(1024 * KY / KX);
const mk = (w, h) => { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; };
const toPx = (lon, lat, w, h) => [(lon - W) / (E - W) * w, (N - lat) / (N - S) * h];
function ringPath(ctx, rings, w, h, close) {
  ctx.beginPath();
  for (const ring of rings) { for (let i = 0; i < ring.length; i += 2) { const x = (ring[i] - W) / (E - W) * w, y = (N - ring[i + 1]) / (N - S) * h; i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); } if (close) ctx.closePath(); }
}
const LANDCODE = { wood: 1, forest: 1, farmland: 2, meadow: 4, grass: 4, park: 4, golf_course: 4, scrub: 6, residential: 3, school: 3, hospital: 3, university: 3, industrial: 3, railway: 3, pitch: 3, pedestrian: 3, commercial: 3, retail: 3 };
const WATER_POLY = k => k === 'water';

let ground, groundHS, topo, hsCv, slopeCv, canopyCv, biomeCv, F, LC, tempCv, BIOME_COUNTS;
function buildStatic() {
  // land cover mask
  const mc = mk(MW, MH), m = mc.getContext('2d');
  m.fillStyle = '#000'; m.fillRect(0, 0, MW, MH);
  const order = [2, 4, 6, 3, 1];
  for (const code of order) { m.fillStyle = `rgb(${code * 40},0,0)`; for (const [k, , g] of B.osm.landuse) if (LANDCODE[k] === code) { ringPath(m, g, MW, MH, true); m.fill('evenodd'); } }
  m.fillStyle = 'rgb(200,0,0)'; for (const [k, , g] of B.osm.water) if (WATER_POLY(k)) { ringPath(m, g, MW, MH, true); m.fill(); }
  m.strokeStyle = 'rgb(200,0,0)'; m.lineCap = 'round';
  for (const [k, , g] of B.osm.water) if (!WATER_POLY(k)) { m.lineWidth = k === 'river' ? 2.2 : 1; ringPath(m, g, MW, MH, false); m.stroke(); }
  const md = m.getImageData(0, 0, MW, MH).data;
  LC = new Uint8Array(MW * MH); F = new Uint8Array(MW * MH);
  for (let i = 0; i < MW * MH; i++) { const r = md[i * 4]; const code = Math.round(r / 40); LC[i] = Math.abs(r - code * 40) < 14 ? code : 0; }
  // forest: OSM wood, plus steep unmapped slopes (Korean hills are mostly forested); clearings from noise
  for (let y = 0; y < MH; y++) for (let x = 0; x < MW; x++) {
    const i = y * MW + x, u = (x + .5) / MW, v = (y + .5) / MH, code = LC[i];
    const s = SL[gIdx(u, v)], n = fbm(u * 38, v * 34, 2);
    F[i] = H[gIdx(u, v)] < .5 ? 0 : (code === 1 && n > .18) || (code === 0 && s > 6.5 + 10 * (n - .5)) || (code === 6 && n > .5) ? 1 : 0;
  }
  // realistic ground (late March: dark pine, bare broadleaf, dry fields)
  const gc = mk(MW, MH), g = gc.getContext('2d'), gi = g.createImageData(MW, MH), gd = gi.data;
  const hc = mk(MW, MH), hx = hc.getContext('2d'), hi = hx.createImageData(MW, MH), hd = hi.data;
  for (let y = 0; y < MH; y++) for (let x = 0; x < MW; x++) {
    const i = y * MW + x, u = (x + .5) / MW, v = (y + .5) / MH, k = gIdx(u, v), s = SL[k], code = LC[i];
    const n1 = fbm(u * 90, v * 80, 3), n2 = fbm(u * 7 + 5, v * 6 + 3, 2);
    let c;
    if (code === 5 || H[k] < .5) c = [78 + 14 * n1, 104 + 12 * n1, 112 + 10 * n1];
    else if (F[i]) {
      const con = [44 + 22 * n1, 60 + 20 * n1, 38 + 12 * n1], dec = [104 + 26 * n1, 92 + 20 * n1, 72 + 14 * n1];
      c = mix3(con, dec, smooth(.48, .66, n2 + (AS[k] > 300 || AS[k] < 60 ? .08 : -.04)));
      if (s > 30) c = mix3(c, [126, 116, 98], smooth(30, 45, s));
    } else if (code === 2) c = [184 + 16 * n1, 168 + 14 * n1, 124 + 10 * n1];
    else if (code === 3) c = [178 + 22 * n1, 170 + 20 * n1, 158 + 18 * n1];
    else if (code === 4 || code === 6) c = [150 + 20 * n1, 146 + 18 * n1, 98 + 12 * n1];
    else c = mix3([182 + 18 * n1, 164 + 14 * n1, 120 + 10 * n1], [150, 140, 96], smooth(.5, .8, n2));
    // hillshade (sun NW, 45°), z-factor 2
    const ge = GE[k] * 2, gn = GN[k] * 2, len = Math.hypot(ge, gn, 1);
    const hs = clamp(((-ge) * -.5 + (-gn) * .5 + 1 * .707) / len / 1.0, 0, 1);
    // valley occlusion / ridge highlight from curvature, plus a light baked hillshade for relief definition
    const kx = k % GX, ky = (k / GX) | 0, lap = (H[ky * GX + Math.max(kx - 2, 0)] + H[ky * GX + Math.min(kx + 2, GX - 1)] + H[Math.max(ky - 2, 0) * GX + kx] + H[Math.min(ky + 2, GY - 1) * GX + kx] - 4 * H[k]);
    const ao = clamp(1 - lap / 120, .72, 1.12) * (.82 + .26 * hs);
    if (code !== 5) c = c.map(v => v * ao);
    gd[i * 4] = c[0]; gd[i * 4 + 1] = c[1]; gd[i * 4 + 2] = c[2]; gd[i * 4 + 3] = 255;
    hd[i * 4] = hd[i * 4 + 1] = hd[i * 4 + 2] = Math.round(255 * (.55 + .45 * hs)); hd[i * 4 + 3] = 255;
  }
  g.putImageData(gi, 0, 0); hx.putImageData(hi, 0, 0); hsCv = hc;
  ground = mk(TW, TH); const G = ground.getContext('2d');
  G.imageSmoothingQuality = 'high'; G.drawImage(gc, 0, 0, TW, TH);
  // farmland furrows
  const pat = mk(14, 10), pc = pat.getContext('2d'); pc.strokeStyle = 'rgba(110,90,55,.55)'; pc.lineWidth = 1; pc.beginPath(); pc.moveTo(0, 2.5); pc.lineTo(14, 2.5); pc.moveTo(0, 7.5); pc.lineTo(14, 7.5); pc.moveTo(4.5, 0); pc.lineTo(4.5, 10); pc.stroke();
  G.save(); G.globalAlpha = .45; G.fillStyle = G.createPattern(pat, 'repeat');
  for (const [k, , gg] of B.osm.landuse) if (LANDCODE[k] === 2) { ringPath(G, gg, TW, TH, true); G.fill('evenodd'); }
  G.restore();
  // tree crowns: dark specks + sunlit tops
  seed = 11; G.fillStyle = 'rgba(16,26,14,.5)'; const crowns = [];
  for (let n = 0; n < 160000; n++) { const u = rnd(), v = rnd(); if (!F[((v * MH) | 0) * MW + ((u * MW) | 0)]) continue; crowns.push(u, v); G.fillRect(u * TW - 1, v * TH - 1, 2.4, 2.4); }
  G.fillStyle = 'rgba(150,152,96,.22)'; for (let n = 0; n < crowns.length; n += 4) G.fillRect(crowns[n] * TW - 1.6, crowns[n + 1] * TH - 1.8, 1.4, 1.4);
  drawWater(G, TW, TH, 'real'); drawRoads(G, TW, TH, 'real');
  // realistic + baked hillshade (2D "실사")
  groundHS = mk(TW, TH); const GH = groundHS.getContext('2d'); GH.drawImage(ground, 0, 0);
  GH.globalCompositeOperation = 'multiply'; GH.drawImage(hc, 0, 0, TW, TH); GH.globalCompositeOperation = 'source-over';

  // topographic map (2D "지형도")
  topo = mk(TW, TH); const T = topo.getContext('2d'), ti = T.createImageData(TW, TH), td = ti.data;
  const sx = (GX - 1) / (TW - 1), sy = (GY - 1) / (TH - 1);
  const row = new Float32Array(TW), next = new Float32Array(TW);
  for (let x = 0; x < TW; x++) row[x] = elevG(x * sx, 0);
  for (let y = 0; y < TH; y++) {
    for (let x = 0; x < TW; x++) next[x] = elevG(x * sx, (y + 1) * sy);
    for (let x = 0; x < TW; x++) {
      const e = row[x], i = (y * TW + x) * 4, mi = ((y * MH / TH) | 0) * MW + ((x * MW / TW) | 0), code = LC[mi];
      let c = code === 5 || e < .5 ? [178, 205, 220] : F[mi] ? [219, 230, 204] : code === 2 ? [243, 236, 212] : code === 3 ? [234, 227, 219] : code === 4 || code === 6 ? [232, 236, 210] : [245, 242, 235];
      const hs = hd[mi * 4] / 255; const k = .62 + .45 * (hs - .55) / .45;
      c = c.map(v => v * clamp(k + .2, .6, 1.06));
      const e2 = x + 1 < TW ? row[x + 1] : e, e3 = next[x];
      const a = Math.floor(e / 50), b = Math.floor(e2 / 50), d = Math.floor(e3 / 50);
      if (code !== 5 && (a !== b || a !== d)) { const idx = Math.floor(Math.max(e, e2, e3) / 250) !== Math.floor(Math.min(e, e2, e3) / 250); c = mix3(c, idx ? [168, 136, 92] : [196, 172, 128], idx ? .85 : .55); }
      td[i] = c[0]; td[i + 1] = c[1]; td[i + 2] = c[2]; td[i + 3] = 255;
    }
    row.set(next);
  }
  T.putImageData(ti, 0, 0); drawWater(T, TW, TH, 'topo'); drawRoads(T, TW, TH, 'topo');

  // slope overlay (real, from DEM)
  slopeCv = mk(GX, GY); { const sc = slopeCv.getContext('2d'), im = sc.createImageData(GX, GY);
    const stops = [[5, [243, 224, 138]], [15, [240, 162, 74]], [25, [217, 98, 43]], [35, [143, 45, 29]]];
    for (let i = 0; i < GX * GY; i++) { const s = SL[i]; if (s < 3) continue; let c = stops[0][1];
      for (let j = 0; j < stops.length - 1; j++) if (s >= stops[j][0]) c = mix3(stops[j][1], stops[j + 1][1], clamp((s - stops[j][0]) / (stops[j + 1][0] - stops[j][0]), 0, 1));
      im.data.set([c[0], c[1], c[2], Math.round(255 * clamp((s - 3) / 8, 0, 1) * .9)], i * 4); }
    sc.putImageData(im, 0, 0); }
  // canopy cover (illustrative): smoothed forest mask
  canopyCv = mk(MW, MH); { const cc = canopyCv.getContext('2d'), fm = mk(MW, MH), fx = fm.getContext('2d'), im = fx.createImageData(MW, MH);
    for (let i = 0; i < MW * MH; i++) if (F[i]) im.data.set([255, 255, 255, 255], i * 4);
    fx.putImageData(im, 0, 0); cc.filter = 'blur(4px)'; cc.drawImage(fm, 0, 0); cc.filter = 'none';
    cc.globalCompositeOperation = 'source-in'; cc.fillStyle = '#2f8a3e'; cc.fillRect(0, 0, MW, MH); }
  // biome classes (illustrative, 8 of the 14 one-hot channels appear here)
  biomeCv = mk(MW, MH); BIOME_COUNTS = new Array(BIOMES.length).fill(0);
  { const bc = biomeCv.getContext('2d'), im = bc.createImageData(MW, MH);
    for (let y = 0; y < MH; y++) for (let x = 0; x < MW; x++) { const i = y * MW + x, u = (x + .5) / MW, v = (y + .5) / MH, b = biomeAt(u, v, i); BIOME_COUNTS[b]++;
      const c = BIOMES[b].rgb; im.data.set([c[0], c[1], c[2], 255], i * 4); }
    bc.putImageData(im, 0, 0); }
  tempCv = mk(GX, GY);
}
const BIOMES = [
  { n: tr('하천·수역', 'Water'), c: '#6f9fc0' }, { n: tr('시가지', 'Built-up'), c: '#b4aca0' }, { n: tr('농경지', 'Farmland'), c: '#e3cd7c' }, { n: tr('초지·관목', 'Grass · scrub'), c: '#c4cf78' },
  { n: tr('저지대 혼효림', 'Lowland mixed forest'), c: '#86ad72' }, { n: tr('남사면 소나무림', 'South-slope pine'), c: '#4f8247' }, { n: tr('북사면 활엽수림', 'North-slope broadleaf'), c: '#a39066' }, { n: tr('고지대 침엽수림', 'Upland conifer'), c: '#2c5a44' },
].map(b => ({ ...b, rgb: hexRgb(b.c) }));
function biomeAt(u, v, mi) {
  const code = LC[mi], k = gIdx(u, v), e = H[k], a = AS[k], s = SL[k];
  if (code === 5) return 0; if (code === 3) return 1; if (code === 2) return 2; if (code === 4 || code === 6) return 3;
  if (F[mi]) { if (e > 430) return 7; if (s > 8 && a > 100 && a < 260) return 5; if (s > 8 && (a > 300 || a < 60)) return 6; return 4; }
  return s < 4 ? 2 : 3;
}
function drawWater(ctx, w, h, style) {
  const s = w / 2048;
  ctx.save(); ctx.lineCap = ctx.lineJoin = 'round';
  ctx.fillStyle = style === 'topo' ? '#a9c9dc' : '#4f7684';
  for (const [k, , g] of B.osm.water) if (WATER_POLY(k)) { ringPath(ctx, g, w, h, true); ctx.fill(); }
  for (const [k, , g] of B.osm.water) if (!WATER_POLY(k)) {
    ctx.strokeStyle = style === 'topo' ? '#8fb6cf' : '#4f7684'; ctx.lineWidth = (k === 'river' ? 2.6 : k === 'stream' ? 1.2 : 1) * s; ctx.globalAlpha = k === 'stream' ? .8 : 1;
    ringPath(ctx, g, w, h, false); ctx.stroke(); }
  ctx.restore();
}
function drawRoads(ctx, w, h, style) {
  const s = w / 2048, topoS = style === 'topo';
  const cls = (k, d) => k === 'highway' ? 0 : k === 'major_road' ? (d === 'trunk' || d === 'primary' || d === 'trunk_link' || d === 'primary_link' ? 1 : 2) : k === 'minor_road' ? 3 : k === 'rail' ? 5 : 4;
  const st = topoS
    ? [{ cw: 5.2, cc: '#c38d4b', w: 3.6, c: '#f7d7a0' }, { cw: 4.2, cc: '#c9a36a', w: 2.8, c: '#fbe6bd' }, { cw: 3.2, cc: '#b9b0a2', w: 2.1, c: '#ffffff' }, { w: 1.3, c: '#ffffff', cw: 2.2, cc: '#cfc8bb' }, { w: .9, c: '#a39a88', dash: [3, 3] }, { w: 1.4, c: '#8a8378', dash: [6, 3] }]
    : [{ cw: 5, cc: '#5f584c', w: 3.4, c: '#d8d0bd' }, { cw: 4, cc: '#6a6255', w: 2.6, c: '#ded6c4' }, { cw: 3, cc: '#71695b', w: 1.9, c: '#d3cab5' }, { w: 1.2, c: '#c9bfa8' }, { w: .9, c: '#a99d82', dash: [3, 3] }, { w: 1.5, c: '#544e45', dash: [6, 3] }];
  ctx.save(); ctx.lineCap = ctx.lineJoin = 'round';
  for (const pass of ['case', 'fill']) for (let level = 5; level >= 0; level--) {
    const y = st[level]; if (pass === 'case' && !y.cw) continue;
    ctx.strokeStyle = pass === 'case' ? y.cc : y.c; ctx.lineWidth = (pass === 'case' ? y.cw : y.w) * s; ctx.setLineDash(pass === 'fill' && y.dash ? y.dash.map(v => v * s) : []);
    for (const [k, d, g] of B.osm.roads) if (cls(k, d) === level) { ringPath(ctx, g, w, h, false); ctx.stroke(); }
  }
  ctx.restore();
}

// ---------------- illustrative environment fields ----------------
function sunPos(h) {
  const date = T0 + h * 3.6e6, rad = Math.PI / 180, n = date / 864e5 + 2440587.5 - 2451545.0;
  const L = (280.460 + .9856474 * n) % 360, g = ((357.528 + .9856003 * n) % 360) * rad;
  const lam = (L + 1.915 * Math.sin(g) + .020 * Math.sin(2 * g)) * rad, eps = (23.439 - 4e-7 * n) * rad;
  const ra = Math.atan2(Math.cos(eps) * Math.sin(lam), Math.cos(lam)), dec = Math.asin(Math.sin(eps) * Math.sin(lam));
  const gmst = ((18.697374558 + 24.06570982441908 * n) % 24 + 24) % 24, lst = (gmst * 15 + LON_C) * rad, ha = lst - ra, lat = LAT_C * rad;
  const el = Math.asin(Math.sin(lat) * Math.sin(dec) + Math.cos(lat) * Math.cos(dec) * Math.cos(ha));
  const az = Math.atan2(-Math.sin(ha), Math.tan(dec) * Math.cos(lat) - Math.sin(lat) * Math.cos(ha));
  return { el: el / rad, az: ((az / rad) + 360) % 360 };
}
const kstHour = t => ((t + H0) % 24 + 24) % 24;
function windBase(t) {
  const hk = kstHour(t);
  const dir = 262 + 16 * Math.sin(t / 9) + 7 * Math.sin(t / 3.1);              // degrees, blowing FROM
  const spd = 5.5 + 4.5 * Math.max(0, Math.sin((hk - 8) / 24 * 2 * Math.PI)) + 1.5 * Math.sin(t / 5.3) + 1.2;
  return { dir, spd };
}
const WGX = 70, WGY = Math.round(70 * KY / KX), WU = new Float32Array(WGX * WGY), WV = new Float32Array(WGX * WGY);
let windT = -1;
function updateWind(t) {
  const { dir, spd } = windBase(t), r = dir * Math.PI / 180, u0 = -spd * Math.sin(r), v0 = -spd * Math.cos(r);
  for (let y = 0; y < WGY; y++) for (let x = 0; x < WGX; x++) {
    const u = x / (WGX - 1), v = y / (WGY - 1), k = gIdx(u, v), ge = GE[k], gn = GN[k], g = Math.hypot(ge, gn);
    const f = 1 + .9 * (H[k] - HMEAN) / (HMAX - HMIN) + .15 * (fbm(u * 6 + t * .05, v * 6, 2) - .5);
    let uu = u0, vv = v0;
    if (g > 1e-3) { const ne = ge / g, nn = gn / g, along = uu * ne + vv * nn, w = Math.min(1, g * 2.5) * .6; uu -= along * ne * w; vv -= along * nn * w; }
    WU[y * WGX + x] = uu * f; WV[y * WGX + x] = vv * f;
  }
  windT = t;
}
function windAt(u, v) {
  const gx = clamp(u * (WGX - 1), 0, WGX - 1.001), gy = clamp(v * (WGY - 1), 0, WGY - 1.001), x0 = gx | 0, y0 = gy | 0, fx = gx - x0, fy = gy - y0, i = y0 * WGX + x0;
  const l = (A) => A[i] * (1 - fx) * (1 - fy) + A[i + 1] * fx * (1 - fy) + A[i + WGX] * (1 - fx) * fy + A[i + WGX + 1] * fx * fy;
  return [l(WU), l(WV)];
}
function tempAt(t, k, sun, glow = 0) {
  const hk = kstHour(t), base = TBASE + 8.5 * Math.sin((hk - 9) / 24 * 2 * Math.PI) + .8 * Math.sin(t / 11);
  const day = smooth(-2, 15, sun.el), sr = sun.az * Math.PI / 180, se = Math.max(0, sun.el) * Math.PI / 180;
  const nx = -GE[k], nn = -GN[k], len = Math.hypot(nx, nn, 1);
  const inc = (nx * Math.sin(sr) * Math.cos(se) + nn * Math.cos(sr) * Math.cos(se) + Math.sin(se)) / len;
  return base - 6.5 * H[k] / 1000 + 2.2 * day * (inc - .5) + 9 * glow;
}
const TBASE = [2, 4, 12, 15, 19, 22, 25, 26, 21, 15, 8, 3][kst(0).getUTCMonth()];   // illustrative daily mean by month
const TEMP_STOPS = [[-2, [70, 110, 190]], [6, [140, 185, 225]], [12, [246, 240, 196]], [18, [244, 170, 92]], [24, [222, 92, 50]], [30, [150, 30, 30]]];
function tempColor(T) { let c = TEMP_STOPS[0][1]; for (let j = 0; j < TEMP_STOPS.length - 1; j++) if (T >= TEMP_STOPS[j][0]) c = mix3(TEMP_STOPS[j][1], TEMP_STOPS[j + 1][1], clamp((T - TEMP_STOPS[j][0]) / (TEMP_STOPS[j + 1][0] - TEMP_STOPS[j][0]), 0, 1)); return c; }
let cellGlow = new Float32Array(NCELL);
function drawTemp(t) {
  const sun = sunPos(t), tc = tempCv.getContext('2d'), im = tc.createImageData(GX, GY), d = im.data;
  for (let y = 0; y < GY; y++) for (let x = 0; x < GX; x++) {
    const k = y * GX + x; let T = tempAt(t, k, sun);
    const c = tempColor(T), iso = ((T % 2) + 2) % 2 < .14;
    const cc = iso ? mix3(c, [90, 40, 20], .55) : c;
    d[k * 4] = cc[0]; d[k * 4 + 1] = cc[1]; d[k * 4 + 2] = cc[2]; d[k * 4 + 3] = iso ? 235 : 190;
  }
  tc.putImageData(im, 0, 0);
}

// ---------------- three.js scene ----------------
const mapEl = $('map');
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: false });
renderer.setPixelRatio(LITE ? 1 : Math.min(devicePixelRatio, 2));
renderer.outputEncoding = THREE.sRGBEncoding;
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.08;
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
mapEl.prepend(renderer.domElement);
const scene = new THREE.Scene(); scene.fog = new THREE.Fog(0xcfd6d9, 30, 150);
const camera = new THREE.PerspectiveCamera(36, 1, .03, 900);
const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.enableDamping = true; controls.dampingFactor = .09; controls.screenSpacePanning = true;
controls.minDistance = 2.5; controls.maxDistance = 150; controls.maxPolarAngle = THREE.MathUtils.degToRad(84);
controls.target.set(1.2, .3, .8); camera.position.set(-2.5, 17, 25);
const hemi = new THREE.HemisphereLight(0xf2f4ff, 0x6d6450, .6); scene.add(hemi);
const sunL = new THREE.DirectionalLight(0xfff1dc, 1.4); sunL.castShadow = true; sunL.shadow.mapSize.set(isPhone ? 2048 : 4096, isPhone ? 2048 : 4096);
Object.assign(sunL.shadow.camera, { left: -44, right: 44, top: 44, bottom: -44, near: 1, far: 260 }); sunL.shadow.bias = -.0005; sunL.shadow.normalBias = .05;
// sky dome: zenith/horizon gradient with sun glow; follows the camera
const skyMat = new THREE.ShaderMaterial({ side: THREE.BackSide, depthWrite: false, fog: false,
  uniforms: { linOut: { value: 0 }, top: { value: new THREE.Color() }, horizon: { value: new THREE.Color() }, sunDir: { value: new THREE.Vector3(0, 1, 0) }, sunCol: { value: new THREE.Color(1, .9, .7) }, sunAmt: { value: 1 } },
  vertexShader: `varying vec3 vDir; void main(){ vDir = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: `uniform vec3 top, horizon, sunCol, sunDir; uniform float sunAmt, linOut; varying vec3 vDir;
    void main(){ vec3 d = normalize(vDir); float h = clamp(d.y, 0.0, 1.0); vec3 c = mix(horizon, top, pow(h, 0.5));
      float s = max(dot(d, normalize(sunDir)), 0.0); c += sunCol * (pow(s, 900.0) * 1.4 + pow(s, 14.0) * 0.22 + pow(s, 3.0) * 0.08) * sunAmt;
      gl_FragColor = vec4(mix(c, pow(c, vec3(2.2)), linOut), 1.0); }` });
const skyDome = new THREE.Mesh(new THREE.SphereGeometry(600, 32, 16), skyMat); skyDome.renderOrder = -1; skyDome.frustumCulled = false; scene.add(skyDome);
scene.add(sunL, sunL.target);

let EXAG = 3, flatF = 0, flatTarget = 0, reliefOn = true;
const yScale = () => (reliefOn ? EXAG : 0) * SF / 1000 * (1 - flatF) + 1e-6;     // metres -> scene units, exaggerated
const yAt = (u, v) => elevUV(u, v) * yScale();

let terrain, matReal, matFlat, tex, emTex, composite, emissive;
function buildTerrain() {
  const geo = new THREE.PlaneGeometry(KX, KY, GX - 1, GY - 1); geo.rotateX(-Math.PI / 2);
  const p = geo.attributes.position;
  composite = mk(TW, TH); emissive = mk(MW, MH);
  tex = new THREE.CanvasTexture(composite); tex.encoding = THREE.sRGBEncoding; tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
  emTex = new THREE.CanvasTexture(emissive); emTex.encoding = THREE.sRGBEncoding;
  matReal = new THREE.MeshStandardMaterial({ map: tex, emissiveMap: emTex, emissive: 0xffffff, emissiveIntensity: .6, roughness: .97, metalness: 0 });
  matFlat = new THREE.MeshBasicMaterial({ map: tex, toneMapped: false });
  terrain = new THREE.Mesh(geo, matReal); terrain.castShadow = terrain.receiveShadow = true;
  // geometry y holds metres/1000 (km at ×1); scale.y applies exaggeration
  for (let i = 0; i < p.count; i++) p.setY(i, H[i] / 1000);
  p.needsUpdate = true; geo.computeVertexNormals();
  scene.add(terrain);
  // skirt so the block reads as a slab of land
  const sk = []; const base = -.25;
  const edge = (fn, n) => { const pts = []; for (let i = 0; i < n; i++) pts.push(fn(i / (n - 1))); return pts; };
  const sides = [edge(t => [t, 0], GX), edge(t => [1, t], GY), edge(t => [1 - t, 1], GX), edge(t => [0, 1 - t], GY)];
  const pos = [], idx = [];
  for (const side of sides) { const b0 = pos.length / 3; side.forEach(([u, v], j) => { pos.push(sxU(u), elevUV(u, v) / 1000, szV(v), sxU(u), base, szV(v)); if (j) { const a = b0 + (j - 1) * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); } }); }
  const sg = new THREE.BufferGeometry(); sg.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); sg.setIndex(idx); sg.computeVertexNormals();
  skirt = new THREE.Mesh(sg, new THREE.MeshStandardMaterial({ color: 0x8d826f, roughness: 1, side: THREE.DoubleSide })); scene.add(skirt);
}
let skirt, ctxMesh, ctxMatReal, ctxMatFlat, boundary;
function buildContext() {
  const geo = new THREE.PlaneGeometry(CKX, CKY, CGX - 1, CGY - 1); geo.rotateX(-Math.PI / 2);
  const p = geo.attributes.position, mlon = 1.5 * (CE - CW) / (CGX - 1), mlat = 1.5 * (CN - CS) / (CGY - 1);
  for (let y = 0; y < CGY; y++) for (let x = 0; x < CGX; x++) { const i = y * CGX + x, lon = CW + x / (CGX - 1) * (CE - CW), lat = CN - y / (CGY - 1) * (CN - CS);
    const inside = lon > W + mlon && lon < E - mlon && lat > S + mlat && lat < N - mlat; p.setY(i, (CH[i] - (inside ? 80 : 0)) / 1000); }
  geo.computeVertexNormals();
  const CTW = isPhone ? 1024 : 2048, CTH = Math.round(CTW * CKY / CKX);
  const real = mk(CTW, CTH), topoC = mk(CTW, CTH), rc = real.getContext('2d'), tc = topoC.getContext('2d'), ri = rc.createImageData(CTW, CTH), ti = tc.createImageData(CTW, CTH);
  const cdx = CKXr * 1000 / (CGX - 1), cdy = CKYr * 1000 / (CGY - 1), haze = [196, 201, 204];
  for (let y = 0; y < CTH; y++) for (let x = 0; x < CTW; x++) {
    const u = x / (CTW - 1), v = y / (CTH - 1), e = celevUV(u, v), du = 1 / (CGX - 1), dv = 1 / (CGY - 1);
    const ge = (celevUV(u + du, v) - celevUV(u - du, v)) / (2 * cdx), gn = (celevUV(u, v - dv) - celevUV(u, v + dv)) / (2 * cdy), s = Math.atan(Math.hypot(ge, gn)) * 57.3;
    const n1 = fbm(u * 260, v * 250, 2), n2 = fbm(u * 22 + 3, v * 21 + 9, 2), i4 = (y * CTW + x) * 4;
    const forest = s > 6 + 9 * (n2 - .5) || e > 420;
    let c = e < 1 ? [86, 112, 122] : forest ? mix3([46 + 22 * n1, 62 + 20 * n1, 40 + 12 * n1], [102 + 24 * n1, 92 + 18 * n1, 72 + 12 * n1], smooth(.5, .68, n2)) : [182 + 18 * n1, 165 + 14 * n1, 122 + 10 * n1];
    if (s > 30) c = mix3(c, [126, 116, 98], smooth(30, 45, s));
    const len = Math.hypot(ge * 2, gn * 2, 1), hs = clamp((ge * 2 * .5 - gn * 2 * .5 + .707) / len, 0, 1);
    c = mix3(c.map(q => q * (.8 + .28 * hs)), haze, .12);
    ri.data[i4] = c[0]; ri.data[i4 + 1] = c[1]; ri.data[i4 + 2] = c[2]; ri.data[i4 + 3] = 255;
    let t = forest ? [222, 231, 208] : [244, 240, 232]; t = t.map(q => q * clamp(.84 + .22 * (hs - .55) / .45 + .12, .7, 1.04));
    const e2 = celevUV(u + 1 / (CTW - 1), v), e3 = celevUV(u, v + 1 / (CTH - 1));
    if (Math.floor(e / 50) !== Math.floor(e2 / 50) || Math.floor(e / 50) !== Math.floor(e3 / 50)) t = mix3(t, Math.floor(Math.max(e, e2, e3) / 250) !== Math.floor(Math.min(e, e2, e3) / 250) ? [168, 136, 92] : [200, 178, 136], .6);
    ti.data[i4] = t[0]; ti.data[i4 + 1] = t[1]; ti.data[i4 + 2] = t[2]; ti.data[i4 + 3] = 255;
  }
  rc.putImageData(ri, 0, 0); tc.putImageData(ti, 0, 0);
  // conifer specks for texture at distance
  seed = 17; rc.fillStyle = 'rgba(16,26,14,.35)'; for (let n = 0; n < (isPhone ? 30000 : 90000); n++) { const u = rnd(), v = rnd(); const e = celevUV(u, v); if (e > 260) rc.fillRect(u * CTW, v * CTH, 1.6, 1.6); }
  const tex = c => { const t = new THREE.CanvasTexture(c); t.encoding = THREE.sRGBEncoding; t.anisotropy = renderer.capabilities.getMaxAnisotropy(); return t; };
  ctxMatReal = new THREE.MeshStandardMaterial({ map: tex(real), roughness: 1, metalness: 0, polygonOffset: true, polygonOffsetFactor: 3, polygonOffsetUnits: 3 });
  ctxMatFlat = new THREE.MeshBasicMaterial({ map: tex(topoC), toneMapped: false, polygonOffset: true, polygonOffsetFactor: 3, polygonOffsetUnits: 3 });
  ctxMesh = new THREE.Mesh(geo, ctxMatReal); ctxMesh.receiveShadow = true; ctxMesh.castShadow = true; scene.add(ctxMesh);
}
function buildBoundary() {
  if (boundary) { boundary.geometry.dispose(); scene.remove(boundary); }
  const ys = yScale(), pts = [], n = 160;
  const edge = (fn) => { for (let i = 0; i < n; i++) { const [u, v] = fn(i / n); pts.push(new THREE.Vector3(sxU(u), elevUV(u, v) * ys + .05 + ys * 10, szV(v))); } };
  edge(t => [t, 0]); edge(t => [1, t]); edge(t => [1 - t, 1]); edge(t => [0, 1 - t]); pts.push(pts[0].clone());
  const g = new THREE.BufferGeometry().setFromPoints(pts);
  boundary = new THREE.Line(g, new THREE.LineDashedMaterial({ color: 0xffffff, dashSize: .4, gapSize: .25, transparent: true, opacity: .95, depthTest: true, toneMapped: false }));
  boundary.computeLineDistances(); boundary.renderOrder = 6; scene.add(boundary);
}

// trees (canopy layer) — instanced conifers and bare broadleaf on forest pixels
let conifers, broadleaf, treeCells = [], treeUV = [];
function buildTrees() {
  const merge = list => { const pos = []; list.forEach(g => { const ng = g.index ? g.toNonIndexed() : g; pos.push(...ng.attributes.position.array); }); const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.computeVertexNormals(); return g; };
  const c1 = new THREE.ConeGeometry(.038, .1, 6); c1.translate(0, .07, 0); const c2 = new THREE.ConeGeometry(.027, .085, 6); c2.translate(0, .125, 0); const tr = new THREE.CylinderGeometry(.006, .008, .04, 4); tr.translate(0, .02, 0);
  const con = merge([c1, c2, tr]);
  const b1 = new THREE.IcosahedronGeometry(.036, 0); b1.scale(1, .85, 1); b1.translate(0, .075, 0); const t2 = new THREE.CylinderGeometry(.006, .009, .05, 4); t2.translate(0, .025, 0);
  const brd = merge([b1, t2]);
  const maxN = isPhone ? 6000 : 18000;
  const list = []; seed = 99;
  while (list.length < maxN) { const u = rnd(), v = rnd(), mi = ((v * MH) | 0) * MW + ((u * MW) | 0); if (!F[mi]) continue; const n = fbm(u * 7 + 5, v * 6 + 3, 2); list.push([u, v, n > .58 ? 1 : 0, .7 + .7 * rnd(), rnd() * 6.28]); }
  const cl = list.filter(t => !t[2]), bl = list.filter(t => t[2]);
  conifers = new THREE.InstancedMesh(con, new THREE.MeshStandardMaterial({ roughness: .9, flatShading: true }), cl.length);
  broadleaf = new THREE.InstancedMesh(brd, new THREE.MeshStandardMaterial({ roughness: .95, flatShading: true }), bl.length);
  for (const [im, arr] of [[conifers, cl], [broadleaf, bl]]) {
    im.userData.items = arr.map(([u, v, , s, r]) => { const [lon, lat] = [W + u * (E - W), N - v * (N - S)]; return { u, v, s, r, cell: cellOf(lon, lat) }; });
    im.castShadow = true; scene.add(im);
  }
  placeTrees(); colorTrees(-1, 0);
}
const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _s = new THREE.Vector3(), _p = new THREE.Vector3(), _yAxis = new THREE.Vector3(0, 1, 0);
function placeTrees() {
  const ys = yScale(), burnK = recIdx(state.t);
  for (const im of [conifers, broadleaf]) { im.userData.items.forEach((it, i) => {
    const burnt = it.cell >= 0 && first[it.cell] <= burnK; const sc = it.s * (burnt ? .75 : 1);
    _p.set(sxU(it.u), elevUV(it.u, it.v) * ys, szV(it.v)); _q.setFromAxisAngle(_yAxis, it.r); _s.set(sc, sc * (burnt ? .8 : 1), sc);
    im.setMatrixAt(i, _m.compose(_p, _q, _s)); }); im.instanceMatrix.needsUpdate = true; }
}
const _c = new THREE.Color();
function colorTrees(prevK, t) {
  const burnK = recIdx(t);
  for (const [im, base] of [[conifers, [0x2f4a2a, 0x3f5a30, 0x26402a]], [broadleaf, [0x7a6a52, 0x8a7a5c, 0x6c5e4a]]]) {
    im.userData.items.forEach((it, i) => { const burnt = it.cell >= 0 && first[it.cell] <= burnK; _c.setHex(burnt ? 0x1e1a17 : base[i % 3]); im.setColorAt(i, _c); });
    im.instanceColor.needsUpdate = true;
  }
}

// 3D heat surface: one vertex per 375 m cell, height ∝ log flux, inferno colours; collapses below ground where flux is negligible
let heatMesh = null;
function buildHeatMesh() {
  const g = new THREE.PlaneGeometry(1, 1, NC - 1, NR - 1); g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(NC * NR * 3), 3));
  heatMesh = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, opacity: .6, side: THREE.DoubleSide, depthWrite: false, toneMapped: false }));
  heatMesh.frustumCulled = false; heatMesh.renderOrder = 7; heatMesh.visible = false; scene.add(heatMesh);
}
function updateHeatMesh(t) {
  if (!heatMesh) return; const zk = hzK(t), on = L.heat3d.on && zk >= 0 && state.mode === '3d'; heatMesh.visible = on; if (!on) return;
  const fld = hzField(zk, (t - HZ[zk].t0) * 3600, state.member), ys = yScale(), p = heatMesh.geometry.attributes.position, c = heatMesh.geometry.attributes.color;
  for (let iy = 0; iy < NR; iy++) for (let ix = 0; ix < NC; ix++) { const i = (NR - 1 - iy) * NC + ix, vi = iy * NC + ix, [lon, lat] = cellCenter(i), u = uOf(lon), v = vOf(lat), fv = fluxV(fld.f[i]), g0 = elevUV(u, v) * ys, up = fv > .5;
    p.setXYZ(vi, sxU(u), up ? g0 + .04 + Math.pow((fv - .5) / .5, 1.2) * 1.1 : g0 - .2, szV(v)); const cc = inferno(.35 + .65 * fv); c.setXYZ(vi, Math.pow(cc[0] / 255, 2.2), Math.pow(cc[1] / 255, 2.2), Math.pow(cc[2] / 255, 2.2)); }
  p.needsUpdate = true; c.needsUpdate = true; heatMesh.material.opacity = .5 * L.heat3d.op / 100;
}
// fire: flames + embers (additive) and smoke (alpha), on active cells
function spriteMat(kind) {
  return new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, blending: kind === 'smoke' ? THREE.NormalBlending : THREE.AdditiveBlending,
    uniforms: { linOut: { value: 0 }, sz: { value: Math.min(3, Math.pow(SF, .8)) }, time: { value: 0 }, scale: { value: 400 }, ys: { value: .0025 }, wind: { value: new THREE.Vector2() }, night: { value: 0 }, op: { value: 1 } },
    vertexShader: `attribute float phase; attribute float kind; attribute float base; uniform float time, scale, ys, sz; uniform vec2 wind; varying float vA; varying float vK; varying float vAge;
      void main(){ vec3 p = position; p.y = base*ys + 0.012; float age; float size;
        if (kind < 0.5) { age = fract(time*1.9 + phase); p.y += sz*(0.02 + age*0.10); p.xz += sz*wind*age*0.08; size = sz*0.13*(1.0-age*0.55)*(0.8+0.4*fract(phase*7.0)); vA = (1.0-age); }
        else if (kind < 1.5) { age = fract(time*0.45 + phase); p.y += sz*age*0.55; p.xz += sz*(wind*age*0.9 + vec2(sin(phase*40.0+time*3.0), cos(phase*31.0+time*2.0))*0.05*age); size = sz*0.022; vA = 1.0-age; }
        else { age = fract(time*0.07 + phase); p.y += sz*age*1.9; p.xz += sz*wind*age*4.0; size = sz*(0.35 + age*1.6); vA = (1.0-age)*smoothstep(0.0,0.1,age); }
        vK = kind; vAge = age; vec4 mv = modelViewMatrix*vec4(p,1.0); gl_PointSize = size*scale/max(0.05,-mv.z); gl_Position = projectionMatrix*mv; }`,
    fragmentShader: `uniform float night, op, linOut; varying float vA; varying float vK; varying float vAge;
      void main(){ vec2 q = gl_PointCoord-0.5; float d = length(q)*2.0; if (d>1.0) discard;
        if (vK < 0.5) { float a = smoothstep(1.0,0.0,d)*vA; vec3 c = mix(vec3(1.0,0.28,0.04), vec3(1.0,0.86,0.45), smoothstep(0.7,0.0,d)*(1.0-vAge)); gl_FragColor = vec4(c*a*op, a*op); }
        else if (vK < 1.5) { float a = smoothstep(1.0,0.2,d)*vA; gl_FragColor = vec4(vec3(1.0,0.55,0.15)*a*op, a*op); }
        else { float a = smoothstep(1.0,0.1,d)*vA*0.32*op; vec3 c = mix(vec3(0.46,0.44,0.42), vec3(0.62,0.6,0.58), vAge); c = mix(c, vec3(0.95,0.42,0.16), night*(1.0-vAge)*0.6); gl_FragColor = vec4(mix(c, pow(c, vec3(2.2)), linOut), a); } }`,
  });
}
const flameMat = spriteMat('flame'), smokeMat = spriteMat('smoke');
smokeMat.uniforms.sz = flameMat.uniforms.sz;
const flames = new THREE.Points(new THREE.BufferGeometry(), flameMat), smoke = new THREE.Points(new THREE.BufferGeometry(), smokeMat);
flames.frustumCulled = smoke.frustumCulled = false; smoke.renderOrder = 2; flames.renderOrder = 3;
scene.add(smoke, flames);
let activeCells = [];
function setFireParticles(cells) {
  const fp = [], fph = [], fk = [], fb = [], sp = [], sph = [], sk = [], sb = [];
  seed = 5;
  cells.forEach((ci, n) => { const [lon, lat] = cellCenter(ci);
    const nf = 5, ne = 2, ns = cells.length > 300 ? (n % 2 ? 0 : 1) : 2;
    const put = (P, PH, K, Bs, kind) => { const u = uOf(lon + (rnd() - .5) * .0036), v = vOf(lat + (rnd() - .5) * .0031); P.push(sxU(u), 0, szV(v)); PH.push(rnd()); K.push(kind); Bs.push(elevUV(u, v)); };
    for (let i = 0; i < nf; i++) put(fp, fph, fk, fb, 0); for (let i = 0; i < ne; i++) put(fp, fph, fk, fb, 1); for (let i = 0; i < ns; i++) put(sp, sph, sk, sb, 2); });
  const set = (pts, P, PH, K, Bs) => { const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(P, 3)); g.setAttribute('phase', new THREE.Float32BufferAttribute(PH, 1)); g.setAttribute('kind', new THREE.Float32BufferAttribute(K, 1)); g.setAttribute('base', new THREE.Float32BufferAttribute(Bs, 1)); pts.geometry.dispose(); pts.geometry = g; };
  set(flames, fp, fph, fk, fb); set(smoke, sp, sph, sk, sb);
}

// wind particles: streak lines, additive so tails fade into the ground
const NP = matchMedia('(max-width: 860px)').matches ? 1300 : 2300;
const wp = new Float32Array(NP * 3); seed = 3; for (let i = 0; i < NP; i++) { wp[i * 3] = rnd(); wp[i * 3 + 1] = rnd(); wp[i * 3 + 2] = rnd() * 4; }
const wgeo = new THREE.BufferGeometry(), wpos = new Float32Array(NP * 6), wcol = new Float32Array(NP * 6);
wgeo.setAttribute('position', new THREE.BufferAttribute(wpos, 3)); wgeo.setAttribute('color', new THREE.BufferAttribute(wcol, 3));
const windMat = new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, opacity: .9 });
const windLines = new THREE.LineSegments(wgeo, windMat); windLines.frustumCulled = false; windLines.renderOrder = 4; scene.add(windLines);
function stepWind(dt) {
  const useU = L.wu.on, useV = L.wv.on, ys = yScale(), k = .045, trail = .55, op = Math.max(L.wu.on ? L.wu.op : 0, L.wv.on ? L.wv.op : 0) / 100;
  for (let i = 0; i < NP; i++) {
    let u = wp[i * 3], v = wp[i * 3 + 1], age = wp[i * 3 + 2];
    let [wu, wv] = windAt(u, v); if (!useU) wu = 0; if (!useV) wv = 0;
    u += wu * k * dt / KX; v -= wv * k * dt / KY; age += dt;
    if (u < 0 || u > 1 || v < 0 || v > 1 || age > 5 + (i % 7)) { u = rnd(); v = rnd(); age = 0; }
    wp[i * 3] = u; wp[i * 3 + 1] = v; wp[i * 3 + 2] = age;
    const tu = u - wu * k * trail / KX, tv = v + wv * k * trail / KY, lift = .05 + .9 * ys / 2.5 * .1;
    const life = Math.sin(Math.PI * clamp(age / (5 + (i % 7)), 0, 1)), sp = Math.hypot(wu, wv), b = life * op * clamp(.35 + sp / 14, .35, 1) * (elevUV(u, v) < .5 ? .3 : 1);
    wpos.set([sxU(u), yAt(u, v) + lift, szV(v), sxU(tu), yAt(tu, tv) + lift, szV(tv)], i * 6);
    const hc = flatF > .5 ? [b * .34, b * .26, b * .14] : [b * .95, b * .97, b];
    wcol.set([hc[0], hc[1], hc[2], 0, 0, 0], i * 6);
  }
  wgeo.attributes.position.needsUpdate = true; wgeo.attributes.color.needsUpdate = true;
}

// evacuation routes (recorded Route-Check results): ribbons + moving vehicle
const VERDICT = { checked_route: { t: tr('확인된 경로', 'Checked route'), c: 0x2f8a57, css: '#2f8a57' }, model_no_route: { t: tr('모델상 경로 없음', 'No route in the model'), c: 0x1e1e1e, css: '#1e1e1e' }, unresolved: { t: tr('미확인', 'Unresolved'), c: 0x8a8a8a, css: '#8a8a8a' } };
// densify for draping: sample every .06 scene units, distances in real km
const densify = pts0 => { const pts = (pts0 || []).map(([lon, lat, ts]) => ({ u: uOf(lon), v: vOf(lat), ts })), dense = [];
  for (let i = 0; i < pts.length - 1; i++) { const a = pts[i], b = pts[i + 1], dkm = Math.hypot((b.u - a.u) * KX, (b.v - a.v) * KY), n = Math.max(1, Math.ceil(dkm / .06));
    for (let j = 0; j < n; j++) { const f = j / n; dense.push({ u: a.u + (b.u - a.u) * f, v: a.v + (b.v - a.v) * f, ts: a.ts + (b.ts - a.ts) * f }); } }
  if (pts.length) dense.push(pts[pts.length - 1]);
  let acc = 0; dense.forEach((p, i) => { if (i) acc += Math.hypot((p.u - dense[i - 1].u) * KXr, (p.v - dense[i - 1].v) * KYr); p.d = acc; p.e = elevUV(p.u, p.v); p.cell = cellOf(W + p.u * (E - W), N - p.v * (N - S)); });
  return { dense, lenKm: acc }; };
const routes = B.routes.map((r, ri) => {
  const t0 = hOf(r.input_time), { dense, lenKm } = densify(r.pts);
  return { ...r, idx: ri, t0, dense, has: dense.length > 1, tDep: t0 + r.dep / 3600, tArr: r.arr != null ? t0 + r.arr / 3600 : null, lenKm, label: r.case.split('_').pop() };
});
function recomputeExposure(k, dense, p) {
  // cell-centre, piecewise-constant approximation of travel + destination dwell exposure, per scenario
  return [0, 1, 2, 3].map(mi => { let dose = p.incurred || 0, peak = 0, contact = false; const series = [[dense.length ? dense[0].ts : 0, dose]];
    for (let i = 0; i < dense.length - 1; i++) { const a = dense[i], b = dense[i + 1], dt = b.ts - a.ts, mid = (a.ts + b.ts) / 2, c = a.cell;
      if (c >= 0 && dt > 0) { const F = hzFlux(k, mi, c, mid); dose += F * dt; peak = Math.max(peak, F); if (hzFlame(k, mi, c, mid)) contact = true; }
      series.push([b.ts, dose]); }
    const last = dense[dense.length - 1];
    if (last && last.cell >= 0 && p.dwell_s) for (let j = 0; j < 12; j++) { const dt = p.dwell_s / 12, mid = p.arr + dt * (j + .5), F = hzFlux(k, mi, last.cell, mid); dose += F * dt; peak = Math.max(peak, F); if (hzFlame(k, mi, last.cell, mid)) contact = true; series.push([p.arr + dt * (j + 1), dose]); }
    return { dose, peak, contact, series }; });
}
const CASES = routes.map(r => { const k = HZ.findIndex(h => Math.abs(h.t0 - r.t0) < 1e-6), pol = {};
  for (const [name, pp] of Object.entries((B.policies || {})[r.case] || {})) { const { dense, lenKm } = densify(pp.pts); pol[name] = { ...pp, dense, lenKm, exp: k >= 0 && dense.length > 1 ? recomputeExposure(k, dense, pp) : null }; }
  const travelHits = pol.travel_only ? flameHits(pol.travel_only.dense, k) : [];
  return { r, k, pol, travelHits }; });
const routeGroup = new THREE.Group(); scene.add(routeGroup);
// vehicles: one per recorded case, moving on the checked (full-policy) route by its recorded times
const cars = routes.map(() => { const grp = new THREE.Group();
  const body = new THREE.Mesh(new THREE.BoxGeometry(.17, .055, .085).translate(0, .045, 0), new THREE.MeshStandardMaterial({ color: 0xf2f1ec, roughness: .35, metalness: .25 }));
  const cab = new THREE.Mesh(new THREE.BoxGeometry(.085, .05, .075).translate(-.012, .095, 0), new THREE.MeshStandardMaterial({ color: 0x2f8a57, roughness: .3 }));
  const lamp = new THREE.Mesh(new THREE.SphereGeometry(.022, 8, 6), new THREE.MeshBasicMaterial({ color: 0xfff1b8, toneMapped: false })); lamp.position.set(.09, .05, 0);
  const beacon = new THREE.Mesh(new THREE.SphereGeometry(.018, 8, 6), new THREE.MeshBasicMaterial({ color: 0x5cff9a, toneMapped: false })); beacon.position.set(-.012, .13, 0);
  body.castShadow = cab.castShadow = true; grp.add(body, cab, lamp, beacon); grp.scale.setScalar(1.8); grp.visible = false; scene.add(grp); return grp; });
function updateCars(t) {
  routes.forEach((r, i) => { const car = cars[i], on = L.routes.on && state.mode === '3d' && r.has && t >= r.tDep && t <= r.tArr && cmpShows('full'); car.visible = on; if (!on) return;
    const s = (t - r.t0) * 3600; let j = r.dense.findIndex(p => p.ts >= s); if (j < 1) j = 1; const a = r.dense[j - 1], b = r.dense[j];
    const f = b.ts > a.ts ? clamp((s - a.ts) / (b.ts - a.ts), 0, 1) : 1, u = a.u + (b.u - a.u) * f, v = a.v + (b.v - a.v) * f;
    car.position.set(sxU(u), yAt(u, v) + .01, szV(v)); car.rotation.y = -Math.atan2((b.v - a.v) * KY, (b.u - a.u) * KX);
    car.children[3].material.color.setHex((Math.floor(performance.now() / 350) % 2) ? 0x5cff9a : 0x1d6b3f); });
}
// ribbon draped on the terrain; dash is in real km along the route
function ribbonMesh(dense, w, color, opacity, dash, lift, order = 5) { const pos = [], idx = [], ys = yScale();
  dense.forEach((p, i) => { const a = dense[Math.max(0, i - 1)], b = dense[Math.min(dense.length - 1, i + 1)];
    let dx = (b.u - a.u) * KX, dz = (b.v - a.v) * KY; const l = Math.hypot(dx, dz) || 1; dx /= l; dz /= l;
    const x = sxU(p.u), z = szV(p.v), y = p.e * ys + lift + ys * 4; pos.push(x - dz * w, y, z + dx * w, x + dz * w, y, z - dx * w);
    if (i && (!dash || Math.floor(p.d / dash) % 2 === 0)) { const k = (i - 1) * 2; idx.push(k, k + 1, k + 2, k + 1, k + 3, k + 2); } });
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx);
  const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ color, transparent: true, opacity, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -6, polygonOffsetUnits: -6, toneMapped: false }));
  m.renderOrder = order; return m; }
function puck(u, v, col, r = .09) { const ys = yScale(), grp = new THREE.Group();
  const s = new THREE.Mesh(new THREE.CylinderGeometry(r, r, .05, 16), new THREE.MeshBasicMaterial({ color: col, toneMapped: false }));
  const ring = new THREE.Mesh(new THREE.CylinderGeometry(r * 1.33, r * 1.33, .04, 16), new THREE.MeshBasicMaterial({ color: 0x1e1e1e, toneMapped: false }));
  s.position.set(sxU(u), elevUV(u, v) * ys + .03 + ys * 4, szV(v)); ring.position.copy(s.position); ring.position.y -= .01; grp.add(ring, s); return grp; }
// flame-contact marks on a route: dense points inside a cell that a scenario marks as flame at that time (cell-centre recomputation)
function flameHits(dense, k) { const out = []; if (k < 0) return out;
  dense.forEach((p, i) => { if (p.cell < 0) return; const ms = [0, 1, 2, 3].filter(m => hzFlame(k, m, p.cell, p.ts)); if (ms.length) out.push({ i, p, ms }); }); return out; }
const disposeGroup = g => { g.traverse(o => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); }); g.clear(); };
function buildRouteMeshes() {
  disposeGroup(routeGroup); const ys = yScale();
  const ribbon = (...a) => routeGroup.add(ribbonMesh(...a));
  // flame contact: red over each run of consecutive dense points inside a flame cell, with a marker at the run start
  const markHits = (dense, hits, w) => { let run = null; const flush = () => { if (!run) return; const seg = dense.slice(run[0], run[1] + 2);
      if (seg.length > 1) routeGroup.add(ribbonMesh(seg, w, 0xff2a14, 1, 0, .05, 9));
      const p0 = dense[run[0]], m = new THREE.Mesh(new THREE.SphereGeometry(w * .9, 12, 8), new THREE.MeshBasicMaterial({ color: 0xff2a14, toneMapped: false })); m.position.set(sxU(p0.u), p0.e * ys + .1 + ys * 4, szV(p0.v)); m.renderOrder = 9; routeGroup.add(m); run = null; };
    for (const h of hits) { if (run && h.i === run[1] + 1) run[1] = h.i; else { flush(); run = [h.i, h.i]; } } flush(); };
  const sc = CASES[selRoute], op = L.routes.op / 100;
  // comparison mode "travel time only": every case's travel-time-only route, flame contact marked in red
  if (state.cmp === 'travel') {
    for (const c of CASES) { const pp = c.pol.travel_only; if (!pp || pp.dense.length < 2) continue; const sel = c === sc;
      ribbon(pp.dense, sel ? .09 : .06, POLICY.travel_only.c, .95 * op, 0, .03);
      markHits(pp.dense, c.travelHits, sel ? .13 : .1);
      routeGroup.add(puck(pp.dense[0].u, pp.dense[0].v, 0xffffff), puck(pp.dense[pp.dense.length - 1].u, pp.dense[pp.dense.length - 1].v, POLICY.travel_only.c)); }
    return;
  }
  if (sc && cmpShows('full')) for (const name of POLICY_ORDER) { if (name === 'full' || !state.pols.has(name)) continue; const pp = sc.pol[name]; if (pp && pp.dense.length > 1) { ribbon(pp.dense, name === 'travel_only' ? .085 : .05, POLICY[name].c, .95 * op, name === 'travel_only' ? .3 : 0, .03);
    if (name === 'travel_only') markHits(pp.dense, sc.travelHits, .12); } }
  if (!cmpShows('full')) return;
  for (const r of routes) {
    if (!r.has) { if (r.o && r.d) { const v = VERDICT[r.verdict] || VERDICT.unresolved; routeGroup.add(puck(uOf(r.o[0]), vOf(r.o[1]), 0xffffff), puck(uOf(r.d[0]), vOf(r.d[1]), v.c)); } continue; }
    const w = selRoute === r.idx ? .07 : .045, pos = [], idx = [];
    r.dense.forEach((p, i) => { const a = r.dense[Math.max(0, i - 1)], b = r.dense[Math.min(r.dense.length - 1, i + 1)];
      let dx = (b.u - a.u) * KX, dz = (b.v - a.v) * KY; const l = Math.hypot(dx, dz) || 1; dx /= l; dz /= l;
      const x = sxU(p.u), z = szV(p.v), y = p.e * ys + .018 + ys * 4;
      pos.push(x - dz * w, y, z + dx * w, x + dz * w, y, z - dx * w);
      if (i) { const k = (i - 1) * 2; idx.push(k, k + 1, k + 2, k + 1, k + 3, k + 2); } });
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx);
    const v = VERDICT[r.verdict] || VERDICT.unresolved;
    const m = new THREE.Mesh(g, new THREE.MeshBasicMaterial({ color: v.c, transparent: true, opacity: (selRoute === r.idx ? 1 : .8) * L.routes.op / 100, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -6, polygonOffsetUnits: -6, toneMapped: false }));
    m.renderOrder = 5; routeGroup.add(m);
    for (const [p, col] of [[r.dense[0], 0xffffff], [r.dense[r.dense.length - 1], v.c]]) routeGroup.add(puck(p.u, p.v, col));
  }
}
let selRoute = routes[2] && routes[2].has ? 2 : Math.max(0, routes.findIndex(r => r.has));

// ---------------- layers & state ----------------
const N_ORIG = B.places.filter(p => p.role === 'origin').length, N_DEST = B.places.filter(p => p.role === 'destination').length;
const LAYERS = [
  { g: tr('지형·바탕', 'Terrain · base'), id: 'relief', n: tr('지형 (3D)', 'Terrain (3D)'), src: tr('공개 DEM', 'Public DEM'), on: true, op: 100, noOp: true },
  { id: 'base', n: tr('바탕 지도', 'Base map'), src: tr('OSM 도로·하천·토지이용', 'OSM roads · water · land use'), on: true, op: 100 },
  { id: 'slope', n: tr('경사', 'Slope'), src: tr('DEM에서 계산 · 1ch', 'From the DEM · 1 ch'), on: false, op: 75 },
  { g: tr('환경 입력 ✱ 설명용', 'Environment inputs ✱ illustrative'), id: 'temp', n: tr('기온', 'Temperature'), src: tr('설명용 · 1ch', 'Illustrative · 1 ch'), ill: true, on: false, op: 70 },
  { id: 'wu', n: tr('바람 u (동서 성분)', 'Wind u (east–west)'), src: tr('설명용 · 1ch', 'Illustrative · 1 ch'), ill: true, on: true, op: 90 },
  { id: 'wv', n: tr('바람 v (남북 성분)', 'Wind v (north–south)'), src: tr('설명용 · 1ch', 'Illustrative · 1 ch'), ill: true, on: true, op: 90 },
  { id: 'canopy', n: tr('수목 피복률', 'Canopy cover'), src: tr('설명용 · 1ch · 3D 나무 포함', 'Illustrative · 1 ch · with 3D trees'), ill: true, on: true, op: 100 },
  { id: 'biome', n: tr('생물군계', 'Biome'), src: tr('설명용 · one-hot 14ch', 'Illustrative · one-hot 14 ch'), ill: true, on: false, op: 65 },
  { g: tr('기록 · 모델 출력', 'Records · model output'), id: 'burn', n: tr('연소 상태 B(t)', 'Burned state B(t)'), src: tr(`기록 (재구성) · ${B.footprints.length}개 시각`, `Recorded (reconstructed) · ${B.footprints.length} times`), on: true, op: 92 },
  { id: 'front', n: tr('연소 전선', 'Fire front'), src: tr('기록 경계 · 활성 셀', 'Recorded edge · active cells'), on: true, op: 100 },
  { id: 'q', n: tr('새 연소 확률 q', 'New-burn probability q'), src: tr('모델 출력 · 다음 1시간', 'Model output · next hour'), on: true, op: 88 },
  { id: 'heat', n: tr('복사 열유속 F(x)', 'Radiant heat flux F(x)'), src: tr('경로 위험 입력 · 화재 scenario 4개 · 입력 후 1시간', 'Routing hazard input · 4 fire scenarios · 1 h after input'), on: true, op: 90 },
  { id: 'heat3d', n: tr('열유속 3D 표면', 'Heat flux 3D surface'), src: tr('같은 값 · log 높이 (3D 지형에서만)', 'Same values · log height (3D only)'), on: true, op: 80 },
  { id: 'mc', n: tr('시간별 누적 연소 확률 F(h)', 'Hourly cumulative burn probability F(h)'), src: HR ? tr(`몬테카를로 ${HR.meta.n_samples.toLocaleString()}회 · 1–${HH}시간`, `Monte Carlo ${HR.meta.n_samples.toLocaleString()} runs · 1–${HH} h`) : tr('데이터 없음 · Mac에서 내보내기 필요', 'No data · export on the Mac'), ill: !HR, on: !!HR, op: 80, disabled: !HR },
  { g: tr('대피 계획', 'Evacuation planning'), id: 'routes', n: tr('대피 경로 점검', 'Route checks'), src: tr(`기록된 Route-Check ${routes.length}건`, `${routes.length} recorded Route-Checks`), on: true, op: 100 },
  { id: 'booth', n: tr('대피 현황 (부스 캐시)', 'Evacuation status (booth cache)'), src: B.booth ? tr('실제 API 결과 · 출발지별 판정', 'Real API results · per origin') : tr('이 지역은 캐시 없음', 'No cache for this region'), on: !!B.booth, op: 100, disabled: !B.booth },
  { id: 'places', n: tr('마을 · 대피소', 'Villages · shelters'), src: tr(`OSM · 출발지 ${N_ORIG}, 대피소 ${N_DEST}`, `OSM · ${N_ORIG} origins, ${N_DEST} shelters`), on: true, op: 100 },
  { id: 'labels', n: tr('지명 · 산', 'Place names · peaks'), src: 'OSM', on: true, op: 100 },
];
const L = Object.fromEntries(LAYERS.map(l => [l.id, l]));
const state = { t: B.id === 'uiseong_andong_2025' ? 70.3 : INP[INP.length - 1] + .3, playing: false, speed: 1, mode: '3d', base2d: 'topo', member: -1, detail: false, dk: 0, pols: new Set(['travel_only']), cmp: 'ours', boothK: -1, focus: null };
// which result layers the comparison mode keeps: 'ours' = everything
const cmpShows = what => state.cmp === 'ours' || (state.cmp === 'travel' && what === 'travel');
let dirty = true, lastKey = '';

// ---------------- compose draped texture ----------------
const QX = new Float32Array(NCELL * 4), QY = new Float32Array(NCELL * 4), EQX = new Float32Array(NCELL * 4), EQY = new Float32Array(NCELL * 4);
for (let r = 0; r < NR; r++) for (let c = 0; c < NC; c++) { const i = r * NC + c; [[r, c], [r, c + 1], [r + 1, c + 1], [r + 1, c]].forEach(([rr, cc], j) => { const [lo, la] = lat_(rr, cc); const [x, y] = toPx(lo, la, TW, TH); QX[i * 4 + j] = x; QY[i * 4 + j] = y; EQX[i * 4 + j] = x * MW / TW; EQY[i * 4 + j] = y * MH / TH; }); }
function quad(ctx, i, X, Y) { ctx.moveTo(X[i * 4], Y[i * 4]); ctx.lineTo(X[i * 4 + 1], Y[i * 4 + 1]); ctx.lineTo(X[i * 4 + 2], Y[i * 4 + 2]); ctx.lineTo(X[i * 4 + 3], Y[i * 4 + 3]); ctx.closePath(); }
const Q_STOPS = [[.005, [253, 230, 205]], [.03, [251, 196, 140]], [.1, [244, 140, 66]], [.25, [226, 85, 43]], [.5, [170, 30, 25]]];
function qColor(q) { let c = Q_STOPS[0][1]; for (let j = 0; j < Q_STOPS.length - 1; j++) if (q >= Q_STOPS[j][0]) c = mix3(Q_STOPS[j][1], Q_STOPS[j + 1][1], clamp((q - Q_STOPS[j][0]) / (Q_STOPS[j + 1][0] - Q_STOPS[j][0]), 0, 1)); return c; }
const MC_STOPS = [[.01, [214, 194, 238]], [.1, [186, 146, 222]], [.3, [158, 105, 200]], [.6, [110, 50, 160]], [.9, [64, 16, 110]]];
function mcColor(q) { let c = MC_STOPS[0][1]; for (let j = 0; j < MC_STOPS.length - 1; j++) if (q >= MC_STOPS[j][0]) c = mix3(MC_STOPS[j][1], MC_STOPS[j + 1][1], clamp((q - MC_STOPS[j][0]) / (MC_STOPS[j + 1][0] - MC_STOPS[j][0]), 0, 1)); return c; }
const ageOf = (i, t) => first[i] === 0 ? t + 24 : t - REC[first[i]];   // the first record already holds fire from 03-22
function burnedAt(i, k) { return first[i] !== 255 && first[i] <= k; }
function frontEdges(k, t) {
  // perimeter edges of the recorded burned area at record k; active where the cell burned in that record
  const act = [], old = [];
  if (k < 0) return { act, old };
  for (let r = 0; r < NR; r++) for (let c = 0; c < NC; c++) { const i = r * NC + c; if (!burnedAt(i, k)) continue;
    const active = ageOf(i, t) < 18;
    const nb = [[r, c + 1, [r, c + 1], [r + 1, c + 1]], [r, c - 1, [r, c], [r + 1, c]], [r + 1, c, [r + 1, c], [r + 1, c + 1]], [r - 1, c, [r, c], [r, c + 1]]];
    for (const [rr, cc, a, b] of nb) { const out = rr < 0 || rr >= NR || cc < 0 || cc >= NC || !burnedAt(rr * NC + cc, k); if (out) (active ? act : old).push([a, b, i]); } }
  return { act, old };
}
let tempKey = '', emberPat, emberPatE, cellsCv;
function vnP(x, y, P) { const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi, u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf), m = a => ((a % P) + P) % P;
  const a = h2(m(xi), m(yi)), b = h2(m(xi + 1), m(yi)), c = h2(m(xi), m(yi + 1)), d = h2(m(xi + 1), m(yi + 1)); return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v; }
function buildEmber() {
  const n = 256, c = mk(n, n), x = c.getContext('2d'), im = x.createImageData(n, n);
  for (let py = 0; py < n; py++) for (let px = 0; px < n; px++) {
    let f = 0, a = .5, nn = 0; for (let o = 0; o < 4; o++) { const P = 8 << o; f += a * vnP(px / n * P, py / n * P, P); nn += a; a *= .5; } f /= nn;
    const heat = smooth(.5, .74, f), col = heat > .6 ? mix3([255, 140, 50], [255, 222, 140], (heat - .6) / .4) : mix3([140, 28, 10], [250, 110, 36], heat / .6);
    im.data.set([col[0], col[1], col[2], Math.round(255 * Math.min(1, heat * 1.15))], (py * n + px) * 4);
  }
  x.putImageData(im, 0, 0);
  cellsCv = mk(TW, TH); emberPat = cellsCv.getContext('2d').createPattern(c, 'repeat'); emberPatE = emissive.getContext('2d').createPattern(c, 'repeat');
}
function compose() {
  const t = state.t, k = recIdx(t), qi = inpIdx(t), flat = state.mode === '2d';
  const cx = composite.getContext('2d'); cx.globalAlpha = 1; cx.globalCompositeOperation = 'source-over';
  if (L.base.on) { cx.drawImage(flat ? (state.base2d === 'topo' ? topo : groundHS) : ground, 0, 0); if (L.base.op < 100) { cx.globalAlpha = 1 - L.base.op / 100; cx.fillStyle = '#d6d2c9'; cx.fillRect(0, 0, TW, TH); } }
  else { cx.fillStyle = '#d9d5cc'; cx.fillRect(0, 0, TW, TH); if (flat) { cx.globalCompositeOperation = 'multiply'; cx.drawImage(hsCv, 0, 0, TW, TH); cx.globalCompositeOperation = 'source-over'; } }
  cx.imageSmoothingEnabled = true;
  if (L.biome.on) { cx.globalAlpha = L.biome.op / 100; cx.drawImage(biomeCv, 0, 0, TW, TH); }
  if (L.canopy.on) { cx.globalAlpha = (flat ? .55 : .2) * L.canopy.op / 100; cx.drawImage(canopyCv, 0, 0, TW, TH); }
  if (L.slope.on) { cx.globalAlpha = L.slope.op / 100; cx.drawImage(slopeCv, 0, 0, TW, TH); }
  if (L.temp.on) { const tk = Math.round(t * 2) / 2; if (tk + '' !== tempKey) { drawTemp(tk); tempKey = tk + ''; } cx.globalAlpha = L.temp.op / 100; cx.drawImage(tempCv, 0, 0, TW, TH); }
  // B(t): recorded burned cells as char; newly recorded cells smoulder (mottled embers) and cool over ~4 h
  const qiNow = qi, bc = cellsCv.getContext('2d'); bc.clearRect(0, 0, TW, TH);
  const em = emissive.getContext('2d'); em.globalAlpha = 1; em.fillStyle = '#000'; em.fillRect(0, 0, MW, MH);
  const buckets = new Map();
  if (k >= 0) for (let i = 0; i < NCELL; i++) { if (!burnedAt(i, k)) continue; const gl = Math.exp(-ageOf(i, t) / 4); if (gl < .04) continue; const key = Math.round(gl * 10); (buckets.get(key) || buckets.set(key, []).get(key)).push(i); }
  const ember = (cells, a, tint) => {
    for (const [ctx, X, Y, pat, w, h] of [[bc, QX, QY, emberPat, TW, TH], [em, EQX, EQY, emberPatE, MW, MH]]) {
      ctx.save(); ctx.beginPath(); cells.forEach(i => quad(ctx, i, X, Y)); ctx.clip(); ctx.globalAlpha = a; ctx.fillStyle = pat; ctx.fillRect(0, 0, w, h);
      if (tint && ctx === bc) { ctx.globalAlpha = tint; ctx.fillStyle = '#ff7a2a'; ctx.fillRect(0, 0, w, h); } ctx.restore(); }
  };
  if (L.burn.on && k >= 0) {
    bc.fillStyle = 'rgb(44,39,35)'; bc.beginPath(); for (let i = 0; i < NCELL; i++) if (burnedAt(i, k)) quad(bc, i, QX, QY); bc.fill();
    bc.fillStyle = 'rgba(139,132,122,.4)'; seed = 41;
    for (let i = 0; i < NCELL; i++) if (burnedAt(i, k)) for (let n = 0; n < 4; n++) { const a = rnd(), b = rnd(); bc.fillRect(QX[i * 4] + (QX[i * 4 + 1] - QX[i * 4]) * a, QY[i * 4] + (QY[i * 4 + 3] - QY[i * 4]) * b, 2, 2); }
    for (const [key, cells] of buckets) ember(cells, key / 10 * .9);
  }
  if (L.front.on && qiNow >= 0 && BURNING[qiNow].size) { if (!L.burn.on) { bc.fillStyle = 'rgb(44,39,35)'; bc.beginPath(); for (const i of BURNING[qiNow]) quad(bc, i, QX, QY); bc.fill(); } ember([...BURNING[qiNow]], 1, .22); }
  if ((L.burn.on && k >= 0) || L.front.on) { cx.globalAlpha = (L.burn.on ? L.burn.op : 100) / 100; cx.filter = 'blur(1.4px)'; cx.drawImage(cellsCv, 0, 0); cx.filter = 'none'; }
  // F(h): recursive Monte Carlo cumulative new-burn probability, stepped by whole hours after its input time
  const hk = hourIdx(t);
  if (L.mc.on && HR && hk >= 0) { const hh = t - HCUT[hk], hs = hourStep(t, hk), f = hh <= HH ? 1 : .4; cx.globalAlpha = L.mc.op / 100 * f;
    for (let i = 0; i < NCELL; i++) { if (!HV[hk][i]) continue; const v = Fh(hk, i, hs); if (v < .01) continue; const c = mcColor(v); cx.fillStyle = `rgb(${c.map(Math.round)})`; cx.beginPath(); quad(cx, i, QX, QY); cx.fill(); }
    cx.globalAlpha = L.mc.op / 100 * f * .9; cx.strokeStyle = '#2b0b4a'; cx.lineWidth = 1.6; cx.setLineDash([6, 4]); cx.beginPath();
    const a = A50[hk];
    for (let r = 0; r < NR; r++) for (let c = 0; c < NC; c++) { const i = r * NC + c, ai = a[i];
      for (const [rr, cc, p1, p2] of [[r, c + 1, [r, c + 1], [r + 1, c + 1]], [r + 1, c, [r + 1, c], [r + 1, c + 1]]]) { if (rr >= NR || cc >= NC) continue; const aj = a[rr * NC + cc]; if (ai === aj) continue; if (Math.min(ai, aj) > hs) continue;
        const A = toPx(...lat_(...p1), TW, TH), Bp = toPx(...lat_(...p2), TW, TH); cx.moveTo(...A); cx.lineTo(...Bp); } }
    cx.stroke(); cx.setLineDash([]); }
  // q: model output, valid one hour after its input time
  if (L.q.on && qi >= 0) { const age = t - INP[qi], f = age <= 1 ? 1 : .42; cx.globalAlpha = L.q.op / 100 * f;
    const q = QF[qi];
    for (let i = 0; i < NCELL; i++) { const v = q[i]; if (v < .005 || (L.burn.on && burnedAt(i, k) && age > 1)) continue; const c = qColor(v); cx.fillStyle = `rgb(${c.map(Math.round)})`; cx.beginPath(); quad(cx, i, QX, QY); cx.fill(); }
    if (age <= 1) { cx.globalAlpha = L.q.op / 100 * .9; cx.strokeStyle = 'rgba(120,20,10,.55)'; cx.lineWidth = 1; for (let i = 0; i < NCELL; i++) if (q[i] >= .1) { cx.beginPath(); quad(cx, i, QX, QY); cx.stroke(); } }
  }
  // F(x): recorded routing hazard (incident radiant flux) for the selected scenario, or the maximum of the four
  const zk = hzK(t);
  if (L.heat.on && zk >= 0) { const fld = hzField(zk, (t - HZ[zk].t0) * 3600, state.member);
    for (let i = 0; i < NCELL; i++) { const v = fluxV(fld.f[i]); if (v < .5) continue; const c = inferno(.15 + .85 * v); cx.globalAlpha = L.heat.op / 100 * smooth(.5, .75, v) * .9; cx.fillStyle = `rgb(${c.map(Math.round)})`; cx.beginPath(); quad(cx, i, QX, QY); cx.fill(); }
    cx.globalAlpha = L.heat.op / 100; cx.fillStyle = '#fff3c0'; cx.beginPath(); fld.flame.forEach(i => quad(cx, i, QX, QY)); cx.fill();
    em.globalAlpha = .8; em.fillStyle = '#ffd27a'; em.beginPath(); fld.flame.forEach(i => quad(em, i, EQX, EQY)); em.fill(); em.globalAlpha = 1; }
  // front
  const fe = frontEdges(k, t), act = new Set();
  if (L.front.on && k >= 0) {
    cx.globalAlpha = L.front.op / 100; cx.lineCap = 'round';
    cx.strokeStyle = 'rgba(70,40,30,.9)'; cx.lineWidth = 1.6; cx.beginPath(); for (const [a, b] of fe.old) { const A = toPx(...lat_(...a), TW, TH), Bp = toPx(...lat_(...b), TW, TH); cx.moveTo(...A); cx.lineTo(...Bp); } cx.stroke();
    cx.strokeStyle = '#ff6a1f'; cx.lineWidth = 3.2; cx.beginPath(); for (const [a, b, i] of fe.act) { act.add(i); const A = toPx(...lat_(...a), TW, TH), Bp = toPx(...lat_(...b), TW, TH); cx.moveTo(...A); cx.lineTo(...Bp); } cx.stroke();
    em.strokeStyle = '#ff7a2a'; em.lineWidth = 2.4; em.beginPath(); for (const [a, b] of fe.act) { const A = toPx(...lat_(...a), MW, MH), Bp = toPx(...lat_(...b), MW, MH); em.moveTo(...A); em.lineTo(...Bp); } em.stroke();
  }
  if (zk >= 0) hzField(zk, (t - HZ[zk].t0) * 3600, state.member).flame.forEach(i => act.add(i)); else if (qi >= 0) for (const i of BURNING[qi]) act.add(i);
  cx.globalAlpha = 1;
  tex.needsUpdate = true; emTex.needsUpdate = true;
  activeCells = L.front.on ? [...act] : [];
  setFireParticles(activeCells); updateHeatMesh(t);
}

// ---------------- labels / markers (DOM) ----------------
const labelsEl = $('labels'), domItems = [], PLACE_DOM = new Map();
function addDom(cls, html, u, v, extra = {}) { const el = document.createElement('div'); el.className = cls; el.innerHTML = html; labelsEl.appendChild(el); const it = { el, u, v, ...extra }; domItems.push(it); return it; }
function buildDom() {
  const nm = o => EN ? (o.ne || o.n) : o.n;
  const towns = B.labels.filter(l => l.k === 'town' || l.k === 'city'), vill = B.labels.filter(l => l.k !== 'town' && l.k !== 'city');
  towns.forEach(l => addDom('lb town', nm(l), uOf(l.lon), vOf(l.lat), { layer: 'labels', lift: .25 }));
  vill.forEach(l => addDom('lb', nm(l), uOf(l.lon), vOf(l.lat), { layer: 'labels', near: 13, lift: .15 }));
  [...B.peaks].sort((a, b) => (b.e || 0) - (a.e || 0)).slice(0, 12).forEach(p => addDom('lb peak', `${nm(p)}<small>${p.e ? p.e.toLocaleString() + ' m' : ''}</small>`, uOf(p.lon), vOf(p.lat), { layer: 'labels', lift: .05 }));
  B.places.forEach(p => { const cls = p.role === 'destination' ? 'mk shelter' : p.vul ? 'mk care' : 'mk';
    const it = addDom(cls, '', uOf(p.lon), vOf(p.lat), { layer: 'places', lift: .03, place: p });
    PLACE_DOM.set(p.id, it);
    it.el.title = placeName(p) + ' · ' + (p.role === 'destination' ? tr('대피소', 'Shelter') + ' (OSM ' + catName(p.cat) + ')' : p.vul ? tr('요양·복지시설 (취약)', 'Care facility (vulnerable)') : tr('마을 출발지', 'Village origin')); });
  routes.forEach(r => { r.veh = addDom('veh', '', 0, 0, { layer: 'routes', veh: r }); });
}
const _v = new THREE.Vector3();
function placeDom() {
  const w = mapEl.clientWidth, h = mapEl.clientHeight, camD = camera.position.distanceTo(controls.target), t = state.t;
  for (const it of domItems) {
    const lay = L[it.layer]; let show = lay.on && it.show !== false;
    let u = it.u, v = it.v, extraY = 0;
    if (it.veh) { const r = it.veh; show = show && r.has && cmpShows('full') && t >= r.tDep && t <= r.tArr + .05; if (show) { const s = (t - r.t0) * 3600; let j = r.dense.findIndex(p => p.ts >= s); if (j < 0) j = r.dense.length - 1; const p = r.dense[j]; u = p.u; v = p.v;
      it.el.innerHTML = `<b>●</b> ${r.label} ${tr('이동 중', 'moving')} · ${fmt(t, false)} · ${(p.d).toFixed(1)}/${r.lenKm.toFixed(1)} km`; } }
    if (show && it.near && camD > it.near * 1.6) show = false;
    if (!show) { if (it.el.style.display !== 'none') it.el.style.display = 'none'; continue; }
    _v.set(sxU(u), yAt(u, v) + (it.lift || 0) * (flatF > .5 ? 0 : 1) + extraY, szV(v)).project(camera);
    if (_v.z > 1 || Math.abs(_v.x) > 1.1 || Math.abs(_v.y) > 1.1) { it.el.style.display = 'none'; continue; }
    it.el.style.display = ''; it.el.style.opacity = lay.op / 100;
    it.el.style.transform = `translate(${((_v.x + 1) / 2 * w).toFixed(1)}px, ${((1 - _v.y) / 2 * h).toFixed(1)}px)` + (it.el.classList.contains('peak') ? ' translate(-50%, -100%)' : it.el.classList.contains('lb') ? ' translate(-50%, -50%)' : it.el.classList.contains('veh') ? ' translate(-50%, -130%)' : '');
  }
}
