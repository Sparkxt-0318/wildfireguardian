// ---------------- names ----------------
const CAT = { village: ['마을', 'village'], hamlet: ['마을', 'hamlet'], social_facility: ['복지시설', 'social facility'], nursing_home: ['요양시설', 'nursing home'], school: ['학교', 'school'], community_centre: ['마을회관', 'community centre'], community_hall: ['마을회관', 'village hall'], shelter: ['대피소', 'shelter'], research: ['연구 사례 출발지', 'research origin'] };
const catName = c => (CAT[c] || [c || '', c || ''])[EN ? 1 : 0];
// the nearest named village (OSM place=village/hamlet), to say where an unnamed or building-only place is
const nearVillage = p => { if (p.lon == null) return ''; let best = null, bd = 1e9;
  for (const q of B.places) if (q !== p && (q.cat === 'village' || q.cat === 'hamlet') && q.name) { const d = (q.lon - p.lon) ** 2 + (q.lat - p.lat) ** 2; if (d < bd) { bd = d; best = q; } }
  return best ? (EN ? best.ne || best.name : best.name) : ''; };
// OSM names as they are; an unnamed place says what it is and where; a school building (교사동, 체육관…) says it is one
const placeName = p => { const v = nearVillage(p), at = v ? tr(` · ${v} 부근`, ` · near ${v}`) : '', n = EN ? p.ne || p.name : p.name;
  if (!n) return (p.role === 'destination' ? tr(`이름 없는 ${catName(p.cat) || '대피소'}`, `Unnamed ${catName(p.cat) || 'shelter'}`) : tr('이름 없는 출발지', 'Unnamed origin')) + at;
  if (p.cat === 'school' && !/학교|초등|대학|school|college|university/i.test(n)) return tr(`${n} (학교 건물)${at}`, `${n} (school building)${at}`);
  return n; };
// what a dot is, in plain words
const placeKind = p => p.role === 'destination' ? tr(`대피소 · ${catName(p.cat) || '시설'}`, `Shelter · ${catName(p.cat) || 'facility'}`) : p.vul ? tr('요양·복지시설 (취약 계층) · 대피 출발지', 'Care facility (vulnerable people) · evacuation origin') : tr('마을 · 대피 출발지', 'Village · evacuation origin');
const REG_NAME = r => EN ? r.name.en : r.name.ko;
const caseLabel = r => r.label;
const fmtS = s => s == null ? '–' : EN ? `${Math.floor(s / 60)} min ${String(Math.round(s % 60)).padStart(2, '0')} s` : `${Math.floor(s / 60)}분 ${String(Math.round(s % 60)).padStart(2, '0')}초`;
const fmtMin = s => EN ? `${Math.round(s / 60)} min` : `${Math.round(s / 60)}분`;
const sci = (x, d = 2) => x == null || !isFinite(x) ? '–' : x === 0 ? '0' : x < 1e-3 ? x.toExponential(1) : x.toFixed(d);
const kstDay = iso => iso ? new Date(Date.parse(iso) + 9 * 3.6e6).toISOString().slice(0, 10) : '';
const fmtLim = v => v >= 10 ? v.toFixed(0) : v >= 1 ? v.toFixed(2) : v.toPrecision(2);
const niceMax = v => { v = Math.max(v, 1e-6) * 1.1; const e = Math.pow(10, Math.floor(Math.log10(v))); return [1, 2, 2.5, 5, 10].map(m => m * e).find(m => m >= v); };
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const STATUS = {
  checked_route: { k: 'ok', c: '#2f8a57', t: tr('확인된 경로', 'Checked route') },
  model_no_route: { k: 'nr', c: '#1e1e1e', t: tr('모델상 경로 없음', 'No route in the model') },
  unresolved: { k: 'un', c: '#8a8a8a', t: tr('미확인', 'Unresolved') },
  not_checkable: { k: 'na', c: '#b9b2a6', t: tr('점검 불가 (진입 도로 없음)', 'Not checkable (no road entry)') },
};

// ---------------- UI: layers panel ----------------
function thumb(cv, id) {
  const c = cv.getContext('2d'); c.clearRect(0, 0, 60, 60);
  const crop = (src, fx = .42, fy = .42, fw = .18) => { const sw = src.width * fw; c.drawImage(src, src.width * fx, src.height * fy, sw, sw, 0, 0, 60, 60); };
  ({
    relief: () => crop(hsCv, .3, .2, .25), base: () => crop(ground, .5, .45, .08), slope: () => { crop(hsCv, .3, .2, .25); crop(slopeCv, .3, .2, .25); },
    temp: () => { drawTemp(state.t); crop(tempCv, .3, .3, .3); },
    wu: () => { c.fillStyle = '#dfe9f1'; c.fillRect(0, 0, 60, 60); c.strokeStyle = '#3c6f9c'; c.lineWidth = 3; for (let y = 12; y < 60; y += 16) { c.beginPath(); c.moveTo(8, y); c.lineTo(48, y); c.lineTo(42, y - 5); c.moveTo(48, y); c.lineTo(42, y + 5); c.stroke(); } },
    wv: () => { c.fillStyle = '#dfe9f1'; c.fillRect(0, 0, 60, 60); c.strokeStyle = '#3c6f9c'; c.lineWidth = 3; for (let x = 12; x < 60; x += 16) { c.beginPath(); c.moveTo(x, 52); c.lineTo(x, 10); c.lineTo(x - 5, 16); c.moveTo(x, 10); c.lineTo(x + 5, 16); c.stroke(); } },
    canopy: () => { crop(ground, .55, .3, .06); }, biome: () => { BIOMES.forEach((b, i) => { c.fillStyle = b.c; c.fillRect((i % 4) * 15, ((i / 4) | 0) * 30, 15, 30); }); },
    burn: () => { c.fillStyle = '#d8cfbf'; c.fillRect(0, 0, 60, 60); c.fillStyle = '#2e2824'; c.beginPath(); c.moveTo(0, 0); c.lineTo(44, 0); c.lineTo(30, 30); c.lineTo(38, 60); c.lineTo(0, 60); c.fill(); },
    front: () => { c.fillStyle = '#2e2824'; c.fillRect(0, 0, 60, 60); c.strokeStyle = '#ff6a1f'; c.lineWidth = 5; c.beginPath(); c.moveTo(40, 0); c.lineTo(28, 22); c.lineTo(38, 40); c.lineTo(30, 60); c.stroke(); },
    heat: () => { const g = c.createRadialGradient(30, 34, 2, 30, 30, 34); g.addColorStop(0, '#fcffa4'); g.addColorStop(.25, '#f37819'); g.addColorStop(.6, '#932667'); g.addColorStop(1, '#160b39'); c.fillStyle = g; c.fillRect(0, 0, 60, 60); },
    heat3d: () => { c.fillStyle = '#1b1530'; c.fillRect(0, 0, 60, 60); c.fillStyle = '#f37819'; c.beginPath(); c.moveTo(4, 52); c.quadraticCurveTo(30, -10, 56, 52); c.fill(); c.fillStyle = '#fcffa4'; c.beginPath(); c.moveTo(20, 52); c.quadraticCurveTo(30, 18, 40, 52); c.fill(); },
    mc: () => { const g = c.createLinearGradient(0, 0, 60, 0); g.addColorStop(0, '#40106e'); g.addColorStop(.45, '#9e69c8'); g.addColorStop(1, '#ede2f6'); c.fillStyle = g; c.fillRect(0, 0, 60, 60); c.strokeStyle = 'rgba(255,255,255,.8)'; c.setLineDash([4, 3]); c.lineWidth = 2; for (const r of [14, 26, 40]) { c.beginPath(); c.arc(0, 60, r, -Math.PI / 2, 0); c.stroke(); } },
    q: () => { const g = c.createLinearGradient(0, 0, 60, 0); g.addColorStop(0, '#aa1e19'); g.addColorStop(.4, '#f48c42'); g.addColorStop(1, '#fde6cd'); c.fillStyle = g; c.fillRect(0, 0, 60, 60); },
    routes: () => { c.fillStyle = '#e8e2d4'; c.fillRect(0, 0, 60, 60); c.strokeStyle = '#2f8a57'; c.lineWidth = 6; c.lineJoin = 'round'; c.beginPath(); c.moveTo(6, 50); c.lineTo(24, 30); c.lineTo(36, 36); c.lineTo(54, 10); c.stroke(); },
    booth: () => { c.fillStyle = '#e8e2d4'; c.fillRect(0, 0, 60, 60); [[14, 16, '#2f8a57'], [34, 12, '#2f8a57'], [46, 30, '#2f8a57'], [20, 40, '#1e1e1e'], [40, 48, '#8a8a8a']].forEach(([x, y, col]) => { c.fillStyle = col; c.strokeStyle = '#fff'; c.lineWidth = 2.5; c.beginPath(); c.arc(x, y, 6, 0, 7); c.fill(); c.stroke(); }); },
    places: () => { c.fillStyle = '#e8e2d4'; c.fillRect(0, 0, 60, 60); c.fillStyle = '#fff'; c.strokeStyle = '#2a2724'; c.lineWidth = 4; c.beginPath(); c.arc(20, 22, 7, 0, 7); c.fill(); c.stroke(); c.fillStyle = '#2f8a57'; c.fillRect(32, 32, 16, 16); },
    labels: () => { c.fillStyle = '#e8e2d4'; c.fillRect(0, 0, 60, 60); c.fillStyle = '#2a2724'; c.font = '700 22px sans-serif'; c.fillText(EN ? 'Aa' : '가', EN ? 14 : 18, 38); },
  })[id]?.();
}
function legendHTML(id) {
  if (id === 'heat') return `<div class="legend" style="display:block"><div class="memsel" id="memsel">${[tr('최대', 'Max'), 'S1', 'S2', 'S3', 'S4'].map((n, i) => `<button type="button" data-m="${i - 1}" aria-pressed="${i === 0}">${n}</button>`).join('')}</div>
    <span>0.01</span><span class="ramp" style="background:linear-gradient(90deg,#c43c4e,#e8602c,#f8961e,#f6d746,#fcffa4)"></span><span>1 kW/m² · <i style="background:#fff3c0"></i>${tr('화염 접촉 셀', 'flame-contact cell')}</span><br><span>${tr('0.01 kW/m² 미만은 그리지 않습니다. 모델 입력 시각부터 1시간만 있으니 1시간 상세로 보세요.', 'Below 0.01 kW/m² is not drawn. Exists for 1 h after each model input; use the 1-hour detail.')}</span></div>`;
  if (id === 'heat3d') return '';
  if (id === 'mc') return HM ? `<div class="legend"><span>1%</span><span class="ramp" style="background:linear-gradient(90deg,#d6c2ee,#ba92de,#9e69c8,#6e32a0,#40106e)"></span><span>90%+ · ${tr('점선: 50% 도달 시각(1시간 간격)', 'dashed: hour F reaches 50%')}</span></div>`
    : `<div class="legend" style="color:var(--warn)">${tr('시간별 결과는 환경 입력 래스터가 필요해 이 화면에 아직 없습니다. 자료 탭의 출처를 보세요.', 'The hourly results need the environmental input rasters and are not in this view yet. See Sources in the Docs tab.')}</div>`;
  if (id === 'q') return `<div class="legend"><span>0.5%</span><span class="ramp" style="background:linear-gradient(90deg,#fde6cd,#fbc48c,#f48c42,#e2552b,#aa1e19)"></span><span>50%+</span></div>`;
  if (id === 'temp') return `<div class="legend"><span>−2°</span><span class="ramp" style="background:linear-gradient(90deg,#466ebe,#8cb9e1,#f6f0c4,#f4aa5c,#de5c32,#961e1e)"></span><span>30°C · ${tr('등온선 2°C', 'isotherms 2°C')}</span></div>`;
  if (id === 'slope') return `<div class="legend"><i style="background:#f3e08a"></i>5°<i style="background:#f0a24a"></i>15°<i style="background:#d9622b"></i>25°<i style="background:#8f2d1d"></i>35°+</div>`;
  if (id === 'biome') return `<div class="legend">${BIOMES.map(b => `<span><i style="background:${b.c}"></i>${b.n}</span>`).join('')}</div>`;
  if (id === 'burn') return `<div class="legend"><span><i style="background:radial-gradient(#ffd68a,#d6541e 60%,#2c2723)"></i>${tr('새로 기록된 셀 (식는 중)', 'Newly recorded (cooling)')}</span><span><i style="background:#2e2824"></i>${tr('이미 연소한 셀', 'Burned earlier')}</span></div>`;
  if (id === 'front') return `<div class="legend"><span><i style="background:#ff6a1f"></i>${tr('활성 (최근 18시간 기록 · 모델 입력 활성 셀)', 'Active (recorded in last 18 h · active input cells)')}</span><span><i style="background:#46281e"></i>${tr('이전 경계', 'Earlier edge')}</span></div>`;
  if (id === 'routes') return `<div class="legend"><span><i style="background:#2f8a57"></i>${VERDICT.checked_route.t}</span><span><i style="background:#1e1e1e"></i>${VERDICT.model_no_route.t}</span><span><i style="background:#e8862a"></i>${tr('이동시간만 (비교)', 'Travel time only (comparison)')}</span><span><i style="background:#ff2a14;border-radius:50%"></i>${tr('화염 접촉 지점', 'Flame contact')}</span></div>`;
  if (id === 'booth') return B.booth ? `<div class="legend">${Object.values(STATUS).map(s => `<span><i style="background:${s.c};border-radius:50%"></i>${s.t}</span>`).join('')}<span><i style="background:repeating-linear-gradient(90deg,#d9472b 0 4px,transparent 4px 7px)"></i>${tr('이동시간만 경로의 화염 접촉', 'Travel-time-only route with flame contact')}</span></div>` : '';
  if (id === 'places') return `<div class="legend"><span><i style="background:#fff;border:2px solid #2a2724;border-radius:50%"></i>${tr('마을', 'Village')}</span><span><i style="background:#fff;border:2px solid #e2552b;border-radius:50%"></i>${tr('요양·복지시설', 'Care facility')}</span><span><i style="background:#3c6f9c"></i>${tr('대피소', 'Shelter')}</span></div>`;
  return '';
}
function buildLayerPanel() {
  const root = $('pLayers'); root.innerHTML = '';
  // the gist (fire, spread, routes, villages) on top; the other layers folded under "more layers", each can be added on top
  const more = document.createElement('details'); more.className = 'more-layers';
  more.innerHTML = `<summary>${tr(`레이어 더 보기 (${LAYERS.filter(l => !l.core).length}개 · 바람·기온·수목·열유속·몬테카를로 등)`, `More layers (${LAYERS.filter(l => !l.core).length} · wind, temperature, canopy, heat flux, Monte Carlo …)`)}</summary>`;
  let grp = null; const seen = new Set();
  LAYERS.forEach(l => {
    if (l.g) grp = l.g; const p = l.core ? root : more;
    if (grp && !seen.has(grp + l.core)) { seen.add(grp + l.core); p.insertAdjacentHTML('beforeend', `<div class="grp-h"><span>${grp}</span>${!l.core && grp === LAYERS.find(x => x.id === 'temp').g ? `<span>${tr('19ch 중 표시', 'of the 19 channels')}</span>` : ''}</div>`); }
    const row = document.createElement('div'); row.className = 'lr' + (l.on ? '' : ' off'); row.id = 'lr-' + l.id;
    row.innerHTML = `<input type="checkbox" ${l.on ? 'checked' : ''} ${l.disabled ? `disabled title="${tr('이 화면에 이 층의 데이터가 없습니다', 'No data for this layer here')}"` : ''} aria-label="${l.n}"><canvas width="60" height="60"></canvas><div class="nm"><div>${l.n}</div><small class="${l.ill ? 'ill' : ''}">${l.src}</small></div>
      <div class="op">${l.noOp ? '' : `<input type="range" min="0" max="100" value="${l.op}" aria-label="${l.n} ${tr('불투명도', 'opacity')}"><span>${l.op}%</span>`}</div>`;
    p.appendChild(row); l.row = row;
    const lg = legendHTML(l.id); if (lg) { const d = document.createElement('div'); d.innerHTML = lg; d.firstElementChild.dataset.for = l.id; d.firstElementChild.hidden = !l.on && !l.disabled; p.appendChild(d.firstElementChild); }
    thumb(row.querySelector('canvas'), l.id);
    row.querySelector('input[type=checkbox]').onchange = e => { l.on = e.target.checked; row.classList.toggle('off', !l.on); const lg = root.querySelector(`.legend[data-for="${l.id}"]`); if (lg) lg.hidden = !l.on; onLayerChange(l.id); };
    const rg = row.querySelector('input[type=range]'); if (rg) rg.oninput = e => { l.op = +e.target.value; rg.nextElementSibling.textContent = l.op + '%'; onLayerChange(l.id); };
  });
  root.appendChild(more);
  more.insertAdjacentHTML('beforeend', `<p class="note" style="margin:10px 4px 0">${tr('모델 입력은 환경 19채널(기온 1 · 바람 u 1 · 바람 v 1 · 경사 1 · 수목 피복률 1 · 생물군계 14)과 현재 연소 상태 B(t)입니다. ✱ 표시 층은 무늬와 색이 설명용이며 실제 입력 값이 아닙니다.', 'The model input is 19 environmental channels (temperature 1 · wind u 1 · wind v 1 · slope 1 · canopy 1 · biome 14) plus the burned state B(t). Layers marked ✱ show illustrative patterns, not the real input values.')}</p>`);
}
function setLayer(id, on) { const l = L[id]; if (!l || l.disabled || l.on === on) return; const cb = l.row.querySelector('input[type=checkbox]'); cb.checked = on; cb.onchange({ target: cb }); }
document.addEventListener('click', e => { const b = e.target.closest('#memsel button'); if (!b) return; state.member = +b.dataset.m; document.querySelectorAll('#memsel button').forEach(x => x.setAttribute('aria-pressed', String(x === b))); if (state.detail) buildTrack(); dirty = true; });
function onLayerChange(id) {
  if (id === 'relief') { reliefOn = L.relief.on; applyHeights(); }
  if (id === 'canopy') { conifers.visible = broadleaf.visible = L.canopy.on && state.mode === '3d'; conifers.material.opacity = broadleaf.material.opacity = 1; }
  if (id === 'routes') { routeGroup.visible = L.routes.on; buildRouteMeshes(); }
  if (id === 'booth') { boothGroup.visible = L.booth.on; updateBooth(true); }
  if (id === 'heat3d') updateHeatMesh(state.t);
  if (id === 'wu' || id === 'wv') windLines.visible = L.wu.on || L.wv.on;
  dirty = true;
}
function applyHeights() {
  terrain.scale.y = yScale() * 1000; skirt.scale.y = yScale() * 1000; detailGroup.scale.y = yScale() * 1000; if (ctxMesh) ctxMesh.scale.y = yScale() * 1000; buildBoundary();
  flameMat.uniforms.ys.value = smokeMat.uniforms.ys.value = yScale();
  placeTrees(); buildRouteMeshes(); updateHeatMesh(state.t); updateBooth(true);
}

// ---------------- evacuation status from the booth cache (real Route-Check API results) ----------------
const boothGroup = new THREE.Group(); scene.add(boothGroup);
const BOOTH = (B.booth || []).map(b => ({ ...b, t0: hOf(b.input_time), k: INP.findIndex(h => Math.abs(h - hOf(b.input_time)) < 1e-6),
  rows: b.rows.map(r => ({ ...r, dense: r.pts ? densify(r.pts).dense : [], tdense: r.travel && r.travel.pts ? densify(r.travel.pts).dense : [], hit: !!(r.travel && r.travel.passes === false) })) }));
