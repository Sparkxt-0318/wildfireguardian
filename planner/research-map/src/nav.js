// ---------------- 길 안내 (navigation view): one recorded case played on a road map ----------------
// One headline case per region for now. The car moves by the routing engine's recorded departure and arrival times for
// that case; the fire is the routing hazard input (worst of the four scenarios at each moment); red road = flame contact
// in the cell-centre recomputation. The pass / fail on the route cards is the recorded full-risk check
// (tests/planner/test_research_map.py::test_navigation_view).
const NAV_CASES = { uiseong_andong_2025: '20250324T090000Z_FL2' };
const NAV_ROUTES = [
  ['full', tr('점검된 길', 'Checked route'), tr('화재 위험 검사 통과', 'passes the fire-risk check')],
  ['travel_only', tr('가장 빠른 길', 'Fastest route'), tr('이동 시간만 고려', 'travel time only')],
];
// views: a chase camera behind the car and a driver's-eye camera on a real 3D map (satellite photos on terrain), or the 2D road map
const NAV_VIEWS = [['chase', tr('3D 따라가기', '3D chase')], ['driver', tr('운전자 시점', "Driver's view")], ['2d', tr('2D 지도', '2D map')]];
const navNum = x => x < 1e-4 ? '< 0.0001' : x < .01 ? x.toExponential(1) : x.toPrecision(2);
const navName = l => l ? (EN ? (l.ne || l.n) : l.n) : '';
const navClock = h => { const d = kst(h); return `${p2(d.getUTCHours())}:${p2(d.getUTCMinutes())}`; };
const navKm = (a, b) => Math.hypot((a.u - b.u) * KXr, (a.v - b.v) * KYr);
function navNear(u, v, maxKm) { let best = null, bd = maxKm; for (const l of B.labels) { const d = Math.hypot((uOf(l.lon) - u) * KXr, (vOf(l.lat) - v) * KYr); if (d < bd) { bd = d; best = l; } } return best; }
// where the car is at s seconds after the input time (before departure: at the start; after arrival: at the end)
function navAt(dense, s) {
  if (s <= dense[0].ts) return { ...dense[0], i: 0 };
  const j = dense.findIndex(q => q.ts >= s); if (j < 0) return { ...dense[dense.length - 1], i: dense.length - 1 };
  const a = dense[j - 1], b = dense[j], f = b.ts > a.ts ? (s - a.ts) / (b.ts - a.ts) : 1;
  return { u: a.u + (b.u - a.u) * f, v: a.v + (b.v - a.v) * f, d: a.d + (b.d - a.d) * f, cell: f < .5 ? a.cell : b.cell, i: j };
}
// the trip as a list: start, villages passed (closest approach within 0.7 km, at least 1.5 km apart), flame contact, arrival
function navSteps(sc, p) {
  const d = p.dense, steps = [], first = d[0], last = d[d.length - 1];
  const start = navNear(first.u, first.v, 3), end = navNear(last.u, last.v, 3), seen = new Map();
  d.forEach((q, i) => { const l = navNear(q.u, q.v, .7); if (!l || l === start || l === end) return;
    const dk = Math.hypot((uOf(l.lon) - q.u) * KXr, (vOf(l.lat) - q.v) * KYr); if (!seen.has(l) || seen.get(l).dk > dk) seen.set(l, { i, dk }); });
  steps.push({ s: p.dep, kind: 'start', km: 0, text: tr(`출발 · ${start ? navName(start) + ' 부근' : '출발지'}`, `Depart · near ${start ? navName(start) : 'the origin'}`) });
  let lastKm = -9;
  [...seen].sort((a, b) => a[1].i - b[1].i).forEach(([l, o]) => { const q = d[o.i]; if (q.d - lastKm < 1.5) return; lastKm = q.d;
    steps.push({ s: q.ts, kind: 'pass', km: q.d, text: tr(`${navName(l)} 지나감`, `Pass ${navName(l)}`) }); });
  // flame contact: consecutive dense points in a cell that some scenario marks as flame at that moment
  const hits = sc.k >= 0 ? flameHits(d, sc.k) : []; let run = null; const runs = [];
  for (const h of hits) { if (run && h.i === run.b + 1) { run.b = h.i; h.ms.forEach(m => run.ms.add(m)); } else { run = { a: h.i, b: h.i, ms: new Set(h.ms) }; runs.push(run); } }
  for (const r of runs) { const a = d[r.a], b = d[Math.min(d.length - 1, r.b + 1)], near = navNear(a.u, a.v, 2.5);
    steps.push({ s: a.ts, s2: b.ts, kind: 'fire', km: a.d, text: tr(`화염 속을 지남${near ? ' · ' + navName(near) + ' 부근' : ''}`, `Drives through flame${near ? ' · near ' + navName(near) : ''}`),
      sub: tr(`${Math.max(.1, b.d - a.d).toFixed(1)} km · 화재 scenario ${r.ms.size}/4개에서 화염`, `${Math.max(.1, b.d - a.d).toFixed(1)} km · flame in ${r.ms.size} of 4 fire scenarios`) }); }
  const dest = EN ? (sc.r.dest_en || sc.r.dest) : sc.r.dest;
  steps.push({ s: p.arr, kind: 'end', km: last.d, text: tr(`도착 · ${dest || navName(end)} 대피소`, `Arrive · ${dest || navName(end)} shelter`) });
  if (p.dwell_s) steps.push({ s: p.arr + p.dwell_s, kind: 'dwell', km: last.d, text: tr(`대피소에서 ${Math.round(p.dwell_s / 60)}분 머묾 (점검 포함)`, `${Math.round(p.dwell_s / 60)} min at the shelter (checked too)`) });
  return steps.sort((a, b) => a.s - b.s || (a.kind === 'end' ? -1 : 1));
}
function navInit() {
  NAV.ci = CASES.findIndex(c => c.r.case === NAV_CASES[B.id] && c.pol.full && c.pol.travel_only);
  if (NAV.ci < 0) return;
  $('tabNav').hidden = false;
  NAV.car = addDom('navcar', '<i></i>', 0, 0, { layer: 'routes', lift: .06, show: false });
  controls.addEventListener('start', () => { if (NAV.on && NAV.follow) { NAV.follow = false; const cb = $('navFollow'); if (cb) cb.checked = false; } });
}
function navEnter() {
  if (NAV.on || NAV.ci < 0) { if (NAV.on) navPanel(); return; }
  NAV.on = true; NAV.follow = true;
  NAV.prev = { cmp: state.cmp, layers: Object.fromEntries(LAYERS.map(l => [l.id, l.on])), mode: state.mode, base2d: state.base2d, pols: new Set(state.pols), sel: selRoute };
  if (state.cmp !== 'ours') setCompare('ours');
  const want = new Set(['base', 'burn', 'front', 'heat', 'routes', 'places', 'labels']);
  for (const l of LAYERS) if (l.id !== 'relief') setLayer(l.id, want.has(l.id));
  state.pols = new Set(); selRoute = NAV.ci;
  setBase('road');
  const sc = CASES[NAV.ci]; if (sc.k >= 0) setDetail(true, sc.k);
  mapEl.classList.add('nav'); $('navHud').hidden = false;
  navView(NAV.view || 'chase', true); navRoute(NAV.pol);
}
function navExit(to = 'pRoute') {
  if (!NAV.on) return; NAV.on = false; setPlaying(false); navReal(false);
  const pv = NAV.prev; mapEl.classList.remove('nav'); $('navHud').hidden = true;
  for (const l of LAYERS) if (l.id !== 'relief' && l.id in pv.layers) setLayer(l.id, pv.layers[l.id]);
  state.pols = pv.pols; setBase(pv.base2d); if (pv.mode !== state.mode) setMode(pv.mode);
  if (pv.cmp !== state.cmp) setCompare(pv.cmp);
  navMarks(); selectRoute(pv.sel); showTab(to);
}
// choose the route, then play it from just before departure
function navRoute(pol) {
  NAV.pol = pol; const sc = CASES[NAV.ci], p = sc.pol[pol];
  NAV.steps = navSteps(sc, p); NAV.cur = -1; buildRouteMeshes(); navPanel(); if (NAV.view === '2d') navFit(); navMarks(); navMapRoute();
  setTime(sc.r.t0 + Math.max(0, p.dep - 20) / 3600); setPlaying(true, Number($('speed').value) || 1);
}
// a label on the map where the route drives through flame
function navMarks() {
  for (const it of NAV.marks || []) { it.el.remove(); const i = domItems.indexOf(it); if (i >= 0) domItems.splice(i, 1); }
  const sc = CASES[NAV.ci], d = sc.pol[NAV.pol].dense;
  NAV.marks = NAV.on ? NAV.steps.filter(st => st.kind === 'fire').map(st => { const q = navAt(d, st.s);
    return addDom('lb navfire', `${tr('화염', 'Flame')} ${navClock(sc.r.t0 + st.s / 3600)}`, q.u, q.v, { layer: 'routes', lift: .1 }); }) : [];
}
// frame both routes; while following, the camera keeps the car in view instead
function navFit() {
  const sc = CASES[NAV.ci], pts = [...sc.pol.full.dense, ...sc.pol.travel_only.dense];
  const u0 = Math.min(...pts.map(q => q.u)), u1 = Math.max(...pts.map(q => q.u)), v0 = Math.min(...pts.map(q => q.v)), v1 = Math.max(...pts.map(q => q.v));
  const asp = mapEl.clientWidth / Math.max(1, mapEl.clientHeight), span = Math.max((v1 - v0) * KY, (u1 - u0) * KX / asp) * 1.35;
  const u = (u0 + u1) / 2, v = (v0 + v1) / 2;
  tweenView({ r: Math.max(4, span / (2 * Math.tan(camera.fov * Math.PI / 360))), phi: .0005, th: 0, tgt: new THREE.Vector3(sxU(u), yAt(u, v), szV(v)) }, 900);
}
function navPanel() {
  const sc = CASES[NAV.ci], r = sc.r, el = $('pNav'), first = sc.pol.full.dense[0];
  const start = navNear(first.u, first.v, 3), dest = EN ? (r.dest_en || r.dest) : r.dest;
  const card = ([pol, name, why]) => { const p = sc.pol[pol], hits = sc.k >= 0 ? flameHits(p.dense, sc.k) : [], ok = p.full_check ? p.full_check.passed : !hits.length;
    return `<button type="button" class="nav-rt${pol === NAV.pol ? ' sel' : ''}" data-pol="${pol}" aria-pressed="${pol === NAV.pol}">
      <span class="t"><b>${fmtMin(p.arr - p.dep)}</b> ${(p.length_m / 1000).toFixed(1)} km</span>
      <span class="n">${name} <small>${why}</small></span>
      <span class="${ok ? 'ok' : 'bad'}">${ok ? tr('✓ 화염 접촉 없음 · 열 한도 이하', '✓ no flame contact · within heat limits') : tr(`✕ ${(p.full_check.components || []).includes('FLAME') ? '화염 통과' : '위험 검사 불통과'} (${(p.full_check.components || []).map(c => ({ FLAME: '화염', WHOLE_ROAD_CONTACT: '도로 접촉', DOSE: '누적 노출', PEAK: '순간 열유속' }[c] || c)).join(' · ')})`, `✕ ${(p.full_check.components || []).includes('FLAME') ? 'through flame' : 'fails the risk check'} (${(p.full_check.components || []).join(', ').toLowerCase().replace(/_/g, ' ')})`)}</span></button>`; };
  el.innerHTML = `<div class="nav">
    <div class="nav-h"><b>${tr(`${B.name.ko} 산불 · ${navDate(r.t0)} ${navClock(r.t0)} 출발`, `${B.name.en} fire · depart ${navDate(r.t0)} ${navClock(r.t0)}`)}</b>
      <small>${tr(`기록된 경로 점검 사례 ${r.label} · 화재 scenario 4개`, `Recorded route-check case ${r.label} · 4 fire scenarios`)}</small></div>
    <div class="nav-od"><div><i class="o"></i>${tr(`출발 · ${start ? navName(start) + ' 부근 ' : ''}(연구 사례 출발지)`, `From · ${start ? 'near ' + navName(start) + ' ' : ''}(research origin)`)}</div>
      <div><i class="d"></i>${tr(`도착 · ${dest} 대피소`, `To · ${dest} shelter`)}</div></div>
    <div class="seg nav-views" role="group">${NAV_VIEWS.map(([v, n]) => `<button type="button" data-view="${v}" aria-pressed="${v === NAV.view}"${NAV.realErr && v !== '2d' ? ' disabled' : ''}>${n}</button>`).join('')}</div>
    ${NAV.realErr ? `<p class="note nav-err">${tr('3D 실제 지도를 불러오지 못했습니다. 위성 사진과 지형은 인터넷 연결이 있어야 보입니다.', 'Could not load the real 3D map. Satellite photos and terrain need an internet connection.')}</p>` : ''}
    <div class="nav-rts">${NAV_ROUTES.map(card).join('')}</div>
    <div class="nav-ctl"><button type="button" class="btn" id="navPlay"></button><button type="button" class="btn" id="navRestart">${tr('처음부터', 'Restart')}</button>
      <label ${NAV.view === '2d' ? '' : 'hidden'}><input type="checkbox" id="navFollow" ${NAV.follow ? 'checked' : ''}> ${tr('차 따라가기', 'Follow the car')}</label></div>
    <h4>${tr('경로 안내', 'Directions')} <small>${tr('누르면 그 순간으로', 'click to jump there')}</small></h4>
    <ol class="nav-steps">${NAV.steps.map((st, i) => `<li class="${st.kind}" data-i="${i}"><time>${navClock(r.t0 + st.s / 3600)}</time><span>${st.text}${st.sub ? `<small>${st.sub}</small>` : ''}</span><em>${st.km.toFixed(1)} km</em></li>`).join('')}</ol>
    <p class="note">${tr('차는 경로 엔진이 이 사례에서 계산한 출발·도착 시각대로 움직입니다. 불은 경로 점검에 쓴 화재 위험 입력(모델, 화재 scenario 4개 중 가장 나쁜 값)입니다: 빨강 = 화염, 주황 = 복사 열, 검정 = 기록된 연소 범위. 빨간 길 = 차가 지나는 그 시각에 화염인 칸으로, 기록된 전체 위험 검사 결과와 같습니다. OSM 자료에 도로 이름이 없어 가까운 마을 이름으로 안내합니다. 3D 시점은 위성 사진(Esri)과 실제 지형(Terrain Tiles) 위에 같은 기록 자료를 평평하게 겹친 것입니다. 사진은 화재 당시가 아니라 다른 시기에 찍은 것이며, 인터넷 연결이 필요합니다. 연구 재현이며 실제 대피 지시가 아닙니다.',
      'The car moves by the departure and arrival times the routing engine computed for this case. The fire is the hazard input used for route checking (model, worst of 4 fire scenarios): red = flame, orange = radiant heat, black = recorded burned area. Red road = cells in flame at the moment the car passes, matching the recorded full-risk check. OSM has no road names here, so directions use nearby villages. The 3D views lay the same recorded data flat on satellite photos (Esri) and real terrain (Terrain Tiles); the photos were taken at another time, not during the fire, and need an internet connection. A research replay, not an evacuation instruction.')}</p>
    <button type="button" class="btn" id="navExit">${tr('길 안내 끝내기', 'Leave navigation')}</button></div>`;
  el.querySelectorAll('.nav-rt').forEach(b => b.onclick = () => navRoute(b.dataset.pol));
  el.querySelectorAll('.nav-views button').forEach(b => b.onclick = () => navView(b.dataset.view));
  el.querySelectorAll('.nav-steps li').forEach(li => li.onclick = () => { const st = NAV.steps[+li.dataset.i]; setPlaying(false); setTime(r.t0 + (st.kind === 'fire' ? (st.s + st.s2) / 2 : st.s) / 3600); });
  $('navPlay').onclick = () => { const p = sc.pol[NAV.pol], s = (state.t - r.t0) * 3600; if (!state.playing && s >= p.arr + p.dwell_s) setTime(r.t0 + Math.max(0, p.dep - 20) / 3600); setPlaying(!state.playing, Number($('speed').value) || 1); };
  $('navRestart').onclick = () => navRoute(NAV.pol);
  $('navFollow').onchange = e => { NAV.follow = e.target.checked; if (!NAV.follow) navFit(); };
  $('navExit').onclick = () => navExit();
}
const navDate = h => { const d = kst(h); return EN ? `${d.getUTCDate()} ${['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][d.getUTCMonth()]} ${d.getUTCFullYear()}` : `${d.getUTCFullYear()}년 ${d.getUTCMonth() + 1}월 ${d.getUTCDate()}일`; };
const _navT = new THREE.Vector3();
let navHudKey = '';
function navFrame(t) {
  if (!NAV.car) return;
  NAV.car.show = NAV.on && NAV.view === '2d'; if (!NAV.on) return;
  const sc = CASES[NAV.ci], p = sc.pol[NAV.pol], s = (t - sc.r.t0) * 3600, q = navAt(p.dense, s), k = sc.k;
  NAV.car.u = q.u; NAV.car.v = q.v;
  const cut = Math.abs(s - (NAV.lastS ?? s)) > 20; NAV.lastS = s;     // a jump in time: cut, don't glide
  const moving = s >= p.dep && s <= p.arr + p.dwell_s;
  // conditions at the car: flame in any scenario, highest heat flux, dose so far (highest scenario)
  let fl = 0, F = 0, D = 0;
  if (k >= 0 && q.cell >= 0 && moving) for (let mi = 0; mi < 4; mi++) { if (hzFlame(k, mi, q.cell, s)) fl++; F = Math.max(F, hzFlux(k, mi, q.cell, s)); }
  if (p.exp) for (const m of p.exp) { let v = 0; for (const [ts, dv] of m.series) { if (ts > s) break; v = dv; } D = Math.max(D, v); }
  const lim = p.limits, state_ = !moving ? 'idle' : fl || F >= lim.peak_kw_m2 || D >= lim.dose_kj_m2 ? 'fire' : F >= lim.peak_kw_m2 * .1 ? 'warn' : 'ok';
  NAV.car.el.className = `navcar ${state_}`;
  if (state.playing && s >= p.arr + p.dwell_s) setPlaying(false);
  const cur = NAV.steps.reduce((c, st, i) => st.s <= s + .5 ? i : c, -1);
  if (cur !== NAV.cur) { NAV.cur = cur; document.querySelectorAll('#pNav .nav-steps li').forEach((li, i) => li.classList.toggle('now', i === cur)); }
  const play = $('navPlay'); if (play) play.textContent = state.playing ? tr('일시정지', 'Pause') : s >= p.arr + p.dwell_s ? tr('다시 재생', 'Replay') : tr('재생', 'Play');
  const phase = s < p.dep ? tr('출발 전', 'Before departure') : s <= p.arr ? tr(`출발 후 ${fmtS(s - p.dep)}`, `${fmtS(s - p.dep)} after departure`) : s <= p.arr + p.dwell_s ? tr('대피소 도착 · 머무는 중', 'At the shelter') : tr('도착 완료', 'Arrived');
  // at the car's position now; whole-road contact is in the recorded check on the route card
  const stTxt = !moving ? (s < p.dep ? tr('출발 전', 'Not yet on the road') : tr('도착 · 이동 끝', 'Arrived · trip over')) : fl ? tr(`차 위치: 화염 속 · 화재 scenario ${fl}/4개`, `At the car: in flame · ${fl} of 4 fire scenarios`) : state_ === 'fire' ? tr('차 위치: 열 한도 초과', 'At the car: over the heat limit') : state_ === 'warn' ? tr('차 위치: 강한 복사 열', 'At the car: strong radiant heat') : tr('차 위치: 화염 없음 · 열 한도 이하', 'At the car: no flame · within heat limits');
  const key = [navClock(t), phase, stTxt, q.d.toFixed(1), F.toPrecision(2), D.toPrecision(2), NAV.pol].join('|');
  if (key !== navHudKey) { navHudKey = key; const name = NAV_ROUTES.find(x => x[0] === NAV.pol)[1];
    $('navHud').innerHTML = `<div class="nh-top"><b>${navClock(t)}</b><span>${phase}</span></div>
      <div class="nh-st ${state_}">${stTxt}</div>
      <dl><dt>${name}</dt><dd>${q.d.toFixed(1)} / ${(p.length_m / 1000).toFixed(1)} km</dd>
        <dt>${tr('차 위치 복사 열', 'Heat at the car')}</dt><dd>${navNum(F)} kW/m² <small>${tr('한도', 'limit')} ${lim.peak_kw_m2}</small></dd>
        <dt>${tr('누적 열 노출', 'Heat dose so far')}</dt><dd>${navNum(D)} kJ/m² <small>${tr('한도', 'limit')} ${fmtLim(lim.dose_kj_m2)}</small></dd></dl>`; }
  if (NAV.view !== '2d') navMapFrame(t, p, q, state_, cut);
  else if (NAV.follow && !tween) { _navT.set(sxU(q.u), yAt(q.u, q.v), szV(q.v)).sub(controls.target).multiplyScalar(.08); controls.target.add(_navT); camera.position.add(_navT); }
}

