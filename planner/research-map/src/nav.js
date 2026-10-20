// ---------------- 길 안내 (navigation view): one recorded case played on a road map ----------------
// One headline case per region for now. The car moves by the routing engine's recorded departure and arrival times for
// that case; the fire is the routing hazard input (worst of the four scenarios at each moment); red road = flame contact
// in the cell-centre recomputation. The pass / fail on the route cards is the recorded full-risk check
// (tests/planner/test_research_map.py::test_navigation_view).
// one headline case per fire: where the travel-time-only route fails the recorded full check. In 울진 and 영덕 (and
// 의성·안동) the checker found a detour; in 밀양 and 홍성 every such case is recorded as no fire-safe route at all.
const NAV_CASES = { uljin_2022: '20220304T060000Z_FL1', miryang_2022: '20220601T080000Z_FD1', hongseong_2023: '20230402T070000Z_FN1',
  uiseong_andong_2025: '20250324T090000Z_FL2', yeongdeok_2025: '20250325T190000Z_FX2' };
const navHas = pol => (CASES[NAV.ci]?.pol[pol]?.dense?.length || 0) > 1;     // a recorded route to drive (none: model_no_route)
const navPols = () => ['full', 'travel_only'].filter(navHas);
// the shelter's name; where the record only says "research" (a research shelter), the village nearest the route's end
function navDest(sc) {
  const r = sc.r; if (r.dest && r.dest !== 'research') return EN ? (r.dest_en || r.dest) : r.dest;
  const d = sc.pol[navPols()[0]].dense, e = d[d.length - 1], l = navNear(e.u, e.v, 3);
  return l ? tr(`${navName(l)} 부근`, `near ${navName(l)}`) : tr('연구 사례 도착지', 'research destination');
}
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
  const dest = navDest(sc);
  steps.push({ s: p.arr, kind: 'end', km: last.d, text: tr(`도착 · ${dest || navName(end)} 대피소`, `Arrive · ${dest || navName(end)} shelter`) });
  if (p.dwell_s) steps.push({ s: p.arr + p.dwell_s, kind: 'dwell', km: last.d, text: tr(`대피소에서 ${Math.round(p.dwell_s / 60)}분 머묾 (점검 포함)`, `${Math.round(p.dwell_s / 60)} min at the shelter (checked too)`) });
  return steps.sort((a, b) => a.s - b.s || (a.kind === 'end' ? -1 : 1));
}
function navInit() {
  NAV.ci = CASES.findIndex(c => c.r.case === NAV_CASES[B.id] && (c.pol.travel_only?.dense?.length || 0) > 1);
  if (NAV.ci < 0) return;
  NAV.pol = navHas('full') ? 'full' : 'travel_only';
  window.__wfgLoad(B.id + '.pano.js').then(() => { NAV.ids = null; });     // the baked photo list, when there is one
  $('tabNav').hidden = false;
  NAV.car = addDom('navcar', '<i></i>', 0, 0, { layer: 'routes', lift: .06, show: false });
  NAV.car2 = addDom('navcar alt', '<i></i><b></b>', 0, 0, { layer: 'routes', lift: .06, show: false });     // the other route's car (race)
  NAV.race = true;
  setTimeout(() => (window.requestIdleCallback || setTimeout)(navWarm, { timeout: 1500 }), 1200);
  // road view first (its photos come from Kakao, not the map hosts): library, first photo and photo list straight away
  if (navKey() && !isPhone) setTimeout(() => { NAV.sv ??= navSvSamples(CASES[NAV.ci].pol[NAV.pol].dense); NAV.svI ??= 0; navStreetWarm(); navResolve(); }, 500);
  // the Kakao key can come with the link (#…&kakao=KEY): kept in this browser, then taken out of the address
  const hp = new URLSearchParams(location.hash.slice(1));
  if (hp.get('kakao')) { navKeySet(hp.get('kakao')); hp.delete('kakao'); history.replaceState(null, '', '#' + hp.toString()); }
  addEventListener('keydown', e => { if (!NAV.street || /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
    const k = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1 }[e.key];
    if (k) { e.preventDefault(); navAuto(false); navSvStep(k * (e.shiftKey ? 5 : 1)); } else if (e.key === ' ') { e.preventDefault(); navAuto(!NAV.auto); } });
}
function navEnter() {
  if (NAV.on || NAV.ci < 0) { if (NAV.on) navPanel(); return; }
  NAV.on = true;
  NAV.prev = { cmp: state.cmp, layers: Object.fromEntries(LAYERS.map(l => [l.id, l.on])), mode: state.mode, base2d: state.base2d, pols: new Set(state.pols), sel: selRoute };
  if (state.cmp !== 'ours') setCompare('ours');
  const want = new Set(['base', 'burn', 'front', 'heat', 'q', 'routes', 'places', 'labels']);     // q: where the model expects it to spread next
  for (const l of LAYERS) if (l.id !== 'relief') setLayer(l.id, want.has(l.id));
  state.pols = new Set(); selRoute = NAV.ci;
  setBase('road');
  const sc = CASES[NAV.ci]; if (sc.k >= 0) setDetail(true, sc.k);
  mapEl.classList.add('nav'); $('navHud').hidden = false; $('navLegend').hidden = false;
  navView(NAV.view || (navKey() ? 'street' : 'chase'), true); navRoute(NAV.pol); navToMap();
}
// phones: the map sits above the panel, so bring it into view when navigation opens or the view changes
const navToMap = () => { if (matchMedia('(max-width: 860px)').matches) mapEl.scrollIntoView({ behavior: 'smooth', block: 'start' }); };
function navExit(to = 'pRoute') {
  if (!NAV.on) return; NAV.on = false; setPlaying(false); navReal(false); navStreet(false);
  const pv = NAV.prev; mapEl.classList.remove('nav'); $('navHud').hidden = true; $('navLegend').hidden = true;
  for (const l of LAYERS) if (l.id !== 'relief' && l.id in pv.layers) setLayer(l.id, pv.layers[l.id]);
  state.pols = pv.pols; setBase(pv.base2d); if (pv.mode !== state.mode) setMode(pv.mode);
  if (pv.cmp !== state.cmp) setCompare(pv.cmp);
  navMarks(); selectRoute(pv.sel); showTab(to);
}
// choose the route, then play it from just before departure
function navRoute(pol) {
  NAV.pol = pol; NAV.camBear = NAV.camC = null; const sc = CASES[NAV.ci], p = sc.pol[pol];
  NAV.steps = navSteps(sc, p); NAV.cur = -1; NAV.sv = navSvSamples(p.dense); NAV.svI = 0; navResolve(); buildRouteMeshes(); navPanel(); if (NAV.view === '2d') navFit(); navMarks(); if (NAV.real) navMapRoute();
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
  const sc = CASES[NAV.ci], pts = navPols().flatMap(p => sc.pol[p].dense);
  const u0 = Math.min(...pts.map(q => q.u)), u1 = Math.max(...pts.map(q => q.u)), v0 = Math.min(...pts.map(q => q.v)), v1 = Math.max(...pts.map(q => q.v));
  const asp = mapEl.clientWidth / Math.max(1, mapEl.clientHeight), span = Math.max((v1 - v0) * KY, (u1 - u0) * KX / asp) * 1.35;
  const u = (u0 + u1) / 2, v = (v0 + v1) / 2;
  tweenView({ r: Math.max(4, span / (2 * Math.tan(camera.fov * Math.PI / 360))), phi: .0005, th: 0, tgt: new THREE.Vector3(sxU(u), yAt(u, v), szV(v)) }, 900);
}
function navPanel() {
  const sc = CASES[NAV.ci], r = sc.r, el = $('pNav'), first = sc.pol[NAV.pol].dense[0];
  const start = navNear(first.u, first.v, 3), dest = navDest(sc);
  const card = ([pol, name, why]) => { if (!navHas(pol)) return `<div class="nav-rt none"><span class="n">${name} <small>${why}</small></span>
      <span class="bad">${tr('✕ 없음: 이 출발지에서 화재 위험 검사를 통과하는 길을 모델이 찾지 못했습니다 (기록)', '✕ none: the model found no route from here that passes the fire-risk check (recorded)')}</span></div>`;
    const p = sc.pol[pol], hits = sc.k >= 0 ? flameHits(p.dense, sc.k) : [], ok = p.full_check ? p.full_check.passed : !hits.length;
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
    ${navOther() ? `<div class="seg nav-show" role="group" aria-label="${tr('보여 줄 길', 'Routes shown')}">${[['both', tr('두 길 함께', 'Both routes')], ['full', tr('점검된 길만', 'Checked route only')], ['travel_only', tr('불 통과 길만', 'Through-fire route only')]].map(([k, n]) =>
      `<button type="button" data-show="${k}" aria-pressed="${k === (NAV.race ? 'both' : NAV.pol)}">${n}</button>`).join('')}</div>` : ''}
    ${NAV.view === 'chase' ? `<label class="nav-race"><input type="checkbox" id="navFree" ${NAV.free ? 'checked' : ''}> ${tr('자유 시점: 끌어서 이동·회전, 휠로 확대·축소 (오른쪽 끌기·Ctrl: 기울이기)', 'Free view: drag to move and turn, wheel to zoom (right-drag or Ctrl: tilt)')}</label>` : ''}
    <div class="nav-graph"><div class="h">${tr('가장 가까운 불까지 거리', 'Distance to the nearest fire')} <small>${tr('출발 후 분 · 기록·모델 불', 'minutes after departure · recorded and model fire')}</small></div><svg id="navGraph" role="img"></svg>
      <div class="k">${navPols().map(p => `<span><i style="background:${p === 'full' ? '#1a73e8' : '#8a8f96'}"></i>${NAV_ROUTES.find(x => x[0] === p)[1]}</span>`).join('')}<span><i class="fl"></i>${tr('화염 접촉', 'flame contact')}</span></div></div>
    <div class="nav-ctl"><button type="button" class="btn" id="navPlay"></button><button type="button" class="btn" id="navRestart">${tr('처음부터', 'Restart')}</button>
</div>
    <h4>${tr('경로 안내', 'Directions')} <small>${tr('누르면 그 순간으로', 'click to jump there')}</small></h4>
    <ol class="nav-steps">${NAV.steps.map((st, i) => `<li class="${st.kind}" data-i="${i}"><time>${navClock(r.t0 + st.s / 3600)}</time><span>${st.text}${st.sub ? `<small>${st.sub}</small>` : ''}</span><em>${st.km.toFixed(1)} km</em></li>`).join('')}</ol>
    <p class="note">${tr('차는 경로 엔진이 이 사례에서 계산한 출발·도착 시각대로 움직입니다. 불은 경로 점검에 쓴 화재 위험 입력(모델, 화재 scenario 4개 중 가장 나쁜 값)입니다: 빨강 = 화염, 주황 = 복사 열, 검정 = 기록된 연소 범위. 빨간 길 = 차가 지나는 그 시각에 화염인 칸으로, 기록된 전체 위험 검사 결과와 같습니다. OSM 자료에 도로 이름이 없어 가까운 마을 이름으로 안내합니다. 3D 시점은 위성 사진(Esri)과 실제 지형(Terrain Tiles) 위에 같은 기록 자료를 평평하게 겹친 것입니다. 사진은 화재 당시가 아니라 다른 시기에 찍은 것이며, 인터넷 연결이 필요합니다. 연구 재현이며 실제 대피 지시가 아닙니다.',
      'The car moves by the departure and arrival times the routing engine computed for this case. The fire is the hazard input used for route checking (model, worst of 4 fire scenarios): red = flame, orange = radiant heat, black = recorded burned area. Red road = cells in flame at the moment the car passes, matching the recorded full-risk check. OSM has no road names here, so directions use nearby villages. The 3D views lay the same recorded data flat on satellite photos (Esri) and real terrain (Terrain Tiles); the photos were taken at another time, not during the fire, and need an internet connection. A research replay, not an evacuation instruction.')}</p>
    <button type="button" class="btn" id="navExit">${tr('길 안내 끝내기', 'Leave navigation')}</button></div>`;
  el.querySelectorAll('.nav-rt').forEach(b => b.onclick = () => navRoute(b.dataset.pol));
  el.querySelectorAll('.nav-views button').forEach(b => b.onclick = () => { navView(b.dataset.view); navToMap(); });
  el.querySelectorAll('.nav-steps li').forEach(li => li.onclick = () => { const st = NAV.steps[+li.dataset.i]; setPlaying(false); navToMap(); setTime(r.t0 + (st.kind === 'fire' ? (st.s + st.s2) / 2 : st.s) / 3600); });
  if ($('navKeySave')) $('navKeySave').onclick = () => { const v = $('navKey').value.trim(); if (!v) return; navKeySet(v); if (window.kakao?.maps) location.reload(); else { navPanel(); if (NAV.view === 'street') navStreet(true); else navView('street'); } };
  if ($('navKeyClear')) $('navKeyClear').onclick = () => { navKeySet(''); location.reload(); };
  $('navPlay').onclick = () => { if (NAV.street) return navAuto(!NAV.auto); const p = sc.pol[NAV.pol], s = (state.t - r.t0) * 3600; if (!state.playing && s >= p.arr + p.dwell_s) setTime(r.t0 + Math.max(0, p.dep - 20) / 3600); setPlaying(!state.playing, Number($('speed').value) || 1); };
  $('navRestart').onclick = () => navRoute(NAV.pol);
  document.querySelectorAll('#pNav .nav-show button').forEach(b => b.onclick = () => { const k = b.dataset.show; navHudKey = ''; NAV.camC = null;
    if (k === 'both') { NAV.race = true; navMapRoute(); navPanel(); } else { NAV.race = false; if (k !== NAV.pol && navHas(k)) navRoute(k); else { navMapRoute(); navPanel(); } } });
  if ($('navFree')) $('navFree').onchange = e => navFree(e.target.checked);
  navGraph();
  $('navExit').onclick = () => navExit();
}
const navDate = h => { const d = kst(h); return EN ? `${d.getUTCDate()} ${['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][d.getUTCMonth()]} ${d.getUTCFullYear()}` : `${d.getUTCFullYear()}년 ${d.getUTCMonth() + 1}월 ${d.getUTCDate()}일`; };
// the fire around the car at time t: distance to the nearest flame or burning cell (recorded front and the hazard input's
// flame, worst scenario), and the direction the model's next-hour new-burn probability lies from the burning cells
const NAV_DIRS = [['북', 'N', '↑'], ['북동', 'NE', '↗'], ['동', 'E', '→'], ['남동', 'SE', '↘'], ['남', 'S', '↓'], ['남서', 'SW', '↙'], ['서', 'W', '←'], ['북서', 'NW', '↖']];
function navFireNear(t, s, q, noDir) {
  const qi = inpIdx(t), zk = hzK(t), cells = new Set(qi >= 0 ? BURNING[qi] : []);
  if (zk >= 0) for (const i of hzField(zk, (t - HZ[zk].t0) * 3600, state.member).flame) cells.add(i);
  let best = Infinity, bu = 0, bv = 0, n = 0, nu = 0, nv = 0;
  for (const i of cells) { const [lon, lat] = cellCenter(i), u = uOf(lon), v = vOf(lat), d = Math.hypot((u - q.u) * KXr, (v - q.v) * KYr); if (d < best) { best = d; nu = u; nv = v; } bu += u; bv += v; n++; }
  let dir = null;
  if (!noDir && qi >= 0 && n && t - INP[qi] <= 1) { let wu = 0, wv = 0, w = 0; const Q = QF[qi];
    for (let i = 0; i < NCELL; i++) if (Q[i] >= .05) { const [lon, lat] = cellCenter(i); wu += uOf(lon) * Q[i]; wv += vOf(lat) * Q[i]; w += Q[i]; }
    if (w > 0) { const dx = (wu / w - bu / n) * KXr, dy = -(wv / w - bv / n) * KYr; if (Math.hypot(dx, dy) > .2) dir = NAV_DIRS[Math.round(((Math.atan2(dx, dy) * 180 / Math.PI + 360) % 360) / 45) % 8]; } }
  return { km: n ? best : null, dir, u: nu, v: nv };
}
let navHudKey = '';
// a car on route p at s seconds: where, flame in how many scenarios, heat, and its colour class
function navCarAt(p, s, k) {
  const q = navAt(p.dense, s), moving = s >= p.dep && s <= p.arr + p.dwell_s; let fl = 0, F = 0;
  if (k >= 0 && q.cell >= 0 && moving) for (let mi = 0; mi < 4; mi++) { if (hzFlame(k, mi, q.cell, s)) fl++; F = Math.max(F, hzFlux(k, mi, q.cell, s)); }
  return { q, moving, fl, F, cls: !moving ? 'idle' : fl || F >= p.limits.peak_kw_m2 ? 'fire' : F >= p.limits.peak_kw_m2 * .1 ? 'warn' : 'ok' };
}
const navOther = () => navPols().find(x => x !== NAV.pol);
const navRacing = () => NAV.race && !!navOther() && !NAV.street;
function navFrame(t) {
  if (!NAV.car) return;
  NAV.car.show = NAV.on && NAV.view === '2d'; NAV.car2.show = NAV.on && NAV.view === '2d' && navRacing(); if (!NAV.on) return;
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
  // race: the other route's car at the same moment
  const op = navRacing() ? sc.pol[navOther()] : null, o = op ? navCarAt(op, s, k) : null;
  if (o) { NAV.car2.u = o.q.u; NAV.car2.v = o.q.v; NAV.car2.el.className = `navcar alt ${o.cls}`; NAV.car2.el.querySelector('b').textContent = NAV_ROUTES.find(x => x[0] === navOther())[1]; }
  if (state.playing && s >= Math.max(p.arr + p.dwell_s, op ? op.arr + op.dwell_s : 0)) setPlaying(false);
  navGraphNow(s);
  const cur = NAV.steps.reduce((c, st, i) => st.s <= s + .5 ? i : c, -1);
  if (cur !== NAV.cur) { NAV.cur = cur; document.querySelectorAll('#pNav .nav-steps li').forEach((li, i) => li.classList.toggle('now', i === cur)); }
  const play = $('navPlay'); if (play) play.textContent = NAV.street ? (NAV.auto ? tr('자동 주행 정지', 'Stop driving') : tr('자동 주행', 'Drive')) : state.playing ? tr('일시정지', 'Pause') : s >= p.arr + p.dwell_s ? tr('다시 재생', 'Replay') : tr('재생', 'Play');
  const phase = s < p.dep ? tr('출발 전', 'Before departure') : s <= p.arr ? tr(`출발 후 ${fmtS(s - p.dep)}`, `${fmtS(s - p.dep)} after departure`) : s <= p.arr + p.dwell_s ? tr('대피소 도착 · 머무는 중', 'At the shelter') : tr('도착 완료', 'Arrived');
  // at the car's position now; whole-road contact is in the recorded check on the route card
  const stTxt = !moving ? (s < p.dep ? tr('출발 전', 'Not yet on the road') : tr('도착 · 이동 끝', 'Arrived · trip over')) : fl ? tr(`차 위치: 화염 속 · 화재 scenario ${fl}/4개`, `At the car: in flame · ${fl} of 4 fire scenarios`) : state_ === 'fire' ? tr('차 위치: 열 한도 초과', 'At the car: over the heat limit') : state_ === 'warn' ? tr('차 위치: 강한 복사 열', 'At the car: strong radiant heat') : tr('차 위치: 화염 없음 · 열 한도 이하', 'At the car: no flame · within heat limits');
  const fk = [recIdx(t), inpIdx(t), hzSig(t), (q.d * 10).toFixed(0)].join(':'); if (fk !== NAV.fireK) { NAV.fireK = fk; NAV.fire = navFireNear(t, s, q); } const fire = NAV.fire;
  const oTxt = o ? `${NAV_ROUTES.find(x => x[0] === navOther())[1]}: ${!o.moving ? (s < op.dep ? tr('출발 전', 'not yet on the road') : tr('도착', 'arrived')) : o.fl ? tr(`화염 속 (scenario ${o.fl}/4)`, `in flame (${o.fl} of 4)`) : o.cls === 'warn' ? tr('강한 복사 열', 'strong radiant heat') : tr('화염 없음', 'no flame')}` : '';
  const key = [navClock(t), phase, stTxt, q.d.toFixed(1), F.toPrecision(2), D.toPrecision(2), NAV.pol, fire.km, fire.dir?.[1], oTxt, o?.cls].join('|');
  if (key !== navHudKey) { navHudKey = key; const name = NAV_ROUTES.find(x => x[0] === NAV.pol)[1];
    $('navHud').innerHTML = `<div class="nh-st ${state_}">${stTxt}</div>${o ? `<div class="nh-race ${o.cls}"><i></i>${oTxt}</div>` : ''}
      <dl><dt>${name}</dt><dd>${q.d.toFixed(1)} / ${(p.length_m / 1000).toFixed(1)} km</dd>
        <dt>${tr('가장 가까운 불', 'Nearest fire')}</dt><dd>${fire.km == null ? '–' : fire.km < .05 ? tr('차 위치', 'at the car') : fire.km.toFixed(1) + ' km'}</dd>
        ${fire.dir ? `<dt>${tr('번지는 방향 (모델, 1시간)', 'Spreading toward (model, 1 h)')}</dt><dd>${fire.dir[2]} ${EN ? fire.dir[1] : fire.dir[0]}</dd>` : ''}
        <dt class="ph-x">${tr('차 위치 복사 열', 'Heat at the car')}</dt><dd class="ph-x">${navNum(F)} kW/m² <small>${tr('한도', 'limit')} ${lim.peak_kw_m2}</small></dd>
        <dt class="ph-x">${tr('누적 열 노출', 'Heat dose so far')}</dt><dd class="ph-x">${navNum(D)} kJ/m² <small>${tr('한도', 'limit')} ${fmtLim(lim.dose_kj_m2)}</small></dd></dl>`; }
  navFlames2D(t);
  if (NAV.street) navSvFrame(t, p, s, q);
  else if (NAV.view !== '2d') navMapFrame(t, p, q, state_, cut);
}

// ---- 2D navigation: flames as glowing, flickering points over the map (modelled flame and cells burning in the record) ----
function navGlowTex(stops) { const c = document.createElement('canvas'); c.width = c.height = 64; const x = c.getContext('2d'), g = x.createRadialGradient(32, 32, 0, 32, 32, 32);
  stops.forEach(([o, col]) => g.addColorStop(o, col)); x.fillStyle = g; x.fillRect(0, 0, 64, 64); return new THREE.CanvasTexture(c); }
function navFlames2D(t) {
  const on = NAV.on && NAV.view === '2d';
  if (!NAV.fl2) { if (!on) return;
    const mat = (tex, size) => new THREE.PointsMaterial({ map: tex, size, transparent: true, depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending, sizeAttenuation: true });
    const [a, b] = [cellCenter(0), cellCenter(1)], cw = Math.abs(sxU(uOf(b[0])) - sxU(uOf(a[0]))) || .1;
    NAV.fl2 = { cw, glow: new THREE.Points(new THREE.BufferGeometry(), mat(navGlowTex([[0, 'rgba(255,90,20,.9)'], [.45, 'rgba(255,60,10,.35)'], [1, 'rgba(255,40,0,0)']]), cw * 5)),
      core: new THREE.Points(new THREE.BufferGeometry(), mat(navGlowTex([[0, 'rgba(255,250,200,1)'], [.35, 'rgba(255,200,60,.9)'], [1, 'rgba(255,90,0,0)']]), cw * 2.2)) };
    NAV.fl2.glow.renderOrder = NAV.fl2.core.renderOrder = 20; scene.add(NAV.fl2.glow, NAV.fl2.core); }
  const F = NAV.fl2; F.glow.visible = F.core.visible = on; if (!on) return;
  const zk = hzK(t), qi = inpIdx(t), key = hzSig(t) + ':' + qi + ':' + state.member;
  if (key !== F.key) { F.key = key; const cells = new Set();
    if (zk >= 0) hzField(zk, (t - HZ[zk].t0) * 3600, state.member).flame.forEach(i => cells.add(i));
    if (qi >= 0 && t - INP[qi] <= 1) for (const i of BURNING[qi]) cells.add(i);
    const pos = []; for (const i of cells) { const [lon, lat] = cellCenter(i), u = uOf(lon), v = vOf(lat); pos.push(sxU(u), yAt(u, v) + .02, szV(v)); }
    for (const o of [F.glow, F.core]) { o.geometry.dispose(); o.geometry = new THREE.BufferGeometry(); o.geometry.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); } }
  const now = performance.now() / 1000, k = .5 + .5 * Math.sin(now * 8.5) * Math.sin(now * 4.7);
  F.glow.material.size = F.cw * (4.4 + 1.4 * k); F.glow.material.opacity = .7 + .3 * k; F.core.material.size = F.cw * (1.9 + .6 * (1 - k));
}

// ---- distance to the nearest fire along each route (a sample every 30 s of the trip), drawn under the route cards ----
function navDist(pol) {
  const sc = CASES[NAV.ci], key = sc.r.case + ':' + pol; NAV.dist ??= {}; if (NAV.dist[key]) return NAV.dist[key];
  const p = sc.pol[pol], out = [];
  for (let s = p.dep; s <= p.arr + 1e-6; s += 30) { const q = navAt(p.dense, s), f = navFireNear(sc.r.t0 + s / 3600, s, q, true); out.push({ m: (s - p.dep) / 60, km: f.km, fl: navCarAt(p, s, sc.k).fl > 0 }); }
  return NAV.dist[key] = out;
}
function navGraph() {
  const svg = $('navGraph'); if (!svg) return; const W = svg.clientWidth || 300, H = 120, pl = 30, pr = 8, pt = 8, pb = 18;
  const sc = CASES[NAV.ci], pols = navPols(), ser = pols.map(p => [p, navDist(p)]), mMax = Math.max(...ser.flatMap(([, d]) => d.map(x => x.m)), 1);
  const kMax = Math.min(8, Math.max(1, ...ser.flatMap(([, d]) => d.map(x => x.km ?? 0)))) * 1.1;
  const X = m => pl + m / mMax * (W - pl - pr), Y = km => pt + (1 - Math.min(km, kMax) / kMax) * (H - pt - pb);
  let g = `<line x1="${pl}" x2="${W - pr}" y1="${Y(0)}" y2="${Y(0)}" stroke="#e23b1d" stroke-width="1" stroke-dasharray="3 3"/>`;
  for (const v of [0, Math.round(kMax / 2), Math.floor(kMax)]) g += `<text x="${pl - 4}" y="${Y(v) + 3}" text-anchor="end">${v} km</text>`;
  for (const m of [0, Math.round(mMax / 2), Math.round(mMax)]) g += `<text x="${X(m)}" y="${H - 4}" text-anchor="middle">${m}${tr('분', ' min')}</text>`;
  for (const [pol, d] of ser) { const col = pol === 'full' ? '#1a73e8' : '#8a8f96', w = pol === NAV.pol ? 2.6 : 1.8;
    g += `<polyline fill="none" stroke="${col}" stroke-width="${w}" points="${d.filter(x => x.km != null).map(x => `${X(x.m).toFixed(1)},${Y(x.km).toFixed(1)}`).join(' ')}"/>`;
    g += d.filter(x => x.fl).map(x => `<circle cx="${X(x.m).toFixed(1)}" cy="${Y(0)}" r="3.2" fill="#e23b1d"/>`).join('');
  }
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.style.height = H + 'px';
  svg.innerHTML = g + `<line id="navGraphNow" y1="${pt}" y2="${H - pb}" stroke="#2a2724" stroke-width="1.2"/>`;
  NAV.graphX = s => X((s - sc.pol[NAV.pol].dep) / 60);
  svg.setAttribute('aria-label', tr('두 길의 가장 가까운 불까지 거리 그래프', 'Graph of the distance to the nearest fire on both routes'));
}
function navGraphNow(s) { const l = $('navGraphNow'); if (l && NAV.graphX) { const x = Math.max(30, NAV.graphX(s)); l.setAttribute('x1', x); l.setAttribute('x2', x); } }

// ---- 3D views: a real map (satellite photos on real terrain, MapLibre) with the same recorded data laid flat on it ----
// Photos: Esri World Imagery; roads and place names: Esri reference layers; elevation: Terrain Tiles (Mapzen, AWS Open Data).
// The photos were taken at another time, not during the fire. Needs an internet connection; without one the 2D map stays.
const NAV_ML = '__MAPLIBRE__';     // tools/build_viewer.py: vendor/maplibre-gl. (site, offline folder) or the pinned CDN copy, 4.7.1
const NAV_SRI = { js: 'sha384-SYKAG6cglRMN0RVvhNeBY0r3FYKNOJtznwA0v7B5Vp9tr31xAHsZC0DqkQ/pZDmj', css: 'sha384-MinO0mNliZ3vwppuPOUnGa+iq619pfMhLVUXfC4LHwSCvF9H+6P/KO4Q7qBOYV5V' };
// tile addresses: photos and roads on Esri's two host names (more connections at once), heights on AWS. Photos go to zoom 17
// (sharp near the car), road lines to 16
const NAV_TILES = { sat: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  roads: 'https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}',
  dem: 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png' };
const navLL = (u, v) => [W + u * (E - W), N - v * (N - S)];
const NAV_CHASE = { pitch: 62, zoom: 15.8 };
let navMapP = null;
function navView(v, quiet) {
  if (v !== 'chase' && NAV.free) navFree(false);
  NAV.view = v; NAV.hd = null; NAV.camC = null;
  if (state.mode !== '2d') setMode('2d');
  navStreet(v === 'street'); navReal(v === 'chase'); if (v === '2d') navFit();
  if (!quiet) navPanel();
}
function navReal(on) {
  NAV.real = on; mapEl.classList.toggle('nav3d', on);
  let el = $('navReal'); if (!on) { if (el) { el.classList.add('warm'); $('navPhoto').hidden = true; } return; }     // kept, hidden: ready next time
  el = navRealEl(); el.classList.remove('warm');
  $('navPhoto').hidden = !NAV.tileErr; $('navPhoto').textContent = tr('위성 사진·지형을 불러오지 못했습니다 · 인터넷 연결을 확인하세요', 'Satellite photos or terrain did not load · check the internet connection');
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
  navPrefetch(6);
  // the 3D map itself, built out of sight at the departure view: its first picture loads before anyone opens the view
  // and drawn once with the route and the fire, so its drawing programs are compiled now, not when a view opens
  navLib().then(() => { navRealEl(); return navMap(); }).then(map => { navMapRoute(); const sc = CASES[NAV.ci]; navFire(map, sc.r.t0 + sc.pol[NAV.pol].dep / 3600); map.triggerRepaint(); }).catch(() => { });
  if (navKey()) { NAV.sv ??= navSvSamples(CASES[NAV.ci].pol[NAV.pol].dense); NAV.svI ??= 0; navStreetWarm(); navResolve(); }
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
  const pts = []; for (const pol of navPols()) { let last = -1; for (const q of sc.pol[pol].dense) if (q.d - last >= .15) { last = q.d; pts.push(q); } }
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
    const ras = (k, attribution) => ({ type: 'raster', tiles: [NAV_TILES[k]], tileSize: 256, maxzoom: k === 'sat' ? 17 : 16, attribution });
    const fc = { type: 'FeatureCollection', features: [] }, d0 = CASES[NAV.ci].pol[NAV.pol].dense, first = d0[0], a0 = navAhead(d0, { ...first, i: 0 }, .25);
    const map = new maplibregl.Map({ container: 'navReal', interactive: false, attributionControl: false, maxPitch: 85, fadeDuration: 0,
      center: navLL(first.u, first.v), bearing: navBear(navLL(first.u, first.v), navLL(a0.u, a0.v)), ...NAV_CHASE, style: { version: 8,
        sources: { sat: ras('sat', 'Imagery © Esri, Maxar, Earthstar Geographics'), roads: ras('roads', 'Roads © Esri'),
          dem: { type: 'raster-dem', tiles: [NAV_TILES.dem], tileSize: 256, maxzoom: 15, encoding: 'terrarium', attribution: 'Elevation: Terrain Tiles (Mapzen, AWS Open Data)' },
          burn: { type: 'geojson', data: fc }, heat: { type: 'geojson', data: fc }, flame: { type: 'geojson', data: fc },
          alt: { type: 'geojson', data: fc }, route: { type: 'geojson', data: fc }, hits: { type: 'geojson', data: fc }, ends: { type: 'geojson', data: fc } },
        terrain: { source: 'dem', exaggeration: 1 },
        sky: { 'sky-color': '#8db7de', 'horizon-color': '#dfe8ee', 'fog-color': '#dfe6ea', 'sky-horizon-blend': .6, 'horizon-fog-blend': .7, 'fog-ground-blend': .75 },
        layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#d8d5cd' } },
          { id: 'sat', type: 'raster', source: 'sat' },
          { id: 'burn', type: 'fill', source: 'burn', paint: { 'fill-color': '#0e0a08', 'fill-opacity': .74, 'fill-antialias': false } },
          { id: 'heat', type: 'fill', source: 'heat', paint: { 'fill-color': ['get', 'c'], 'fill-opacity': ['get', 'o'], 'fill-antialias': false } },
          { id: 'flame', type: 'fill-extrusion', source: 'flame', paint: { 'fill-extrusion-color': ['get', 'c'], 'fill-extrusion-height': ['get', 'h'], 'fill-extrusion-opacity': .9, 'fill-extrusion-vertical-gradient': true } },
          { id: 'roads', type: 'raster', source: 'roads', paint: { 'raster-opacity': .8 } },
          { id: 'alt', type: 'line', source: 'alt', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#9aa0a6', 'line-width': 5, 'line-opacity': .9 } },
          { id: 'casing', type: 'line', source: 'route', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#ffffff', 'line-width': 10 } },
          { id: 'route', type: 'line', source: 'route', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#1a73e8', 'line-width': 6 } },
          { id: 'hits', type: 'line', source: 'hits', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#ff2a14', 'line-width': 7 } },
          { id: 'ends', type: 'circle', source: 'ends', paint: { 'circle-radius': 7, 'circle-color': ['get', 'c'], 'circle-stroke-color': '#1e1e1e', 'circle-stroke-width': 2.5, 'circle-pitch-alignment': 'map' } }] } });
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'top-right');
    map.once('idle', () => map.getContainer().querySelector('.maplibregl-ctrl-attrib')?.classList.remove('maplibregl-compact-show'));     // credits folded to the (i) button
    map.on('error', e => { if (!NAV.tileErr && (e.sourceId === 'sat' || e.sourceId === 'dem')) { NAV.tileErr = true; if (NAV.real) navReal(true); } });
    await new Promise(ok => map.isStyleLoaded() ? ok() : map.once('style.load', ok));
    const car = document.createElement('div'); car.className = 'navmlcar'; car.innerHTML = '<svg viewBox="0 0 24 24"><path d="M12 2 20 21 12 17 4 21z"/></svg>';
    NAV.mlCar = new maplibregl.Marker({ element: car, rotationAlignment: 'map', pitchAlignment: 'map' }).setLngLat(map.getCenter()).addTo(map);
    const car2 = car.cloneNode(true); car2.classList.add('alt');
    NAV.mlCar2 = new maplibregl.Marker({ element: car2, rotationAlignment: 'map', pitchAlignment: 'map' }).setLngLat(map.getCenter()).addTo(map);
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
  map.getSource('alt').setData(A && A.dense.length > 1 && NAV.race ? line(A.dense) : { type: 'FeatureCollection', features: [] });
  map.getSource('route').setData(line(P.dense));
  map.getSource('hits').setData({ type: 'FeatureCollection', features: runs.map(([a, b]) => line(P.dense.slice(a, b + 2))) });
  const a = P.dense[0], b = P.dense[P.dense.length - 1], pt = (q, c) => ({ type: 'Feature', properties: { c }, geometry: { type: 'Point', coordinates: navLL(q.u, q.v) } });
  map.getSource('ends').setData({ type: 'FeatureCollection', features: [pt(a, '#ffffff'), pt(b, '#d93025')] });
  for (const m of NAV.mlMarks || []) m.remove();
  NAV.mlMarks = (NAV.steps || []).filter(st => st.kind === 'fire').map(st => { const q = navAt(P.dense, st.s), e = document.createElement('div');
    e.className = 'navmlfire'; e.textContent = `${tr('화염', 'Flame')} ${navClock(sc.r.t0 + st.s / 3600)}`;
    return new maplibregl.Marker({ element: e, anchor: 'bottom', offset: [0, -6] }).setLngLat(navLL(q.u, q.v)).addTo(map); });
}
// free view in 3D: the map takes the mouse (drag, wheel, right-drag to tilt) and the camera stops following the car
function navFree(on) {
  NAV.free = on; const map = NAV.map; if (!map) return;
  for (const h of ['dragPan', 'scrollZoom', 'dragRotate', 'touchZoomRotate', 'touchPitch', 'keyboard', 'doubleClickZoom']) map[h]?.[on ? 'enable' : 'disable']();
  map.getContainer().classList.toggle('free', on); if (!on) NAV.camC = null;
}
// fire at time t as cell polygons laid on the terrain: recorded burned area dark (changes with the record), radiant heat
// orange and flame cells red (change with the hazard input). Polygons, not one picture: MapLibre 4.7.1 drapes an image
// source on terrain only inside a single map tile.
const navCell = (i, c, o) => { const r = (i / NC) | 0, k = i % NC;
  return { type: 'Feature', properties: { c, o }, geometry: { type: 'Polygon', coordinates: [[lat_(r, k), lat_(r, k + 1), lat_(r + 1, k + 1), lat_(r + 1, k), lat_(r, k)]] } }; };
function navFire(map, t) {
  const k = recIdx(t), zk = hzK(t), hk = hzSig(t), qi = inpIdx(t), fc = features => ({ type: 'FeatureCollection', features });
  if (k !== NAV.burnK) { NAV.burnK = k; const f = []; if (k >= 0) for (let i = 0; i < NCELL; i++) if (burnedAt(i, k)) f.push(navCell(i)); map.getSource('burn').setData(fc(f)); }
  const fk = hk + ':' + qi;
  if (fk !== NAV.heatK) { NAV.heatK = fk; const f = [], fl = new Set(), pts = [];
    if (zk >= 0) { const fld = hzField(zk, (t - HZ[zk].t0) * 3600, state.member); fld.flame.forEach(i => fl.add(i));
      for (let i = 0; i < NCELL; i++) { if (fl.has(i)) continue; const v = fluxV(fld.f[i]); if (v >= .4) f.push(navCell(i, `rgb(${inferno(.25 + .75 * v).map(Math.round)})`, .25 + smooth(.4, .8, v) * .5)); } }
    if (qi >= 0 && t - INP[qi] <= 1) for (const i of BURNING[qi]) fl.add(i);     // burning now in the record
    NAV.flCells = [...fl]; NAV.flT = 0;
    map.getSource('heat').setData(fc(f)); }
  // flames: each burning cell as a cluster of 4×4 thin columns, 15–120 m, yellow to red, redrawn a few times a second so they flicker
  const now = performance.now() / 1000;
  if (NAV.flCells && now - (NAV.flT || 0) > .16) { NAV.flT = now; const cols = ['#fff07a', '#ffd23a', '#ffa21f', '#ff7a14', '#f04a12', '#d81e10'], n = 4, out = [];
    for (const i of NAV.flCells) { const r = (i / NC) | 0, c = i % NC, A = lat_(r, c), Bq = lat_(r, c + 1), C = lat_(r + 1, c + 1), D = lat_(r + 1, c);
      const at = (x, y) => [A[0] + (Bq[0] - A[0]) * x + (D[0] - A[0]) * y + (A[0] - Bq[0] + C[0] - D[0]) * x * y, A[1] + (Bq[1] - A[1]) * x + (D[1] - A[1]) * y + (A[1] - Bq[1] + C[1] - D[1]) * x * y];
      for (let a = 0; a < n; a++) for (let b = 0; b < n; b++) { const x0 = (a + .18) / n, x1 = (a + .82) / n, y0 = (b + .18) / n, y1 = (b + .82) / n, rnd = Math.random(), edge = Math.min(a, b, n - 1 - a, n - 1 - b) === 0;
        const h = (edge ? 15 : 45) + rnd * (edge ? 50 : 75), col = cols[Math.min(5, Math.floor((1 - h / 120) * 4 + Math.random() * 2))];
        out.push({ type: 'Feature', properties: { c: col, h }, geometry: { type: 'Polygon', coordinates: [[at(x0, y0), at(x1, y0), at(x1, y1), at(x0, y1), at(x0, y0)]] } }); } }
    map.getSource('flame').setData({ type: 'FeatureCollection', features: out }); }
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
  // race: the other route's car, heading along its own road
  const c2 = NAV.mlCar2.getElement(), op = navRacing() ? CASES[NAV.ci].pol[navOther()] : null; c2.classList.toggle('off', !op);
  if (op) { const s2 = (t - CASES[NAV.ci].r.t0) * 3600, o = navCarAt(op, s2, CASES[NAV.ci].k), h2 = navLL(o.q.u, o.q.v), a2 = navAhead(op.dense, o.q, .25);
    NAV.mlCar2.setLngLat(h2).setRotation(navBear(h2, navLL(a2.u, a2.v))); for (const c of ['ok', 'warn', 'fire', 'idle']) c2.classList.toggle(c, c === o.cls); }
  // a calm camera: one fixed direction (start to end of the route), height and tilt; it drifts gently after the car instead
  // of turning with every bend
  const d = p.dense, e0 = navLL(d[0].u, d[0].v), e1 = navLL(d[d.length - 1].u, d[d.length - 1].v);
  NAV.camBear ??= navBear(e0, e1);
  // racing: aim between the two cars and pull back far enough to keep both in view
  let aim = here, zoom = 14.6; const rop = navRacing() ? CASES[NAV.ci].pol[navOther()] : null;
  if (rop) { const o = navAt(rop.dense, (t - CASES[NAV.ci].r.t0) * 3600), h2 = navLL(o.u, o.v), km = Math.hypot((h2[0] - here[0]) * 111.32 * Math.cos(here[1] * Math.PI / 180), (h2[1] - here[1]) * 110.57);
    aim = [(here[0] + h2[0]) / 2, (here[1] + h2[1]) / 2]; zoom = 14.6 - Math.log2(Math.max(1, km / 1.4)); }
  if (!NAV.camC || cut) { NAV.camC = aim.slice(); NAV.camZ = zoom; } else { NAV.camC[0] += (aim[0] - NAV.camC[0]) * .025; NAV.camC[1] += (aim[1] - NAV.camC[1]) * .025; NAV.camZ += (zoom - NAV.camZ) * .025; }
  if (NAV.free) return;
  map.jumpTo({ center: NAV.camC, bearing: NAV.camBear, pitch: 55, zoom: NAV.camZ, padding: { top: Math.round(map.getContainer().clientHeight * .15), bottom: 0, left: 0, right: 0 } });
}

// ---- 로드뷰: Kakao Roadview photos along the recorded route ----
// Keys: one Kakao JavaScript key per web address it is registered for (site/kakao-keys.js); a key pasted in the panel
// overrides it in that browser. Kakao serves only registered addresses, so road view does not work from file://.
// The photos were taken at other times; the fire shown (inset map, box) is the recorded data at the moment the car would
// be at that spot.
// Smooth stepping: the photo nearest every 30 m stop of both routes is looked up once, ahead of time (kept in the
// browser), and two road views take turns: the next photo loads, sharp, in the hidden one while the current one is
// shown, then they cross-fade and the view turns gently towards the road ahead.
const navKey = () => { try { return localStorage.getItem('wfgKakaoKey') || (window.WFG_KAKAO_KEYS || {})[location.origin] || ''; } catch { return (window.WFG_KAKAO_KEYS || {})[location.origin] || ''; } };
const navKeySet = v => { try { v ? localStorage.setItem('wfgKakaoKey', v) : localStorage.removeItem('wfgKakaoKey'); } catch { } };
let navKakaoP = null;
function navKakao() {
  return navKakaoP ??= new Promise((ok, no) => {
    if (window.kakao?.maps?.Roadview) return ok();
    if (!navKey()) return no(new Error('no key'));
    setTimeout(() => no(new Error('timeout')), 15000);
    navLoad('script', { src: `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(navKey())}&autoload=false` })
      .then(() => window.kakao?.maps?.load ? kakao.maps.load(ok) : no(new Error('no kakao.maps')), no);
  }).catch(e => { navKakaoP = null; throw e; });
}
// stops along the route every 30 m, each with the time the car is there
function navSvSamples(dense) { const out = []; let next = 0; for (const q of dense) if (q.d >= next) { out.push(q); next = q.d + .03; } if (out[out.length - 1] !== dense[dense.length - 1]) out.push(dense[dense.length - 1]); return out; }
const navSvMsg = t => { const m = $('navSvMsg'); if (m) m.textContent = t; };
// ---- photo IDs along both routes, looked up once (four at a time) and kept in this browser ----
const navIdKey = pol => `wfgPano:${B.id}:${CASES[NAV.ci].r.case}:${pol}`;
// baked list first (site/regions/<id>.pano.js, tools/bake_panos.mjs), then this browser's own lookups
function navIds(pol) {
  NAV.ids ??= {};
  if (!NAV.ids[pol]) { const bk = (window.WFG_PANO || {})[B.id]; let a = !NAV_BAKING && bk && bk.case === CASES[NAV.ci].r.case ? bk[pol] : null;
    if (!a && !NAV_BAKING) try { a = JSON.parse(localStorage.getItem(navIdKey(pol)) || 'null'); } catch { }
    const n = navSvSamples(CASES[NAV.ci].pol[pol].dense).length; NAV.ids[pol] = a && a.length === n ? a : new Array(n).fill(undefined); }
  return NAV.ids[pol];
}
const NAV_BAKING = /(^#|&)bakepano=1(&|$)/.test(location.hash);
window.__navPano = () => ({ case: NAV.ci >= 0 ? CASES[NAV.ci].r.case : null, pols: navPols(), ids: NAV.ids || {}, left: (NAV.resQ?.length || 0) + (NAV.resN || 0) });
function navResolve() {
  if (NAV.ci < 0 || !navKey()) return;
  navKakao().then(() => {
    NAV.rvc ??= new kakao.maps.RoadviewClient();
    // the chosen route from the current stop first, then the rest of it, then the other route
    const order = [];
    for (const pol of [NAV.pol, ...navPols().filter(x => x !== NAV.pol)]) { const ids = navIds(pol), from = pol === NAV.pol ? NAV.svI || 0 : 0;
      for (let k = 0; k < ids.length; k++) { const j = (from + k) % ids.length; if (ids[j] === undefined) order.push([pol, j]); } }
    NAV.resQ = order; NAV.resN ??= 0; for (let k = 0; k < 4; k++) navResolveNext();
  }, () => { });
}
function navResolveNext() {
  if (NAV.resN >= 4 || !NAV.resQ?.length) return;
  const [pol, j] = NAV.resQ.shift(), ids = navIds(pol); if (ids[j] !== undefined) return navResolveNext();
  const q = navSvSamples(CASES[NAV.ci].pol[pol].dense)[j], ll = navLL(q.u, q.v); NAV.resN++;
  NAV.rvc.getNearestPanoId(new kakao.maps.LatLng(ll[1], ll[0]), 50, id => {
    NAV.resN--; ids[j] = id ?? null; (NAV.resW ??= {})[pol] = true;
    if (pol === NAV.pol && NAV.svWait === j) { NAV.svWait = null; navSvShow(j); }
    if (!NAV.resQ.length || NAV.resQ.length % 40 === 0) navIdSave();
    navResolveNext(); });
}
function navIdSave() { for (const pol in NAV.ids || {}) try { localStorage.setItem(navIdKey(pol), JSON.stringify(NAV.ids[pol])); } catch { } }
// ---- the two road views ----
function navStreetEl() {
  let el = $('navStreet'); if (el) return el;
  el = document.createElement('div'); el.id = 'navStreet'; el.className = 'navstreet warm';
  el.innerHTML = `<div class="sv-view" id="navSvA"></div><div class="sv-view" id="navSvB"></div><div class="sv-view" id="navSvC"></div><div class="sv-haze" id="svHaze"></div><div class="sv-glow" id="svGlow"></div><div class="sv-danger" id="svDanger"></div><div class="sv-msg" id="navSvMsg"></div>
    <div class="sv-curtain"><i></i>${tr('로드뷰 준비 중…', 'Preparing road view…')}</div>
    <div class="sv-minibox"><canvas class="sv-mini" id="navMini" width="520" height="380" aria-label="${tr('작은 지도: 경로와 기록된 불', 'Inset map: routes and recorded fire')}"></canvas>
      <div class="sv-zoom"><button type="button" id="miniIn" title="${tr('확대', 'Zoom in')}">+</button><button type="button" id="miniOut" title="${tr('축소', 'Zoom out')}">−</button></div></div>
    <div class="sv-ctl"><button type="button" id="svBack" title="${tr('뒤로 (←, Shift: 크게)', 'Back (←, Shift: bigger step)')}">◀</button>
      <button type="button" id="svAuto"></button><button type="button" id="svFwd" title="${tr('앞으로 (→, Shift: 크게)', 'Forward (→, Shift: bigger step)')}">▶</button>
      <select id="svSpeed" aria-label="${tr('자동 주행 속도', 'Drive speed')}"><option value="1500">${tr('천천히', 'Slow')}</option><option value="1000" selected>${tr('보통', 'Normal')}</option><option value="650">${tr('빠르게', 'Fast')}</option></select><span id="svPos"></span></div>`;
  mapEl.appendChild(el);
  $('svBack').onclick = e => { navAuto(false); navSvStep(-(e.shiftKey ? 5 : 1)); };
  $('svFwd').onclick = e => { navAuto(false); navSvStep(e.shiftKey ? 5 : 1); };
  $('svAuto').onclick = () => navAuto(!NAV.auto);
  const zoom = f => { NAV.miniKm = Math.max(.8, Math.min(16, (NAV.miniKm || 2.4) * f)); };
  $('miniIn').onclick = () => zoom(1 / 1.6); $('miniOut').onclick = () => zoom(1.6);
  $('navMini').addEventListener('wheel', e => { e.preventDefault(); zoom(e.deltaY > 0 ? 1.25 : .8); }, { passive: false });
  navAuto(false);
  return el;
}
function navSvInit() {
  if (NAV.rvs) return;
  NAV.rvc ??= new kakao.maps.RoadviewClient();
  // one road view first (each costs Kakao a lot of work when it starts); the second, for the photo ahead, once the first
  // photo is on screen
  NAV.rvs = [navSvMake('navSvA')]; NAV.front = 0; NAV.rvs[0].el.classList.add('on');
}
function navSvMake(id) {
  const b = { el: $(id), id: null, ready: false };
  b.rv = new kakao.maps.Roadview(b.el);
  // Kakao drops a photo asked for before the view has started: ask again once it says it is ready
  kakao.maps.event.addListener(b.rv, 'init', () => { if (!b.inited) { b.inited = true; if (b.id != null && b.at) { b.rv.setPanoId(b.id, b.at); if (b.pan != null) b.rv.setViewpoint({ pan: b.pan, tilt: 0, zoom: 0 }); } } });
  const loaded = () => { clearTimeout(b.t); b.t = setTimeout(() => { b.ready = true; if (b.onReady) { const f = b.onReady; b.onReady = null; f(); } }, 120); };
  kakao.maps.event.addListener(b.rv, 'init', loaded); kakao.maps.event.addListener(b.rv, 'panoid_changed', loaded);
  setTimeout(() => b.rv.relayout(), 50);     // Kakao waits for a size before it loads photos
  return b;
}
// the hidden views, once the first photo is on screen: one for the photo ahead and one for the photo behind
function navSvSecond() { for (const id of ['navSvA', 'navSvB', 'navSvC']) if (!NAV.rvs.some(b => b.el.id === id)) NAV.rvs.push(navSvMake(id)); }
// build out of sight at the first stop, so the first photo is already there when the view opens
function navStreetWarm() {
  if (!navKey() || NAV.ci < 0) return;
  navStreetEl(); navKakao().then(() => { navSvInit(); if (NAV.sv && NAV.rvs[NAV.front].id == null) navSvGo(NAV.svI || 0, true); }, () => { });
}
function navStreet(on) {
  NAV.street = on; mapEl.classList.toggle('navsv', on);
  const el = on ? navStreetEl() : $('navStreet'); if (!el) return;
  el.classList.toggle('warm', !on); if (!on) { navAuto(false); return; }
  navAuto(false);
  if (!navKey()) return navSvMsg(tr('로드뷰 키가 없습니다. 오른쪽 패널에 카카오 JavaScript 키를 넣으세요.', 'No road view key. Add a Kakao JavaScript key in the panel on the right.'));

  navKakao().then(() => new Promise(ok => requestAnimationFrame(() => requestAnimationFrame(ok)))).then(() => { if (!NAV.street) return; navSvInit(); NAV.rvs.forEach(b => b.rv.relayout()); if (NAV.sv) navSvGo(NAV.svI || 0, true); navResolve(); },
    () => navSvMsg(tr(`카카오 로드뷰를 불러오지 못했습니다. 키와 등록된 주소(${location.origin}), 인터넷 연결을 확인하세요.`, `Could not load Kakao road view. Check the key, the registered address (${location.origin}) and the internet connection.`)));
}
// heading at stop j: along the route, 60 m ahead
function navSvHd(j) { const S = NAV.sv, q = S[j], d = CASES[NAV.ci].pol[NAV.pol].dense, a = navAhead(d, q, .06); return (navBear(navLL(q.u, q.v), navLL(a.u, a.v)) + 360) % 360; }
// step n stops (each to a different photo); the car's time follows
function navSvStep(n) {
  NAV.svDir = Math.sign(n) || 1; const S = NAV.sv; if (!S) return; const ids = NAV.rvs ? navIds(NAV.pol) : null, dir = Math.sign(n); let j = NAV.svI, left = Math.abs(n);
  while (left > 0 && j + dir >= 0 && j + dir < S.length) { j += dir; const id = ids?.[j]; if (id === null) continue; if (!ids || id === undefined || id !== ids[NAV.svI]) left--; }
  navSvGo(j);
}
// go to stop j: time, inset map, then the photo
function navSvGo(j, keepTime) {
  const S = NAV.sv; if (!S) return; j = Math.max(0, Math.min(S.length - 1, j)); NAV.svI = j;
  const sc = CASES[NAV.ci], q = S[j]; NAV.svHd = navSvHd(j);
  if (!keepTime) { NAV.svT = sc.r.t0 + q.ts / 3600; setTime(NAV.svT); }
  const pos = $('svPos'); if (pos) pos.textContent = `${q.d.toFixed(2)} / ${(sc.pol[NAV.pol].length_m / 1000).toFixed(1)} km`;
  if (NAV.rvs) navSvShow(j);
}
// show stop j's photo: from a hidden view that already holds it (cross-fade, sharp at once); a click whose photo is
// still loading waits for it a moment, then loads it in the visible view. Afterwards the hidden views load the photos
// on both sides (ahead and behind; while driving, the next two ahead).
function navSvShow(j) {
  const ids = navIds(NAV.pol), id = ids[j], F = NAV.rvs[NAV.front], others = NAV.rvs.filter(b => b !== F), pan = NAV.svHd;
  if (id === undefined) { NAV.svWait = j; navSvLookup(j); return; }
  if (id === null) { NAV.svMiss = j; navSvMsg(tr('이 지점 50 m 안에는 로드뷰 사진이 없습니다 · 앞뒤로 이동해 보세요', 'No road photo within 50 m of this point · step on or back')); NAV.stepDone?.(); return; }
  if (NAV.svMiss != null) { NAV.svMiss = null; navSvMsg(''); }
  const ll = navLL(NAV.sv[j].u, NAV.sv[j].v), at = new kakao.maps.LatLng(ll[1], ll[0]);
  const after = () => { NAV.stepDone?.(); navSvPreload(j); };
  if (!others.length) {     // only one view yet: load into it, then add the others
    if (F.id !== id) { F.id = id; F.at = at; F.pan = pan; F.ready = false; F.rv.setPanoId(id, at); F.rv.setViewpoint({ pan, tilt: 0, zoom: 0 }); }
    F.onReady = () => { if (NAV.svI !== j) return; $('navStreet')?.classList.add('ready'); navSvMsg(''); setTimeout(() => { navSvSecond(); after(); }, 300); };
    if (F.ready && F.id === id) F.onReady();
    return; }
  clearTimeout(NAV.svFall);
  if (F.id === id) { navSvTurn(F, pan); return after(); }
  // straight away, the current photo moves the way we go (forward: zooms in, back: out) while the next one gets ready
  const dir = NAV.svDir || 1; F.el.classList.remove('go-fwd', 'go-back'); void F.el.offsetWidth; if (F.id != null) F.el.classList.add(dir > 0 ? 'go-fwd' : 'go-back');
  const swap = Bk => { if (NAV.svI !== j) return; clearTimeout(NAV.svFall); Bk.rv.setViewpoint({ pan, tilt: 0, zoom: 0 }); Bk.el.classList.remove('go-fwd', 'go-back');
    Bk.el.classList.add('on'); F.el.classList.remove('on'); NAV.front = NAV.rvs.indexOf(Bk); navSvMsg(''); $('navStreet')?.classList.add('ready');
    setTimeout(() => F.el.classList.remove('go-fwd', 'go-back'), 450); after(); };
  let H = others.find(b => b.id === id);
  if (H && H.ready) return swap(H);
  if (!H) { H = others.find(b => b.onReady == null) || others[0]; H.id = id; H.at = at; H.pan = pan; H.ready = false; H.rv.relayout(); H.rv.setPanoId(id, at); H.rv.setViewpoint({ pan, tilt: 0, zoom: 0 }); }
  others.forEach(b => { if (b !== H) b.onReady = null; }); H.onReady = () => swap(H);
  if (!NAV.auto) NAV.svFall = setTimeout(() => {     // still not there after 1.5 s: load it in the visible view instead
    if (NAV.svI !== j || NAV.rvs[NAV.front] !== F) return; H.onReady = null; F.el.classList.remove('go-fwd', 'go-back');
    F.id = id; F.at = at; F.pan = pan; F.ready = false; F.rv.setPanoId(id, at); F.rv.setViewpoint({ pan, tilt: 0, zoom: 0 }); after(); }, 1500);
}
// the photos next to stop j into the hidden views, each facing the way it will be seen
function navSvPreload(j) {
  const ids = navIds(NAV.pol), cur = ids[j], F = NAV.rvs[NAV.front], others = NAV.rvs.filter(b => b !== F); if (!others.length) return;
  const near = (k, d) => { while (k >= 0 && k + d >= 0 && k + d < ids.length) { k += d; if (ids[k] && ids[k] !== cur && ids[k] !== ids[k - d]) return k; } return -1; };
  const dir = NAV.svDir || 1, a = near(j, NAV.auto ? 1 : dir), ks = (NAV.auto ? [a, near(a, 1)] : [a, near(j, -dir)]).filter(k => k >= 0);
  const free = others.filter(b => b.onReady == null && !ks.some(k => ids[k] === b.id));
  for (const k of ks) { if (others.some(b => b.id === ids[k])) continue; const b = free.shift(); if (!b) break;
    const ll = navLL(NAV.sv[k].u, NAV.sv[k].v); b.id = ids[k]; b.at = new kakao.maps.LatLng(ll[1], ll[0]); b.pan = navSvHd(k); b.ready = false;
    b.rv.setPanoId(b.id, b.at); b.rv.setViewpoint({ pan: b.pan, tilt: 0, zoom: 0 }); }
}
// a stop not looked up yet: ask now (ahead of the queue)
function navSvLookup(j) {
  const ids = navIds(NAV.pol), q = NAV.sv[j], ll = navLL(q.u, q.v);
  NAV.rvc.getNearestPanoId(new kakao.maps.LatLng(ll[1], ll[0]), 50, id => { if (ids[j] === undefined) ids[j] = id ?? null; if (NAV.svWait === j) { NAV.svWait = null; navSvShow(j); } });
}
// turn the view gently to the road's direction (shortest way round, 0.5 s)
function navSvTurn(b, pan) {
  cancelAnimationFrame(NAV.turnRaf); const v0 = b.rv.getViewpoint ? b.rv.getViewpoint() : { pan, tilt: 0 }, p0 = v0.pan || 0, d = ((pan - p0) % 360 + 540) % 360 - 180, t0 = performance.now();
  if (Math.abs(d) < 1) return;
  const f = now => { const k = Math.min(1, (now - t0) / 500), e = k * k * (3 - 2 * k); b.rv.setViewpoint({ pan: (p0 + d * e + 360) % 360, tilt: 0, zoom: v0.zoom || 0 }); if (k < 1) NAV.turnRaf = requestAnimationFrame(f); };
  NAV.turnRaf = requestAnimationFrame(f);
}
// automatic drive: the next photo every beat (1.5 / 1 / 0.65 s), already loaded in the hidden view
function navAuto(on) {
  NAV.auto = on; clearTimeout(NAV.autoT); NAV.stepDone = null;
  const b = $('svAuto'); if (b) b.textContent = on ? tr('■ 정지', '■ Stop') : tr('▶ 자동 주행', '▶ Drive');
  if (on) navAutoStep();
}
function navAutoStep() {
  if (!NAV.auto || !NAV.street) return;
  if (NAV.svI >= NAV.sv.length - 1) return navAuto(false);
  const gap = +($('svSpeed')?.value || 1000), t0 = performance.now(); $('navStreet')?.style.setProperty('--svgap', gap + 'ms');
  let next = () => { next = null; NAV.stepDone = null; NAV.autoT = setTimeout(navAutoStep, Math.max(0, gap - (performance.now() - t0))); };
  NAV.stepDone = () => next && next(); NAV.autoT = setTimeout(() => next && next(), NAV.rvs ? 6000 : gap);
  navSvStep(1);
}
// each frame in road view: follow time changes made elsewhere (directions list, timeline), the timeline's play drives,
// and the inset map is redrawn
function navSvFrame(t, p, s, q) {
  if (state.playing) { setPlaying(false); navAuto(true); }
  if (NAV.sv && NAV.svT != null && Math.abs(t - NAV.svT) > 1e-7) { NAV.svT = t; let j = 0, bd = 1e9;
    NAV.sv.forEach((x, i) => { const d = Math.abs(x.ts - s); if (d < bd) { bd = d; j = i; } }); if (j !== NAV.svI) navSvGo(j, true); }
  NAV.svT ??= t;
  navSvFire(t, p, s, q);
  navMini(p, q);
}
// inset map, heading up (the road ahead points up, as in the photo): the road map with the recorded fire (the 2D view's
// picture), both routes, the car and a pulsing ring on the nearest fire; + / − or the wheel zoom it
function navMini(p, q) {
  const c = $('navMini'); if (!c || !composite) return;
  const km = NAV.miniKm || 2.4, x = c.getContext('2d'), cw = c.width, ch = c.height, sw = km / KXr * TW, sh = sw * ch / cw, x0 = q.u * TW - sw / 2, y0 = q.v * TH - sh / 2;
  const P = (u, v) => [(u * TW - x0) * cw / sw, (v * TH - y0) * ch / sh], hd = (NAV.svView ?? NAV.svHd ?? 0) * Math.PI / 180;
  x.fillStyle = '#e8e4da'; x.fillRect(0, 0, cw, ch);
  x.save(); x.translate(cw / 2, ch / 2); x.rotate(-hd); x.translate(-cw / 2, -ch / 2);
  const mg = sw * .75, md = mg * cw / sw; x.drawImage(composite, x0 - mg, y0 - mg, sw + 2 * mg, sh + 2 * mg, -md, -md, cw + 2 * md, ch + 2 * md);     // wider than the box: corners stay filled when it turns
  const sc = CASES[NAV.ci], line = (d, w, col) => { x.beginPath(); d.forEach((pt, i) => { const [a, b] = P(pt.u, pt.v); i ? x.lineTo(a, b) : x.moveTo(a, b); }); x.lineWidth = w; x.strokeStyle = col; x.stroke(); };
  x.lineCap = x.lineJoin = 'round';
  const A = sc.pol[NAV.pol === 'full' ? 'travel_only' : 'full']; if (A) line(A.dense, 6, '#9aa0a6');
  line(p.dense, 11, '#fff'); line(p.dense, 7, '#1a73e8');
  const end = p.dense[p.dense.length - 1], [ex, ey] = P(end.u, end.v); x.beginPath(); x.arc(ex, ey, 9, 0, 7); x.fillStyle = '#d93025'; x.fill(); x.lineWidth = 3; x.strokeStyle = '#fff'; x.stroke();
  const f = NAV.svF; if (f && f.km != null) { const [fx, fy] = P(f.u, f.v), k = (performance.now() % 1400) / 1400;
    x.beginPath(); x.arc(fx, fy, 10 + 26 * k, 0, 7); x.lineWidth = 5; x.strokeStyle = `rgba(255,60,20,${1 - k})`; x.stroke();
    x.beginPath(); x.arc(fx, fy, 8, 0, 7); x.fillStyle = '#ff3c14'; x.fill(); }
  x.restore();
  if (f && f.km != null) {     // off the box: a red arrow on its edge points to it
    const [fx, fy] = P(f.u, f.v), dx = fx - cw / 2, dy = fy - ch / 2, c_ = Math.cos(-hd), s_ = Math.sin(-hd), rx = dx * c_ - dy * s_, ry = dx * s_ + dy * c_;
    if (Math.abs(rx) > cw / 2 - 14 || Math.abs(ry) > ch / 2 - 40) { const k = Math.min((cw / 2 - 26) / Math.abs(rx || 1e-9), (ch / 2 - 52) / Math.abs(ry || 1e-9)), ax = cw / 2 + rx * k, ay = ch / 2 + ry * k;
      x.save(); x.translate(ax, ay); x.rotate(Math.atan2(ry, rx)); x.beginPath(); x.moveTo(18, 0); x.lineTo(-8, -12); x.lineTo(-8, 12); x.closePath(); x.fillStyle = '#ff3c14'; x.fill(); x.lineWidth = 3; x.strokeStyle = '#fff'; x.stroke(); x.restore(); } }
  // the car, always pointing up; N shows where north is
  x.save(); x.translate(cw / 2, ch / 2); x.beginPath(); x.moveTo(0, -16); x.lineTo(11, 12); x.lineTo(0, 6); x.lineTo(-11, 12); x.closePath(); x.fillStyle = '#1a73e8'; x.fill(); x.lineWidth = 3; x.strokeStyle = '#fff'; x.stroke(); x.restore();
  x.save(); x.translate(cw - 34, 30); x.rotate(-hd); x.font = '700 18px system-ui, sans-serif'; x.textAlign = 'center'; x.textBaseline = 'middle';
  x.beginPath(); x.arc(0, 0, 17, 0, 7); x.fillStyle = 'rgba(255,255,255,.9)'; x.fill(); x.fillStyle = '#d93025'; x.fillText('N', 0, 1); x.restore();
  x.font = '600 20px system-ui, sans-serif'; x.fillStyle = 'rgba(255,255,255,.88)'; x.fillRect(0, ch - 32, cw, 32); x.fillStyle = '#3c3a36';
  x.fillText(tr(`진행 방향 위 · 빨간 고리: 가장 가까운 불 · ${km < 1 ? Math.round(km * 1000) + ' m' : km.toFixed(1) + ' km'} 폭`, `heading up · red ring: nearest fire · ${km < 1 ? Math.round(km * 1000) + ' m' : km.toFixed(1) + ' km'} wide`), 10, ch - 10);
}
// ---- the fire around the road view: all from the recorded fire and the model, laid over the photo (taken on another day) ----
// 1 glow on the side of the photo where the nearest fire is, stronger when closer; 2 haze when the fire is close or the
// heat at the car is high (an effect, not real smoke); 3 distance, side and trend, and the model's chance of spread onto
// the road ahead in the next hour; 5 where the other route's car would be at this moment.
const NAV_SIDE = rel => { const a = ((rel % 360) + 540) % 360 - 180, A = Math.abs(a);
  return A <= 30 ? tr('앞', 'ahead') : A >= 150 ? tr('뒤', 'behind') : (a > 0 ? tr('오른쪽', 'right') : tr('왼쪽', 'left')) + (A < 70 ? tr(' 앞', ' ahead') : A > 110 ? tr(' 뒤', ' behind') : ''); };
function navSvFire(t, p, s, q) {
  const sc = CASES[NAV.ci], k = sc.k, F_ = NAV.rvs?.[NAV.front], vp = F_?.rv?.getViewpoint?.();
  NAV.svView = vp && vp.pan != null ? vp.pan : NAV.svHd;
  const key = [recIdx(t), inpIdx(t), hzSig(t), (q.d * 20).toFixed(0), NAV.pol].join(':');
  if (key !== NAV.svFk) { NAV.svFk = key;
    const f = navFireNear(t, s, q, true), f0 = navFireNear(t - 1 / 60, s - 60, navAt(p.dense, s - 60), true), me = navCarAt(p, s, k);
    // the road in the next 1 km: the model's highest chance of fire there in the next hour (latest input, if within the hour)
    const qi = inpIdx(t); let risk = null;
    if (qi >= 0 && t - INP[qi] <= 1) { risk = 0; for (const pt of p.dense) if (pt.d >= q.d && pt.d <= q.d + 1 && pt.cell >= 0) risk = Math.max(risk, QF[qi][pt.cell]); }
    const op = sc.pol[navOther() || ''], o = op ? navCarAt(op, s, k) : null;
    NAV.svF = f; NAV.svFo = { f0, me, risk, o, op }; }
  const f = NAV.svF, { f0, me, risk, o, op } = NAV.svFo, lim = p.limits, glow = $('svGlow'), haze = $('svHaze'), box = $('svDanger'); if (!glow) return;
  const brg = f.km != null ? (Math.atan2((f.u - q.u) * KXr, -(f.v - q.v) * KYr) * 180 / Math.PI + 360) % 360 : null, rel = brg == null ? 0 : brg - NAV.svView;
  // 1 glow: within 4 km, full at the car
  const near = f.km == null ? 0 : Math.max(0, Math.min(1, 1 - f.km / 5)), hot = me.moving ? Math.min(1, me.F / lim.peak_kw_m2) : 0, a = Math.max(.25 + .75 * near, hot, me.fl ? 1 : 0) * (near > 0 || hot > 0 ? 1 : 0);
  const r = rel * Math.PI / 180, gx = 50 + 50 * Math.sin(r), gy = 50 - 50 * Math.cos(r);
  glow.style.background = a > .02 ? `radial-gradient(ellipse 75% 70% at ${gx.toFixed(1)}% ${gy.toFixed(1)}%, rgba(255,70,20,${(.75 * a).toFixed(3)}), rgba(255,120,30,${(.35 * a).toFixed(3)}) 40%, rgba(255,120,30,0) 72%)` : 'none';
  glow.classList.toggle('pulse', a > .6);
  // 2 haze: kept light; strongest only in flame
  const h = Math.max(near > .6 ? (near - .6) / .4 * .35 : 0, hot * .45, me.fl ? .5 : 0); haze.style.opacity = h.toFixed(3);
  // 3 + 5 the panel
  const trend = f.km == null || f0.km == null ? '' : f.km < f0.km - .02 ? `<em class="up">${tr('▲ 가까워지는 중', '▲ getting closer')}</em>` : f.km > f0.km + .02 ? `<em class="dn">${tr('▼ 멀어지는 중', '▼ falling behind')}</em>` : `<em>${tr('거리 비슷', 'about the same')}</em>`;
  const st = !me.moving ? (s < p.dep ? tr('출발 전', 'not yet on the road') : tr('도착', 'arrived')) : me.fl ? tr('지금 화염 속', 'in flame now') : me.cls === 'warn' ? tr('강한 복사 열', 'strong radiant heat') : tr('화염 없음 · 열 한도 이하', 'no flame · within heat limits');
  const on = NAV_ROUTES.find(x => x[0] === navOther())?.[1], ost = o ? (!o.moving ? (s < op.dep ? tr('출발 전', 'not yet on the road') : tr('도착', 'arrived')) : o.fl ? tr('지금 화염 속', 'in flame now') : o.cls === 'warn' ? tr('강한 복사 열', 'strong radiant heat') : tr('화염 없음', 'no flame')) : '';
  const html = `<div class="big ${me.cls}">${f.km == null ? tr('주변에 기록된 불 없음', 'No recorded fire nearby') : f.km < .05 ? tr('불이 차 위치에', 'Fire at the car') : `${tr('가장 가까운 불', 'Nearest fire')} <b>${f.km < 1 ? Math.round(f.km * 1000) + ' m' : f.km.toFixed(1) + ' km'}</b> · ${NAV_SIDE(rel)}`}</div>
    <div class="row">${trend}<span class="st ${me.cls}">${tr('차 위치', 'At the car')}: ${st}</span></div>
    ${risk != null && me.moving ? `<div class="row risk">${tr('앞 1 km 도로 · 다음 1시간 번질 확률 (모델)', 'Road 1 km ahead · chance of spread in the next hour (model)')} <b class="${risk >= .3 ? 'hi' : risk >= .05 ? 'mid' : ''}">${risk < .005 ? '<1' : Math.round(risk * 100)}%</b></div>` : ''}
    ${o ? `<div class="row ghost ${o.cls}">${tr(`${on}이었다면 지금`, `On the ${on} now`)}: <b>${ost}</b></div>` : ''}
    <div class="note">${tr('사진은 평상시 · 불빛·연기는 기록·모델 자료로 그린 표시', 'Photos from an ordinary day · glow and haze drawn from the recorded and model data')}</div>`;
  if (html !== NAV.svHtml) { NAV.svHtml = html; box.innerHTML = html; }
}