const boothAt = t => { if (!BOOTH.length) return -1; let k = 0; BOOTH.forEach((b, i) => { if (b.t0 <= t + 1e-6) k = i; }); return k; };
const RESEARCH_DOM = [];
function boothCounts(b) {
  const out = { all: {}, village: {}, care: {}, total: { all: 0, village: 0, care: 0 }, hits: 0 };
  for (const r of b.rows) { const g = r.research ? null : r.vul ? 'care' : 'village'; out.all[r.v] = (out.all[r.v] || 0) + 1; out.total.all++;
    if (g) { out[g][r.v] = (out[g][r.v] || 0) + 1; out.total[g]++; } if (r.hit) out.hits++; }
  return out;
}
let boothKey = '';
function updateBooth(force) {
  const k = boothAt(state.t), key = [k, L.booth.on, state.focus, state.mode, state.cmp, EXAG, reliefOn, Math.round(flatF * 50)].join('|');
  if (!force && key === boothKey) return; boothKey = key; state.boothK = k;
  disposeGroup(boothGroup);
  const on = L.booth.on && k >= 0 && state.cmp === 'ours';
  // marker colours follow the selected input time's verdicts
  for (const [id, it] of PLACE_DOM) { const p = it.place; if (p.role !== 'origin') continue; it.el.classList.remove('st-ok', 'st-nr', 'st-un', 'st-na', 'focus');
    if (!on) continue; const row = BOOTH[k].rows.find(r => r.id === id); if (row) it.el.classList.add('st-' + STATUS[row.v].k); if (state.focus === id) it.el.classList.add('focus'); }
  RESEARCH_DOM.forEach(it => { it.show = on && BOOTH[k].rows.some(r => r.id === it.rid); const row = BOOTH[k].rows.find(r => r.id === it.rid); it.el.className = 'mk research' + (row ? ' st-' + STATUS[row.v].k : '') + (state.focus === it.rid ? ' focus' : ''); });
  if (!on) return;
  const op = L.booth.op / 100;
  for (const r of BOOTH[k].rows) { const f = state.focus === r.id;
    if (r.dense.length > 1) boothGroup.add(ribbonMesh(r.dense, f ? .075 : .032, 0x2f8a57, (f ? 1 : .7) * op, 0, f ? .035 : .012, f ? 6 : 4));
    if (r.tdense.length > 1 && (r.hit || f)) boothGroup.add(ribbonMesh(r.tdense, f ? .07 : .045, r.hit ? 0xd9472b : 0xe8862a, (f ? 1 : .85) * op, .25, .02, 5));
    if (f && r.dense.length > 1) boothGroup.add(puck(r.dense[r.dense.length - 1].u, r.dense[r.dense.length - 1].v, 0x2f8a57, .07)); }
}
// ---------------- map dots: what each one is (click), and a zoom to it ----------------
function caseIdLabel(name) {     // case ids such as 20250325T170000Z_FW1 -> FW1 · 03-26 02:00 입력 (KST)
  const m = /^(\d{4})(\d\d)(\d\d)T(\d\d)(\d\d)\d\dZ_(\w+)$/.exec(name || ''); if (!m) return name;
  const d = new Date(Date.UTC(+m[1], m[2] - 1, +m[3], +m[4] + 9, +m[5]));
  return `${m[6]} · ${p2(d.getUTCMonth() + 1)}-${p2(d.getUTCDate())} ${p2(d.getUTCHours())}:${p2(d.getUTCMinutes())} ${tr('입력', 'input')}`;
}
function dotInfo(it) {
  const k = state.boothK, rowOf = id => L.booth.on && k >= 0 && state.cmp === 'ours' ? BOOTH[k].rows.find(r => r.id === id) : null;
  if (it.place) { const p = it.place, row = p.role === 'origin' ? rowOf(p.id) : null;
    return { name: placeName(p), kind: placeKind(p), row }; }
  if (it.rid != null) { const row = rowOf(it.rid); return { name: caseIdLabel(row ? row.name : it.rname), kind: tr('연구 사례 출발지', 'Research case origin'), row }; }
  return null;
}
function dotOpen(it, x, y) {
  const d = dotInfo(it); if (!d) return; const pop = $('dotPop');
  pop.innerHTML = `<b>${d.name}</b><span>${d.kind}</span>${d.row ? `<span class="st"><i style="background:${STATUS[d.row.v].c}"></i>${tr('대피 결과', 'Evacuation result')}: ${STATUS[d.row.v].t}</span>` : ''}
    <div><button type="button" class="btn" id="dotZoom">${tr('확대', 'Zoom in')}</button>${d.row && d.row.v !== 'not_checkable' ? `<button type="button" class="btn" id="dotApi">${tr('API 응답', 'API response')}</button>` : ''}<button type="button" class="btn" id="dotClose">${tr('닫기', 'Close')}</button></div>`;
  const r = mapEl.getBoundingClientRect(); pop.hidden = false;
  pop.style.left = Math.min(r.width - 230, Math.max(8, x - r.left + 12)) + 'px'; pop.style.top = Math.min(r.height - 120, Math.max(8, y - r.top + 12)) + 'px';
  $('dotClose').onclick = () => { pop.hidden = true; };
  if ($('dotApi')) $('dotApi').onclick = () => { pop.hidden = true; apiOpen(d.row.id); };
  $('dotZoom').onclick = () => { pop.hidden = true; const flat = state.mode === '2d';
    tweenView({ r: flat ? 4 : 6, phi: flat ? .0005 : THREE.MathUtils.degToRad(50), th: flat ? 0 : sph(camera.position, controls.target).th, tgt: new THREE.Vector3(sxU(it.u), yAt(it.u, it.v), szV(it.v)) }, 1000); };
}
// ---------------- API 응답 보기: the recorded real Route-Check API exchange behind an origin's verdict ----------------
// site/regions/<id>.api.js (tools/build_api_log.py) holds the jobs exactly as the API returned them, loaded on first open.
const PLACE_ID = new Map(B.places.map(p => [p.id, p]));
let apiReq = null, apiSel = null;
const apiData = () => apiReq || (apiReq = window.__wfgLoad(`${B.id}.api.js`).then(ok => ok && (window.WFG_API || {})[B.id] || null));
const jsonHTML = o => esc(JSON.stringify(o, null, 2)).replace(/(&quot;(?:[^&]|&(?!quot;))*?&quot;)(\s*:)?|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:e[+-]?\d+)?)/gi,
  (m, str, colon, lit, num) => str ? `<span class="${colon ? 'jk' : 'js'}">${str}</span>${colon || ''}` : lit ? `<span class="jl">${lit}</span>` : `<span class="jn">${num}</span>`);
const API_C = { checked_route: '#2f8a57', model_no_route: '#4a4f57', unresolved: '#8a8a8a' };     // verdict colours readable on the dark viewer
const apiDur = (a, b) => a && b ? ((Date.parse(b) - Date.parse(a)) / 1000).toFixed(1) + ' s' : '–';
const apiName = id => { const rm = /^research:[^:]+:([^:]+):(origin|destination)$/.exec(id || '');
  if (rm) return tr('연구 사례 ', 'Research ') + caseIdLabel(rm[1]) + (rm[2] === 'destination' ? tr(' · 도착지', ' · destination') : '');
  const p = PLACE_ID.get(id); if (p) return placeName(p); const r = BOOTH.flatMap(b => b.rows).find(x => x.id === id); return r ? (r.research ? tr('연구 사례 ', 'Research ') + caseIdLabel(r.name) : r.name) : id; };
function apiOpen(oid, k) {
  if (!BOOTH.length) return;
  k = k ?? Math.max(0, state.boothK); const rows = BOOTH[k].rows.filter(r => r.v !== 'not_checkable');
  apiSel = { k, oid: rows.some(r => r.id === oid) ? oid : (rows.find(r => r.v === 'checked_route') || rows[0] || {}).id };
  const box = $('apiView'); box.hidden = false; box.querySelector('.api-body').innerHTML = `<p class="note">${tr('기록된 API 응답을 불러오는 중…', 'Loading the recorded API responses…')}</p>`;
  apiData().then(d => apiRender(d));
}
function apiRender(d) {
  const box = $('apiView'), body = box.querySelector('.api-body'); if (box.hidden) return;
  const { k, oid } = apiSel, t = d && d.times.find(x => x.input_time === BOOTH[k].input_time), row = t && t.rows[oid];
  const rows = BOOTH[k].rows.filter(r => r.v !== 'not_checkable').sort((a, z) => (a.research ? 0 : 1) - (z.research ? 0 : 1) || String(apiName(a.id)).localeCompare(apiName(z.id)));
  const head = `<div class="api-pick"><label>${tr('입력 시각', 'Input time')} <span class="seg2">${BOOTH.map((x, i) => `<button type="button" data-ak="${i}" aria-pressed="${i === k}">${fmt(x.t0)}</button>`).join('')}</span></label>
    <label>${tr('출발지', 'Origin')} <select id="apiOrigin">${rows.map(r => `<option value="${esc(r.id)}"${r.id === oid ? ' selected' : ''}>${esc(apiName(r.id))} · ${STATUS[r.v].t}</option>`).join('')}</select></label></div>`;
  if (!row) { body.innerHTML = head + `<p class="note">${tr('이 출발지·입력 시각의 기록된 API 응답이 없습니다.', 'No recorded API response for this origin and input time.')}</p>`; apiWire(d); return; }
  const rc = row.rc && t.rc[row.rc], plan = row.plan && t.plans[row.plan], res = (rc && rc.result) || {}, pv = (rc && rc.result && rc.result.provenance) || (rc && rc.provenance) || {};
  const hp = t.health || {}, host = pv.host || {};
  // the dispatch plan as the API returned it, with this origin's own attempt list put back in place
  const planView = plan && JSON.parse(JSON.stringify(plan));
  if (planView) for (const o of planView.result.plans) o.attempts = o.origin_id === oid
    ? row.att.map(([dest, dep, v, arr, cs, job]) => ({ destination_id: dest, depart_offset_s: dep, verdict: v, arrival_s: arr, compute_s: cs, route_check_job_id: job }))
    : tr(`… 시도 ${o.attempts}건 (다른 출발지)`, `… ${o.attempts} attempts (another origin)`);
  const dests = [...new Set(row.att.map(a => a[0]))], deps = [...new Set(row.att.map(a => a[1]))].sort((a, z) => a - z);
  const cell = (dst, dep) => { const a = row.att.find(x => x[0] === dst && x[1] === dep); if (!a) return `<td class="na">–</td>`;
    const tip = `${a[5]} · ${STATUS[a[2]].t}${a[3] != null ? ` · ${tr('도착', 'arrival')} +${fmtS(a[3])}` : ''} · ${tr('계산', 'compute')} ${a[4] != null ? a[4].toFixed(1) + ' s' : '–'}`;
    return `<td title="${esc(tip)}" class="${a[5] === row.rc ? 'shown' : ''}" style="background:${API_C[a[2]] || '#8a8a8a'}">${a[4] != null ? a[4].toFixed(1) : ''}</td>`; };
  const step = (n, verb, path, code, note, open) => `<details class="api-step"${open ? ' open' : ''}><summary><b>${n}</b><span class="verb ${verb.toLowerCase()}">${verb}</span><code>${esc(path)}</code><small>${note}</small></summary>${code}</details>`;
  const pre = o => `<pre class="json">${jsonHTML(o)}</pre>`;
  const steps = plan
    ? [step(1, 'GET', '/v1/health', pre(hp), tr('API 상태 · 버전 확인 (200)', 'API status and versions (200)')),
       step(2, 'POST', '/v1/dispatch-plans', pre(plan.request) + `<div class="api-resp">→ <b>202 Accepted</b> · job_id <code>${esc(plan.job_id)}</code></div>`, tr('출발지 × 대피소 × 출발 시각을 한 번에 점검 요청', 'one request: origins × shelters × departure times'), true),
       step(3, 'GET', `/v1/dispatch-plans/${plan.job_id}`, pre(planView), tr(`200 · ${plan.status} · ${apiDur(plan.started_at, plan.finished_at)}`, `200 · ${plan.status} · ${apiDur(plan.started_at, plan.finished_at)}`)),
       rc ? step(4, 'GET', `/v1/route-checks/${rc.job_id}`, pre(rc), tr(`200 · 판정 ${res.verdict} · 지도에 그린 경로`, `200 · verdict ${res.verdict} · the route drawn on the map`), true) : '']
    : [step(1, 'GET', '/v1/health', pre(hp), tr('API 상태 · 버전 확인 (200)', 'API status and versions (200)')),
       step(2, 'POST', '/v1/route-checks', pre(rc.request) + `<div class="api-resp">→ <b>202 Accepted</b> · job_id <code>${esc(rc.job_id)}</code></div>`, tr('연구 사례 출발지 한 경로 점검 요청', 'one route check for a research-case origin'), true),
       step(3, 'GET', `/v1/route-checks/${rc.job_id}`, pre(rc), tr(`200 · 판정 ${res.verdict}`, `200 · verdict ${res.verdict}`), true)];
  body.innerHTML = head + `
    <div class="api-prov">${tr('실제 API 기록', 'Recorded real API run')}: <b>Route-Check API ${esc(pv.api_version || d.cache.api_version)}</b> · ${esc(pv.package || '')} ${esc(pv.package_version || '')} · ${tr('키트', 'kit')} ${esc(pv.kit || '')} · ${tr('체크포인트', 'checkpoint')} <code>${esc((pv.checkpoint || '').slice(0, 8))}</code> · git <code>${esc((pv.git_commit || '').slice(0, 7))}</code>
      <br>${tr('실행', 'Run')} ${esc(kstDay(pv.generated_at || d.cache.created_at))} · ${esc(host.platform || '')}${host.cpu_count ? ` · ${host.cpu_count} ${tr('코어', 'cores')}` : ''} · ${tr('요청당 시간 예산', 'time budget per request')} ${pv.budget_s || 30} s · <code>${esc(t.base || '')}</code></div>
    <div class="api-sum">
      <div><small>${tr('판정', 'Verdict')}</small><b style="color:${res.verdict === 'checked_route' ? '#7fd1a2' : res.verdict === 'model_no_route' ? '#f0a58f' : '#e6e9ec'}">${STATUS[res.verdict]?.t || esc(res.verdict)}</b><code>${esc(res.verdict || '')}${res.reason_code ? ' · ' + esc(res.reason_code) : ''}</code></div>
      <div><small>${res.verdict === 'checked_route' ? tr('대피소', 'Shelter') : tr('펼친 작업의 대피소', 'Shelter of the job shown')}</small><b>${esc(apiName(row.att.find(a => a[5] === row.rc)?.[0]))}</b></div>
      <div><small>${tr('출발 → 도착', 'Departure → arrival')}</small><b>+${fmtS(res.departure_s || 0)} → ${res.arrival_s != null ? '+' + fmtS(res.arrival_s) : '–'}</b></div>
      <div><small>${tr('API 계산 시간', 'API compute time')}</small><b>${res.compute_s != null ? res.compute_s.toFixed(2) + ' s' : '–'} / ${pv.budget_s || 30} s</b><code>${res.within_budget ? tr('예산 안', 'within budget') : tr('예산 초과', 'over budget')}</code></div>
    </div>
    <div class="api-grid"><div class="sub-h" style="margin:10px 0 4px">${tr(`이 출발지에 보낸 점검 ${row.att.length}건 · 칸마다 실제 API 작업 1개 (숫자 = 계산 초)`, `${row.att.length} checks sent for this origin · each cell is one real API job (number = compute seconds)`)}</div>
      <table><tr><th></th>${deps.map(x => `<th>+${Math.round(x / 60)}${tr('분', 'm')}</th>`).join('')}</tr>${dests.map(dst => `<tr><th>${esc(apiName(dst))}</th>${deps.map(x => cell(dst, x)).join('')}</tr>`).join('')}</table>
      <div class="api-key">${['checked_route', 'model_no_route', 'unresolved'].map(v => `<span><i style="background:${API_C[v]}"></i>${STATUS[v].t}</span>`).join('')}<span><i class="shown"></i>${tr('아래에 펼친 작업', 'job shown below')}</span></div></div>
    <div class="api-steps">${steps.join('')}</div>
    <p class="note">${tr('응답은 저장된 그대로입니다. 경로 좌표 같은 긴 배열만 개수로 줄였습니다(지도에 그린 선). 이 화면은 인터넷 없이도 열립니다.', 'Responses are shown as stored; only long arrays such as route coordinates are folded to a count (the line drawn on the map). This view works without internet.')}</p>`;
  apiWire(d);
}
function apiWire(d) {
  const body = $('apiView').querySelector('.api-body');
  body.querySelectorAll('[data-ak]').forEach(b => b.onclick = () => { apiSel.k = +b.dataset.ak; apiRender(d); });
  const sel = body.querySelector('#apiOrigin'); if (sel) sel.onchange = () => { apiSel.oid = sel.value; apiRender(d); };
}
$('apiView').addEventListener('click', e => { if (e.target.id === 'apiView' || e.target.closest('.api-close')) $('apiView').hidden = true; });
addEventListener('keydown', e => { if (e.key === 'Escape') $('apiView').hidden = true; });
labelsEl.addEventListener('click', e => { const el = e.target.closest('.mk'); if (!el) return; const it = domItems.find(x => x.el === el); if (it) { e.stopPropagation(); dotOpen(it, e.clientX, e.clientY); } });
controls.addEventListener('start', () => { $('dotPop').hidden = true; });
function focusOrigin(id) {
  state.focus = state.focus === id ? null : id; updateBooth(true); renderEvac();
  const k = state.boothK, r = k >= 0 && BOOTH[k].rows.find(x => x.id === id);
  if (state.focus && r && r.lon != null && state.mode === '3d') { const u = uOf(r.lon), v = vOf(r.lat); tweenView({ r: 11, phi: THREE.MathUtils.degToRad(48), th: sph(camera.position, controls.target).th, tgt: new THREE.Vector3(sxU(u), elevUV(u, v) * yScale(), szV(v)) }, 1000); }
}
function stackBar(c, n) {
  if (!n) return '';
  return `<div class="stack">${['checked_route', 'model_no_route', 'unresolved', 'not_checkable'].map(v => c[v] ? `<span style="flex:${c[v]};background:${STATUS[v].c}" title="${STATUS[v].t} ${c[v]}"></span>` : '').join('')}</div>`;
}
function renderEvac() {
  const el = $('pEvac'); if (!el) return;
  if (!BOOTH.length) {
    el.innerHTML = `<div class="grp-h"><span>${tr('대피 현황', 'Evacuation status')}</span></div>
      <p class="note" style="margin:4px">${tr(`이 지역(${REG_NAME(B)})에는 출발지 전체를 점검한 부스 캐시가 없습니다. 부스 캐시는 실제 Route-Check API로 미리 계산한 두 시연 지역(의성·안동, 영덕)에만 있습니다.`, `This region (${REG_NAME(B)}) has no booth cache covering every origin. The booth cache was precomputed with the real Route-Check API for the two demo regions only (Uiseong–Andong, Yeongdeok).`)}</p>
      <div class="grp-h" style="margin-top:12px"><span>${tr('이 지역의 기록된 연구 사례', 'Recorded research cases in this region')}</span></div>
      ${caseTable()}
      <div class="regbtns">${RIDX.filter(r => r.booth).map(r => `<button type="button" class="chipbtn sel" data-reg="${r.id}">${REG_NAME(r)} ${tr('대피 현황 보기', 'evacuation status')} →</button>`).join('')}</div>`;
    el.querySelectorAll('[data-reg]').forEach(b => b.onclick = () => switchRegion(b.dataset.reg, { tab: 'pEvac' }));
    return;
  }
  const k = Math.max(0, state.boothK), b = BOOTH[k], c = boothCounts(b), api = b.api || {};
  const noRoute = b.rows.filter(r => r.v !== 'checked_route').sort((a, z) => ['model_no_route', 'unresolved', 'not_checkable'].indexOf(a.v) - ['model_no_route', 'unresolved', 'not_checkable'].indexOf(z.v));
  // deadline = latest contiguous checked departure from +0 (planner rule); later isolated checks are noted, never counted
  const hor = 3000, dk = r => r.contig == null ? -1 : r.contig, dl = b.rows.filter(r => r.v === 'checked_route' && r.last != null).sort((a, z) => dk(a) - dk(z) || (z.vul ? 1 : 0) - (a.vul ? 1 : 0));
  const urgent = dl.filter(r => dk(r) < hor || r.last !== r.contig), dlText = r => r.contig == null
      ? tr(`+0분 출발 미확인 · +${Math.round(r.last / 60)}분 출발만 확인`, `+0 min not checked · only +${Math.round(r.last / 60)} min checked`)
      : `${fmt(b.t0 + r.contig / 3600, false)}${r.last !== r.contig ? tr(' (이후 일부 시각도 확인)', ' (some later times also checked)') : ''} · ${esc(placeName({ name: r.dname, ne: r.dne, role: 'destination' }))}`, rowHTML = (r, extra) => `<li><button type="button" data-o="${esc(r.id)}" class="${state.focus === r.id ? 'sel' : ''}"><span class="dot" style="background:${STATUS[r.v].c}"></span><span class="x">${esc(placeName({ name: r.research ? tr('연구 사례 ', 'Research ') + caseIdLabel(r.name) : r.name, ne: r.ne }))}${r.vul ? ` <em class="care">${tr('요양·복지', 'care')}</em>` : ''}</span><span class="t">${extra}</span></button></li>`;
  el.innerHTML = `
    <div class="grp-h"><span>${tr('입력 시각별 판정 · 부스 캐시', 'Verdicts per input time · booth cache')}</span><span>${tr('타임라인을 따라감', 'follows the timeline')}</span></div>
    <div class="seg2">${BOOTH.map((x, i) => `<button type="button" data-k="${i}" aria-pressed="${i === k}">${fmt(x.t0)}</button>`).join('')}</div>
    <button type="button" class="api-open" id="evacApi"><b>${tr('API 응답 보기', 'View API responses')}</b><span>${state.focus && b.rows.some(r => r.id === state.focus && r.v !== 'not_checkable') ? tr(`${esc(apiName(state.focus))}의 판정을 만든 실제 Route-Check API 요청·응답`, `The real Route-Check API request and response behind ${esc(apiName(state.focus))}`) : tr('이 판정들을 만든 실제 Route-Check API 요청·응답 (출발지를 골라 보기)', 'The real Route-Check API requests and responses behind these verdicts (pick an origin)')}</span></button>
    <div class="tiles">
      <div class="tile ok"><b>${c.all.checked_route || 0}</b><span>/ ${c.total.all} ${tr('출발지', 'origins')}</span><small>${tr('확인된 경로 (연구 사례 출발지 포함)', 'checked route (incl. recorded research origins)')}</small></div>
      <div class="tile bad"><b>${c.total.all - (c.all.checked_route || 0)}</b><small>${tr('확인된 경로 없음', 'no checked route')}<br>${tr(`경로 없음 ${c.all.model_no_route || 0} · 미확인 ${c.all.unresolved || 0} · 점검 불가 ${c.all.not_checkable || 0}`, `no route ${c.all.model_no_route || 0} · unresolved ${c.all.unresolved || 0} · not checkable ${c.all.not_checkable || 0}`)}</small></div>
      <div class="tile care">${c.total.care ? `<b>${c.care.checked_route || 0}</b><span>/ ${c.total.care}</span><small>${tr('요양·복지시설 확인된 경로', 'care facilities with a checked route')}</small>` : `<b>–</b><small>${tr('이 지역 OSM 출발지에 요양·복지시설이 없습니다', 'No care facilities among this region’s OSM origins')}</small>`}</div>
      <div class="tile hit"><b>${c.hits}</b><small>${tr('같은 출발 시각에 이동시간만 고려한 경로였다면 화염 접촉', 'would touch flame on the travel-time-only route at the same departure')}</small></div>
    </div>
    <div class="bars"><div><span>${tr('마을', 'Villages')} ${c.total.village}</span>${stackBar(c.village, c.total.village)}</div><div><span>${tr('요양·복지', 'Care')} ${c.total.care}</span>${stackBar(c.care, c.total.care)}</div></div>
    <h4 class="sub-h">${tr('확인된 경로가 없는 출발지', 'Origins without a checked route')} <small>${noRoute.length}</small></h4>
    <ul class="olist">${noRoute.map(r => rowHTML(r, STATUS[r.v].t)).join('') || `<li class="note" style="padding:4px 8px">${tr('없음', 'None')}</li>`}</ul>
    <h4 class="sub-h">${tr('출발 마감이 이른 곳', 'Earliest departure deadlines')} <small>${tr('입력 시각부터 이 시각까지 모든 출발 시각에 확인된 경로', 'every departure from the input time up to this time has a checked route')}</small></h4>
    <ul class="olist">${urgent.slice(0, 12).map(r => rowHTML(r, dlText(r))).join('') || `<li class="note" style="padding:4px 8px">${tr('모든 출발지가 점검한 마지막 출발 시각(+50분)까지 확인된 경로가 있습니다.', 'Every origin has a checked route up to the last departure checked (+50 min).')}</li>`}</ul>
    ${dl.length - urgent.length ? `<p class="note" style="margin:2px 4px 8px">${tr(`나머지 ${dl.length - urgent.length}곳은 점검한 모든 출발 시각(+0–50분)에 확인된 경로가 있습니다.`, `The other ${dl.length - urgent.length} have a checked route at every departure checked (+0–50 min).`)}</p>` : ''}
    <h4 class="sub-h">${tr('입력 시각별 요약', 'Summary per input time')}</h4>
    <table class="mini"><tr><th>${tr('입력', 'Input')}</th><th>${tr('확인', 'Checked')}</th><th>${tr('경로 없음', 'No route')}</th><th>${tr('미확인', 'Unres.')}</th><th>${tr('불가', 'N/C')}</th><th>${tr('요양 확인', 'Care ok')}</th><th>${tr('접촉*', 'Flame*')}</th></tr>
      ${BOOTH.map(x => { const cc = boothCounts(x); return `<tr><td>${fmt(x.t0)}</td><td>${cc.all.checked_route || 0}</td><td>${cc.all.model_no_route || 0}</td><td>${cc.all.unresolved || 0}</td><td>${cc.all.not_checkable || 0}</td><td>${cc.care.checked_route || 0}/${cc.total.care}</td><td>${cc.hits}</td></tr>`; }).join('')}</table>
    <p class="note" style="margin:6px 4px">${tr(`* 이동시간만 고려한 경로를 같은 화재 입력의 전체 위험(4개 시나리오)으로 검사해 도로 전체 화염 접촉이 확인된 출발지 수입니다(마을 출발지와 연구 사례 출발지 포함). 표의 수는 연구 사례 출발지를 포함하고, 마을·요양 막대는 OSM 출발지만 셉니다.<br>출처: 부스 캐시 · 실제 Route-Check API ${api.version || ''} · ${api.host || ''} · ${kstDay(api.created_at)} KST 계산 · 출발 +0–50분 ${b.step_min}분 간격 · 가까운 대피소 ${b.shelters}곳. 계획 보조 결과이며 실제 대피 명령이 아닙니다.`, `* Origins whose travel-time-only route, checked against the full hazard of the same fire input (4 scenarios), has confirmed whole-road flame contact (village and recorded research origins). Table counts include research origins; the village and care bars count OSM origins only.<br>Source: booth cache · real Route-Check API ${api.version || ''} · ${api.host || ''} · computed ${kstDay(api.created_at)} KST · departures +0–50 min every ${b.step_min} min · nearest ${b.shelters} shelters. Planning aid, not an evacuation order.`)}</p>`;
  el.querySelectorAll('.seg2 button').forEach(bt => bt.onclick = () => { if (state.detail) setDetail(false); setTime(BOOTH[+bt.dataset.k].t0 + .02); setPlaying(false); });
  el.querySelectorAll('[data-o]').forEach(bt => bt.onclick = () => focusOrigin(bt.dataset.o));
  $('evacApi').onclick = () => apiOpen(state.focus, k);
}

