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
// views: street-level photos along the route (Kakao Roadview, stepped with buttons or driven automatically), a chase camera
// on a real 3D map (satellite photos on terrain), or the 2D road map
const NAV_VIEWS = [['street', tr('로드뷰', 'Road view')], ['chase', tr('3D 위성', '3D satellite')], ['2d', tr('2D 지도', '2D map')]];
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
  setTimeout(() => (window.requestIdleCallback || setTimeout)(navWarm), 3000);
  // the Kakao key can come with the link (#…&kakao=KEY): kept in this browser, then taken out of the address
  const hp = new URLSearchParams(location.hash.slice(1));
  if (hp.get('kakao')) { navKeySet(hp.get('kakao')); hp.delete('kakao'); history.replaceState(null, '', '#' + hp.toString()); }
  addEventListener('keydown', e => { if (!NAV.street || /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
    const k = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1 }[e.key];
    if (k) { e.preventDefault(); navAuto(false); navSvGo(NAV.svI + k * (e.shiftKey ? 5 : 1)); } else if (e.key === ' ') { e.preventDefault(); navAuto(!NAV.auto); } });
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
  navView(NAV.view || (navKey() ? 'street' : 'chase'), true); navRoute(NAV.pol);
}
function navExit(to = 'pRoute') {
  if (!NAV.on) return; NAV.on = false; setPlaying(false); navReal(false); navStreet(false);
  const pv = NAV.prev; mapEl.classList.remove('nav'); $('navHud').hidden = true;
  for (const l of LAYERS) if (l.id !== 'relief' && l.id in pv.layers) setLayer(l.id, pv.layers[l.id]);
  state.pols = pv.pols; setBase(pv.base2d); if (pv.mode !== state.mode) setMode(pv.mode);
  if (pv.cmp !== state.cmp) setCompare(pv.cmp);
  navMarks(); selectRoute(pv.sel); showTab(to);
}
// choose the route, then play it from just before departure
function navRoute(pol) {
  NAV.pol = pol; const sc = CASES[NAV.ci], p = sc.pol[pol];
  NAV.steps = navSteps(sc, p); NAV.cur = -1; NAV.sv = navSvSamples(p.dense); NAV.svI = 0; buildRouteMeshes(); navPanel(); if (NAV.view === '2d') navFit(); navMarks(); navMapRoute();
  setTime(sc.r.t0 + Math.max(0, p.dep - 20) / 3600);
  if (NAV.view === 'street') { navAuto(false); navSvGo(0); } else setPlaying(true, Number($('speed').value) || 1);
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
    ${NAV.view === 'street' || !navKey() ? `<details class="nav-key"${navKey() ? '' : ' open'}><summary>${tr('로드뷰 키 (카카오)', 'Road view key (Kakao)')}${navKey() ? ' ✓' : ''}</summary>
      <p>${tr('카카오 개발자 사이트(developers.kakao.com)에서 만든 JavaScript 키를 넣으세요. 이 브라우저에만 저장되고 저장소에는 올라가지 않습니다. 앱 설정의 Web 플랫폼에 이 주소를 등록해야 합니다:', 'Paste the JavaScript key from developers.kakao.com. It is kept in this browser only, never in the repository. Register this address under the app\'s Web platform:')} <code>${location.origin}</code></p>
      <div><input id="navKey" type="password" autocomplete="off" placeholder="${tr('JavaScript 키', 'JavaScript key')}" value=""> <button type="button" class="btn" id="navKeySave">${tr('저장', 'Save')}</button>${navKey() ? ` <button type="button" class="btn" id="navKeyClear">${tr('지우기', 'Remove')}</button>` : ''}</div></details>` : ''}
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
  if ($('navKeySave')) $('navKeySave').onclick = () => { const v = $('navKey').value.trim(); if (!v) return; navKeySet(v); if (window.kakao?.maps) location.reload(); else { navPanel(); if (NAV.view === 'street') navStreet(true); else navView('street'); } };
  if ($('navKeyClear')) $('navKeyClear').onclick = () => { navKeySet(''); location.reload(); };
  $('navPlay').onclick = () => { if (NAV.street) return navAuto(!NAV.auto); const p = sc.pol[NAV.pol], s = (state.t - r.t0) * 3600; if (!state.playing && s >= p.arr + p.dwell_s) setTime(r.t0 + Math.max(0, p.dep - 20) / 3600); setPlaying(!state.playing, Number($('speed').value) || 1); };
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
  const play = $('navPlay'); if (play) play.textContent = NAV.street ? (NAV.auto ? tr('자동 주행 정지', 'Stop driving') : tr('자동 주행', 'Drive')) : state.playing ? tr('일시정지', 'Pause') : s >= p.arr + p.dwell_s ? tr('다시 재생', 'Replay') : tr('재생', 'Play');
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
  if (NAV.street) navSvFrame(t, p, s, q);
  else if (NAV.view !== '2d') navMapFrame(t, p, q, state_, cut);
  else if (NAV.follow && !tween) { _navT.set(sxU(q.u), yAt(q.u, q.v), szV(q.v)).sub(controls.target).multiplyScalar(.08); controls.target.add(_navT); camera.position.add(_navT); }
}