// ---- 3D views: a real map (satellite photos on real terrain, MapLibre) with the same recorded data laid flat on it ----
// Photos: Esri World Imagery; roads and place names: Esri reference layers; elevation: Terrain Tiles (Mapzen, AWS Open Data).
// The photos were taken at another time, not during the fire. Needs an internet connection; without one the 2D map stays.
const NAV_ML = '__MAPLIBRE__';     // tools/build_viewer.py: vendor/maplibre-gl. (site, offline folder) or the pinned CDN copy, 4.7.1
const NAV_SRI = { js: 'sha384-SYKAG6cglRMN0RVvhNeBY0r3FYKNOJtznwA0v7B5Vp9tr31xAHsZC0DqkQ/pZDmj', css: 'sha384-MinO0mNliZ3vwppuPOUnGa+iq619pfMhLVUXfC4LHwSCvF9H+6P/KO4Q7qBOYV5V' };
const NAV_ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services/';
const navLL = (u, v) => [W + u * (E - W), N - v * (N - S)];
let navMapP = null;
function navView(v, quiet) {
  NAV.view = v; NAV.hd = null;
  if (state.mode !== '2d') setMode('2d');
  if (v === '2d') { navReal(false); navFit(); } else navReal(true);
  if (!quiet) navPanel();
}
function navReal(on) {
  NAV.real = on; mapEl.classList.toggle('nav3d', on);
  let el = $('navReal'); if (!on) { if (el) { el.hidden = true; $('navPhoto').hidden = true; } return; }
  if (!el) { el = document.createElement('div'); el.id = 'navReal'; el.className = 'navreal'; el.dataset.msg = tr('실제 지도를 불러오는 중…', 'Loading the real map…'); mapEl.appendChild(el);
    const bd = document.createElement('div'); bd.id = 'navPhoto'; bd.className = 'navphoto'; mapEl.appendChild(bd); }
  $('navPhoto').hidden = false; $('navPhoto').textContent = NAV.tileErr ? tr('위성 사진·지형을 불러오지 못했습니다 · 인터넷 연결을 확인하세요', 'Satellite photos or terrain did not load · check the internet connection')
    : tr('위성 사진은 화재 당시 모습이 아닙니다 · 불·경로는 기록 자료', 'Photos are not from the time of the fire · fire and routes are recorded data');
  el.hidden = false;
  navMap().then(map => { map.resize(); navMapRoute(); NAV.burnK = NAV.heatK = null; },
    () => { NAV.realErr = true; navMapP = null; if (NAV.real) navView('2d'); });
}
const navLoad = (tag, attrs) => new Promise((ok, no) => { const e = Object.assign(document.createElement(tag), attrs, { onload: ok, onerror: no }); document.head.appendChild(e); });
const navSri = k => NAV_ML.startsWith('https:') ? { integrity: NAV_SRI[k], crossOrigin: 'anonymous' } : {};     // CDN copy only: file:// cannot be checked
function navMap() {
  if (navMapP) return navMapP;
  return navMapP = (async () => {
    if (!window.maplibregl) await Promise.all([navLoad('script', { src: NAV_ML + 'js', ...navSri('js') }), navLoad('link', { rel: 'stylesheet', href: NAV_ML + 'css', ...navSri('css') })]);
    const ras = (path, attribution) => ({ type: 'raster', tiles: [NAV_ESRI + path + '/MapServer/tile/{z}/{y}/{x}'], tileSize: 256, maxzoom: 18, attribution });
    const fc = { type: 'FeatureCollection', features: [] }, first = CASES[NAV.ci].pol.full.dense[0];
    const map = new maplibregl.Map({ container: 'navReal', interactive: false, attributionControl: false, maxPitch: 85, fadeDuration: 0,
      center: navLL(first.u, first.v), zoom: 14, pitch: 60, style: { version: 8,
        sources: { sat: ras('World_Imagery', 'Imagery © Esri, Maxar, Earthstar Geographics'), roads: ras('Reference/World_Transportation', 'Roads © Esri'),
          places: ras('Reference/World_Boundaries_and_Places', 'Places © Esri'),
          dem: { type: 'raster-dem', tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'], tileSize: 256, maxzoom: 15, encoding: 'terrarium', attribution: 'Elevation: Terrain Tiles (Mapzen, AWS Open Data)' },
          burn: { type: 'geojson', data: fc }, heat: { type: 'geojson', data: fc },
          alt: { type: 'geojson', data: fc }, route: { type: 'geojson', data: fc }, hits: { type: 'geojson', data: fc }, ends: { type: 'geojson', data: fc } },
        terrain: { source: 'dem', exaggeration: 1 },
        sky: { 'sky-color': '#8db7de', 'horizon-color': '#dfe8ee', 'fog-color': '#dfe6ea', 'sky-horizon-blend': .6, 'horizon-fog-blend': .7, 'fog-ground-blend': .75 },
        layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#d8d5cd' } },
          { id: 'sat', type: 'raster', source: 'sat' },
          { id: 'burn', type: 'fill', source: 'burn', paint: { 'fill-color': '#1f1a17', 'fill-opacity': .5, 'fill-antialias': false } },
          { id: 'heat', type: 'fill', source: 'heat', paint: { 'fill-color': ['get', 'c'], 'fill-opacity': ['get', 'o'], 'fill-antialias': false } },
          { id: 'roads', type: 'raster', source: 'roads', paint: { 'raster-opacity': .8 } },
          { id: 'places', type: 'raster', source: 'places' },
          { id: 'alt', type: 'line', source: 'alt', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#9aa0a6', 'line-width': 5, 'line-opacity': .9 } },
          { id: 'casing', type: 'line', source: 'route', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#ffffff', 'line-width': 10 } },
          { id: 'route', type: 'line', source: 'route', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#1a73e8', 'line-width': 6 } },
          { id: 'hits', type: 'line', source: 'hits', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#ff2a14', 'line-width': 7 } },
          { id: 'ends', type: 'circle', source: 'ends', paint: { 'circle-radius': 7, 'circle-color': ['get', 'c'], 'circle-stroke-color': '#1e1e1e', 'circle-stroke-width': 2.5, 'circle-pitch-alignment': 'map' } }] } });
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');
    map.on('error', e => { if (!NAV.tileErr && (e.sourceId === 'sat' || e.sourceId === 'dem')) { NAV.tileErr = true; if (NAV.real) navReal(true); } });
    await new Promise(ok => map.isStyleLoaded() ? ok() : map.once('style.load', ok));
    const car = document.createElement('div'); car.className = 'navmlcar'; car.innerHTML = '<svg viewBox="0 0 24 24"><path d="M12 2 20 21 12 17 4 21z"/></svg>';
    NAV.mlCar = new maplibregl.Marker({ element: car, rotationAlignment: 'map', pitchAlignment: 'map' }).setLngLat(map.getCenter()).addTo(map);
    NAV.map = map; return map;
  })();
}
// the chosen route (blue on white), the other one (grey), flame contact (red) and the start and end points
function navMapRoute() {
  const map = NAV.map; if (!map) return;
  const sc = CASES[NAV.ci], P = sc.pol[NAV.pol], A = sc.pol[NAV.pol === 'full' ? 'travel_only' : 'full'];
  const line = d => ({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: d.map(q => navLL(q.u, q.v)) } });
  const runs = []; let run = null;
  for (const h of sc.k >= 0 ? flameHits(P.dense, sc.k) : []) { if (run && h.i === run[1] + 1) run[1] = h.i; else { run = [h.i, h.i]; runs.push(run); } }
  map.getSource('alt').setData(A && A.dense.length > 1 ? line(A.dense) : { type: 'FeatureCollection', features: [] });
  map.getSource('route').setData(line(P.dense));
  map.getSource('hits').setData({ type: 'FeatureCollection', features: runs.map(([a, b]) => line(P.dense.slice(a, b + 2))) });
  const a = P.dense[0], b = P.dense[P.dense.length - 1], pt = (q, c) => ({ type: 'Feature', properties: { c }, geometry: { type: 'Point', coordinates: navLL(q.u, q.v) } });
  map.getSource('ends').setData({ type: 'FeatureCollection', features: [pt(a, '#ffffff'), pt(b, '#d93025')] });
  for (const m of NAV.mlMarks || []) m.remove();
  NAV.mlMarks = NAV.steps.filter(st => st.kind === 'fire').map(st => { const q = navAt(P.dense, st.s), e = document.createElement('div');
    e.className = 'navmlfire'; e.textContent = `${tr('화염', 'Flame')} ${navClock(sc.r.t0 + st.s / 3600)}`;
    return new maplibregl.Marker({ element: e, anchor: 'bottom', offset: [0, -6] }).setLngLat(navLL(q.u, q.v)).addTo(map); });
}
// fire at time t as cell polygons laid on the terrain: recorded burned area dark (changes with the record), radiant heat
// orange and flame cells red (change with the hazard input). Polygons, not one picture: MapLibre 4.7.1 drapes an image
// source on terrain only inside a single map tile.
const navCell = (i, c, o) => { const r = (i / NC) | 0, k = i % NC;
  return { type: 'Feature', properties: { c, o }, geometry: { type: 'Polygon', coordinates: [[lat_(r, k), lat_(r, k + 1), lat_(r + 1, k + 1), lat_(r + 1, k), lat_(r, k)]] } }; };
function navFire(map, t) {
  const k = recIdx(t), zk = hzK(t), hk = hzSig(t), fc = features => ({ type: 'FeatureCollection', features });
  if (k !== NAV.burnK) { NAV.burnK = k; const f = []; if (k >= 0) for (let i = 0; i < NCELL; i++) if (burnedAt(i, k)) f.push(navCell(i)); map.getSource('burn').setData(fc(f)); }
  if (hk !== NAV.heatK) { NAV.heatK = hk; const f = [];
    if (zk >= 0) { const fld = hzField(zk, (t - HZ[zk].t0) * 3600, state.member), fl = new Set(fld.flame);
      for (let i = 0; i < NCELL; i++) { if (fl.has(i)) { f.push(navCell(i, '#e23b1d', .6)); continue; }
        const v = fluxV(fld.f[i]); if (v >= .5) f.push(navCell(i, `rgb(${inferno(.15 + .85 * v).map(Math.round)})`, smooth(.5, .75, v) * .55)); } }
    map.getSource('heat').setData(fc(f)); }
}
// heading along the route: from the car to a point `ahead` km further on
function navAhead(dense, q, ahead) { const want = q.d + ahead; let j = Math.max(1, q.i || 1); while (j < dense.length - 1 && dense[j].d < want) j++; return dense[j]; }
const navBear = (a, b) => Math.atan2((b[0] - a[0]) * Math.cos(a[1] * Math.PI / 180), b[1] - a[1]) * 180 / Math.PI;
const navStep = (ll, deg, km) => { const r = deg * Math.PI / 180; return [ll[0] + Math.sin(r) * km / (111.32 * Math.cos(ll[1] * Math.PI / 180)), ll[1] + Math.cos(r) * km / 110.57]; };
function navMapFrame(t, p, q, cls, cut) {
  const map = NAV.map; if (!map || !NAV.real) return;
  navFire(map, t);
  const here = navLL(q.u, q.v), a = navAhead(p.dense, q, .25), ah = navLL(a.u, a.v);
  if (Math.hypot(ah[0] - here[0], ah[1] - here[1]) > 1e-7) { const hd = navBear(here, ah); NAV.hd = NAV.hd == null || cut ? hd : NAV.hd + (((hd - NAV.hd) % 360 + 540) % 360 - 180) * .08; }
  const hd = NAV.hd ?? 0;
  NAV.mlCar.setLngLat(here).setRotation(hd); const ce = NAV.mlCar.getElement();     // classList: MapLibre keeps its own classes on the marker
  for (const c of ['ok', 'warn', 'fire', 'idle']) ce.classList.toggle(c, c === cls); ce.classList.toggle('off', NAV.view !== 'chase');
  // chase: behind and above the car, the car in the lower part of the view
  if (NAV.view === 'chase') { map.jumpTo({ center: here, bearing: hd, pitch: 62, zoom: 15.8, padding: { top: Math.round(map.getContainer().clientHeight * .3), bottom: 0, left: 0, right: 0 } }); return; }
  // driver's view: eye 15 m above the road, aimed at the road 160 m ahead (pitch about 85°, MapLibre's limit; the horizon
  // stays in view above)
  const ground = ll => { const z = map.queryTerrainElevation(ll); return z == null ? 0 : z + map.transform.elevation; };
  const to = navStep(here, hd, .16), o = map.calculateCameraOptionsFromTo(maplibregl.LngLat.convert(here), ground(here) + 15, maplibregl.LngLat.convert(to), ground(to));
  map.jumpTo({ ...o, bearing: hd, padding: { top: 0, bottom: 0, left: 0, right: 0 } });
}