// ---------------- prior research comparison ----------------
const TABLE1 = [
  ['FARSITE', ['산불 확산 시뮬레이션', 'Wildfire spread simulation'], ['대피 경로 계획은 별도', 'Evacuation routing is separate'], ['예측·경로 탐색 연계', 'Forecast linked to routing']],
  ['Google ML', ['미래 산불 지도', 'Future fire maps'], ['개인 이동 중 노출 미평가', 'No exposure along a trip'], ['이동 경로별 위험 점검', 'Hazard checked per route']],
  ['WUIVAC', ['대피 개시 구역', 'Evacuation trigger zones'], ['사전 지정 경로 평가', 'Evaluates preset routes'], ['경로 탐색·누적 노출 평가', 'Route search + dose check']],
  ['WUI-NITY', ['산불·대피 연계 시뮬레이션', 'Coupled fire–evacuation simulation'], ['인구 집단 시뮬레이션 중심', 'Population-level simulation'], ['개별 이동 독립 검증', 'Each trip checked on its own']],
  ['Time-expanded routing', ['위험 반영 대피 흐름', 'Hazard-aware evacuation flow'], ['해당 정식화에 개인 누적 열노출 한도 없음', 'No per-person cumulative heat limit'], ['시나리오별 누적 열노출·목적지 체류 평가·최적화', 'Per-scenario dose, destination dwell, evaluation and optimization']],
];
const CMP = {
  spread: { n: tr('확산 예측만', 'Spread forecast only'), d: tr('FARSITE·ML 확산 지도류가 내놓는 산출물: 연소 상태와 확률 지도. 경로·노출 평가 없음.', 'What spread simulators and ML fire maps output: burned state and probability maps. No routes or exposure.'), on: ['burn', 'front', 'q', 'mc'], off: ['heat', 'heat3d', 'routes', 'booth'] },
  travel: { n: tr('이동시간 최단 경로', 'Shortest travel time'), d: tr('화재 조건 없이 가장 빨리 도착하는 경로(이 연구의 travel_only 정책 기록). 빨간 점 = 그 경로가 화염 셀을 지나는 지점.', 'The fastest route with no fire constraint (this study’s travel_only policy records). Red dots = where that route passes a flame cell.'), on: ['burn', 'front', 'heat', 'routes'], off: ['q', 'heat3d', 'booth', 'mc'] },
  ours: { n: 'WildfireGuardian', d: tr('예측 → 열유속 → 노출 제한 경로 점검까지 모두 켠 화면.', 'Everything on: forecast → heat flux → exposure-limited route check.'), on: ['burn', 'front', 'q', 'heat', 'heat3d', 'routes', 'booth', 'mc'], off: [] },
};
function setCompare(m) {
  state.cmp = m; const p = CMP[m];
  p.off.forEach(id => setLayer(id, false)); p.on.forEach(id => setLayer(id, true));
  if (m === 'travel') { const i = CASES[selRoute] && CASES[selRoute].travelHits.length ? selRoute : CASES.findIndex(c => c.travelHits.length); if (i >= 0) { selRoute = i; buildRouteTab(); const c = CASES[i]; if (c.k >= 0) setDetail(true, c.k); const h = c.travelHits[0]; setTime(c.r.t0 + Math.max(0, h.p.ts - 60) / 3600); setPlaying(false); flyTo(c.r); } }
  buildRouteMeshes(); updateBooth(true); renderCompare(); dirty = true;
  $('cmpChip').hidden = m === 'ours'; $('cmpChip').innerHTML = m === 'ours' ? '' : `<b>${tr('비교 보기', 'Comparison view')}</b> ${p.n} <button type="button" id="cmpBack">${tr('WildfireGuardian으로', 'Back to WildfireGuardian')}</button>`;
  if (m !== 'ours') $('cmpBack').onclick = () => setCompare('ours');
}
function rq3Rows() { const out = []; for (const r of RIDX) for (const q of r.rq3) out.push({ ...q, rid: r.id, rname: REG_NAME(r) }); return out; }
function renderCompare() {
  const el = $('pCompare'); if (!el) return; const rows = rq3Rows(), fails = rows.filter(q => q.travel_fails_full), det = fails.filter(q => q.full_verdict === 'checked_route').length;
  el.innerHTML = `
    <div class="grp-h"><span>${tr('같은 지도에서 보기', 'See it on the same map')}</span></div>
    <div class="cmpbtns">${Object.entries(CMP).map(([k, p]) => `<button type="button" data-c="${k}" aria-pressed="${state.cmp === k}"><b>${p.n}</b><small>${p.d}</small></button>`).join('')}</div>
    <p class="note" style="margin:4px">${tr('각 접근법이 내놓는 산출물의 종류만 켠 화면입니다. FARSITE·Google ML 등을 실제로 실행한 결과가 아닙니다. 이동시간 최단 경로는 이 연구가 같은 사례를 travel_only 정책으로 점검한 실제 기록입니다.', 'Each view turns on only the kind of output that approach produces. It is not a run of FARSITE, Google ML or the others. The shortest-travel-time routes are this study’s real travel_only policy records for the same cases.')}</p>
    <div class="grp-h" style="margin-top:12px"><span>${tr('이동시간만 고려한 경로 vs 전체 조건 (5개 지역 · 20건)', 'Travel time only vs full constraints (5 regions · 20 cases)')}</span></div>
    <p class="live" style="margin:2px 4px 6px">${tr(`이동시간만 고려한 경로 20건 중 <b>${fails.length}건</b>이 같은 화재 입력의 전체 위험 검사에서 화염 접촉으로 불통과합니다. WildfireGuardian은 그중 <b>${det}건</b>에서 확인된 우회 경로를 찾고, <b>${fails.length - det}건</b>은 모델상 경로 없음으로 판정합니다.`, `Of 20 travel-time-only routes, <b>${fails.length}</b> fail the full-hazard check of the same fire input with flame contact. WildfireGuardian finds a checked detour for <b>${det}</b> of them and reports <b>${fails.length - det}</b> as no route in the model.`)}</p>
    <table class="mini rq3"><tr><th>${tr('지역 · 사례', 'Region · case')}</th><th>${tr('이동시간만', 'Travel only')}</th><th>${tr('전체 조건', 'Full')}</th></tr>
      ${rows.map(q => `<tr class="${q.rid === RID ? 'here' : ''}" data-r="${q.rid}" data-case="${q.case}"><td><button type="button">${q.rname} ${q.case.split('_').pop()}</button></td><td>${q.travel_fails_full ? `<span class="pill bad">${tr('화염 접촉', 'Flame')}${q.components && q.components.includes('DOSE') ? tr(' + 누적', ' + dose') : ''}</span>` : `<span class="pill">${tr('통과', 'Pass')}</span>`}</td><td><span class="pill ${q.full_verdict === 'checked_route' ? 'ok' : 'dark'}">${q.full_verdict === 'checked_route' ? VERDICT.checked_route.t : VERDICT.model_no_route.t}</span></td></tr>`).join('')}</table>
    <p class="note" style="margin:4px">${tr('출처: 저장소 기록(mock_api/fixtures/records, full_policy_check). 지도 위 빨간 점은 이 화면이 셀 중심 값으로 다시 찾은 화염 셀이며 20건 모두 기록 판정과 일치합니다.', 'Source: repository records (mock_api/fixtures/records, full_policy_check). The red dots are flame cells this view finds again at cell centres; they agree with the recorded result in all 20 cases.')}</p>
    <div class="grp-h" style="margin-top:12px"><span>${tr('기존 접근법과 본 연구 (포스터 표 1)', 'Prior approaches and this study (poster Table 1)')}</span></div>
    <table class="mini t1"><tr><th>${tr('접근법', 'Approach')}</th><th>${tr('제공 기능', 'Provides')}</th><th>${tr('한계·범위', 'Limit · scope')}</th><th>${tr('본 연구', 'This study')}</th></tr>
      ${TABLE1.map(([a, f, l, o]) => `<tr><td><b>${a}</b></td><td>${f[EN ? 1 : 0]}</td><td>${l[EN ? 1 : 0]}</td><td class="ours">${o[EN ? 1 : 0]}</td></tr>`).join('')}</table>`;
  el.querySelectorAll('.cmpbtns button').forEach(b => b.onclick = () => setCompare(b.dataset.c));
  el.querySelectorAll('tr[data-r] button').forEach(b => { const tr_ = b.closest('tr'); b.onclick = () => { if (tr_.dataset.r === RID) { const i = CASES.findIndex(c => c.r.case === tr_.dataset.case); if (i >= 0) { if (state.cmp !== 'travel') setCompare('travel'); openCase(i); } } else switchRegion(tr_.dataset.r, { caseid: tr_.dataset.case, cmp: 'travel', tab: 'pCompare' }); }; });
}