// ---- 3D views: a real map (satellite photos on real terrain, MapLibre) with the same recorded data laid flat on it ----
// Photos: Esri World Imagery; roads and place names: Esri reference layers; elevation: Terrain Tiles (Mapzen, AWS Open Data).
// The photos were taken at another time, not during the fire. Needs an internet connection; without one the 2D map stays.
const NAV_ML = '__MAPLIBRE__';     // tools/build_viewer.py: vendor/maplibre-gl. (site, offline folder) or the pinned CDN copy, 4.7.1
const NAV_SRI = { js: 'sha384-SYKAG6cglRMN0RVvhNeBY0r3FYKNOJtznwA0v7B5Vp9tr31xAHsZC0DqkQ/pZDmj', css: 'sha384-MinO0mNliZ3vwppuPOUnGa+iq619pfMhLVUXfC4LHwSCvF9H+6P/KO4Q7qBOYV5V' };
// tile addresses: photos and roads on Esri's two host names (more connections at once), heights on AWS. Photos and roads stop
// at zoom 16 (MapLibre enlarges them closer in): a quarter of the zoom-17 requests the chase camera would otherwise make
const NAV_TILES = { sat: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  roads: 'https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}',
  dem: 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png' };
const navLL = (u, v) => [W + u * (E - W), N - v * (N - S)];
const NAV_CHASE = { pitch: 62, zoom: 15.8 };
let navMapP = null;
function navView(v, quiet) {
  NAV.view = v; NAV.hd = null;
  if (state.mode !== '2d') setMode('2d');
  navStreet(v === 'street'); navReal(v === 'chase'); if (v === '2d') navFit();
  if (!quiet) navPanel();
}
function navReal(on) {
  NAV.real = on; mapEl.classList.toggle('nav3d', on);
  let el = $('navReal'); if (!on) { if (el) { el.classList.add('warm'); $('navPhoto').hidden = true; } return; }     // kept, hidden: ready next time
  el = navRealEl(); el.classList.remove('warm');
  $('navPhoto').hidden = false; $('navPhoto').textContent = NAV.tileErr ? tr('위성 사진·지형을 불러오지 못했습니다 · 인터넷 연결을 확인하세요', 'Satellite photos or terrain did not load · check the internet connection')
    : tr('위성 사진은 화재 당시 모습이 아닙니다 · 불·경로는 기록 자료', 'Photos are not from the time of the fire · fire and routes are recorded data');
  // while the view's own first picture loads, the look-ahead waits (same hosts, same connections)
  NAV.pfHold = true; const resume = () => { if (!NAV.pfHold) return; NAV.pfHold = false; navPrefetch(4); }; setTimeout(resume, 6000);
  const hold = !NAV.map && state.playing; if (hold) setPlaying(false);     // first time: don't drive into an empty map
  navMap().then(map => { map.resize(); navMapRoute(); NAV.burnK = NAV.heatK = null; map.once('idle', resume);
    if (hold) { let go = () => { go = null; if (NAV.real && !state.playing) setPlaying(true, Number($('speed').value) || 1); };
      map.once('idle', () => go && go()); setTimeout(() => go && go(), 5000); } },
    () => { NAV.realErr = true; navMapP = null; if (NAV.real) navView('2d'); });
}
const navLoad = (tag, attrs) => new Promise((ok, no) => { const e = Object.assign(document.createElement(tag), attrs, { onload: ok, onerror: no }); document.head.appendChild(e); });
const navSri = k => NAV_ML.startsWith('https:') ? { integrity: NAV_SRI[k], crossOrigin: 'anonymous' } : {};     // CDN copy only: file:// cannot be checked
let navLibP = null;
const navLib = () => navLibP ??= window.maplibregl ? Promise.resolve()
  : Promise.all([navLoad('script', { src: NAV_ML + 'js', ...navSri('js') }), navLoad('link', { rel: 'stylesheet', href: NAV_ML + 'css', ...navSri('css') })]).catch(e => { navLibP = null; throw e; });
// Warm-up, a few seconds after the page has opened (not on phones or data saver): the map library, connections to the tile
// hosts, and the tiles along both routes, nearest the start first. Both hosts let the browser keep tiles, so when the tab
// opens and the car drives, the ground is already here instead of arriving while it moves.
function navWarm() {
  if (NAV.ci < 0 || isPhone || navigator.connection?.saveData) return;
  for (const h of ['https://server.arcgisonline.com', 'https://services.arcgisonline.com', 'https://s3.amazonaws.com'])
    document.head.appendChild(Object.assign(document.createElement('link'), { rel: 'preconnect', href: h, crossOrigin: 'anonymous' }));
  navPrefetch(3);
  // the 3D map itself, built out of sight at the departure view: its first picture loads before anyone opens the view
  navLib().then(() => { navRealEl(); return navMap(); }).catch(() => { });
  if (navKey()) navKakao().catch(() => { });
}
// the 3D map's element: created once, hidden (class warm) when another view is shown
function navRealEl() {
  let el = $('navReal'); if (el) return el;
  el = document.createElement('div'); el.id = 'navReal'; el.className = 'navreal warm'; el.dataset.msg = tr('실제 지도를 불러오는 중…', 'Loading the real map…'); mapEl.appendChild(el);
  const bd = document.createElement('div'); bd.id = 'navPhoto'; bd.className = 'navphoto'; bd.hidden = true; mapEl.appendChild(bd);
  return el;
}
const navTile = (k, z, x, y) => NAV_TILES[k].replace('{z}', z).replace('{x}', x).replace('{y}', y);
function navPrefetchList() {
  const sc = CASES[NAV.ci], out = [], seen = new Set(), add = u => { if (!seen.has(u)) { seen.add(u); out.push(u); } };
  // zoom levels the chase camera asks for (measured): heights and the wider photo zooms one tile either side of the road,
  // the closest zoom on the road itself (about 300 tiles, 4 MB, for both routes)
  const want = [['dem', 12, 1], ['dem', 13, 1], ['dem', 14, 1], ['sat', 13, 1], ['sat', 14, 1], ['sat', 15, 1], ['sat', 16, 0], ['roads', 15, 0], ['roads', 16, 0]];
  const pts = []; for (const pol of ['full', 'travel_only']) { let last = -1; for (const q of sc.pol[pol].dense) if (q.d - last >= .15) { last = q.d; pts.push(q); } }
  pts.sort((a, b) => a.d - b.d);
  for (const q of pts) { const [lon, lat] = navLL(q.u, q.v), r = lat * Math.PI / 180;
    for (const [k, z, w] of want) { const n = 2 ** z, x = Math.floor((lon + 180) / 360 * n), y = Math.floor((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * n);
      for (let dx = -w; dx <= w; dx++) for (let dy = -w; dy <= w; dy++) add(navTile(k, z, x + dx, y + dy)); } }
  return out;
}
function navPrefetch(par) {
  NAV.pfPar = Math.max(NAV.pfPar || 0, par); if (!NAV.pf) { NAV.pf = navPrefetchList(); NAV.pfI = 0; NAV.pfN = 0; }
  while (!NAV.pfHold && NAV.pfN < NAV.pfPar && NAV.pfI < NAV.pf.length) { const u = NAV.pf[NAV.pfI++]; NAV.pfN++;
    fetch(u, { mode: 'cors', credentials: 'same-origin' }).then(r => r.arrayBuffer()).catch(() => { }).finally(() => { NAV.pfN--; navPrefetch(0); }); }
}
function navMap() {
  if (navMapP) return navMapP;
  return navMapP = (async () => {
    await navLib();
    const ras = (k, attribution) => ({ type: 'raster', tiles: [NAV_TILES[k]], tileSize: 256, maxzoom: 16, attribution });
    const fc = { type: 'FeatureCollection', features: [] }, d0 = CASES[NAV.ci].pol[NAV.pol].dense, first = d0[0], a0 = navAhead(d0, { ...first, i: 0 }, .25);
    const map = new maplibregl.Map({ container: 'navReal', interactive: false, attributionControl: false, maxPitch: 85, fadeDuration: 0,
      center: navLL(first.u, first.v), bearing: navBear(navLL(first.u, first.v), navLL(a0.u, a0.v)), ...NAV_CHASE, style: { version: 8,
        sources: { sat: ras('sat', 'Imagery © Esri, Maxar, Earthstar Geographics'), roads: ras('roads', 'Roads © Esri'),
          dem: { type: 'raster-dem', tiles: [NAV_TILES.dem], tileSize: 256, maxzoom: 15, encoding: 'terrarium', attribution: 'Elevation: Terrain Tiles (Mapzen, AWS Open Data)' },
          burn: { type: 'geojson', data: fc }, heat: { type: 'geojson', data: fc },
          alt: { type: 'geojson', data: fc }, route: { type: 'geojson', data: fc }, hits: { type: 'geojson', data: fc }, ends: { type: 'geojson', data: fc } },
        terrain: { source: 'dem', exaggeration: 1 },
        sky: { 'sky-color': '#8db7de', 'horizon-color': '#dfe8ee', 'fog-color': '#dfe6ea', 'sky-horizon-blend': .6, 'horizon-fog-blend': .7, 'fog-ground-blend': .75 },
        layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#d8d5cd' } },
          { id: 'sat', type: 'raster', source: 'sat' },
          { id: 'burn', type: 'fill', source: 'burn', paint: { 'fill-color': '#1f1a17', 'fill-opacity': .5, 'fill-antialias': false } },
          { id: 'heat', type: 'fill', source: 'heat', paint: { 'fill-color': ['get', 'c'], 'fill-opacity': ['get', 'o'], 'fill-antialias': false } },
          { id: 'roads', type: 'raster', source: 'roads', paint: { 'raster-opacity': .8 } },
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
  map.jumpTo({ center: here, bearing: hd, ...NAV_CHASE, padding: { top: Math.round(map.getContainer().clientHeight * .3), bottom: 0, left: 0, right: 0 } });
}

// ---- 로드뷰: Kakao Roadview photos along the recorded route ----
// The key is the user's own Kakao JavaScript key (developers.kakao.com), kept in this browser's storage, never in the
// repository. Kakao serves only the web addresses registered for that key, so road view does not work from file://.
// The photos were taken at other times; the fire shown (inset map, box) is the recorded data at the moment the car would
// be at that spot.
const navKey = () => { try { return localStorage.getItem('wfgKakaoKey') || ''; } catch { return ''; } };
const navKeySet = v => { try { v ? localStorage.setItem('wfgKakaoKey', v) : localStorage.removeItem('wfgKakaoKey'); } catch { } };
let navKakaoP = null;
function navKakao() {
  return navKakaoP ??= new Promise((ok, no) => {
    if (window.kakao?.maps?.Roadview) return ok();
    setTimeout(() => no(new Error('timeout')), 15000);
    navLoad('script', { src: `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(navKey())}&autoload=false` })
      .then(() => window.kakao?.maps?.load ? kakao.maps.load(ok) : no(new Error('no kakao.maps')), no);
  }).catch(e => { navKakaoP = null; throw e; });
}
// stops along the route every 30 m, each with the time the car is there
function navSvSamples(dense) { const out = []; let next = 0; for (const q of dense) if (q.d >= next) { out.push(q); next = q.d + .03; } if (out[out.length - 1] !== dense[dense.length - 1]) out.push(dense[dense.length - 1]); return out; }
const navSvMsg = t => { const m = $('navSvMsg'); if (m) m.textContent = t; };
function navStreet(on) {
  NAV.street = on; mapEl.classList.toggle('navsv', on);
  let el = $('navStreet'); if (!on) { if (el) el.hidden = true; navAuto(false); return; }
  if (!el) { el = document.createElement('div'); el.id = 'navStreet'; el.className = 'navstreet';
    el.innerHTML = `<div class="sv-view" id="navSvView"></div><div class="sv-msg" id="navSvMsg"></div>
      <div class="navphoto sv-photo">${tr('로드뷰 사진은 화재 당시 모습이 아닙니다 · 불은 기록 자료 (작은 지도·왼쪽 상자)', 'Road photos are not from the time of the fire · the fire is recorded data (inset map, box)')}</div>
      <canvas class="sv-mini" id="navMini" width="520" height="380" aria-label="${tr('작은 지도: 경로와 기록된 불', 'Inset map: routes and recorded fire')}"></canvas>
      <div class="sv-ctl"><button type="button" id="svBack" title="${tr('뒤로 30 m (←, Shift: 150 m)', 'Back 30 m (←, Shift: 150 m)')}">◀</button>
        <button type="button" id="svAuto"></button><button type="button" id="svFwd" title="${tr('앞으로 30 m (→, Shift: 150 m)', 'Forward 30 m (→, Shift: 150 m)')}">▶</button><span id="svPos"></span></div>`;
    mapEl.appendChild(el);
    $('svBack').onclick = e => { navAuto(false); navSvGo(NAV.svI - (e.shiftKey ? 5 : 1)); };
    $('svFwd').onclick = e => { navAuto(false); navSvGo(NAV.svI + (e.shiftKey ? 5 : 1)); };
    $('svAuto').onclick = () => navAuto(!NAV.auto); }
  el.hidden = false; navAuto(false);
  if (!navKey()) return navSvMsg(tr('로드뷰를 보려면 오른쪽 패널에 카카오 JavaScript 키를 넣으세요. 작은 지도와 단계 이동은 키 없이도 됩니다.', 'Add a Kakao JavaScript key in the panel on the right to see road photos. The inset map and stepping work without it.'));
  navSvMsg(tr('로드뷰를 불러오는 중…', 'Loading road view…'));
  navKakao().then(() => { navSvInit(); NAV.rv.relayout(); if (NAV.sv) navSvGo(NAV.svI || 0, true); },
    () => navSvMsg(tr(`카카오 로드뷰를 불러오지 못했습니다. 키가 맞는지, 앱의 Web 플랫폼에 ${location.origin} 이 등록되었는지, 인터넷 연결을 확인하세요.`, `Could not load Kakao road view. Check the key, that ${location.origin} is registered under the app's Web platform, and the internet connection.`)));
}
function navSvInit() {
  if (NAV.rv) return;
  NAV.rv = new kakao.maps.Roadview($('navSvView')); NAV.rvc = new kakao.maps.RoadviewClient();
  const loaded = () => { clearTimeout(NAV.rvWatch); if (NAV.svPan != null) NAV.rv.setViewpoint({ pan: NAV.svPan, tilt: 0, zoom: 0 }); if (NAV.svMiss == null) navSvMsg(''); const f = NAV.svDone; NAV.svDone = null; if (f) f(); };
  kakao.maps.event.addListener(NAV.rv, 'init', loaded); kakao.maps.event.addListener(NAV.rv, 'panoid_changed', loaded);
}
// go to stop j: the time follows (so the box and inset map show the fire then), and the nearest photo within 50 m, facing
// along the route
function navSvGo(j, keepTime) {
  const S = NAV.sv; if (!S) return; j = Math.max(0, Math.min(S.length - 1, j)); NAV.svI = j;
  const sc = CASES[NAV.ci], q = S[j], dense = sc.pol[NAV.pol].dense, ll = navLL(q.u, q.v), a = navAhead(dense, q, .06);
  NAV.svHd = navBear(ll, navLL(a.u, a.v)); NAV.svPan = (NAV.svHd + 360) % 360;
  if (!keepTime) { NAV.svT = sc.r.t0 + q.ts / 3600; setTime(NAV.svT); }
  const pos = $('svPos'); if (pos) pos.textContent = `${q.d.toFixed(2)} / ${(sc.pol[NAV.pol].length_m / 1000).toFixed(1)} km`;
  if (!NAV.rv) return;
  const req = NAV.svReq = (NAV.svReq || 0) + 1, at = new kakao.maps.LatLng(ll[1], ll[0]);
  NAV.rvc.getNearestPanoId(at, 50, id => {
    if (req !== NAV.svReq) return;     // a newer step was asked for
    if (id == null) { NAV.svMiss = j; navSvMsg(tr('이 지점 50 m 안에는 로드뷰 사진이 없습니다 · 앞뒤로 이동해 보세요', 'No road photo within 50 m of this point · step on or back')); const f = NAV.svDone; NAV.svDone = null; if (f) f(); return; }
    NAV.svMiss = null; navSvMsg('');
    clearTimeout(NAV.rvWatch); NAV.rvWatch = setTimeout(() => navSvMsg(tr(`로드뷰 사진이 오지 않습니다. 앱의 Web 플랫폼에 ${location.origin} 이 등록되었는지 확인하세요.`, `Road photos are not arriving. Check that ${location.origin} is registered under the app's Web platform.`)), 8000);
    NAV.rv.setPanoId(id, at); NAV.rv.setViewpoint({ pan: NAV.svPan, tilt: 0, zoom: 0 });
  });
}
// automatic drive: 150 m at a time, waiting for each photo (at most 4 s)
function navAuto(on) {
  NAV.auto = on; clearTimeout(NAV.autoT); NAV.svDone = null;
  const b = $('svAuto'); if (b) b.textContent = on ? tr('■ 정지', '■ Stop') : tr('▶ 자동 주행', '▶ Drive');
  if (on) navAutoStep();
}
function navAutoStep() {
  if (!NAV.auto || !NAV.street) return;
  if (NAV.svI >= NAV.sv.length - 1) return navAuto(false);
  let next = () => { next = null; NAV.autoT = setTimeout(navAutoStep, 700); };
  NAV.svDone = () => next && next(); NAV.autoT = setTimeout(() => next && next(), NAV.rv ? 4000 : 900);
  navSvGo(NAV.svI + 5);
}
// each frame in road view: follow time changes made elsewhere (directions list, timeline), the timeline's play drives,
// and the inset map is redrawn
function navSvFrame(t, p, s, q) {
  if (state.playing) { setPlaying(false); navAuto(true); }
  if (NAV.sv && NAV.svT != null && Math.abs(t - NAV.svT) > 1e-7) { NAV.svT = t; let j = 0, bd = 1e9;
    NAV.sv.forEach((x, i) => { const d = Math.abs(x.ts - s); if (d < bd) { bd = d; j = i; } }); if (j !== NAV.svI) navSvGo(j, true); }
  NAV.svT ??= t;
  navMini(p, q);
}
// inset map: 2.4 km of the road map with the recorded fire (the 2D view's picture), both routes and the car
function navMini(p, q) {
  const c = $('navMini'); if (!c || !composite) return;
  const x = c.getContext('2d'), cw = c.width, ch = c.height, sw = 2.4 / KXr * TW, sh = sw * ch / cw, x0 = q.u * TW - sw / 2, y0 = q.v * TH - sh / 2;
  const P = (u, v) => [(u * TW - x0) * cw / sw, (v * TH - y0) * ch / sh];
  x.fillStyle = '#e8e4da'; x.fillRect(0, 0, cw, ch); x.drawImage(composite, x0, y0, sw, sh, 0, 0, cw, ch);
  const sc = CASES[NAV.ci], line = (d, w, col) => { x.beginPath(); d.forEach((pt, i) => { const [a, b] = P(pt.u, pt.v); i ? x.lineTo(a, b) : x.moveTo(a, b); }); x.lineWidth = w; x.strokeStyle = col; x.stroke(); };
  x.lineCap = x.lineJoin = 'round';
  const A = sc.pol[NAV.pol === 'full' ? 'travel_only' : 'full']; if (A) line(A.dense, 6, '#9aa0a6');
  line(p.dense, 11, '#fff'); line(p.dense, 7, '#1a73e8');
  const [cx, cy] = P(q.u, q.v); x.save(); x.translate(cx, cy); x.rotate((NAV.svHd || 0) * Math.PI / 180);
  x.beginPath(); x.moveTo(0, -16); x.lineTo(11, 12); x.lineTo(0, 6); x.lineTo(-11, 12); x.closePath(); x.fillStyle = '#1a73e8'; x.fill(); x.lineWidth = 3; x.strokeStyle = '#fff'; x.stroke(); x.restore();
  x.font = '600 20px system-ui, sans-serif'; x.fillStyle = 'rgba(255,255,255,.88)'; x.fillRect(0, ch - 32, cw, 32); x.fillStyle = '#3c3a36';
  x.fillText(tr('빨강 화염 · 주황 열 · 검정 연소 (기록) · 2.4 km 폭', 'red flame · orange heat · black burned (recorded) · 2.4 km wide'), 10, ch - 10);
}