// ---------------- docs: route logger + sources ----------------
const figSrc = f => (window.WFG_FIG && window.WFG_FIG[f]) || `logger/${f}.png`;
const LOGGER = {
  title: tr('현장 경로 기록기 (Route Logger)', 'Field route logger (Route Logger)'),
  sub: tr('WildfireGuardian 직접 제작용 GPS 기록기 · 제작 설명서 2026년 10월 · Case v2 · 펌웨어 0.3.0', 'WildfireGuardian build-it-yourself GPS logger · build manual October 2026 · Case v2 · firmware 0.3.0'),
  what: tr('걷거나 차량으로 이동하며 경로와 이벤트 표시를 기록하고, Mac 브라우저 앱에서 다시 재생하는 주머니 크기 GPS 기록기입니다. 직접 출력·배선·조립하며 37단계, 손 작업 약 4시간(추정, 출력 시간 별도)입니다.', 'A pocket GPS logger that records a route (with event marks) on foot or in a vehicle and replays it in a Mac browser app. You print, wire and assemble it yourself: 37 steps, about 4 hours of hands-on work plus printing (estimate).'),
  specs: [
    [tr('보드', 'Board'), 'FireBeetle 2 ESP32-E (DFR0654-F)'],
    ['GNSS', tr('Gravity TEL0157 · UART (D11/D10) · 패치 안테나', 'Gravity TEL0157 · UART (D11/D10) · patch antenna')],
    [tr('화면', 'Display'), tr('1.54인치 240×240 ST7789', '1.54 in 240×240 ST7789')],
    [tr('전원', 'Power'), tr('14500 셀 800 mAh · USB-C 충전 · 계획용 추정 1회 충전 5–6시간 (직접 측정 전)', '14500 cell 800 mAh · USB-C charging · plan on 5–6 h per charge until measured')],
    [tr('기록', 'Logging'), tr('GNSS 에포크마다 1행, 최대 1행/초 (펌웨어 0.3.0) · 행당 48바이트', 'One row per GNSS epoch, at most 1 row per second (firmware 0.3.0) · 48 bytes per row')],
    [tr('저장', 'Storage'), tr('약 2.5 MB · 약 14시간 기록 (48 B/s로 계산, 측정 전)', 'About 2.5 MB · about 14 h of recordings (calculated at 48 B/s, not measured)')],
    [tr('조작', 'Control'), tr('버튼 1개 (IO27): 대기 중 짧게 = 이동 방식 변경 · 기록 중 짧게 = 이벤트 표시 · 2.5초 = 기록 시작/정지 · 대기 중 6초 이상 = Wi-Fi 내보내기', 'One button (IO27): short in idle = change mode · short while recording = event mark · 2.5 s = start/stop · over 6 s in idle = Wi-Fi export')],
    [tr('이동 방식', 'Modes'), 'WALK · VEHICLE · UNKNOWN'],
    [tr('케이스', 'Case'), tr('PETG 3D 출력 · 0.20 mm 층 · 25% gyroid · 180×180 mm 베드', 'PETG 3D print · 0.20 mm layers · 25% gyroid · 180×180 mm bed')],
    [tr('한계', 'Limits'), tr('방수·내열 아님 (비·뜨거운 차 안 주의) · Wi-Fi는 내보내기 모드에서만', 'Not waterproof or heat-proof (rain, hot cars) · Wi-Fi only in export mode')],
  ],
  phases: [
    [tr('1 · 시험 조각 출력', '1 · Print test pieces'), tr('USB·버튼·화면 맞춤을 확인하는 시험 조각과 버튼 부품 출력 (약 1시간)', 'Test pieces and button parts to check USB, button and display fit (about 1 h)')],
    [tr('2 · 펌웨어 올리기', '2 · Flash the firmware'), tr('PlatformIO로 0.3.0 업로드 · 시리얼에서 HELLO → OK HELLO fw=0.3.0', 'Upload 0.3.0 with PlatformIO · HELLO on serial → OK HELLO fw=0.3.0')],
    [tr('3 · 벤치 시험', '3 · Bench test'), tr('화면 8선(BLK는 D7, D13 금지) · GNSS 4선 · 앱 5단계 시험 · 멀티미터로 셀 극성 확인(+3.0–4.2 V) 후 연결·전압 보정', 'Display 8 wires (BLK on D7, never D13) · GNSS 4 wires · 5-step app test · check cell polarity (+3.0–4.2 V), plug in, calibrate')],
    [tr('4 · 맞춤 시험', '4 · Test fits'), tr('USB 플러그(12.4×7.0 mm까지) · 버튼 딸깍 · 화면 창 위치', 'USB plug (up to 12.4×7.0 mm) · button click · display window')],
    [tr('5 · 케이스 출력', '5 · Print the case'), tr('하판 2.5–3.5시간 · 상판 1.5–2시간 · 베젤·GNSS 브래킷 1시간 이내', 'Bottom 2.5–3.5 h · top 1.5–2 h · bezel and GNSS bracket under 1 h')],
    [tr('6 · 조립', '6 · Assemble'), tr('버튼·보드·GNSS 브래킷·안테나·셀·화면·베젤 순서로 조립 · 뒤에서 M3×12 나사 2개', 'Button, board, GNSS bracket, antenna, cell, display, bezel · 2 × M3×12 from the back')],
    [tr('7 · 첫 사용', '7 · First use'), tr('야외에서 초록 3D 확인 → 2.5초 눌러 REC → 짧게 눌러 이벤트 → 2.5초 정지 → USB로 앱에 가져와 재생', 'Outdoors wait for green 3D → hold 2.5 s for REC → short press for events → hold 2.5 s to stop → pull into the app over USB and replay')],
  ],
  figs: [
    ['fig01', tr('전자 부품', 'Electronics parts')], ['fig02', tr('출력 부품', 'Printed parts')], ['fig03', tr('FireBeetle 핀 배치', 'FireBeetle pin map')], ['fig04', tr('화면 배선', 'Display wiring')], ['fig05', tr('GNSS 배선', 'GNSS wiring')],
    ['fig06', tr('화면 GNSS 상태 (NO FIX · no data · 3D)', 'Screen GNSS states (NO FIX · no data · 3D)')], ['fig07', tr('셀 극성 확인', 'Cell polarity check')], ['fig08', tr('GNSS 브래킷의 패치 안테나', 'Patch antenna on the GNSS bracket')], ['fig09', tr('버튼 하나로 조작', 'One-button controls')], ['fig10', tr('화면 읽는 법', 'Reading the screen')],
  ],
  note: tr('설명서 요약입니다. 기록 간격은 펌웨어 0.3.0 설정값입니다. 설명서에는 연구 목적, 비용, 현장 시험 결과가 적혀 있지 않아 여기에도 넣지 않았습니다. 기록은 Mac에 남고 git에는 올리지 않습니다.', 'A summary of the build manual; the logging rate is the firmware 0.3.0 setting. The manual does not state the research purpose, cost or field-test results, so they are not shown here. Recordings stay on the Mac and out of git.'),
};
function buildDocs() {
  const pv = B.provenance, fp = B.footprints;
  $('pDocs').innerHTML = `
    <div class="grp-h"><span>${LOGGER.title}</span></div>
    <p class="note" style="margin:0 4px 6px">${LOGGER.sub}</p>
    ${window.WFG_FIG ? '' : `<a class="logger-open" href="logger.html${EN ? '#lang=en' : ''}"><b>${tr('3D 분해 모델 · 전체 제작 설명서 열기', 'Open the exploded 3D model and full build manual')}</b><span>${tr('부품별 정보, 조립 순서 애니메이션, 37단계 전체', 'Part details, step-by-step assembly, all 37 steps')} →</span></a>`}
    <figure class="hero"><img src="${figSrc('fig10')}" alt="${LOGGER.figs[9][1]}" loading="lazy" data-big="${figSrc('fig10')}"><figcaption>${LOGGER.figs[9][1]}</figcaption></figure>
    ${EN ? '' : `<ol class="fig-key"><li><b>상태</b>: 대기(IDLE), 기록 중(REC, 점 깜빡임), 가득 참(FULL), 내보내기(EXPORT) · 오른쪽은 이동 방식</li><li><b>GNSS</b>: 신호 없음(빨강), 위치 미확정 NO FIX(노랑), 3D·2D 위치와 위성 수·HDOP(초록)</li><li><b>배터리</b>: 잔량(%)과 전압</li><li><b>저장 공간</b>: 사용량과 남은 기록 시간</li><li><b>세션</b>: 세션 번호와 지금까지의 기록 수</li><li><b>마지막 이벤트 표시</b>: 위치(loc) 또는 NO POS, 표시한 뒤 지난 시간</li><li><b>아래 막대</b>: 길게 누르기 카운트다운 또는 안내 문구</li></ol><p class="note">그림 속 글은 기기 화면과 제작 설명서 원본(영어) 그대로입니다.</p>`}
    <p style="margin:6px 4px;font-size:12px;color:var(--ink-2)">${LOGGER.what}</p>
    <dl class="kv" style="padding:0 4px">${LOGGER.specs.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>
    <h4 class="sub-h">${tr('제작 단계', 'Build phases')}</h4>
    <ol class="phases">${LOGGER.phases.map(([a, b]) => `<li><b>${a}</b><span>${b}</span></li>`).join('')}</ol>
    <h4 class="sub-h">${tr('설명서 그림', 'Manual figures')} <small>${tr('누르면 크게', 'click to enlarge')}</small></h4>
    <div class="gallery">${LOGGER.figs.map(([f, c]) => `<button type="button" data-big="${figSrc(f)}" title="${c}"><img src="${figSrc(f)}" alt="${c}" loading="lazy"><span>${c}</span></button>`).join('')}</div>
    <p class="note" style="margin:6px 4px 14px">${LOGGER.note}</p>
    <div class="grp-h"><span>${tr('데이터 출처 · 한계', 'Data sources · limits')}</span></div>
    <ul class="src">
      <li><b>${tr('지형 · 경사', 'Terrain · slope')}</b> — ${tr(`AWS Terrain Tiles (terrarium, SRTM 등 공개 DEM)를 ${B.dem.w}×${B.dem.h} 격자로 재표본. 경사·사면 방향은 이 DEM에서 계산했습니다. 해수면 아래는 0 m로 두고 바다로 그립니다. 높이는 6.5배 과장해 산의 기복이 잘 보이게 했습니다.`, `AWS Terrain Tiles (terrarium; SRTM and other public DEMs) resampled to ${B.dem.w}×${B.dem.h}. Slope and aspect are computed from it. Below sea level is set to 0 m and drawn as sea. Heights are exaggerated 6.5× so the mountains read clearly.`)}</li>
      <li><b>${tr('바탕 지도 · 지명 · 산 높이', 'Base map · names · peaks')}</b> — © OpenStreetMap contributors (${tr('Protomaps 빌드, 플래너 기본 지도와 같은 파일', 'Protomaps build, the same file as the planner basemap')}). ${tr('나무와 산림 색은 OSM 산림 폴리곤과 경사로 추정한 표시입니다.', 'Trees and forest colour are estimated from OSM forest polygons and slope.')}</li>
      <li><b>${tr('연소 상태 B(t)', 'Burned state B(t)')}</b> — ${tr(`기록된 연소 범위를 375 m 셀로 나타낸 ${fp.length}개 시각. 기록 사이에는 직전 기록을 보여 주며, 불씨에서 재로 식는 색은 표시용입니다.`, `${fp.length} recorded burned-area times on the 375 m cells. Between records the previous record is shown; the ember-to-ash colour is for display.`)}</li>
      <li><b>${tr('새 연소 확률 q', 'New-burn probability q')}</b> — ${tr(`모델 출력 p_new_burn_1h (${pv.package}, 체크포인트 ${pv.model}, 시나리오 ${pv.시나리오s}개). 입력 시각부터 1시간만 유효하며 보간하지 않습니다.`, `Model output p_new_burn_1h (${pv.package}, checkpoint ${pv.model}, ${pv.scenarios} scenarios). Valid for 1 h after each input time; never interpolated.`)}</li>
      <li><b>${tr('시간별 누적 연소 확률 F(h)', 'Hourly cumulative probability F(h)')}</b> — ${HM ? tr(`재귀 몬테카를로 확산(predict_cumulative) · 체크포인트 ${HM.checkpoint_sha256.slice(0, 8)} · 궤적 ${HM.n_samples.toLocaleString()}개 · 1–${HM.hours.length}시간. ±는 몬테카를로 표본 오차(95%)입니다.`, `Recursive Monte Carlo (predict_cumulative) · checkpoint ${HM.checkpoint_sha256.slice(0, 8)} · ${HM.n_samples.toLocaleString()} trajectories · 1–${HM.hours.length} h. ± is the Monte Carlo sampling error (95%).`)
        : tr('저장소의 predict_cumulative가 만드는 1시간 간격 누적 확률입니다. 실행에 필요한 환경 입력 래스터가 GitHub에 없어(forecast/README.md, External inputs) 이 화면에는 아직 결과가 없습니다. 만들어 내거나 q로 근사하지 않았습니다.', 'Hourly cumulative probability from the repository’s predict_cumulative. The environmental input rasters it needs are not on GitHub (forecast/README.md, External inputs), so this view has no results yet. Nothing is made up or approximated from q.')}</li>
      <li><b>${tr('복사 열유속 F(x) · 화재 시나리오 4개', 'Radiant flux F(x) · 4 fire scenarios')}</b> — ${tr(`경로 점검에 실제로 쓰인 위험 입력(HAZARD.json, ${HZ.length}개 입력 시각). 입력 시각부터 1시간만 유효하며 연기·대류열·불티는 포함되지 않습니다.`, `The hazard input the route checks used (HAZARD.json, ${HZ.length} input times). Valid for 1 h after input; smoke, convective heat and embers are not included.`)}</li>
      <li><b>${tr('대피 경로 점검 · 정책 비교', 'Route checks · policy comparison')}</b> — ${tr(`기록된 Route-Check ${routes.length}건과 5개 정책 기록. 재계산 누적 노출은 셀 중심 근사이고, 판정과 기록 노출값은 원래 점검 결과입니다.`, `${routes.length} recorded Route-Checks and their 5 policy records. Recomputed dose is a cell-centre approximation; verdicts and recorded exposure are the original results.`)}</li>
      ${B.booth ? `<li><b>${tr('대피 현황', 'Evacuation status')}</b> — ${tr('플래너 부스 캐시(planner/cache): 실제 Route-Check API로 모든 출발지를 미리 점검한 결과. 화면에서는 계산하지 않습니다.', 'Planner booth cache (planner/cache): every origin checked in advance with the real Route-Check API. Nothing is computed in this view.')}</li>` : ''}
      <li><b>${tr('✱ 기온 · 바람 u/v · 수목 피복률 · 생물군계', '✱ Temperature · wind u/v · canopy · biome')}</b> — ${tr('설명용 합성 필드입니다. 실제 모델 입력 값이 아닙니다.', 'Illustrative synthetic fields, not the real model inputs.')}</li>
    </ul>
    <p class="note">${tr('이 화면은 계획 보조용 설명 도구입니다. 실제 대피 판단은 공식 안내를 따르세요.', 'This view is an explanatory planning aid. Follow official guidance for real evacuation decisions.')}</p>`;
  $('pDocs').querySelectorAll('[data-big]').forEach(b => b.onclick = () => openLightbox(b.dataset.big, b.title || b.alt || ''));
}
function openLightbox(src, cap) {
  const lb = $('lightbox'); lb.querySelector('img').src = src; lb.querySelector('figcaption span').textContent = cap; lb.hidden = false; lb.querySelector('button').focus();
}
$('lightbox').onclick = e => { if (e.target.closest('img') && !e.target.closest('button')) return; $('lightbox').hidden = true; };
addEventListener('keydown', e => { if (e.key === 'Escape') { $('lightbox').hidden = true; $('regMenu').hidden = true; $('regBtn').setAttribute('aria-expanded', 'false'); } });

// ---------------- overview ----------------
function caseTable() {
  return `<table class="mini"><tr><th>${tr('사례', 'Case')}</th><th>${tr('입력', 'Input')}</th><th>${tr('전체 조건', 'Full')}</th><th>${tr('이동시간만', 'Travel only')}</th></tr>
    ${CASES.map((c, i) => { const t = c.pol.travel_only, fc = t && t.full_check; return `<tr><td><button type="button" class="lnk" data-case="${i}">${c.r.label}</button></td><td>${fmt(c.r.t0)}</td><td><span class="pill ${c.r.verdict === 'checked_route' ? 'ok' : 'dark'}">${(VERDICT[c.r.verdict] || VERDICT.unresolved).t}</span></td><td>${fc ? (fc.passed ? `<span class="pill">${tr('통과', 'Pass')}</span>` : `<span class="pill bad">${tr('화염 접촉', 'Flame')}</span>`) : '–'}</td></tr>`; }).join('')}</table>`;
}
function buildOverview() {
  const pv = B.provenance, fp = B.footprints;
  $('pOverview').innerHTML = `
    <div class="grp-h"><span>${tr('사건 개요', 'Event')}</span></div>
    <dl class="kv" style="padding:0 4px">
      <dt>${tr('사건', 'Event')}</dt><dd>${tr(`${B.year} ${B.name.ko} 산불`, `${B.year} ${B.name.en} wildfire`)} · ${B.event}</dd>
      <dt>${tr('표시 범위', 'Extent')}</dt><dd>${KXr.toFixed(1)} × ${KYr.toFixed(1)} km · ${EN ? B.loc_en : B.loc_ko}</dd>
      <dt>${tr('격자', 'Grid')}</dt><dd>${tr(`375 m 셀 ${NR} × ${NC} (유효 ${valid.reduce((a, b) => a + b, 0).toLocaleString()}개)`, `375 m cells ${NR} × ${NC} (${valid.reduce((a, b) => a + b, 0).toLocaleString()} valid)`)}</dd>
      <dt>${tr('연소 기록', 'Burn records')}</dt><dd>${tr(`${fp.length}개 시각`, `${fp.length} times`)} · ${fmt(REC[0])} – ${fmt(REC[REC.length - 1])}</dd>
      <dt>${tr('모델 입력', 'Model inputs')}</dt><dd>${INP.map(h => fmt(h)).join(', ')}</dd>
      <dt>${tr('모델', 'Model')}</dt><dd>${pv.package} · ${tr('체크포인트', 'checkpoint')} ${pv.model} · ${tr(`시나리오 ${pv.시나리오s}개`, `${pv.scenarios} scenarios`)}</dd>
      <dt>${tr('현재 기록 면적', 'Recorded area now')}</dt><dd id="ovArea">–</dd>
      <dt>${tr('현재 활성 셀', 'Active cells now')}</dt><dd id="ovActive">–</dd>
    </dl>
    <div class="grp-h" style="margin-top:14px"><span>${tr('5개 연구 지역', 'Five study regions')}</span><span>${tr('누르면 전환', 'click to switch')}</span></div>
    <table class="mini regs"><tr><th>${tr('지역', 'Region')}</th><th>${tr('범위', 'Extent')}</th><th>${tr('출발지', 'Origins')}</th><th>${tr('이동시간만 접촉', 'Travel-only flame')}</th></tr>
      ${RIDX.map(r => `<tr class="${r.id === RID ? 'here' : ''}"><td><button type="button" class="lnk" data-reg="${r.id}">${REG_NAME(r)} ${r.year}</button>${r.booth ? ` <span class="pill ok" title="${tr('부스 캐시 있음', 'Has booth cache')}">${tr('캐시', 'cache')}</span>` : ''}</td><td>${r.km[0].toFixed(0)}×${r.km[1].toFixed(0)} km</td><td>${r.origins}</td><td>${r.rq3.filter(q => q.travel_fails_full).length}/${r.rq3.length}</td></tr>`).join('')}</table>
    <div class="grp-h" style="margin-top:14px"><span>${tr('기록된 연구 사례', 'Recorded research cases')}</span><span>${tr('누르면 그 1시간을 재생', 'click to play that hour')}</span></div>
    ${caseTable()}
    <div id="routeList"></div>`;
  $('pOverview').querySelectorAll('[data-reg]').forEach(b => b.onclick = () => b.dataset.reg !== RID && switchRegion(b.dataset.reg));
  $('pOverview').querySelectorAll('[data-case]').forEach(b => b.onclick = () => openCase(+b.dataset.case));
}

// ---------------- timeline + charts + events ----------------
const track = $('track');
const rangeLo = () => state.detail ? HZ[state.dk].t0 : 0, rangeHi = () => state.detail ? HZ[state.dk].t0 + HZ[state.dk].valid_until / 3600 : TMAX;
const pctOf = h => (h - rangeLo()) / (rangeHi() - rangeLo()) * 100;
const md = d => EN ? `${['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][d.getUTCMonth()]} ${d.getUTCDate()}` : `${d.getUTCMonth() + 1}월 ${d.getUTCDate()}일`;
function setDetail(on, k) {
  if (on && HZ.length) {
    const inside = hzK(state.t);
    state.dk = k != null ? k : inside >= 0 ? inside : HZ.reduce((b, h, i) => Math.abs(h.t0 - state.t) < Math.abs(HZ[b].t0 - state.t) ? i : b, 0);
    state.detail = true; state.t = (k == null && inside >= 0) ? clamp(state.t, rangeLo(), rangeHi() - 1e-4) : rangeLo(); }
  else state.detail = false;
  $('detailBtn').setAttribute('aria-pressed', String(state.detail)); $('detailTxt').textContent = state.detail ? tr(`${fmt(HZ[state.dk].t0)} 입력 후 1시간 · 1× = 1분/초`, `1 h after the ${fmt(HZ[state.dk].t0)} input · 1× = 1 min/s`) : '';
  buildTrack(); dirty = true;
}
function buildTrack() {
  const m = $('tMarks'); m.innerHTML = '';
  if (state.detail) {
    const lo = rangeLo(), Hd = HZ[state.dk];
    for (let mm = 0; mm <= 60; mm += 10) m.insertAdjacentHTML('beforeend', `<div class="tick ${mm === 0 ? 'day' : ''}" style="left:${mm / 60 * 100}%">+${mm}${tr('분', ' min')}<br>${fmt(lo + mm / 60, false)}</div>`);
    const mem = Hd.members[Math.max(0, state.member)]; mem.bp.slice(1, -1).forEach(b => m.insertAdjacentHTML('beforeend', `<div class="mkr bp" style="left:${b / 36}%" title="scenario ${Math.max(0, state.member) + 1} ${tr('구간 경계', 'interval edge')} +${(b / 60).toFixed(1)}${tr('분', ' min')}"></div>`));
    CASES.filter(c => c.k === state.dk).forEach(c => { const r = c.r; m.insertAdjacentHTML('beforeend', `<div class="mkr rt" style="left:${pctOf(r.tDep)}%" title="${r.label} ${tr('출발', 'departs')} ${fmt(r.tDep, false)}"></div>` + (r.tArr != null ? `<div class="mkr arr" style="left:${pctOf(r.tArr)}%" title="${r.label} ${tr('도착', 'arrives')} ${fmt(r.tArr, false)}"></div>` : '')); });
  } else {
    const step = TMAX <= 12 ? 1 : TMAX <= 30 ? 3 : 6;
    for (let h = 0; h <= TMAX; h++) { const hk = kstHour(h); if (hk % step !== 0) continue; const d = kst(h), day = hk === 0 || (h < step && TMAX <= 30 && h === Math.ceil((step - kstHour(0) % step) % step));
      m.insertAdjacentHTML('beforeend', `<div class="tick ${day ? 'day' : ''}" style="left:${h / TMAX * 100}%">${day ? `${md(d)}<br>` : ''}${p2(hk)}:00</div>`); }
    REC.forEach((h, i) => m.insertAdjacentHTML('beforeend', `<div class="mkr rec" style="left:${h / TMAX * 100}%" title="${tr('연소 기록', 'Burn record')} ${fmt(h)} · ${B.footprints[i].area_km2.toFixed(1)} km²"></div>`));
    INP.forEach(h => m.insertAdjacentHTML('beforeend', `<div class="mkr inp" style="left:${h / TMAX * 100}%" title="${tr('모델 입력', 'Model input')} ${fmt(h)}"></div>`));
    routes.forEach(r => m.insertAdjacentHTML('beforeend', `<div class="mkr rt" style="left:${r.tDep / TMAX * 100}%;${r.has ? '' : 'background:#1e1e1e'}" title="${tr('경로 점검', 'Route check')} ${r.label} ${fmt(r.tDep)}"></div>`));
  }
  const set = e => { const rc = track.getBoundingClientRect(); setTime(rangeLo() + clamp((e.clientX - rc.left) / rc.width, 0, 1) * (rangeHi() - rangeLo())); };
  track.onpointerdown = e => { track.setPointerCapture(e.pointerId); set(e); track.onpointermove = set; };
  track.onpointerup = () => { track.onpointermove = null; };
  track.onkeydown = e => { const st = state.detail ? 1 / 60 : 1; if (e.key === 'ArrowRight') setTime(state.t + st); if (e.key === 'ArrowLeft') setTime(state.t - st); };
}
const EVENTS = [];
function buildEvents() {
  B.footprints.forEach((f, i) => EVENTS.push({ t: REC[i], c: 'var(--muted)', x: `${tr('연소 기록', 'Burn record')} · ${f.area_km2.toFixed(1)} km²` }));
  INP.forEach((h, i) => EVENTS.push({ t: h + .001, c: '#e2552b', x: tr(`모델 입력 · 활성 ${BURNING[i].size}셀 · Σq ${(QF[i].reduce((a, b) => a + b, 0)).toFixed(2)}`, `Model input · ${BURNING[i].size} active cells · Σq ${(QF[i].reduce((a, b) => a + b, 0)).toFixed(2)}`) }));
  routes.forEach(r => EVENTS.push({ t: r.tDep, c: r.has ? '#2f8a57' : '#1e1e1e', x: `${tr('경로 점검', 'Route check')} ${r.label} · ${(VERDICT[r.verdict] || VERDICT.unresolved).t}${r.arr != null ? ' · ' + fmtMin(r.arr - r.dep) : ''}`, route: r }));
  BOOTH.forEach(b => { const c = boothCounts(b); EVENTS.push({ t: b.t0 + .002, c: '#3c6f9c', x: tr(`대피 현황 · 출발지 ${c.total.all}곳 중 ${c.all.checked_route || 0}곳 확인된 경로`, `Evacuation status · ${c.all.checked_route || 0} of ${c.total.all} origins have a checked route`), booth: true }); });
  EVENTS.sort((a, b) => a.t - b.t);
  const ul = $('evList'); ul.innerHTML = '';
  EVENTS.forEach(ev => { const li = document.createElement('li'), b = document.createElement('button'); b.type = 'button';
    b.innerHTML = `<span class="ic" style="background:${ev.c}"></span><span class="x">${ev.x}</span><span class="t">${fmt(ev.t)}</span>`;
    b.onclick = () => { if (ev.route) { openCase(ev.route.idx); } else { if (NAV.on) navExit('pLayers'); if (state.detail) setDetail(false); setTime(ev.t + .02); setPlaying(false); if (ev.booth) showTab('pEvac'); } };
    li.appendChild(b); ul.appendChild(li); ev.btn = b; });
}
const svgNS = 'http://www.w3.org/2000/svg';
function chart(svg, { xs, ys, x0, x1, y1, kind, cursor, color = '#e2552b', fill = 'rgba(226,85,43,.14)', xfmt, yticks }) {
  const w = svg.clientWidth || 300, h = svg.clientHeight || 90, pl = 30, pr = 6, pt = 6, pb = 16;
  const X = x => pl + (x - x0) / (x1 - x0) * (w - pl - pr), Y = y => h - pb - y / y1 * (h - pt - pb);
  let s = `<line x1="${pl}" x2="${w - pr}" y1="${Y(0)}" y2="${Y(0)}" stroke="var(--line-2)"/>`;
  (yticks || [y1 / 2, y1]).forEach(v => { s += `<line x1="${pl}" x2="${w - pr}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--line)" stroke-dasharray="2 3"/><text x="${pl - 4}" y="${Y(v) + 3}" text-anchor="end">${v >= 1000 ? (v / 1000).toFixed(1) + 'k' : +v.toFixed(2)}</text>`; });
  if (kind === 'step') { let d = `M${X(xs[0])},${Y(0)} L${X(xs[0])},${Y(ys[0])}`; for (let i = 1; i < xs.length; i++) d += ` L${X(xs[i])},${Y(ys[i - 1])} L${X(xs[i])},${Y(ys[i])}`; d += ` L${X(x1)},${Y(ys[ys.length - 1])}`;
    s += `<path d="${d} L${X(x1)},${Y(0)} Z" fill="${fill}"/><path d="${d}" fill="none" stroke="${color}" stroke-width="1.6"/>`; xs.forEach((x, i) => s += `<circle cx="${X(x)}" cy="${Y(ys[i])}" r="2.6" fill="${color}"/>`); }
  if (kind === 'bar') xs.forEach((x, i) => { const bw = Math.max(6, (w - pl - pr) / 40); s += `<rect x="${X(x) - bw / 2}" y="${Y(ys[i])}" width="${bw}" height="${Y(0) - Y(ys[i])}" rx="1.5" fill="${color}"/><text x="${X(x)}" y="${Y(ys[i]) - 3}" text-anchor="middle">${ys[i].toFixed(2)}</text>`; });
  if (kind === 'area') { let d = ''; xs.forEach((x, i) => d += (i ? ' L' : 'M') + X(x).toFixed(1) + ',' + Y(ys[i]).toFixed(1)); s += `<path d="${d} L${X(xs[xs.length - 1])},${Y(0)} L${X(xs[0])},${Y(0)} Z" fill="${fill}"/><path d="${d}" fill="none" stroke="${color}" stroke-width="1.4"/>`; }
  (xfmt || []).forEach(([x, txt]) => s += `<text x="${X(x)}" y="${h - 3}" text-anchor="middle">${txt}</text>`);
  if (cursor != null) s += `<line x1="${X(cursor[0])}" x2="${X(cursor[0])}" y1="${pt}" y2="${Y(0)}" stroke="var(--ink)" stroke-width="1"/>` + (cursor[1] != null ? `<circle cx="${X(cursor[0])}" cy="${Y(cursor[1])}" r="3.5" fill="var(--panel)" stroke="var(--ink)" stroke-width="1.5"/>` : '');
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`); svg.innerHTML = s;
}
const dayTicks = () => { const a = [], step = TMAX <= 12 ? 3 : TMAX <= 30 ? 6 : 24; for (let h = 0; h <= TMAX; h++) if (kstHour(h) % step === 0) { const d = kst(h); a.push([h, step === 24 ? `${d.getUTCMonth() + 1}/${d.getUTCDate()}` : `${p2(kstHour(h))}h`]); } return a; };
const AREA_MAX = niceMax(Math.max(...B.footprints.map(f => f.area_km2)));
const QS = QF.map(a => a.reduce((x, y) => x + y, 0) * CELL_KM2), QS_MAX = niceMax(Math.max(.05, ...QS));
const ELEV_MAX = niceMax(HMAX);
function drawCharts() {
  const t = state.t, k = recIdx(t), areas = B.footprints.map(f => f.area_km2);
  chart($('c1'), { xs: REC, ys: areas, x0: 0, x1: TMAX, y1: AREA_MAX, kind: 'step', cursor: [t, k >= 0 ? areas[k] : 0], xfmt: dayTicks() });
  $('c1v').textContent = k >= 0 ? areas[k].toFixed(1) + ' km²' : '–';
  const qi = inpIdx(t), hk = hourIdx(t);
  if (HR && hk >= 0 && L.mc.on) {
    const ex = HR.expected_new_km2[hk], hs = hourStep(t, hk), ymax = Math.max(1, ...ex) * 1.15;
    $('c2t').innerHTML = `${tr('몬테카를로 기대 새 연소 면적', 'Monte Carlo expected new burn')} <small>${fmt(HCUT[hk])} ${tr('입력 후 시간별', 'input, hourly')}</small>`;
    chart($('c2'), { xs: [0, ...HR.meta.hours], ys: [0, ...ex], x0: 0, x1: HH, y1: ymax, kind: 'area', color: '#6e32a0', fill: 'rgba(110,50,160,.16)', cursor: t - HCUT[hk] <= HH ? [hs, ex[hs - 1]] : null, xfmt: [[0, '0'], [HH / 2, `${HH / 2}h`], [HH, `${HH}h`]], yticks: [+(ymax / 2).toFixed(1), +ymax.toFixed(1)] });
    $('c2v').textContent = `${ex[hs - 1].toFixed(2)} km² · ${hs}h` + (t - HCUT[hk] > HH ? tr(' (범위 지남)', ' (past range)') : '');
  } else {
    $('c2t').innerHTML = `${tr('모델 기대 새 연소 면적', 'Expected new burn (model)')} <small>${tr('다음 1시간 · Σq', 'next hour · Σq')}</small>`;
    chart($('c2'), { xs: INP, ys: QS, x0: 0, x1: TMAX, y1: QS_MAX, kind: 'bar', cursor: [t, null], xfmt: dayTicks() });
    $('c2v').textContent = qi >= 0 ? QS[qi].toFixed(2) + ' km²' + (t - INP[qi] > 1 ? tr(' (지남)', ' (expired)') : '') : '–';
  }
  const sc = CASES[selRoute];
  if (state.detail && sc && sc.k === state.dk && sc.pol.full && sc.pol.full.exp) { drawDose($('c3'), sc, (t - sc.r.t0) * 3600, false); $('c3t').innerHTML = `${tr('누적 열 노출', 'Cumulative heat dose')} D̂(t) <small>${sc.r.label} · ${tr('시나리오 4개', '4 scenarios')} · log</small>`; const e = sc.pol.full.exp; $('c3v').textContent = `${tr('최대', 'max')} ${Math.max(...e.map(x => x.dose)).toFixed(3)} / ${fmtLim(sc.pol.full.limits.dose_kj_m2)} kJ/m²`; return; }
  const r = routes[selRoute], tpol = sc && sc.pol.travel_only, dense = r && r.has ? r.dense : tpol && tpol.dense.length > 1 ? tpol.dense : null;
  if (!dense) { $('c3').innerHTML = ''; $('c3t').innerHTML = tr('고도 단면', 'Elevation profile'); $('c3v').textContent = ''; return; }
  const len = dense[dense.length - 1].d, s = (t - r.t0) * 3600, moving = r.has && t >= r.tDep && t <= r.tArr;
  let cur = null; if (moving) { const p = dense.find(p => p.ts >= s) || dense[dense.length - 1]; cur = [p.d, p.e]; }
  const step = Math.max(1, Math.floor(dense.length / 160)), dd = dense.filter((_, i) => i % step === 0);
  chart($('c3'), { xs: dd.map(p => p.d), ys: dd.map(p => p.e), x0: 0, x1: len, y1: ELEV_MAX, kind: 'area', color: r.has ? '#3d6b4c' : '#c4741f', fill: r.has ? 'rgba(61,107,76,.16)' : 'rgba(232,134,42,.14)', cursor: cur, xfmt: [[0, '0'], [len / 2, (len / 2).toFixed(1)], [len, len.toFixed(1) + ' km']] });
  $('c3t').innerHTML = `${tr('고도 단면', 'Elevation profile')} <small>${r.label} · ${r.has ? (VERDICT[r.verdict] || VERDICT.unresolved).t : tr('이동시간만 경로 (전체 조건 경로 없음)', 'travel-only route (no full-constraint route)')}</small>`;
  $('c3v').textContent = moving ? `${Math.round(cur[1])} m` : `${tr('최고', 'max')} ${Math.round(Math.max(...dense.map(p => p.e)))} m`;
}
function selectRoute(i) { selRoute = i; buildRouteMeshes(); drawCharts(); buildRouteTab(); }
function showTab(id) { if (id !== 'pNav' && NAV.on) return navExit(id);     // leaving the navigation tab leaves navigation (navExit shows `id`)
  document.querySelectorAll('.tabs button').forEach(x => x.setAttribute('aria-selected', String(x.dataset.p === id))); document.querySelectorAll('.pane').forEach(p => p.hidden = p.id !== id); const b = document.querySelector(`.tabs button[data-p="${id}"]`); if (b) b.scrollIntoView({ block: 'nearest', inline: 'nearest' }); if (id === 'pNav') navEnter(); }
function openCase(i) { const c = CASES[i]; if (!c) return; if (NAV.on) navExit('pRoute'); selectRoute(i); if (c.k >= 0) setDetail(true, c.k); setTime(c.r.tDep - 2 / 60); setPlaying(true, 1); flyTo(c.r); if (state.cmp !== 'travel') showTab('pRoute'); }

// ---------------- research tabs: route check (stage 03) and model structure (01 → 02 → 03) ----------------
function drawDose(svg, sc, sNow, big) {
  const p = sc.pol.full, ex = p.exp, lim = p.limits.dose_kj_m2, w = svg.clientWidth || 300, h = svg.clientHeight || 110, pl = 34, pr = 8, pt = 8, pb = 16;
  const x0 = 0, x1 = 3600, y0 = -4, y1 = Math.log10(lim) + .3, X = x => pl + (x - x0) / (x1 - x0) * (w - pl - pr), Y = v => h - pb - (Math.log10(Math.max(v, 1e-4)) - y0) / (y1 - y0) * (h - pt - pb);
  let o = '';
  const step = h < 130 ? 2 : 1;
  for (let e = -4; e <= Math.floor(y1); e += step) o += `<line x1="${pl}" x2="${w - pr}" y1="${Y(10 ** e)}" y2="${Y(10 ** e)}" stroke="var(--line)" stroke-dasharray="2 3"/><text x="${pl - 4}" y="${Y(10 ** e) + 3}" text-anchor="end">${e < 0 ? '1e' + e : 10 ** e}</text>`;
  o += `<line x1="${pl}" x2="${w - pr}" y1="${Y(lim)}" y2="${Y(lim)}" stroke="#d9472b" stroke-width="1.4" stroke-dasharray="5 3"/><text x="${w - pr}" y="${Y(lim) - 3}" text-anchor="end" style="fill:#d9472b">D_lim ${fmtLim(lim)} kJ/m²</text>`;
  o += `<rect x="${X(p.dep)}" y="${pt}" width="${Math.max(1, X(p.arr) - X(p.dep))}" height="${h - pt - pb}" fill="rgba(47,138,87,.08)"/><rect x="${X(p.arr)}" y="${pt}" width="${Math.max(1, X(p.arr + p.dwell_s) - X(p.arr))}" height="${h - pt - pb}" fill="rgba(47,138,87,.18)"/>`;
  ex.forEach((m, mi) => { let d = `M${X(p.dep)},${Y(m.series[0][1])}`; m.series.forEach(([ts, v]) => d += ` L${X(ts).toFixed(1)},${Y(v).toFixed(1)}`); o += `<path d="${d}" fill="none" stroke="${MEMBER_CSS[mi]}" stroke-width="1.5"/>`; });
  [0, 600, 1200, 1800, 2400, 3000, 3600].forEach(s => o += `<text x="${X(s)}" y="${h - 3}" text-anchor="middle">+${s / 60}${tr('분', 'm')}</text>`);
  if (sNow != null && sNow >= 0 && sNow <= 3600) o += `<line x1="${X(sNow)}" x2="${X(sNow)}" y1="${pt}" y2="${h - pb}" stroke="var(--ink)"/>`;
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`); svg.innerHTML = o;
}
function drawOccupancy(svg, sc, polName = 'full') {
  const p = sc.pol[polName], k = sc.k, w = svg.clientWidth || 300;
  const occ = []; let cur = null;
  for (const q of p.dense) { if (q.cell < 0) continue; if (!cur || cur.cell !== q.cell) { cur = { cell: q.cell, a: q.ts, b: q.ts }; occ.push(cur); } else cur.b = q.ts; }
  const last = occ[occ.length - 1]; if (last) last.b = Math.max(last.b, p.arr + p.dwell_s);
  const score = c => { let m = 0; HZ[k].members.forEach(mm => { for (let j = 0; j < mm.bp.length - 1; j++) m = Math.max(m, mm.flux[j * NCELL + c]); }); return m; };
  const flameIn = o => HZ[k].members.some(mm => mm.flame.some(s => s.has(o.cell)));
  occ.forEach(o => { o.F = score(o.cell); o.fl = flameIn(o); }); const rows = [...occ].sort((a, b) => (b.fl - a.fl) || b.F - a.F).slice(0, 7).sort((a, b) => a.a - b.a); if (last && !rows.includes(last)) rows.push(last);
  const rh = 16, h = rows.length * rh + 24, pl = 92, X = s => pl + s / 3600 * (w - pl - 8); let o = '', flames = 0, overlap = 0;
  rows.forEach((r, ri) => { const y = 6 + ri * rh;
    o += `<text x="2" y="${y + 11}">${r === last ? tr('목적지 체류', 'Dwell at dest.') : `${tr('셀', 'cell')} r${(r.cell / NC) | 0} c${r.cell % NC}`} · ${sci(r.F, 3)}</text>`;
    HZ[k].members.forEach((mm, mi) => { for (let j = 0; j < mm.bp.length - 1; j++) if (mm.flame[j].has(r.cell)) { flames++; if (mm.bp[j] < r.b && mm.bp[j + 1] > r.a) overlap++; o += `<rect x="${X(mm.bp[j])}" y="${y + 1 + mi * 3}" width="${X(mm.bp[j + 1]) - X(mm.bp[j])}" height="3" fill="${MEMBER_CSS[mi]}" opacity=".85"/>`; } });
    o += `<rect x="${X(r.a)}" y="${y + 2}" width="${Math.max(2, X(r.b) - X(r.a))}" height="${rh - 6}" fill="${r === last ? 'none' : polName === 'full' ? '#2f6fa8' : '#e8862a'}" stroke="${polName === 'full' ? '#2f6fa8' : '#c4741f'}" stroke-dasharray="${r === last ? '3 2' : ''}" rx="2"/>`; });
  [0, 1200, 2400, 3600].forEach(s => o += `<text x="${X(s)}" y="${h - 4}" text-anchor="middle">+${s / 60}${tr('분', 'm')}</text>`);
  svg.style.height = h + 'px'; svg.setAttribute('viewBox', `0 0 ${w} ${h}`); svg.innerHTML = o; return { flames, overlap };
}
let routeTabTok = 0;
function buildRouteTab() {
  const el = $('pRoute'); if (!el) return; const sc = CASES[selRoute]; if (!sc) { el.innerHTML = `<p class="note">${tr('기록된 경로 점검 사례가 없습니다.', 'No recorded route checks.')}</p>`; return; }
  const p = sc.pol.full, r = sc.r, ok = p.verdict === 'checked_route', tp = sc.pol.travel_only;
  const head = `<div class="grp-h"><span>${tr(`기록된 Route-Check 사례 · ${B.name.ko}`, `Recorded Route-Check cases · ${B.name.en}`)}</span><span>${tr('누르면 그 1시간을 재생', 'click to play that hour')}</span></div>
    <div class="cases">${CASES.map((c, i) => `<button type="button" data-i="${i}" aria-pressed="${i === selRoute}" class="${c.r.has ? '' : 'nr'}"><b>${c.r.label}</b><small>${fmt(c.r.t0)}</small></button>`).join('')}</div>
    <h4>${r.label} · ${(VERDICT[p.verdict] || VERDICT.unresolved).t} <small>${tr('입력', 'input')} ${fmt(r.t0)} · ${tr('시나리오 4개', '4 scenarios')}</small></h4>`;
  const ablation = `<h4>${tr('제약 제거 비교 (ablation)', 'Constraint ablation')} <small>${tr('같은 사례 · 5개 정책 · 지도에 표시', 'same case · 5 policies · on the map')}</small></h4>
    <table class="mini"><tr><th>${tr('정책', 'Policy')}</th><th>${tr('판정', 'Verdict')}</th><th>${tr('도착', 'Arrival')}</th><th>${tr('길이', 'Length')}</th><th>${tr('전체 위험 검사', 'Full check')}</th></tr>
      ${POLICY_ORDER.filter(n => sc.pol[n]).map(n => { const q = sc.pol[n], fc = q.full_check;
        return `<tr><td><label><input type="checkbox" data-pol="${n}" ${n === 'full' ? `checked disabled title="${tr('기준 경로 (항상 표시)', 'Reference route (always shown)')}"` : state.pols.has(n) ? 'checked' : ''}><i style="display:inline-block;width:10px;height:3px;background:${POLICY[n].css};vertical-align:3px;margin-right:4px"></i>${POLICY[n].n}</label></td><td>${q.verdict === 'checked_route' ? '✓' : tr('없음', 'none')}</td><td>${q.arr != null ? '+' + fmtS(q.arr) : '–'}</td><td>${q.length_m != null ? (q.length_m / 1000).toFixed(1) + ' km' : '–'}</td><td>${fc ? (fc.passed ? tr('통과', 'pass') : `<b style="color:#d9472b">${tr('불통과', 'fail')}</b>`) : '–'}</td></tr>`; }).join('')}</table>
    <p class="note" style="margin:4px">${tr('전체 위험 검사: 각 정책의 경로를 같은 화재 입력의 전체 조건(화염 접촉·순간 열유속·누적 노출, 4개 시나리오)으로 다시 검사한 기록입니다. 주황 점선 = 이동시간만 고려한 경로, 빨간 점 = 그 경로가 화염 셀을 지나는 지점.', 'Full check: each policy’s route re-checked against the full constraints of the same fire input (flame contact, peak flux, dose; 4 scenarios). Orange dashes = travel-time-only route; red dots = where it passes a flame cell.')}</p>`;
  if (!ok) {
    el.innerHTML = head + `
      <div class="flow"><div><b>${tr('결과 · 모델상 경로 없음', 'Result · no route in the model')}</b>${tr('경로 엔진이 이 모델·조건에서 네 시나리오 모두 화염 접촉 없이 도착 허용 시간 안에 체류를 마치는 여정이 없다고 기록했습니다 (공급된 4개 시나리오 · 1초 격자에서의 엔진 증명 기록)', 'The route engine recorded that, in this model and these conditions, no journey avoids flame contact in all four scenarios and finishes its dwell within the arrival window (an engine proof for the 4 supplied scenarios on a 1 s lattice)')} (${esc(p.raw || p.decision || '')}).<br><span class="note">${tr('대피 판단은 공식 안내를 따라야 합니다. 이 판정은 "안전한 길이 없다"가 아니라 "이 모델에서 확인된 길이 없다"는 뜻입니다.', 'Follow official guidance. This means “no route could be checked in this model”, not “there is no safe road”.')}</span></div>
      ${tp ? `<div><b>${tr('같은 출발의 이동시간만 경로', 'Travel-time-only route, same departure')}</b>${tr(`도착 +${fmtS(tp.arr)} · ${(tp.length_m / 1000).toFixed(1)} km · 전체 위험 검사 ${tp.full_check && !tp.full_check.passed ? '불통과 (' + (tp.full_check.components || []).join(', ') + ')' : '통과'} · 이 화면 재계산 화염 셀 통과 ${sc.travelHits.length}지점`, `Arrival +${fmtS(tp.arr)} · ${(tp.length_m / 1000).toFixed(1)} km · full check ${tp.full_check && !tp.full_check.passed ? 'fails (' + (tp.full_check.components || []).join(', ') + ')' : 'passes'} · ${sc.travelHits.length} flame-cell points recomputed here`)}</div>` : ''}</div>
      ${ablation}
      ${tp && tp.dense.length > 1 ? `<h4>${tr('점유 구간 검사 · 이동시간만 경로', 'Occupancy check · travel-only route')} <small>${tr('주황 = 차량 점유 · 색 막대 = 시나리오 화염 구간', 'orange = vehicle occupancy · bars = scenario flame intervals')}</small></h4><svg class="svgbox" id="rtOcc"></svg><p class="note" id="rtOccNote" style="margin:4px"></p>` : ''}`;
    bindRouteTab(el); const tok = ++routeTabTok;
    requestAnimationFrame(() => { if (tok === routeTabTok && tp && tp.dense.length > 1 && $('rtOcc')) { const o = drawOccupancy($('rtOcc'), sc, 'travel_only'); $('rtOccNote').textContent = tr(`차량 점유와 겹치는 화염 구간 ${o.overlap}개 → 화염 접촉.`, `${o.overlap} flame intervals overlap the vehicle’s occupancy → flame contact.`); } });
    return;
  }
  el.innerHTML = head + `
    <dl class="kv" style="padding:0 4px"><dt>${tr('출발 · 도착', 'Depart · arrive')}</dt><dd>+${fmtS(p.dep)} → +${fmtS(p.arr)} (${tr('이동', 'travel')} ${fmtS(p.arr - p.dep)})</dd>
      <dt>${tr('길이', 'Length')}</dt><dd>${(p.length_m / 1000).toFixed(1)} km · ${tr('목적지 체류', 'dwell')} ${p.dwell_s}${tr('초', ' s')} · ${tr('도착 허용', 'window')} [+${fmtS(p.window[0])}, +${fmtS(p.window[1])}]</dd>
      <dt>${tr('허용값', 'Limits')}</dt><dd>${tr('순간 열유속', 'peak flux')} ≤ ${p.limits.peak_kw_m2} kW/m² · ${tr('누적', 'dose')} ≤ ${fmtLim(p.limits.dose_kj_m2)} kJ/m²${p.incurred ? tr(` (이미 받은 노출 ${fmtLim(p.incurred)} kJ/m² 포함)`, ` (incl. ${fmtLim(p.incurred)} kJ/m² already received)`) : ''}</dd>
      <dt>${tr('계산 시간', 'Compute')}</dt><dd>${p.compute_s != null ? p.compute_s.toFixed(2) + tr('초 (30초 한도 ', ' s (30 s budget, ') + (p.within_budget ? tr('안', 'within') : tr('초과', 'over')) + ')' : '–'}</dd></dl>
    <h4>${tr('탐색 순서', 'Search order')} <small>${tr('보고서 그림 6', 'report Fig. 6')}</small></h4>
    <div class="flow"><div><b>${tr('1단계 · 화재 회피 완화 탐색', 'Stage 1 · relaxed fire-avoiding search')}</b>${tr(`순간·누적 열 조건만 빼고 도로·회전·대기·체류·화재 접촉을 지킨 가장 이른 도착 → 하한 L = +${fmtS(p.L)}`, `Earliest arrival keeping roads, turns, waits, dwell and flame contact, dropping only the peak and dose limits → lower bound L = +${fmtS(p.L)}`)}</div>
      <div><b>${tr('2단계 · 전체 여정 검사', 'Stage 2 · whole-journey check')}</b>${tr('후보 여정의 이동·대기·체류 구간을 네 시나리오에서 접촉·순간 열유속·누적 노출로 검사 → 통과', 'The candidate’s travel, wait and dwell are checked in all four scenarios for contact, peak flux and dose → pass')}</div>
      <div class="ok"><b>${tr('결과', 'Result')} · ${(VERDICT[p.verdict] || VERDICT.unresolved).t}</b>${tr('도착', 'Arrival')} +${fmtS(p.arr)} ${p.arr === p.L ? tr('= 하한 L → 이 모델·조건에서 더 이른 도착은 없음 (모델 기준 조건부 최적)', '= lower bound L → no earlier arrival in this model and these conditions (conditional model optimum)') : tr('> 하한 L', '> lower bound L')}<br><span class="note">${p.decision || ''}</span></div></div>
    ${ablation}
    <h4>${tr('시나리오별 노출', 'Exposure per scenario')} <small>${tr('전체 조건 경로', 'full-constraint route')}</small></h4>
    <table class="mini"><tr><th>scenario</th><th>${tr('기록 최대', 'Rec. peak')}</th><th>${tr('기록 누적', 'Rec. dose')}</th><th>${tr('재계산 누적*', 'Recomp.*')}</th><th>${tr('접촉', 'Contact')}</th></tr>
      ${p.exposure.map((e, mi) => `<tr><td><i style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${MEMBER_CSS[mi]};margin-right:5px"></i>S${mi + 1}</td><td>${sci(e.peak, 4)} kW/m²</td><td>${sci(e.dose, 3)} kJ/m²</td><td>${p.exp ? sci(p.exp[mi].dose, 3) : '–'}</td><td>${e.contact ? tr('있음', 'yes') : tr('없음', 'no')}</td></tr>`).join('')}</table>
    <p class="note" style="margin:4px">${tr('* 셀 중심·구간별 상수 열유속으로 이 화면에서 다시 더한 근사입니다. 공식 판정은 셀 경계로 나눈 점유 구간 검사(기록값)입니다.', '* Re-summed in this view with cell-centre, piecewise-constant flux. The official verdict uses the occupancy-interval check split at cell edges (recorded values).')}</p>
    <h4>${tr('누적 열 노출', 'Cumulative heat dose')} D̂(t) <small>${tr('log · 점선 = D_lim', 'log · dashed = D_lim')}</small></h4><svg class="svgbox" id="rtDose"></svg>
    <h4>${tr('점유 구간 검사', 'Occupancy check')} <small>${tr('보고서 그림 5 · 파랑 = 차량 점유 · 색 막대 = 시나리오 화염 구간', 'report Fig. 5 · blue = vehicle occupancy · bars = scenario flame intervals')}</small></h4><svg class="svgbox" id="rtOcc"></svg><p class="note" id="rtOccNote" style="margin:4px"></p>`;
  bindRouteTab(el); const tok = ++routeTabTok;
  requestAnimationFrame(() => { if (tok !== routeTabTok) return; if (p.exp) drawDose($('rtDose'), sc, state.detail ? (state.t - sc.r.t0) * 3600 : null, true); const n = drawOccupancy($('rtOcc'), sc).flames;
    $('rtOccNote').textContent = n ? tr(`화염 구간 ${n}개가 표시됩니다. 차량 점유와 겹치지 않아야 통과합니다.`, `${n} flame intervals shown. The route passes only if none overlaps the vehicle’s occupancy.`) : tr('이 경로가 지나는 셀에는 네 시나리오 모두 이 1시간 동안 화염 구간이 없습니다 (접촉 없음).', 'No scenario has a flame interval in the cells this route crosses during the hour (no contact).'); });
}
function bindRouteTab(el) {
  el.querySelectorAll('.cases button').forEach(b => b.onclick = () => openCase(+b.dataset.i));
  el.querySelectorAll('input[data-pol]').forEach(cb => cb.onchange = () => { cb.checked ? state.pols.add(cb.dataset.pol) : state.pols.delete(cb.dataset.pol); buildRouteMeshes(); });
}
const KERNELS = [[3, 1.029560, 25.23, 5.40, 7.16, .000183], [5, 1.028091, 25.19, 19.96, 22.03, .000550], [7, 1.015684, 24.89, 25.54, 29.70, .000842], [9, 1.007414, 24.69, 49.09, 41.11, .001413]];
let lastCell = null;
function buildModelTab() {
  const a = (HZ[0] || {}).assumptions || {}, Q = a.fuel_load_kg_m2 * a.consumed_fraction * a.heat_of_combustion_j_kg / a.burning_duration_s;
  $('pModel').innerHTML = `
    <p class="note" style="margin:6px 4px 2px">${tr('포스터·보고서의 세 단계를 이 지도 위 값으로 따라갑니다. 지도 위에 커서를 올리면 그 셀의 값이 채워집니다.', 'Follow the poster’s and report’s three stages with the values on this map. Hover a cell to fill in its values.')}</p>
    <div class="stage s1"><h5><i>01</i>${tr('환경 조건부 확산 모델', 'Environment-conditioned spread model')} <small style="color:var(--muted);font-weight:400">Dynamic Filter Network</small></h5>
      <div class="f">R<sub>s,i</sub> = Σ<sub>δ</sub> k<sub>s,i,δ</sub> B<sub>i+δ</sub>  (s ∈ 3,5,7,9 · k ≥ 0, ${tr('중심 0', 'centre 0')})<br>λ<sub>i</sub> = Σ<sub>s</sub> a<sub>s</sub> R<sub>s,i</sub>,  a<sub>s</sub> = softplus(α<sub>s</sub>)<br>q<sub>i</sub> = (1 − B<sub>i</sub>)[1 − exp(−λ<sub>i</sub>Δt)],  Δt = 1 h</div>
      <table class="mini"><tr><th>kernel</th><th>a<sub>s</sub></th><th>${tr('rate 비중 검증/평가', 'rate share val/test')}</th><th>${tr('제거 시 Brier', 'Brier if removed')}</th></tr>${KERNELS.map(k => `<tr><td>${k[0]}×${k[0]}</td><td>${k[1].toFixed(3)}</td><td>${k[3].toFixed(1)}% / ${k[4].toFixed(1)}%</td><td>+${k[5].toFixed(6)}</td></tr>`).join('')}</table>
      <p class="note" style="margin:4px 0 0">${tr('표: 보고서 표 6 (선택 checkpoint c651). 9×9 분기가 rate에 가장 크게 기여(최대 1.5 km 범위).', 'Table: report Table 6 (selected checkpoint c651). The 9×9 branch contributes most to the rate (up to 1.5 km reach).')}</p>
      <div class="live" id="lv1"></div></div>
    <div class="stage s2"><h5><i>02</i>${tr('복사열 계산', 'Radiant heat')} <small style="color:var(--muted);font-weight:400">${tr('화재 시나리오 4개 → 열유속', '4 fire scenarios → heat flux')}</small></h5>
      <div class="f">Q<sub>source</sub> = c·H / T  → ${(a.fuel_load_kg_m2 * a.consumed_fraction).toFixed(1)} kg/m² × ${(a.heat_of_combustion_j_kg / 1e6).toFixed(3)} MJ/kg ÷ ${(a.burning_duration_s || 0).toFixed(0)} s = ${(Q / 1000).toFixed(2)} kW/m²<br>S<sub>i</sub> = χ Q (χ = ${a.radiative_fraction}),  F(x) = Σ<sub>i</sub> G<sub>i</sub>(x) S<sub>i</sub> m<sub>i</sub>  [kW/m²]<br>scenario: ${tr('점화 시각 균등 배정 · 독립', 'ignition times spread evenly · independent')} · seed ${a.seed} · ${tr('방출 높이', 'emission height')} ${a.emission_height_m} m</div>
      <div class="live" id="lv2"></div></div>
    <div class="stage s3"><h5><i>03</i>${tr('경로 탐색', 'Route search')} <small style="color:var(--muted);font-weight:400">${tr('열 노출 제한조건 A*', 'heat-exposure-constrained A*')}</small></h5>
      <div class="f">D̂(γ) = D<sub>prior</sub> + ∫ q<sub>m</sub>(x(t), t) dt ≤ D<sub>lim</sub>  (scenario m = 1…4)<br>${tr('순간 열유속 ≤ 10 kW/m² · 화재 접촉 없음 · 도착 허용 시간 안 체류 완료', 'peak flux ≤ 10 kW/m² · no flame contact · dwell finished inside the window')}<br>${tr('1단계 완화 탐색 → 하한 L,  2단계 전체 여정 검사', 'stage 1 relaxed search → lower bound L, stage 2 whole-journey check')}</div>
      <div class="live" id="lv3"></div></div>
    <div class="grp-h" style="margin-top:12px"><span>${tr('보고서 기록 결과', 'Reported results')}</span><span>${tr('이 화면에서 다시 계산하지 않음', 'not recomputed here')}</span></div>
    <table class="mini"><tr><td>${tr('예측 AP (재구성 평가)', 'Forecast AP (reconstructed test)')}</td><td>0.162 vs ${tr('기준', 'baseline')} 0.092 <span class="note">${tr('(한국 AP는 기준보다 낮음)', '(Korean AP below baseline)')}</span></td></tr><tr><td>${tr('Wapiti 25구간 Brier · AP', 'Wapiti 25 intervals Brier · AP')}</td><td>0.0084 · 0.146 (FARSITE 0.0238 · 0.063) <span class="note">${tr('(시험 지역 1곳)', '(one test region)')}</span></td></tr>
      <tr><td>${tr('경로 탐색 해결 (30초 · 20개 사례)', 'Routing resolved (30 s · 20 cases)')}</td><td>20/20 ${tr('(범위가 정해진 거절 5 포함)', '(incl. 5 scoped refusals)')} vs 13/20</td></tr><tr><td>${tr('이동시간만 고려한 경로 접촉', 'Travel-only routes touching flame')}</td><td>8/20</td></tr>
      <tr><td>${tr('요청 시간 중앙값 (함께 해결된 26쌍)', 'Median request time (26 jointly resolved pairs)')}</td><td>${tr('제안 8.006초 vs 기준 7.344초 (제안이 느림)', 'candidate 8.006 s vs reference 7.344 s (candidate slower)')}</td></tr><tr><td>${tr('영덕 도로 준비 (별도 입력·별도 실험)', 'Yeongdeok road preparation (separate input and experiment)')}</td><td>28.523${tr('초', ' s')} → 2.219${tr('초', ' s')} (−92.2%)</td></tr></table>`;
  renderLive();
}
function renderLive() {
  if (!$('lv1')) return; const t = state.t, qi = inpIdx(t), zk = hzK(t), rk = recIdx(t), ci = lastCell;
  if (ci == null || ci < 0) { $('lv1').innerHTML = $('lv2').innerHTML = `<span class="note">${tr('지도 위 셀에 커서를 올리세요.', 'Hover a cell on the map.')}</span>`; }
  else {
    const q = qi >= 0 ? QF[qi][ci] : null, Bi = burnedAt(ci, rk) ? 1 : 0, lam = q != null && q < 1 ? -Math.log(1 - q) : null;
    $('lv1').innerHTML = `${tr('셀', 'Cell')} r${(ci / NC) | 0} c${ci % NC}: B<sub>i</sub> = <b>${Bi}</b> · q<sub>i</sub> = <b>${q != null ? (q * 100).toFixed(2) + '%' : '–'}</b>${lam != null && !Bi ? ` · λ<sub>i</sub> = −ln(1−q) = <b>${lam.toFixed(4)}</b> h⁻¹` : ''} <span class="note">(${qi >= 0 ? fmt(INP[qi]) + tr(' 입력', ' input') : tr('입력 없음', 'no input')})</span>`;
    $('lv2').innerHTML = zk >= 0 ? `+${((t - HZ[zk].t0) * 60).toFixed(1)}${tr('분', ' min')} F(x): ${[0, 1, 2, 3].map(m => `<span style="color:${MEMBER_CSS[m]}">S${m + 1}</span> <b>${sci(hzFlux(zk, m, ci, (t - HZ[zk].t0) * 3600), 4)}</b>`).join(' · ')} kW/m²${[0, 1, 2, 3].some(m => hzFlame(zk, m, ci, (t - HZ[zk].t0) * 3600)) ? ` · <b style="color:#d9472b">${tr('화염 접촉', 'flame contact')}</b>` : ''}` : `<span class="note">${tr('열유속은 모델 입력 시각부터 1시간만 있습니다 (1시간 상세).', 'Heat flux exists for 1 h after each model input (1-hour detail).')}</span>`;
  }
  const sc = CASES[selRoute];
  if (sc && sc.pol.full && sc.pol.full.exp) { const p = sc.pol.full, s = (t - sc.r.t0) * 3600, cur = p.exp.map(m => { let v = m.series[0][1]; for (const [ts, d] of m.series) if (ts <= s) v = d; return v; });
    $('lv3').innerHTML = `${sc.r.label}: ${zk === sc.k && s >= p.dep ? `+${(s / 60).toFixed(1)}${tr('분 누적', ' min dose')} ${cur.map((v, m) => `<span style="color:${MEMBER_CSS[m]}">S${m + 1}</span> <b>${sci(v, 4)}</b>`).join(' · ')} / ${fmtLim(p.limits.dose_kj_m2)} kJ/m²` : `${tr('기록: 최대', 'Recorded: max')} ${sci(Math.max(...p.exposure.map(e => e.dose)), 3)} kJ/m² ≤ ${fmtLim(p.limits.dose_kj_m2)} · ${tr('접촉', 'contact')} ${p.exposure.filter(e => e.contact).length}/4`} · ${tr('도착', 'arrival')} +${fmtS(p.arr)} = L ${p.arr === p.L ? '✓' : ''}`; }
  else if (sc) $('lv3').innerHTML = `${sc.r.label}: ${VERDICT.model_no_route.t} · ${tr('이동시간만 경로의 화염 셀 통과', 'travel-only route flame-cell points')} ${sc.travelHits.length}`;
}

// ---------------- time & playback ----------------
function setTime(t) { state.t = clamp(t, rangeLo(), state.detail ? rangeHi() - 1e-4 : rangeHi()); dirty = true; }
function setPlaying(p, speed) { state.playing = p; if (speed) { state.speed = speed; $('speed').value = String(speed); }
  $('playIc').innerHTML = p ? '<path d="M4 2.5h3v11H4zM9 2.5h3v11H9z" fill="currentColor"/>' : '<path d="M4 2.5v11l9-5.5z" fill="currentColor"/>'; $('play').setAttribute('aria-label', p ? tr('일시정지', 'Pause') : tr('재생', 'Play')); }
$('play').onclick = () => { if (!state.playing && state.t >= rangeHi() - .01) setTime(rangeLo()); setPlaying(!state.playing); };
$('back').onclick = () => setTime(state.detail ? state.t - 5 / 60 : Math.ceil(state.t - 1.001));
$('fwd').onclick = () => setTime(state.detail ? state.t + 5 / 60 : Math.floor(state.t + 1.001));
// back to the start: the navigation replay restarts; otherwise the first moment of the timeline (or of the 1-hour detail)
$('reset').onclick = () => { setPlaying(false); if (NAV.on) return navRoute(NAV.pol); setTime(rangeLo()); };
$('detailBtn').onclick = () => setDetail(!state.detail);
$('speed').onchange = e => { state.speed = +e.target.value; };
addEventListener('keydown', e => { if (e.target.closest('input,select,textarea')) return; if (e.code === 'Space') { e.preventDefault(); $('play').click(); } });
let prevRec = null, prevBooth = null;
function updateTimeUI() {
  const t = state.t, k = recIdx(t), qi = inpIdx(t), pct = pctOf(t);
  $('tFill').style.width = pct + '%'; $('tKnob').style.left = pct + '%'; $('tBub').style.left = pct + '%'; $('tBub').style.transform = `translateX(${pct > 80 ? -100 : pct < 20 ? 0 : -50}%)`;   /* stays inside the track at the ends */ $('tBub').textContent = state.detail ? `${fmt(t)} · +${((t - rangeLo()) * 60).toFixed(1)}${tr('분', ' min')}` : fmt(t);
  track.setAttribute('aria-valuenow', t.toFixed(1)); track.setAttribute('aria-valuetext', fmt(t) + ' KST');
  const qAge = qi >= 0 ? t - INP[qi] : null;
  $('firechip').innerHTML = `<b>${tr('화재 입력 · 기록 (재구성)', 'Fire input · recorded (reconstructed)')}</b> ${B.event}<br><span>${tr('연소 기록', 'Burn record')} ${k >= 0 ? fmt(REC[k]) : tr('없음', 'none')} · q ${qi >= 0 ? (qAge <= 1 ? `${fmt(INP[qi])} ${tr('입력 (유효)', 'input (valid)')}` : `${fmt(INP[qi])} ${tr('입력 · 유효 시간 지남', 'input · expired')}`) : tr('없음', 'none')}</span>`;
  EVENTS.forEach(ev => { ev.btn.classList.toggle('past', ev.t < t - 1.5); ev.btn.classList.toggle('now', Math.abs(ev.t - t) < .75 || (ev.route && ev.route.tArr != null && t >= ev.route.tDep && t <= ev.route.tArr)); });
  const ov = $('ovArea'); if (ov) { ov.textContent = k >= 0 ? `${B.footprints[k].area_km2.toFixed(1)} km² (${fmt(REC[k])} ${tr('기록', 'record')})` : '–'; $('ovActive').textContent = tr(`${activeCells.length.toLocaleString()}셀 (불꽃 표시)`, `${activeCells.length.toLocaleString()} cells (flames shown)`); }
  const sun = sunPos(t), { dir, spd } = windBase(t);
  $('envTime').textContent = fmt(t) + ' KST';
  $('wxWind').textContent = `${spd.toFixed(1)} m/s`; $('wxDir').textContent = tr(`${aspName(dir)}풍 (${Math.round(dir)}°)`, `from ${aspName(dir)} (${Math.round(dir)}°)`);
  $('wxTemp').textContent = `${tempAt(t, K300, sun).toFixed(1)} °C`;
  $('wxSun').textContent = `${sun.el.toFixed(0)}°`; $('wxSunTxt').textContent = sun.el > 6 ? tr('낮', 'day') : sun.el > -6 ? tr('박명', 'twilight') : tr('밤', 'night');
  if (k !== prevRec) { colorTrees(prevRec, t); placeTrees(); prevRec = k; }
  const bk = boothAt(t); if (bk !== prevBooth) { prevBooth = bk; updateBooth(true); renderEvac(); }
  drawCharts(); renderLive();
  if (state.detail && $('rtDose') && !$('pRoute').hidden) { const sc = CASES[selRoute]; if (sc && sc.pol.full.exp) drawDose($('rtDose'), sc, (t - sc.r.t0) * 3600, true); }
}

// ---------------- view mode (2D / 3D) ----------------
let tween = null;
function sph(pos, tgt) { const o = pos.clone().sub(tgt); const r = o.length(); return { r, phi: Math.acos(clamp(o.y / r, -1, 1)), th: Math.atan2(o.x, o.z) }; }
function tweenView(to, ms = 900) {
  const from = { ...sph(camera.position, controls.target), tgt: controls.target.clone() };
  let dth = to.th - from.th; while (dth > Math.PI) dth -= 2 * Math.PI; while (dth < -Math.PI) dth += 2 * Math.PI;
  tween = { t0: performance.now(), ms, from, to: { ...to, th: from.th + dth } };
}
function stepTween(now) {
  if (!tween) return; const f = clamp((now - tween.t0) / tween.ms, 0, 1), e = f < .5 ? 2 * f * f : 1 - Math.pow(-2 * f + 2, 2) / 2, A = tween.from, Bt = tween.to;
  const r = A.r + (Bt.r - A.r) * e, phi = A.phi + (Bt.phi - A.phi) * e, th = A.th + (Bt.th - A.th) * e;
  controls.target.lerpVectors(A.tgt, Bt.tgt, e);
  camera.position.set(controls.target.x + r * Math.sin(phi) * Math.sin(th), controls.target.y + r * Math.cos(phi), controls.target.z + r * Math.sin(phi) * Math.cos(th));
  if (f >= 1) tween = null;
}
function setMode(m) {
  state.mode = m; const flat = m === '2d';
  for (const [a, b] of [['m2d', 'm3d'], ['v2d', 'v3d']]) { $(a).setAttribute('aria-pressed', String(flat)); $(b).setAttribute('aria-pressed', String(!flat)); }
  $('baseGrp').hidden = !flat; mapEl.classList.toggle('flat', flat);
  flatTarget = flat ? 1 : 0;
  terrain.material = flat ? matFlat : matReal; if (ctxMesh) ctxMesh.material = flat && ctxFlat() || ctxMatReal; skyDome.visible = !flat;
  conifers.visible = broadleaf.visible = !flat && L.canopy.on; smoke.visible = !flat;
  windMat.blending = flat ? THREE.SubtractiveBlending : THREE.AdditiveBlending; windMat.needsUpdate = true;
  controls.enableRotate = !flat;
  controls.mouseButtons = flat ? { LEFT: THREE.MOUSE.PAN, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN } : { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN };
  controls.touches = flat ? { ONE: THREE.TOUCH.PAN, TWO: THREE.TOUCH.DOLLY_PAN } : { ONE: THREE.TOUCH.ROTATE, TWO: THREE.TOUCH.DOLLY_PAN };
  tweenView(flat ? { r: 36, phi: .0005, th: 0, tgt: new THREE.Vector3(0, 0, 0) } : HOME3D());
  dirty = true;
}
const HOME3D = () => ({ r: matchMedia('(max-width: 860px)').matches ? 40 : 33, phi: THREE.MathUtils.degToRad(62), th: THREE.MathUtils.degToRad(-16), tgt: new THREE.Vector3(1, .4, .2) });
function flyTo(r) {
  if (state.mode === '2d') return;
  const sc = CASES[r.idx], dense = r.has ? r.dense : sc && sc.pol.travel_only && sc.pol.travel_only.dense.length > 1 ? sc.pol.travel_only.dense : null;
  if (!dense) { if (r.o) { const u = uOf(r.o[0]), v = vOf(r.o[1]); tweenView({ r: 10, phi: THREE.MathUtils.degToRad(50), th: sph(camera.position, controls.target).th, tgt: new THREE.Vector3(sxU(u), elevUV(u, v) * yScale(), szV(v)) }, 1100); } return; }
  const mid = dense[Math.floor(dense.length / 2)], len = dense[dense.length - 1].d;
  tweenView({ r: Math.max(9, len * SF * .9), phi: THREE.MathUtils.degToRad(50), th: sph(camera.position, controls.target).th, tgt: new THREE.Vector3(sxU(mid.u), mid.e * yScale(), szV(mid.v)) }, 1100);
}
$('m2d').onclick = $('v2d').onclick = () => setMode('2d');
$('m3d').onclick = $('v3d').onclick = () => setMode('3d');
function setBase(b) { state.base2d = b; for (const [id, v] of [['bTopo', 'topo'], ['bReal', 'real'], ['bRoad', 'road']]) $(id).setAttribute('aria-pressed', String(b === v)); dirty = true; }
$('bTopo').onclick = () => setBase('topo'); $('bReal').onclick = () => setBase('real'); $('bRoad').onclick = () => setBase('road');
$('fs').onclick = () => { if (document.fullscreenElement) document.exitFullscreen(); else mapEl.requestFullscreen?.(); };
$('compass').onclick = () => { const s = sph(camera.position, controls.target); tweenView({ r: s.r, phi: s.phi, th: 0, tgt: controls.target.clone() }, 600); };
document.querySelectorAll('.tabs button').forEach(b => b.onclick = () => showTab(b.dataset.p));

// ---------------- hover readout ----------------
const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
function pick(cx, cy) {
  const rc = renderer.domElement.getBoundingClientRect(); ndc.set((cx - rc.left) / rc.width * 2 - 1, -(cy - rc.top) / rc.height * 2 + 1); ray.setFromCamera(ndc, camera);
  const o = ray.ray.origin, d = ray.ray.direction; let tt = 0, prev = null;
  for (let n = 0; n < 900; n++) {
    const x = o.x + d.x * tt, y = o.y + d.y * tt, z = o.z + d.z * tt, u = x / KX + .5, v = z / KY + .5;
    const inside = u >= 0 && u <= 1 && v >= 0 && v <= 1, g = inside ? yAt(u, v) : -1e9;
    if (inside && y <= g) { if (prev == null) return { u, v }; let a = prev, b = tt; for (let j = 0; j < 12; j++) { const m = (a + b) / 2, uu = (o.x + d.x * m) / KX + .5, vv = (o.z + d.z * m) / KY + .5; (o.y + d.y * m <= yAt(uu, vv)) ? b = m : a = m; } return { u: (o.x + d.x * b) / KX + .5, v: (o.z + d.z * b) / KY + .5 }; }
    if (y < -1 && d.y < 0) return null;
    prev = tt; tt += inside ? Math.max(.015, (y - g) * .5) : .25;
  }
  return null;
}
const dms = (x, pos, neg) => { const s = x < 0 ? neg : pos; x = Math.abs(x); const d = Math.floor(x), m = (x - d) * 60; return `${d}°${m.toFixed(2)}′${s}`; };
let hoverQueued = null;
function hover(e) {
  const p = pick(e.clientX, e.clientY), tip = $('tip');
  if (!p) { tip.style.display = 'none'; return; }
  const lon = W + p.u * (E - W), lat = N - p.v * (N - S), k = gIdx(p.u, p.v), el = elevUV(p.u, p.v), t = state.t, rk = recIdx(t), qi = inpIdx(t);
  const ci = cellOf(lon, lat), sun = sunPos(t), [wu, wv] = windAt(p.u, p.v), ws = Math.hypot(wu, wv), wdir = (Math.atan2(-wu, -wv) * 180 / Math.PI + 360) % 360;
  let burn = tr('격자 밖', 'outside the grid'), bc = '#8b8478';
  if (ci >= 0) { if (!valid[ci]) { burn = tr('모델 무효 셀', 'invalid model cell'); } else if (burnedAt(ci, rk)) { burn = tr(`연소 기록 (${fmt(REC[first[ci]])} 기록부터)`, `burned (since the ${fmt(REC[first[ci]])} record)`); bc = '#2e2824'; } else { burn = tr('미연소 (현재 기록 기준)', 'unburned (current record)'); bc = '#2f8a57'; } if (qi >= 0 && BURNING[qi].has(ci)) { burn = tr(`활성 셀 (${fmt(INP[qi])} 모델 입력)`, `active cell (${fmt(INP[qi])} model input)`); bc = '#ff6a1f'; } }
  const qv = ci >= 0 && qi >= 0 ? QF[qi][ci] : null; lastCell = ci; renderLive();
  const zk = hzK(t); let hzTxt = '';
  if (zk >= 0 && ci >= 0) { const s = (t - HZ[zk].t0) * 3600; hzTxt = `F(x) ${[0, 1, 2, 3].map(m => sci(hzFlux(zk, m, ci, s), 4)).join(' / ')} kW/m² (S1–S4)${[0, 1, 2, 3].some(m => hzFlame(zk, m, ci, s)) ? tr(' · 화염 접촉', ' · flame contact') : ''}`; }
  const hk = hourIdx(t); let mcTxt = '';
  if (HR && hk >= 0 && ci >= 0 && HV[hk][ci]) { const hs = hourStep(t, hk), F = Fh(hk, ci, hs), se = SEh(hk, ci, hs);
    mcTxt = `F(${hs}h) ${(F * 100).toFixed(1)}% ± ${(1.96 * se * 100).toFixed(1)}%p · ${tr('50% 도달', '50% reached')} ${A50[hk][ci] < 255 ? A50[hk][ci] + tr('시간', ' h') : tr(`${HH}시간 내 없음`, `not within ${HH} h`)}`; }
  tip.innerHTML = `<b>${Math.round(el).toLocaleString()} m</b> · ${tr('경사', 'slope')} ${SL[k].toFixed(0)}° · ${tr(`${aspName(AS[k])}향 사면`, `${aspName(AS[k])}-facing`)}<br>
    <span class="dot" style="background:${bc}"></span>${burn}<br>
    ${qv != null ? `q ${(qv * 100).toFixed(qv < .01 ? 2 : 1)}% · ${fmt(INP[qi])} ${tr('입력', 'input')}${t - INP[qi] > 1 ? tr(' (지남)', ' (expired)') : ''}<br>` : ''}
    ${mcTxt ? mcTxt + '<br>' : ''}${hzTxt ? hzTxt + '<br>' : ''}
    <span class="d">${tr('기온', 'temp')} ${tempAt(t, k, sun).toFixed(1)}°C ✱ · ${tr('바람', 'wind')} ${tr(`${aspName(wdir)}풍`, aspName(wdir))} ${ws.toFixed(1)} m/s ✱</span><br>
    <span class="d">${dms(lat, 'N', 'S')} ${dms(lon, 'E', 'W')}</span>`;
  const rc = mapEl.getBoundingClientRect(); let x = e.clientX - rc.left + 14, y = e.clientY - rc.top + 14;
  tip.style.display = 'block'; if (x + tip.offsetWidth > rc.width - 8) x -= tip.offsetWidth + 28; if (y + tip.offsetHeight > rc.height - 8) y -= tip.offsetHeight + 28;
  tip.style.left = x + 'px'; tip.style.top = y + 'px';
  $('cursorKv').innerHTML = `<dt>${tr('고도', 'Elevation')}</dt><dd>${Math.round(el)} m</dd><dt>${tr('경사 · 사면', 'Slope · aspect')}</dt><dd>${SL[k].toFixed(1)}° · ${aspName(AS[k])}</dd><dt>${tr('연소 상태', 'Burn state')}</dt><dd>${burn}</dd><dt>${tr('q (다음 1시간)', 'q (next hour)')}</dt><dd>${qv != null ? (qv * 100).toFixed(2) + '%' : '–'}</dd><dt>${tr('셀', 'Cell')}</dt><dd>${ci >= 0 ? `r${(ci / NC) | 0} c${ci % NC}` : '–'}</dd><dt>${tr('좌표', 'Coords')}</dt><dd>${lat.toFixed(4)}, ${lon.toFixed(4)}</dd>`;
}
renderer.domElement.addEventListener('pointermove', e => { if (e.buttons) { $('tip').style.display = 'none'; return; } hoverQueued = e; });
renderer.domElement.addEventListener('pointerleave', () => { hoverQueued = null; $('tip').style.display = 'none'; });

// ---------------- region menu ----------------
function buildRegionMenu() {
  $('regName').textContent = `${REG_NAME(B)} ${B.year}`; $('regEvent').textContent = B.event; $('regLoc').textContent = EN ? B.loc_en : B.loc_ko;
  document.title = tr(`${B.name.ko} 산불 레이어 지도`, `${B.name.en} wildfire layer map`);
  const m = $('regMenu');
  m.innerHTML = `<div class="rm-h">${tr('연구 지역 5곳', 'Five study regions')}</div>` + RIDX.map(r => `<button type="button" role="menuitem" data-reg="${r.id}" class="${r.id === RID ? 'here' : ''}">
    <b>${REG_NAME(r)} ${r.year}</b><span>${r.event} · ${r.km[0].toFixed(0)}×${r.km[1].toFixed(0)} km · ${tr(`출발지 ${r.origins}`, `${r.origins} origins`)}${r.booth ? ` · <em>${tr('대피 현황', 'evac status')}</em>` : ''}</span>
    <small>${tr(`이동시간만 경로 화염 접촉 ${r.rq3.filter(q => q.travel_fails_full).length}/${r.rq3.length}`, `travel-only flame contact ${r.rq3.filter(q => q.travel_fails_full).length}/${r.rq3.length}`)}</small></button>`).join('');
  $('regBtn').onclick = e => { e.stopPropagation(); const open = m.hidden; m.hidden = !open; $('regBtn').setAttribute('aria-expanded', String(open)); };
  m.querySelectorAll('[data-reg]').forEach(b => b.onclick = () => { if (b.dataset.reg !== RID) switchRegion(b.dataset.reg); else m.hidden = true; });
  document.addEventListener('click', e => { if (!e.target.closest('.regwrap')) { m.hidden = true; $('regBtn').setAttribute('aria-expanded', 'false'); } });
  $('lKo').setAttribute('aria-pressed', String(!EN)); $('lEn').setAttribute('aria-pressed', String(EN));
  $('lKo').onclick = () => EN && switchLang('ko'); $('lEn').onclick = () => !EN && switchLang('en');
}
function viewHash(extra = {}) {
  const hp = new URLSearchParams(); hp.set('region', extra.region || RID); hp.set('lang', extra.lang || (EN ? 'en' : 'ko'));
  if (state.mode === '2d') hp.set('mode', '2d');
  if (LITE) hp.set('lite', '1');
  const tab = extra.tab || [...document.querySelectorAll('.tabs button')].find(b => b.getAttribute('aria-selected') === 'true')?.dataset.p; if (tab && tab !== 'pLayers') hp.set('tab', tab);
  for (const k of ['caseid', 'cmp']) if (extra[k]) hp.set(k, extra[k]);
  if (extra.keepTime) hp.set('t', state.t.toFixed(3));
  return hp.toString();
}
function switchRegion(id, extra = {}) { try { localStorage.setItem('wfg3d.region', id); } catch (e) { } location.hash = viewHash({ ...extra, region: id }); location.reload(); }
function switchLang(l) { try { localStorage.setItem('wfg3d.lang', l); } catch (e) { } location.hash = viewHash({ lang: l, keepTime: true, cmp: state.cmp !== 'ours' ? state.cmp : '' }); location.reload(); }

// ---------------- satellite close-up (online only) ----------------
// Zoomed in with an internet connection: Esri World Imagery photos (zoom 16, about 2.4 m per pixel) of a 4 km square
// around the view centre, laid on the terrain with the map's own layers (fire, spread, routes) drawn over them. The
// photos were taken on another day. Without internet (navNet in nav.js) nothing is requested.
const SAT_Z = 16, SAT_R = 2, SAT_N = 2048;
const sat = { mesh: null, photo: null, out: null, key: '', gen: -1, t: 0, want: null };
function satTick(kmPerPx) {
  const on = L.base.on && kmPerPx < .006 && !(NAV.real || NAV.street) && NAV.netOk !== false;
  if (sat.mesh) sat.mesh.visible = on && sat.ready;
  const rop = sat.mesh?.visible ? .4 : 1; for (const m of detailGroup.userData.roads || []) m.material.opacity = rop;     // over the photo the roads are already visible: lighter lines
  if (!on) return;
  if (NAV.netOk == null) { navNet(); return; }
  const tu = controls.target.x / KX + .5, tv = controls.target.z / KY + .5;
  if (sat.cu == null || Math.hypot((tu - sat.cu) * KXr, (tv - sat.cv) * KYr) > SAT_R * .45) {     // moved far: new square once the view rests
    clearTimeout(sat.t); sat.want = [tu, tv]; sat.t = setTimeout(() => satBuild(...sat.want), 600); }
  else if (sat.ready && sat.gen !== layerGen) satPaint();
}
function satBuild(cu, cvv) {
  sat.cu = cu; sat.cv = cvv; sat.ready = false; const du = SAT_R / KXr, dv = SAT_R / KYr, u0 = cu - du, u1 = cu + du, v0 = cvv - dv, v1 = cvv + dv; sat.box = [u0, u1, v0, v1];
  sat.photo ??= mk(SAT_N, SAT_N); sat.out ??= mk(SAT_N, SAT_N); const px = sat.photo.getContext('2d'); px.fillStyle = '#6f7a5e'; px.fillRect(0, 0, SAT_N, SAT_N);
  const lonOf = u => W + u * (E - W), latOf = v => N - v * (N - S), n = 2 ** SAT_Z;
  const tx = lon => Math.floor((lon + 180) / 360 * n), ty = lat => Math.floor((1 - Math.log(Math.tan(lat * Math.PI / 180) + 1 / Math.cos(lat * Math.PI / 180)) / Math.PI) / 2 * n);
  const lonT = x => x / n * 360 - 180, latT = y => Math.atan(Math.sinh(Math.PI * (1 - 2 * y / n))) * 180 / Math.PI;
  const X = u => (u - u0) / (u1 - u0) * SAT_N, Y = v => (v - v0) / (v1 - v0) * SAT_N, key = sat.key = u0.toFixed(5) + ':' + v0.toFixed(5);
  let left = 0;
  for (let x = tx(lonOf(u0)); x <= tx(lonOf(u1)); x++) for (let y = ty(latOf(v0)); y <= ty(latOf(v1)); y++) { left++;
    const im = new Image(); im.crossOrigin = 'anonymous';
    im.onload = () => { if (sat.key !== key) return; const a = X(uOf(lonT(x))), b = Y(vOf(latT(y))), c = X(uOf(lonT(x + 1))), d = Y(vOf(latT(y + 1))); px.drawImage(im, a, b, c - a + .6, d - b + .6); if (--left === 0) satDone(); else if (left % 12 === 0) satPaint(); };
    im.onerror = () => { if (sat.key === key && --left === 0) satDone(); };
    im.src = NAV_TILES.sat.replace('{z}', SAT_Z).replace('{x}', x).replace('{y}', y); }
  // the ground piece the photos lie on: a 128 × 128 grid following the terrain
  const G = 128, pos = [], uvs = [], idx = [];
  for (let j = 0; j <= G; j++) for (let i = 0; i <= G; i++) { const u = u0 + (u1 - u0) * i / G, v = v0 + (v1 - v0) * j / G;
    pos.push(sxU(u), elevUV(clamp(u, 0, 1), clamp(v, 0, 1)) / 1000 + .0008, szV(v)); uvs.push(i / G, 1 - j / G);
    if (i < G && j < G) { const k = j * (G + 1) + i; idx.push(k, k + G + 1, k + 1, k + 1, k + G + 1, k + G + 2); } }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2)); g.setIndex(idx); g.computeVertexNormals();
  if (!sat.mesh) { const tx_ = new THREE.CanvasTexture(sat.out); tx_.encoding = THREE.sRGBEncoding; tx_.anisotropy = renderer.capabilities.getMaxAnisotropy();
    sat.mesh = new THREE.Mesh(g, new THREE.MeshStandardMaterial({ map: tx_, transparent: true, roughness: 1, metalness: 0, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }));
    sat.mesh.renderOrder = 2; sat.mesh.receiveShadow = true; detailGroup.add(sat.mesh); }
  else { sat.mesh.geometry.dispose(); sat.mesh.geometry = g; }
  setTimeout(() => { if (sat.key === key && !sat.ready) satDone(); }, 8000);
}
function satDone() { sat.ready = true; satPaint(); dirty = true; }
// photo + the map's layer sheet for the same square, edges faded into the map
function satPaint() {
  if (!sat.out || !layerCv) return; const o = sat.out.getContext('2d'), [u0, u1, v0, v1] = sat.box;
  o.globalCompositeOperation = 'source-over'; o.globalAlpha = 1; o.clearRect(0, 0, SAT_N, SAT_N); o.drawImage(sat.photo, 0, 0);
  o.imageSmoothingEnabled = true; o.drawImage(layerCv, u0 * TW, v0 * TH, (u1 - u0) * TW, (v1 - v0) * TH, 0, 0, SAT_N, SAT_N);
  const fade = o.createRadialGradient(SAT_N / 2, SAT_N / 2, SAT_N * .36, SAT_N / 2, SAT_N / 2, SAT_N * .5); fade.addColorStop(0, 'rgba(0,0,0,1)'); fade.addColorStop(1, 'rgba(0,0,0,0)');
  o.globalCompositeOperation = 'destination-in'; o.fillStyle = fade; o.fillRect(0, 0, SAT_N, SAT_N); o.globalCompositeOperation = 'source-over';
  sat.gen = layerGen; if (sat.mesh) sat.mesh.material.map.needsUpdate = true; dirty = true;
}

// ---------------- resize / loop ----------------
let composer = null, bloom = null;
if (!isPhone && THREE.EffectComposer && THREE.UnrealBloomPass && THREE.GammaCorrectionShader) {
  composer = new THREE.EffectComposer(renderer); composer.addPass(new THREE.RenderPass(scene, camera));
  bloom = new THREE.UnrealBloomPass(new THREE.Vector2(512, 512), .5, .55, .86); composer.addPass(bloom);
  composer.addPass(new THREE.ShaderPass(THREE.GammaCorrectionShader));
}
function resize() {
  const w = mapEl.clientWidth, h = mapEl.clientHeight; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
  if (composer) { composer.setPixelRatio(renderer.getPixelRatio()); composer.setSize(w, h); }
  const sc = h * renderer.getPixelRatio() / (2 * Math.tan(camera.fov * Math.PI / 360)); flameMat.uniforms.scale.value = smokeMat.uniforms.scale.value = sc;
  drawCharts();
}
new ResizeObserver(resize).observe(mapEl);
const sky = { day: new THREE.Color(0xd5dde1), dusk: new THREE.Color(0xe2ae84), night: new THREE.Color(0x1d2433) };
const skyTop = { day: new THREE.Color(0x5d8fc6), dusk: new THREE.Color(0x56688f), night: new THREE.Color(0x070b18) };
const _sc = new THREE.Color();
let last = performance.now(), hoverT = 0, uiT = 0;
function frame(now) {
  const dt = Math.min(.05, (now - last) / 1000); last = now;
  if (state.playing) { state.t += dt * state.speed * (state.detail ? 1 / 60 : 1 / 1.4); const hi = state.detail ? rangeHi() - 1e-4 : TMAX; if (state.t >= hi) { state.t = hi; setPlaying(false); } dirty = true; }
  if (Math.abs(flatF - flatTarget) > 1e-3) { flatF += (flatTarget - flatF) * Math.min(1, dt * 7); if (Math.abs(flatF - flatTarget) < 2e-3) flatF = flatTarget; applyHeights(); }
  const t = state.t;
  const key = [recIdx(t), inpIdx(t), t - INP[Math.max(0, inpIdx(t))] <= 1, Math.round(t * 2), Math.ceil(t - 1e-6), hzSig(t), state.mode, state.base2d, NAV.on, ...LAYERS.map(l => (l.on ? 1 : 0) + ':' + l.op)].join('|');
  if (key !== lastKey) { lastKey = key; if (!NAV.real) compose(); updateTimeUI(); }     // the real 3D map (nav.js) hides the scene
  else if (dirty && (now - uiT > 90 || !state.playing)) { updateTimeUI(); uiT = now; }
  dirty = false;
  const sun = sunPos(t), el = sun.el * Math.PI / 180, az = sun.az * Math.PI / 180;
  const day = smooth(-4, 14, sun.el), dusk = Math.exp(-Math.pow(sun.el / 7, 2));
  sunL.position.set(Math.sin(az) * Math.cos(el) * 110, Math.max(.05, Math.sin(el)) * 110 + 4, -Math.cos(az) * Math.cos(el) * 110);
  sunL.intensity = .5 + 1.35 * day;     // at night a cool moonlight keeps the terrain readable
  sunL.color.setRGB(.72 + .28 * day, .8 + (.02 + .16 * (1 - dusk)) * day, .95 + (-.33 + .3 * (1 - dusk)) * day);
  hemi.intensity = .38 + .12 * day; hemi.color.setRGB(.62 + .35 * day, .68 + .3 * day, .9 + .08 * day);
  _sc.copy(sky.night).lerp(sky.day, day).lerp(sky.dusk, dusk * .55 * (day > .05 ? 1 : .4));
  renderer.setClearColor(_sc);
  skyMat.uniforms.horizon.value.copy(_sc); skyMat.uniforms.top.value.copy(skyTop.night).lerp(skyTop.day, day).lerp(skyTop.dusk, dusk * .35 * (day > .05 ? 1 : .3));
  skyMat.uniforms.sunDir.value.set(Math.sin(az) * Math.cos(el), Math.sin(el), -Math.cos(az) * Math.cos(el)); skyMat.uniforms.sunAmt.value = smooth(-3, 3, sun.el);
  skyMat.uniforms.sunCol.value.setRGB(1, .78 + .2 * (1 - dusk), .5 + .4 * (1 - dusk)); skyDome.position.copy(camera.position);
  scene.fog.color.copy(_sc).convertSRGBToLinear(); scene.fog.near = state.mode === '2d' ? 900 : 30; scene.fog.far = state.mode === '2d' ? 1000 : 150;
  matReal.emissiveIntensity = .55 + 1.2 * (1 - day);
  const night = 1 - day; flameMat.uniforms.night.value = smokeMat.uniforms.night.value = night;
  if (Math.abs(windT - t) > .05) updateWind(t);
  const [mu, mv] = windAt(.5, .5); flameMat.uniforms.wind.value.set(mu * .03, -mv * .03); smokeMat.uniforms.wind.value.copy(flameMat.uniforms.wind.value);
  const tm = reduceMotion ? 0 : now / 1000; flameMat.uniforms.time.value = smokeMat.uniforms.time.value = tm;
  flameMat.uniforms.op.value = smokeMat.uniforms.op.value = L.front.op / 100;
  if (windLines.visible) stepWind(reduceMotion ? 0 : dt);
  stepTween(now); controls.update();
  updateCars(t); try { navFrame(t); } catch (e) { console.error(e); }     // a navigation error must not stop the viewer
  const useBloom = composer && state.mode === '3d' && flatF < .01;
  skyMat.uniforms.linOut.value = flameMat.uniforms.linOut.value = smokeMat.uniforms.linOut.value = useBloom ? 1 : 0;
  if (NAV.real || NAV.street) { /* the real map or road view covers the scene (nav.js) */ } else if (useBloom) { bloom.strength = .32 + .55 * night; composer.render(); } else renderer.render(scene, camera);
  placeDom();
  $('needle').style.transform = `rotate(${(sph(camera.position, controls.target).th * 180 / Math.PI).toFixed(1)}deg)`;
  const dist = camera.position.distanceTo(controls.target), kmPerPx = 2 * dist * Math.tan(camera.fov * Math.PI / 360) / mapEl.clientHeight / SF;
  detailGroup.visible = L.base.on && kmPerPx < .012 && !(NAV.real || NAV.street);     // close-up roads and buildings below ~12 m per pixel
  satTick(kmPerPx);
  const nice = [.1, .25, .5, 1, 2, 5, 10].find(v => v / kmPerPx >= 60) || 10; $('scaleBar').style.width = (nice / kmPerPx).toFixed(0) + 'px'; $('scaleTxt').textContent = (nice < 1 ? nice * 1000 + ' m' : nice + ' km') + (state.mode === '3d' ? tr(' (화면 중심)', ' (at centre)') : '');
  if (hoverQueued && now - hoverT > 70) { hover(hoverQueued); hoverQueued = null; hoverT = now; }
  requestAnimationFrame(frame);
}

// ---------------- boot ----------------
async function boot() {
  const hit = await loadTextures();
  const hp0 = new URLSearchParams(location.hash.slice(1));
  // drawing the terrain here, or the 2D maps, uses the OSM vectors; without them the terrain is drawn plain and not stored
  const osmOk = (!hit || hp0.get('mode') === '2d') ? await needOsm() : true;
  if (!hit && !osmOk) B.osm = { roads: [], water: [], landuse: [] };
  buildStatic(hit); buildTerrain(); buildEmber(); buildTrees(); skirt.visible = false; conifers.visible = broadleaf.visible = L.canopy.on;     // 3D trees follow the canopy layer (off at first) buildDom();
  // the surrounding terrain ring is added when its heights arrive (they load while this first frame is built)
  const ctxDone = (window.__wfgCtx || Promise.resolve(null)).then(b64 => {
    if (!b64) return; attachContext(b64); buildContext(hit); ctxMesh.scale.y = yScale() * 1000;
    if (state.mode === '2d') ctxMesh.material = ctxFlat() || ctxMatReal;
    dirty = true; if (!hit && osmOk) setTimeout(saveTextures, 800);
  });
  await ctxDone;
  for (const b of BOOTH) for (const r of b.rows) if (r.research && r.lon != null && !RESEARCH_DOM.some(x => x.rid === r.id)) { const it = addDom('mk research', '', uOf(r.lon), vOf(r.lat), { layer: 'booth', lift: .03 }); it.rid = r.id; it.rname = r.name; it.el.title = tr('연구 사례 출발지 ', 'Research origin ') + caseIdLabel(r.name); RESEARCH_DOM.push(it); }
  navInit(); buildRegionMenu(); buildLayerPanel(); buildOverview(); buildTrack(); buildEvents(); buildDocs(); renderCompare();
  // close-up roads and buildings: loaded after the first picture, built once
  setTimeout(() => window.__wfgLoad(RID + '.detail.js').then(ok => { const D = ok && (window.WFG_DETAIL || {})[RID]; if (D) { buildDetail(D); dirty = true; } }), 1500);
  buildHeatMesh(); buildModelTab(); selectRoute(selRoute); applyHeights(); updateWind(state.t);
  const h = HOME3D(); controls.target.copy(h.tgt); camera.position.set(h.tgt.x + h.r * Math.sin(h.phi) * Math.sin(h.th), h.tgt.y + h.r * Math.cos(h.phi), h.tgt.z + h.r * Math.sin(h.phi) * Math.cos(h.th));
  const hp = new URLSearchParams(location.hash.slice(1));
  if (hp.has('t')) state.t = clamp(+hp.get('t') || 0, 0, TMAX);
  for (const id of (hp.get('on') || '').split(',').filter(Boolean)) setLayer(id, true);
  for (const id of (hp.get('off') || '').split(',').filter(Boolean)) setLayer(id, false);
  if (hp.get('mode') === '2d') setMode('2d');
  if (hp.get('base') === 'real') $('bReal').click();
  if (hp.has('caseid')) { const i = CASES.findIndex(c => c.r.case === hp.get('caseid')); if (i >= 0) hp.set('case', i); }
  if (hp.has('case')) openCase(clamp(+hp.get('case') || 0, 0, CASES.length - 1));
  if (hp.has('cmp') && CMP[hp.get('cmp')]) setCompare(hp.get('cmp'));
  if (hp.has('dt')) { setDetail(true, hzK(state.t) >= 0 ? hzK(state.t) : null); setTime(rangeLo() + (+hp.get('dt')) / 60); setPlaying(false); }
  if (hp.has('member')) document.querySelector(`#memsel button[data-m="${+hp.get('member')}"]`)?.click();
  if (hp.has('focus')) { const k = boothAt(state.t), r = k >= 0 && BOOTH[k].rows.find(x => x.name === hp.get('focus') || x.id === hp.get('focus')); if (r) focusOrigin(r.id); }
  if (hp.has('tab')) showTab(hp.get('tab'));
  renderEvac();
  resize(); setPlaying(false);
  $('loading').remove();
  window.__wfg = { state, routes, CASES, BOOTH, RID, SF, TMAX, setTime: x => setTime(x), detail: () => detailGroup.userData.n && { n: detailGroup.userData.n, vis: detailGroup.visible, kids: detailGroup.children.length, sat: !!sat.ready },
    look: (lon, lat, r = 1.2) => { const u = uOf(lon), v = vOf(lat); tweenView({ r, phi: THREE.MathUtils.degToRad(55), th: sph(camera.position, controls.target).th, tgt: new THREE.Vector3(sxU(u), yAt(u, v), szV(v)) }, 10); } };
  // tools/bake_textures.mjs: the opening view as a picture, shown by the loader while the next visit starts up
  window.__wfgPoster = () => { if (composer && state.mode === '3d') composer.render(); else renderer.render(scene, camera); return renderer.domElement.toDataURL('image/webp', .72); };
  requestAnimationFrame(frame);
  if (hit) setTimeout(() => ctxDone.then(needOsm), 2500);   // then the OSM vectors, so a switch to 2D is instant
  if (!HR && B.hourly_meta) setTimeout(() => window.__wfgLoad(`${B.id}.hourly.js`).then(ok => { const h = ok && (window.WFG_HOURLY || {})[B.id]; if (h) { attachHourly(h); lastKey = ''; dirty = true; } }), 400);
}
requestAnimationFrame(() => setTimeout(() => boot().catch(e => { const ld = $('loading'); if (ld) { ld.className = 'loading'; ld.style.backgroundImage = '';
  ld.textContent = tr('지도를 시작하지 못했습니다: ', 'The map could not start: ') + (e && e.message || e); } console.error(e); }), 30));
