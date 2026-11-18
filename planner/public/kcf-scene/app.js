/* KCF replay — one 3D scene, three zoom levels (region, place, road).
 *
 * Plain classic script (no modules, no fetch): it must run from GitHub Pages and from a folder opened with file://.
 * All data comes from window.KCF.{scene, terrain, basemap, fonts}, written by research/kcf-replay/scene/build_*.py
 * from committed files. MapLibre reads tiles and glyphs through the "kcf://" protocol handler below; nothing leaves
 * the page. Design and data contract: research/kcf-replay/scene/DESIGN.md.
 */
(function () {
  'use strict';

  var KCF = window.KCF || {};
  var S = KCF.scene, TER = KCF.terrain, BM = KCF.basemap, FONTS = KCF.fonts;
  var T0 = window.KCF_T0 || 0;
  var timings = { scripts_parsed_ms: Math.round(performance.now() - T0) };
  var Q = new URLSearchParams(location.search);
  var LITE = Q.has('lite');
  var TOUR = Q.has('tour');

  function fatal(msg) {
    var el = document.getElementById('loadingMsg');
    if (el) { el.textContent = msg; el.style.color = '#ff6b6b'; }
    throw new Error(msg);
  }
  if (!window.maplibregl) fatal('vendor/maplibre-gl.js did not load');
  if (!S) fatal('data/scene.js did not load');
  if (!TER) fatal('data/terrain.js did not load');
  if (!FONTS) fatal('data/fonts.js did not load (the map labels cannot show clocks without it)');
  if (!BM && window.console) console.warn('data/basemap.js did not load: no roads or water on the map');
  function webglInfo() {
    try {
      var c = document.createElement('canvas'), gl = c.getContext('webgl2') || c.getContext('webgl');
      if (!gl) return null;
      var ext = gl.getExtension('WEBGL_debug_renderer_info');
      return { renderer: String(ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)) };
    } catch (e) { return null; }
  }
  var GL = webglInfo();
  if (!GL) fatal('This browser cannot draw 3D (WebGL is off or blocked: hardware acceleration off, remote desktop or a VM). Turn on hardware acceleration, or play the 90-s recording kcf_scene_tour_90s.mp4 in this folder.');
  // a software renderer (no GPU) draws each frame in seconds: switch to lite unless ?full
  var SOFT = /SwiftShader|llvmpipe|softpipe|Basic Render|Software/i.test(GL.renderer);
  if (SOFT && !Q.has('full')) LITE = true;
  timings.renderer = GL.renderer; timings.software_gl = SOFT; timings.lite = LITE;

  // ------------------------------------------------------------------ constants and paths
  var SRC = Object.assign({
    per_place: 'research/kcf-replay/per_place.csv',
    named_timeline: 'research/kcf-replay/named_places_timeline.csv',
    sources_md: 'research/kcf-replay/SOURCES.md',
    results_md: 'research/kcf-replay/RESULTS.md',
    fire_discs: 'research/kcf-replay/fire_discs.json',
    hotspot_rule: 'research/kcf-replay/HOTSPOT_RULE.md',
    replay_py: 'research/kcf-replay/replay.py',
    analyze_py: 'research/kcf-replay/analyze.py',
    planner_cache_dir: 'research/kcf-replay/planner_cache/RUNNING_8h',
    score: 'research/kcf-replay/score.json',
    scene_js: 'planner/public/kcf-scene/data/scene.js',
    build_scene: 'research/kcf-replay/scene/build_scene.py'
  }, S.src || {});
  var SCENE_JS = SRC.scene_js;
  var H = S.horizon_s || 28800, DWELL = S.dwell_s || 120, NK = (S.issues_s || []).length || 13;
  var STEP_TXT = {
    LEAVE_NOW: ['LEAVE NOW', '위험구역 (R(5 h) ≥ distance); "leave now" is this replay\'s reading'],
    PREPARE_VULNERABLE_FIRST: ['VULNERABLE FIRST', '잠재적 위험구역 (R(8 h) ≥ distance): vulnerable people first'],
    NONE: ['no step', 'outside 8 h reach']
  };
  var STATE_TXT = {
    LATEST_SAFE_DEPARTURE: 'latest safe departure',
    NOT_CUT_WITHIN_H: 'not cut within 8 h',
    INSIDE_KNOWN_FIRE_AREA: 'inside known fire area',
    NO_SAFE_DEPARTURE: 'no safe departure'
  };
  var COLORS = { leave: '#ffd60a', vuln: '#5ac8fa', none: '#e5e5ea', inside: '#3a3a3c', insideStroke: '#ff453a',
    fire: '#ff6a2a', fireOld: '#a8241a', closed: '#b48cff', route: '#5ef0ff', shelter: '#30d158', fail: '#ff2d55' };
  var EXAG = { region: 1.8, place: 1.4, drive: 1.0 };

  // ------------------------------------------------------------------ state
  var st = {
    s: 0, standin: S.default_standin || 'RUNNING', view: 'region', place: null, drive: null,
    check: null, playing: false, sourcesOpen: false
  };
  var placeById = {}, placeByName = {};
  var CAT_KO = { nursing_home: '요양시설', social_facility: '사회복지시설', village: '마을', hamlet: '마을' };
  var CAT_EN = { nursing_home: 'nursing home', social_facility: 'social facility', village: 'village', hamlet: 'hamlet' };
  S.places.forEach(function (p, i) {
    p._i = i; placeById[p.id] = p;
    p.label = p.name || ((CAT_KO[p.category] || p.category) + ' (이름 없음)');
    if (p.name) placeByName[p.name] = placeByName[p.name] || p;
  });
  var cellIndex = {};
  Object.keys(S.roadCells).forEach(function (r) {
    var m = new Map(); S.roadCells[r].cells.forEach(function (c, i) { m.set(c, i); }); cellIndex[r] = m;
  });
  var discS = S.discs.rows.map(function (d) { return d[0]; }); // sorted

  // ------------------------------------------------------------------ small helpers
  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function srcAttr(path, detail) {
    return ' data-src="' + esc(path) + '" data-detail="' + esc(detail || '') + '" title="' + esc(path + (detail ? ' — ' + detail : '')) + '"';
  }
  function kOf(s) { return Math.max(0, Math.min(NK - 1, Math.floor(s / 3600))); }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  // scene second -> KST clock text; 12:00 KST at s = 0
  function kst(s, withSec) {
    var tot = Math.floor(12 * 3600 + s), day = 25 + Math.floor(tot / 86400);
    var r = ((tot % 86400) + 86400) % 86400;
    var t = pad(Math.floor(r / 3600)) + ':' + pad(Math.floor(r / 60) % 60) + (withSec ? ':' + pad(r % 60) : '');
    return day === 25 ? t : t + ' (' + day + ' Mar)';
  }
  function issueLabel(k) { return (S.issue_kst && S.issue_kst[k]) || kst(3600 * k); }
  // CSV text "03-25 18:47" -> "18:47"; "03-26 00:12" -> "00:12 (26 Mar)"
  function csvClock(t) {
    if (!t) return '';
    var m = /^(\d\d)-(\d\d) (\d\d:\d\d)/.exec(t);
    if (!m) return t;
    return m[2] === '25' ? m[3] : m[3] + ' (' + Number(m[2]) + ' Mar)';
  }
  function fmtInt(n) { return Number(n).toLocaleString('en-US'); }
  function b64ToBuf(s) {
    var bin = atob(s), u = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
    return u.buffer;
  }
  function lowerBound(arr, x) { var lo = 0, hi = arr.length; while (lo < hi) { var m = (lo + hi) >> 1; if (arr[m] < x) lo = m + 1; else hi = m; } return lo; }
  function upperBound(arr, x) { var lo = 0, hi = arr.length; while (lo < hi) { var m = (lo + hi) >> 1; if (arr[m] <= x) lo = m + 1; else hi = m; } return lo; }
  function hourly(placeId, k, standin) { var h = S.hourly[standin || st.standin]; return h && h[placeId] ? h[placeId][k] : null; }
  function routeOf(placeId, k, standin) { var r = S.routes[standin || st.standin]; return r && r[placeId] ? r[placeId][k] : null; }
  function routesAvailable(standin) { return !!(S.routes[standin || st.standin]); }
  function stepClass(h) { return h.state === 'INSIDE_KNOWN_FIRE_AREA' ? 'INSIDE' : h.step; }
  function placeClock(h, short) {
    if (!h) return '';
    if (h.state === 'LATEST_SAFE_DEPARTURE') return csvClock(h.lsd);
    if (short && h.state === 'INSIDE_KNOWN_FIRE_AREA') return 'inside fire area';
    return STATE_TXT[h.state] || h.state;
  }
  function csvIssue(k) { var t = 12 + k; return t < 24 ? '03-25 ' + pad(t) + ':00' : '03-26 ' + pad(t - 24) + ':00'; } // per_place.csv issue_kst text
  function csvDetail(h, col, standin, k) {
    return 'line ' + (h.row + 1) + ', column ' + col + ' (standin = ' + (standin || st.standin) + ', horizon = 8h, issue_kst = ' + csvIssue(k) + ')';
  }
  // the 13 issue times, the 8 h horizon and the 30-min planner grid are fixed by the frozen rule / the cache generator
  function issueSpan(k) { return '<span' + srcAttr(SRC.hotspot_rule, 'Issue times: 2025-03-25 03:00 … 15:00 UTC = 12:00 … 24:00 KST (scene.js issue_kst[' + k + '])') + '>' + esc(issueLabel(k)) + '</span>'; }
  function horizonSpan() { return '<span' + srcAttr(SRC.hotspot_rule, 'horizon H = 8 h (Latest safe departure; replay.py HORIZONS)') + '>8 h</span>'; }
  function shelterSpan(id, h, k) { return '<span' + srcAttr(SRC.per_place, h ? csvDetail(h, 'shelter_name / shelter_id', null, k) : 'shelter_name / shelter_id') + '>' + esc(shelterName(id)) + '</span>'; }
  var APP_JS = 'planner/public/kcf-scene/app.js';
  function standinInfo(name) { return (S.standins && S.standins[name || st.standin]) || { label: name || st.standin }; }
  // R(h) arms: three labelled stand-ins (HOTSPOT_RULE.md) and two MEASURED arms (MEASURED_RULE.md, one class per issue hour)
  var CLS_TXT = { all: 'all hours', quiet: 'quiet class (prior-3 h spread < 1 km)', slow: 'slow class (prior-3 h spread 1–3 km)',
    running: 'running class (prior-3 h spread ≥ 3 km)', 'g<10': 'gust < 10 m/s class', 'g10-20': 'gust 10–20 m/s class',
    'g>=20': 'gust ≥ 20 m/s class' };
  var ARM_STATE = { NOT_CUT_WITHIN_H: 'not cut in 8 h', INSIDE_KNOWN_FIRE_AREA: 'inside fire area', NO_SAFE_DEPARTURE: 'no safe departure' };
  function isArm(name) { return standinInfo(name).kind === 'measured'; }
  function armClass(name, k) { var si = standinInfo(name); return si.classes ? si.classes[k] : null; }
  function kmTxt(m) { return (m / 1000).toFixed(1); }
  function shortLabel(name) { var si = standinInfo(name); return si.kind === 'measured' ? si.label + (si.provisional ? ' (PROVISIONAL)' : '') : (si.label || name || st.standin); }
  // "MEASURED · running class (…) · R(5 h) 7.6 km, R(8 h) 10.0 km" for the issue-k screen
  function firesTxt(c) { return c && c.n_fires ? (c.n_fires === 28 ? 'R from all 28 calibration fires' : 'R from ' + c.n_fires + ' of the 28 calibration fires') : ''; }
  function armText(name, k) {
    var si = standinInfo(name), c = armClass(name, k);
    if (!c) return shortLabel(name);
    return shortLabel(name) + ' · ' + (CLS_TXT[c.cls] || c.cls) + ' at ' + issueLabel(k) + ' · R(5 h) ' + kmTxt(c.r5_m) + ' km, R(8 h) ' + kmTxt(c.r8_m) + ' km (' + firesTxt(c) + ')';
  }
  function armSrc(name, k) {
    var si = standinInfo(name);
    if (si.kind !== 'measured') return srcAttr(SRC.hotspot_rule, 'R(h) stand-ins: ' + (si.basis || ''));
    var c = armClass(name, k) || {};
    return srcAttr(SRC.results_md, 'section 2b, line ' + si.results_line + ': R(5 h), R(8 h) ' + si.r_text + '; class picked: ' + si.basis + ' (rule ' + (si.src || SRC.measured_rule) + '; R and n_fires (' + (c.n_fires || '?') + ') from ' + (si.numbers || SRC.margin_numbers) + ' table, all28, alpha 0.10; class at ' + issueLabel(k) + ' = ' + (c.cls || '?') + ' by ' + (si.code || SRC.measured_arms_py) + ')');
  }
  function gustSpan(name, k) {
    var c = armClass(name, k);
    if (!c || c.gust_ms == null) return '';
    var si = standinInfo(name), kma = si.gust_source === 'KMA ASOS';
    return ' · <span' + srcAttr(si.gust_hours || SRC.gust_hours, 'kst_stamp ' + (12 + k) + ', fwd8.fire_wide_max (' + (kma ? 'KMA ASOS hourly gust, maximum over the stations present; primary series' : 'ERA5, maximum over five points; PROVISIONAL, secondary series') + ')') + '>next-8 h max gust ' + c.gust_ms.toFixed(1) + ' m/s (' + (kma ? 'KMA' : 'ERA5') + ')</span>';
  }

  // ------------------------------------------------------------------ geometry
  function circleRing(lon, lat, r, n) {
    var ring = [], dlat = r / 111320, dlon = r / (111320 * Math.cos(lat * Math.PI / 180));
    for (var i = 0; i < n; i++) { var a = 2 * Math.PI * i / n; ring.push([lon + dlon * Math.cos(a), lat + dlat * Math.sin(a)]); }
    ring.push(ring[0]);
    return ring;
  }
  function distM(a, b) {
    var R = 6371008.8, la1 = a[1] * Math.PI / 180, la2 = b[1] * Math.PI / 180, dla = la2 - la1, dlo = (b[0] - a[0]) * Math.PI / 180;
    var h = Math.sin(dla / 2) * Math.sin(dla / 2) + Math.cos(la1) * Math.cos(la2) * Math.sin(dlo / 2) * Math.sin(dlo / 2);
    return 2 * R * Math.asin(Math.sqrt(h));
  }
  function routeCoords(region, rt) {
    var E = S.routeEdges[region], out = [];
    rt.e.forEach(function (ei, j) {
      var c = E[ei].c;
      for (var i = (j === 0 ? 0 : 1); i < c.length; i++) out.push(c[i]);
    });
    return out;
  }

  // ------------------------------------------------------------------ re-walk (analyze.py recheck, edge by edge)
  // Departing at `depart` (seconds after the issue hour), every edge segment must be left strictly before its road
  // cell closes (t + D*z_end < b), the dwell [arr, arr + DWELL] must end before the shelter cell closes, and
  // arr + DWELL <= H. Closures: the issue-k screen's own, close[standin][region][k].
  function rewalk(place, k, depart, standin) {
    standin = standin || st.standin;
    var rt = routeOf(place.id, k, standin);
    if (!rt) return null;
    var region = place.region, E = S.routeEdges[region], idx = cellIndex[region];
    var close = S.close[standin][region][k];
    var t = depart, times = [t];
    function closeOf(cell) { var i = idx.get(cell); return i === undefined ? -1 : close[i]; }
    for (var j = 0; j < rt.e.length; j++) {
      var e = E[rt.e[j]], D = e.D;
      for (var q = 0; q < e.seg.length; q++) {
        var cell = e.seg[q][0], end = e.seg[q][1], b = closeOf(cell);
        if (b >= 0 && t + D * end >= b) {
          return { ok: false, depart: depart, edge: j, edges: rt.e.length, cell: cell, closeAt: b, leaveAt: t + D * end, times: times, rt: rt, k: k, standin: standin };
        }
      }
      t += D; times.push(t);
    }
    var bs = closeOf(rt.sh_cell);
    if (bs >= 0 && t + DWELL >= bs) return { ok: false, depart: depart, shelterCell: true, cell: rt.sh_cell, closeAt: bs, arrival: t, times: times, rt: rt, k: k, standin: standin };
    return { ok: t + DWELL <= H, overH: !(t + DWELL <= H), depart: depart, arrival: t, shelterClose: bs, times: times, rt: rt, k: k, standin: standin, edges: rt.e.length };
  }

  // ------------------------------------------------------------------ MapLibre setup
  maplibregl.addProtocol('kcf', function (params) {
    var u = params.url.slice('kcf://'.length);
    if (u.indexOf('dem/') === 0) {
      var key = u.slice(4);
      return Promise.resolve({ data: b64ToBuf(TER.tiles[key] || TER.flat) });
    }
    if (u.indexOf('glyphs/') === 0) {
      var parts = decodeURIComponent(u.slice(7)).split('/');
      var stack = parts[0].split(',')[0], range = (parts[1] || '').replace('.pbf', '');
      var g = FONTS && FONTS.glyphs && FONTS.glyphs[stack] && FONTS.glyphs[stack][range];
      return Promise.resolve({ data: g ? b64ToBuf(g) : new ArrayBuffer(0) });
    }
    return Promise.reject(new Error('kcf: unknown resource ' + u));
  });

  var FONT_FAMILY = (FONTS && FONTS.ui && FONTS.ui.family) || 'KCF Pretendard';
  function loadUiFont() {
    if (!FONTS || !FONTS.ui || !FONTS.ui.faces || !window.FontFace) return Promise.resolve();
    var all = FONTS.ui.faces.map(function (f) {
      try {
        var ff = new FontFace(FONT_FAMILY, 'url(' + f.src + ')', { weight: f.weight || '400', style: 'normal' });
        document.fonts.add(ff);
        return ff.load().catch(function () {});
      } catch (e) { return Promise.resolve(); }
    });
    return Promise.all(all);
  }

  function emptyFC() { return { type: 'FeatureCollection', features: [] }; }

  function buildFireFC() {
    var n = LITE ? 20 : 32;
    return { type: 'FeatureCollection', features: S.discs.rows.map(function (d, i) {
      return { type: 'Feature', id: i, properties: { s: d[0], src: d[4] }, geometry: { type: 'Polygon', coordinates: [circleRing(d[1], d[2], d[3], n)] } };
    }) };
  }
  function buildCellsFC() {
    var feats = [];
    Object.keys(S.roadCells).forEach(function (region) {
      var rc = S.roadCells[region], close = S.close[st.standin][region];
      rc.cells.forEach(function (c, i) {
        var props = { region: region, cell: c };
        for (var k = 0; k < NK; k++) props['k' + k] = close[k][i];
        feats.push({ type: 'Feature', properties: props, geometry: { type: 'Polygon', coordinates: [rc.ring[i]] } });
      });
    });
    return { type: 'FeatureCollection', features: feats };
  }
  function buildPlacesFC(k) {
    return { type: 'FeatureCollection', features: S.places.map(function (p) {
      var h = hourly(p.id, k) || {};
      var clock = placeClock(h, true);
      var lsdMin = 9999;
      if (h.state === 'LATEST_SAFE_DEPARTURE') { var m = /(\d\d):(\d\d)$/.exec(h.lsd); if (m) lsdMin = (h.lsd.slice(3, 5) === '26' ? 1440 : 0) + Number(m[1]) * 60 + Number(m[2]); }
      return { type: 'Feature', properties: {
        id: p.id, name: p.label, step: h.step || 'NONE', inside: h.state === 'INSIDE_KNOWN_FIRE_AREA' ? 1 : 0,
        label: p.label + '\n' + clock, named: p.named ? 1 : 0, vul: p.vulnerable ? 1 : 0,
        sort: p.named ? 0 : (h.state === 'LATEST_SAFE_DEPARTURE' ? 1 + lsdMin : 5000)
      }, geometry: { type: 'Point', coordinates: [p.lon, p.lat] } };
    }) };
  }

  var bounds0 = [[128.40, 36.22], [129.50, 36.62]];
  var map;
  try { map = new maplibregl.Map({
    container: 'map',
    bounds: bounds0,
    fitBoundsOptions: { padding: { top: 80, bottom: 150, left: 40, right: 40 } },
    pitch: 52, bearing: -8, maxPitch: 85, keyboard: false,
    pixelRatio: LITE ? 1 : Math.min(window.devicePixelRatio || 1, 2),
    fadeDuration: TOUR ? 0 : 200,
    attributionControl: { compact: true },
    localIdeographFontFamily: "'" + FONT_FAMILY + "', 'Apple SD Gothic Neo', 'Malgun Gothic', 'Noto Sans KR', 'Noto Sans CJK KR', sans-serif",
    canvasContextAttributes: { preserveDrawingBuffer: TOUR },
    style: {
      version: 8,
      glyphs: 'kcf://glyphs/{fontstack}/{range}.pbf',
      sources: {
        dem: { type: 'raster-dem', tiles: ['kcf://dem/{z}/{x}/{y}'], tileSize: TER.tileSize || 256, minzoom: TER.minzoom || 5,
          maxzoom: TER.maxzoom || 12, encoding: TER.encoding || 'terrarium', attribution: TER.attribution || 'Terrain Tiles (Mapzen, AWS Open Data)' },
        demHs: { type: 'raster-dem', tiles: ['kcf://dem/{z}/{x}/{y}'], tileSize: TER.tileSize || 256, minzoom: TER.minzoom || 5,
          maxzoom: TER.maxzoom || 12, encoding: TER.encoding || 'terrarium' },
        water: { type: 'geojson', data: (BM && BM.water) || emptyFC(), attribution: '© OpenStreetMap contributors (ODbL)' },
        roads: { type: 'geojson', data: (BM && BM.roads) || emptyFC() },
        towns: { type: 'geojson', data: emptyFC() },
        fire: { type: 'geojson', data: emptyFC(), buffer: 64, tolerance: 0.5 },
        cells: { type: 'geojson', data: emptyFC(), buffer: 16 },
        places: { type: 'geojson', data: emptyFC() },
        route: { type: 'geojson', data: emptyFC() },
        walk: { type: 'geojson', data: emptyFC() },
        mark: { type: 'geojson', data: emptyFC() }
      },
      layers: [
        { id: 'bg', type: 'background', paint: { 'background-color': '#151a22' } },
        { id: 'relief', type: 'color-relief', source: 'demHs', paint: { 'color-relief-opacity': 1, 'color-relief-color': ['interpolate', ['linear'], ['elevation'],
          0, '#0b1a2a', 0.5, '#1f2e26', 120, '#26372c', 300, '#2f3d30', 500, '#3b4436', 750, '#4a4a3e', 1000, '#57534a', 1300, '#615e58'] } },
        { id: 'hillshade', type: 'hillshade', source: 'demHs', paint: { 'hillshade-exaggeration': 0.75, 'hillshade-shadow-color': 'rgba(0,0,0,0.62)', 'hillshade-highlight-color': 'rgba(255,255,240,0.22)', 'hillshade-accent-color': 'rgba(0,0,0,0.25)', 'hillshade-illumination-direction': 315 } },
        { id: 'water-fill', type: 'fill', source: 'water', filter: ['all', ['==', ['geometry-type'], 'Polygon'], ['!=', ['get', 's'], '']], paint: { 'fill-color': '#173350', 'fill-opacity': 0.9 } },
        { id: 'water-line', type: 'line', source: 'water', filter: ['==', ['geometry-type'], 'LineString'], paint: { 'line-color': '#2b5d8c', 'line-width': ['interpolate', ['linear'], ['zoom'], 9, 0.5, 14, 2] } },
        { id: 'roads-minor', type: 'line', source: 'roads', filter: ['all', ['!=', ['get', 'k'], 'major_road'], ['!=', ['get', 'k'], 'highway'], ['!=', ['get', 'k'], 'rail']], minzoom: 10.5, paint: { 'line-color': '#7d8593', 'line-opacity': 0.75, 'line-width': ['interpolate', ['linear'], ['zoom'], 10.5, 0.4, 15, 2.4, 18, 7] } },
        { id: 'roads-major', type: 'line', source: 'roads', filter: ['any', ['==', ['get', 'k'], 'major_road'], ['==', ['get', 'k'], 'highway']], paint: { 'line-color': '#b9c0cb', 'line-opacity': 0.85, 'line-width': ['interpolate', ['linear'], ['zoom'], 8, 0.6, 15, 3.6, 18, 10] } },
        { id: 'fire-old', type: 'fill', source: 'fire', filter: ['<', ['get', 's'], -1e9], paint: { 'fill-color': COLORS.fireOld, 'fill-opacity': ['case', ['==', ['get', 'src'], 'AHI'], 0.42, 0.8] } },
        { id: 'fire-new', type: 'fill', source: 'fire', filter: ['<', ['get', 's'], -1e9], paint: { 'fill-color': COLORS.fire, 'fill-opacity': ['case', ['==', ['get', 'src'], 'AHI'], 0.45, 0.9] } },
        { id: 'fire-new-line', type: 'line', source: 'fire', filter: ['<', ['get', 's'], -1e9], paint: { 'line-color': '#ffb48a', 'line-width': 1.2, 'line-opacity': 0.8 } },
        { id: 'cells-fill', type: 'fill', source: 'cells', filter: ['==', ['get', 'cell'], -1], paint: { 'fill-color': COLORS.closed, 'fill-opacity': 0.32 } },
        { id: 'cells-line', type: 'line', source: 'cells', filter: ['==', ['get', 'cell'], -1], paint: { 'line-color': '#cdb3ff', 'line-width': ['interpolate', ['linear'], ['zoom'], 9, 0.5, 14, 1.6], 'line-opacity': 0.9 } },
        { id: 'route-casing', type: 'line', source: 'route', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#05080c', 'line-width': ['interpolate', ['linear'], ['zoom'], 10, 5, 16, 13, 19, 22] } },
        { id: 'route-line', type: 'line', source: 'route', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': COLORS.route, 'line-width': ['interpolate', ['linear'], ['zoom'], 10, 2.5, 16, 8, 19, 14] } },
        { id: 'walk-line', type: 'line', source: 'walk', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#ffffff', 'line-width': ['interpolate', ['linear'], ['zoom'], 10, 2.5, 16, 6, 19, 10] } },
        { id: 'mark-cell', type: 'line', source: 'mark', filter: ['==', ['get', 'kind'], 'failcell'], paint: { 'line-color': COLORS.fail, 'line-width': 4 } },
        { id: 'towns', type: 'symbol', source: 'towns', maxzoom: 12.5, layout: { 'text-field': ['get', 'name'], 'text-font': ['Noto Sans Regular'], 'text-size': 12, 'text-allow-overlap': false }, paint: { 'text-color': '#aeb7c6', 'text-halo-color': '#0b0e14', 'text-halo-width': 1.4 } },
        { id: 'places-circle', type: 'circle', source: 'places', paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 8, ['case', ['==', ['get', 'named'], 1], 5, 3.4], 13, ['case', ['==', ['get', 'named'], 1], 9, 7]],
          'circle-color': ['case', ['==', ['get', 'inside'], 1], COLORS.inside, ['match', ['get', 'step'], 'LEAVE_NOW', COLORS.leave, 'PREPARE_VULNERABLE_FIRST', COLORS.vuln, COLORS.none]],
          'circle-stroke-color': ['case', ['==', ['get', 'inside'], 1], COLORS.insideStroke, '#0b0d12'],
          'circle-stroke-width': ['case', ['==', ['get', 'vul'], 1], 2.5, 1.2], 'circle-pitch-alignment': 'viewport' } },
        { id: 'mark-shelter', type: 'circle', source: 'mark', filter: ['==', ['get', 'kind'], 'shelter'], paint: { 'circle-radius': 9, 'circle-color': COLORS.shelter, 'circle-stroke-color': '#04150a', 'circle-stroke-width': 2.5 } },
        { id: 'mark-vehicle', type: 'circle', source: 'mark', filter: ['==', ['get', 'kind'], 'vehicle'], paint: { 'circle-radius': 10, 'circle-color': '#ffffff', 'circle-stroke-color': '#0b0d12', 'circle-stroke-width': 3, 'circle-pitch-alignment': 'viewport', 'circle-pitch-scale': 'viewport' } },
        { id: 'mark-place', type: 'circle', source: 'mark', filter: ['==', ['get', 'kind'], 'place'], paint: { 'circle-radius': 13, 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-color': '#ffffff', 'circle-stroke-width': 2.5 } },
        { id: 'places-label', type: 'symbol', source: 'places', layout: {
          'text-field': ['get', 'label'], 'text-font': ['Noto Sans Regular'],
          'text-size': ['interpolate', ['linear'], ['zoom'], 8, ['case', ['==', ['get', 'named'], 1], 12.5, 10.5], 13, 14],
          'text-variable-anchor': ['left', 'right', 'top', 'bottom'], 'text-radial-offset': 0.7, 'text-justify': 'auto',
          'symbol-sort-key': ['get', 'sort'], 'text-padding': 2 },
          paint: { 'text-color': ['case', ['==', ['get', 'named'], 1], '#ffffff', '#d7dde6'], 'text-halo-color': '#0b0e14', 'text-halo-width': 1.6 } },
        { id: 'mark-label', type: 'symbol', source: 'mark', filter: ['==', ['get', 'kind'], 'shelter'], layout: { 'text-field': ['get', 'label'], 'text-font': ['Noto Sans Regular'], 'text-size': 13, 'text-anchor': 'top', 'text-offset': [0, 1.0], 'text-allow-overlap': true }, paint: { 'text-color': '#b6f5c6', 'text-halo-color': '#04150a', 'text-halo-width': 1.8 } }
      ],
      terrain: { source: 'dem', exaggeration: EXAG.region },
      sky: { 'sky-color': '#0d1220', 'horizon-color': '#3b2a26', 'fog-color': '#151a22', 'fog-ground-blend': 0.55, 'horizon-fog-blend': 0.7, 'sky-horizon-blend': 0.6, 'atmosphere-blend': 0 }
    }
  }); } catch (e) { fatal('The 3D map could not start (' + (e && e.message) + '). Turn on hardware acceleration, or play the 90-s recording kcf_scene_tour_90s.mp4 in this folder.'); }
  // lite: one DEM-derived layer fewer (no colour relief), cheaper drive camera
  if (LITE) map.once('styledata', function () { if (map.getLayer('relief')) map.removeLayer('relief'); map.setPaintProperty('bg', 'background-color', '#27322b'); });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'bottom-right');
  map.on('load', function () { var a = document.querySelector('.maplibregl-ctrl-attrib'); if (a) a.classList.remove('maplibregl-compact-show'); });
  map.on('error', function (e) { if (window.console) console.warn('map error', e && e.error && e.error.message); });

  // ------------------------------------------------------------------ layer state updates
  var lastFireKey = null, lastCellKey = null, lastPlacesKey = null;
  // fire: discs strictly before `x` (scene seconds). recent = the last hour before x
  function setFire(x) {
    var key = lowerBound(discS, x) + ':' + lowerBound(discS, x - 3600);
    if (key === lastFireKey) return;
    lastFireKey = key;
    map.setFilter('fire-old', ['<', ['get', 's'], x - 3600]);
    map.setFilter('fire-new', ['all', ['>=', ['get', 's'], x - 3600], ['<', ['get', 's'], x]]);
    map.setFilter('fire-new-line', ['all', ['>=', ['get', 's'], x - 3600], ['<', ['get', 's'], x]]);
  }
  function setFireOpacity(drive) {
    map.setPaintProperty('fire-old', 'fill-opacity', ['case', ['==', ['get', 'src'], 'AHI'], drive ? 0.28 : 0.42, drive ? 0.55 : 0.8]);
    map.setPaintProperty('fire-new', 'fill-opacity', ['case', ['==', ['get', 'src'], 'AHI'], drive ? 0.3 : 0.45, drive ? 0.6 : 0.9]);
  }
  // road cells of the issue-k screen closed by `ds` seconds after the issue hour
  function setCells(k, ds) {
    var key = k + ':' + Math.floor(ds / 30);
    if (key === lastCellKey) return;
    lastCellKey = key;
    var f = ['all', ['>=', ['get', 'k' + k], 0], ['<=', ['get', 'k' + k], ds]];
    map.setFilter('cells-fill', f);
    map.setFilter('cells-line', f);
  }
  var fontsLoaded = false;
  function setPlaces(k) {
    if (!fontsLoaded) return;
    var key = st.standin + ':' + k;
    if (key === lastPlacesKey) return;
    lastPlacesKey = key;
    map.getSource('places').setData(buildPlacesFC(k));
  }

  // ------------------------------------------------------------------ UI: static parts
  function renderStandinBtn() {
    var si = standinInfo(), k = kOf(st.drive ? 3600 * st.drive.k : st.s), c = armClass(st.standin, k);
    if (si.kind === 'measured' && c) {
      $('standinBtn').innerHTML = 'R(h): ' + esc(shortLabel()) + ' · ' + esc((CLS_TXT[c.cls] || c.cls).replace(/ \(.*\)$/, '')) + ' at ' + esc(issueLabel(k)) + ': ' + kmTxt(c.r5_m) + ' km at 5 h, ' + kmTxt(c.r8_m) + ' km at 8 h' +
        ' <em>frozen margin: R from ' + (c.n_fires === 28 ? 'all 28' : c.n_fires + ' of 28') + ' calibration fires' + (si.provisional ? ' · ERA5 gusts only' : '') + ' · R to change</em>';
      $('standinBtn').setAttribute('data-src', SRC.results_md);
      $('standinBtn').setAttribute('data-detail', 'section 2b (MEASURED arms): ' + si.r_text + '; ' + si.basis + '; n_fires per class: ' + (si.numbers || SRC.margin_numbers));
      $('standinBtn').title = 'R(h) arm ' + si.label + ' (' + (si.src || SRC.measured_rule) + '; R per class from ' + (si.numbers || SRC.margin_numbers) + '). Click or press R to change.';
    } else {
      $('standinBtn').innerHTML = 'R(h) stand-in: ' + esc(si.label || st.standin) + ' <em>a stand-in, not the frozen R(h) · R to change</em>';
      $('standinBtn').setAttribute('data-src', SRC.hotspot_rule);
      $('standinBtn').setAttribute('data-detail', 'R(h) stand-ins table; ' + (si.basis || ''));
      $('standinBtn').title = 'R(h) stand-in (HOTSPOT_RULE.md), not the frozen R(h). Click or press R to change.';
    }
    $('standinBtn').classList.toggle('arm', si.kind === 'measured');
    $('standinBtn').classList.toggle('prov', !!si.provisional);
  }
  function renderBookmarks() {
    var html = '<span class="label">RESULTS.md §4:</span>';
    (S.named || []).forEach(function (n, i) {
      html += '<button type="button" data-id="' + esc(n.id) + '" title="' + esc(n.name) + ' (key ' + (i + 1) + ')"><kbd>' + (i + 1) + '</kbd>' + esc(n.name) + '</button>';
    });
    $('bookmarks').innerHTML = html;
    Array.prototype.forEach.call($('bookmarks').querySelectorAll('button'), function (b) {
      b.addEventListener('click', function () { selectPlace(b.getAttribute('data-id')); });
    });
  }
  function renderTicks() {
    var html = '';
    for (var k = 0; k < NK; k++) html += '<span style="left:' + (100 * k / (NK - 1)) + '%">' + esc(issueLabel(k)) + '</span>';
    $('sliderTicks').innerHTML = html;
    $('sliderTicks').setAttribute('data-src', SRC.hotspot_rule);
    $('sliderTicks').setAttribute('data-detail', 'Issue times: 2025-03-25 03:00 … 15:00 UTC = 12:00 … 24:00 KST (scene.js issue_kst)');
  }
  function renderLegend() {
    var si = standinInfo();
    $('legend').setAttribute('data-src', SRC.hotspot_rule);
    $('legend').setAttribute('data-detail', 'disc radii 375 m / 1 km / 2 km, 375 m routing cells, closure = T + h* where R(h*) = distance, steps R(5 h) and R(8 h)');
    $('legend').innerHTML =
      '<div class="li"><span class="sw" style="background:' + COLORS.fireOld + '"></span>known fire area: detections before the issue hour (solid: FIRMS 375 m / 1 km; light: AHI "fire within 2 km")</div>' +
      '<div class="li"><span class="sw" style="background:' + COLORS.fire + '"></span>… detected in the last hour before it</div>' +
      '<div class="li"><span class="sw" style="background:' + COLORS.closed + ';opacity:.8"></span>road cell (375 m) closed by this screen (when R(h) reaches it; recomputed every hour)</div>' +
      '<div class="li"><span class="dot" style="background:' + COLORS.leave + '"></span>위험구역 (5 h), read here as "leave now"</div>' +
      '<div class="li"><span class="dot" style="background:' + COLORS.vuln + '"></span>잠재적 위험구역 (8 h): vulnerable first</div>' +
      '<div class="li"><span class="dot" style="background:' + COLORS.none + '"></span>no step</div>' +
      '<div class="li"><span class="dot" style="background:' + COLORS.inside + ';border-color:' + COLORS.insideStroke + '"></span>inside the known fire area</div>' +
      '<div class="li"><span class="sw" style="background:' + COLORS.route + '"></span>witness road · <span style="color:' + COLORS.shelter + '">●</span> shelter</div>' +
      '<div class="note" style="margin-top:4px">Label: latest safe departure under ' + esc(shortLabel()) + ', 8 h horizon.</div>';
  }

  // ------------------------------------------------------------------ UI: summary card (level 1)
  function renderSummary() {
    var k = kOf(st.s), dc = S.discCounts && S.discCounts[k];
    var counts = { LEAVE_NOW: 0, PREPARE_VULNERABLE_FIRST: 0, NONE: 0 }, inside = 0, lsd = 0;
    S.places.forEach(function (p) {
      var h = hourly(p.id, k); if (!h) return;
      counts[h.step] = (counts[h.step] || 0) + 1;
      if (h.state === 'INSIDE_KNOWN_FIRE_AREA') inside++;
      if (h.state === 'LATEST_SAFE_DEPARTURE') lsd++;
    });
    var csvd = 'count of the ' + S.places.length + ' rows with standin = ' + st.standin + ', horizon = 8h, issue_kst = ' + csvIssue(k);
    var html = '<h3>Screen issued at ' + issueSpan(k) + ' KST</h3>';
    if (isArm()) html += '<div class="armline' + (standinInfo().provisional ? ' prov' : '') + '"><span' + armSrc(st.standin, k) + '>' + esc(armText(st.standin, k)) + '</span>' + gustSpan(st.standin, k) + '</div>';
    if (dc) html += '<div class="kv"><span class="muted">known fire area</span><span' + srcAttr(SRC.fire_discs, 'discs with t_utc strictly before ' + (S.issue_utc ? S.issue_utc[k] : issueLabel(k)) + ' (counted in ' + SCENE_JS + ' discCounts[' + k + '])') + '>' + fmtInt(dc.total) + ' detections (AHI ' + fmtInt(dc.AHI) + ' · FIRMS ' + fmtInt(dc.FIRMS) + ')</span></div>';
    html += '<div class="kv" style="margin-top:4px">' +
      '<span class="step LEAVE_NOW">LEAVE NOW*</span><span' + srcAttr(SRC.per_place, csvd + ', government_step = LEAVE_NOW') + '>' + counts.LEAVE_NOW + ' of ' + S.places.length + ' places</span>' +
      '<span class="muted" style="padding-left:10px">… inside fire area</span><span' + srcAttr(SRC.per_place, csvd + ', departure_state = INSIDE_KNOWN_FIRE_AREA (all of them have government_step LEAVE_NOW)') + '>of which ' + inside + '</span>' +
      '<span class="step PREPARE_VULNERABLE_FIRST">VULNERABLE FIRST</span><span' + srcAttr(SRC.per_place, csvd + ', government_step = PREPARE_VULNERABLE_FIRST') + '>' + counts.PREPARE_VULNERABLE_FIRST + '</span>' +
      '<span class="step NONE">no step</span><span' + srcAttr(SRC.per_place, csvd + ', government_step = NONE') + '>' + counts.NONE + '</span>' +
      '<span class="muted">leave-by clock</span><span' + srcAttr(SRC.per_place, csvd + ', departure_state = LATEST_SAFE_DEPARTURE') + '>' + lsd + ' places</span></div>';
    html += '<div class="note" style="margin-top:6px"><span' + srcAttr(SRC.sources_md, '위험구역 = "leave now" is NOT stated in the sources; this replay\'s reading (also RESULTS.md section 7)') + '>* 위험구역 (5 h reach), read here as "leave now" — this replay\'s reading.</span> <span' + srcAttr(SRC.results_md, 'section 3 table (8 h): leave now / vulnerable first / none') + '>Step counts equal RESULTS.md §3 (8 h)</span>; inside and leave-by counts are counted from per_place.csv. Click a place, or a bookmark above.</div>';
    $('summary').innerHTML = html;
  }

  // ------------------------------------------------------------------ UI: clock, slider marks
  function renderClock() {
    var k = kOf(st.s);
    $('clock').setAttribute('data-src', st.drive ? SCENE_JS : APP_JS);
    $('clock').setAttribute('data-detail', st.drive ? 'routes.' + st.drive.standin + '["' + st.drive.place.id + '"][' + st.drive.k + ']: departure ld + edge travel ticks' : 'slider position (presentation clock, 12:00 + slider seconds); the screen shown is the issue hour at or before it');
    if (st.drive) {
      $('clock').textContent = kst(3600 * st.drive.k + st.drive.tau, true) + ' KST';
      $('clockNote').innerHTML = 'driving the witness road of the ' + issueSpan(st.drive.k) + ' screen';
    } else {
      $('clock').textContent = kst(st.s) + ' KST';
      $('clockNote').innerHTML = 'showing the screen issued at <b>' + issueSpan(k) + '</b> · ' + horizonSpan() + ' horizon';
    }
    $('slider').value = String(st.drive ? Math.min(43200, 3600 * st.drive.k + st.drive.tau) : st.s);
  }
  function parseKstToS(t) { // "18:00", "~20:40", "00:07 (26 Mar)" -> scene seconds or null
    var m = /(\d{1,2}):(\d\d)/.exec(t || ''); if (!m) return null;
    var h = Number(m[1]), mi = Number(m[2]);
    var s = (h - 12) * 3600 + mi * 60;
    if (/\(26 Mar\)|\b03-26\b/.test(t) || h < 12) s += 24 * 3600;
    return s;
  }
  function renderSliderMarks() {
    var marks = [];
    if (st.place && !st.drive) {
      var p = st.place, k = kOf(st.s), h = hourly(p.id, k);
      var rep = S.reported && S.reported[p.id];
      if (rep && rep.rows) rep.rows.forEach(function (r) {
        var s = parseKstToS(r.kst); if (s == null || s < 0 || s > 43200) return;
        marks.push({ s: s, cls: 'rep', attr: srcAttr(SRC.sources_md, 'line ' + r.line + ': reported ' + r.kst + ' ' + (r.what || '') + ' (' + (r.source || '') + ')'), text: '◆', tick: true });
      });
      if (h && h.state === 'LATEST_SAFE_DEPARTURE') {
        var m = /(\d\d):(\d\d)$/.exec(h.lsd), s2 = m ? (Number(m[1]) - 12) * 3600 + Number(m[2]) * 60 + (h.lsd.slice(3, 5) === '26' ? 86400 : 0) : null;
        if (s2 != null && s2 <= 43200) marks.push({ s: s2, cls: 'lsd', attr: srcAttr(SRC.per_place, csvDetail(h, 'latest_safe_departure_kst', null, k)), text: 'leave by ' + csvClock(h.lsd), first: true });
      }
    }
    // two rows; the leave-by label takes the lower row, reported labels avoid each other
    var W = ($('sliderWrap').clientWidth || 1000), rows = [[], []], html = '';
    marks.sort(function (a, b) { return (b.first ? 1 : 0) - (a.first ? 1 : 0) || a.s - b.s; });
    marks.forEach(function (mk) {
      if (mk.tick) { html += '<span class="m rep tick" style="left:' + (100 * mk.s / 43200) + '%;top:22px"' + mk.attr + '>' + mk.text + '</span>'; return; }
      var x = W * mk.s / 43200, wpx = 7 * mk.text.length + 10, row = 0;
      for (row = 0; row < 2; row++) if (!rows[row].some(function (r) { return Math.abs(r - x) < (wpx + 20) / 2 + 40; })) break;
      if (row > 1) row = 1;
      rows[row].push(x);
      html += '<span class="m ' + mk.cls + '" style="left:' + (100 * mk.s / 43200) + '%;top:' + (row === 0 ? 4 : 0) + 'px"' + mk.attr + '>' + esc(mk.text) + '</span>';
    });
    // the legend sits at the left of the diamonds' row: every reported time on this slider is 18:00 or later (SOURCES.md)
    if (marks.some(function (m) { return m.tick; })) html += '<span class="m legend"' + srcAttr(SRC.sources_md, 'reported times: outlet, URL and SINGLE flag per line') + '>◆ = reported time (SOURCES.md), not an outcome</span>';
    $('sliderMarks').innerHTML = html;
  }

  // ------------------------------------------------------------------ UI: place panel (level 2)
  function shelterName(id) { var s = S.shelters && S.shelters[id]; return s ? (s.name || ((CAT_KO[s.category] || s.category || 'shelter') + ' (이름 없음)')) : (id || '—'); }
  function renderPanel() {
    var p = st.place;
    if (!p) { $('panel').hidden = true; document.body.classList.remove('panel-open'); return; }
    $('panel').hidden = false; document.body.classList.add('panel-open');
    var k = kOf(st.s), h = hourly(p.id, k) || {}, rt = routeOf(p.id, k), si = standinInfo();
    var cls = stepClass(h);
    var html = '<button class="close" type="button" id="panelClose" title="back to region (Esc)">×</button>';
    html += '<div class="name">' + esc(p.label) + '</div>';
    html += '<div class="sub">' + esc(CAT_EN[p.category] || String(p.category || '').replace(/_/g, ' ')) + ' · ' + esc(p.sigungu || '') + (p.vulnerable ? ' · <b>care facility (vulnerable)</b>' : '') + ' · ' + esc(p.id) + '</div>';
    html += '<div class="muted">Screen issued at <b>' + issueSpan(k) + ' KST</b> · <span' + armSrc(st.standin, k) + '>' + esc(isArm() ? armText(st.standin, k) : (si.label || st.standin)) + '</span> · ' + horizonSpan() + ' horizon</div>';
    // big clock
    if (h.state === 'LATEST_SAFE_DEPARTURE') {
      html += '<div class="big"><span class="t"' + srcAttr(SRC.per_place, csvDetail(h, 'latest_safe_departure_kst', null, k)) + '>' + esc(csvClock(h.lsd)) + '</span><span class="lab">latest safe departure<br>(leave-by clock)</span></div>';
    } else {
      html += '<div class="big"><span class="t state"' + srcAttr(SRC.per_place, csvDetail(h, 'departure_state', null, k)) + '>' + esc(STATE_TXT[h.state] || h.state || '—') + '</span></div>';
      if (h.state === 'NOT_CUT_WITHIN_H' && h.last) html += '<div class="muted">last departure checked inside the horizon: <span' + srcAttr(SRC.per_place, csvDetail(h, 'last_departure_in_horizon_kst', null, k)) + '>' + esc(csvClock(h.last)) + '</span> (a horizon cap, not a deadline)</div>';
    }
    html += '<div class="grid2">';
    html += '<div>government step</div><div><span class="step ' + esc(cls) + '"' + srcAttr(SRC.per_place, csvDetail(h, 'government_step', null, k)) + '>' + esc((STEP_TXT[h.step] || [h.step])[0]) + '</span> <span class="muted"' + srcAttr(SRC.sources_md, 'rule and rate sources: 5 h → 위험구역, 8 h → 잠재적 위험구역 (YTN 2025-04-16); 위험구역 = "leave now" NOT stated, this replay\'s reading') + '>' + esc((STEP_TXT[h.step] || ['', ''])[1]) + '</span></div>';
    html += '<div>distance to known fire</div><div><span' + srcAttr(SRC.per_place, csvDetail(h, 'dist_known_fire_km', null, k)) + '>' + esc(h.d_km === '' ? '—' : h.d_km + ' km') + '</span></div>';
    if (h.shelter) {
      html += '<div>shelter</div><div>' + shelterSpan(h.shelter, h, k) + '</div>';
      html += '<div>arrival (leaving at <span' + srcAttr(SRC.per_place, csvDetail(h, h.state === 'LATEST_SAFE_DEPARTURE' ? 'latest_safe_departure_kst' : 'last_departure_in_horizon_kst', null, k)) + '>' + esc(csvClock(h.state === 'LATEST_SAFE_DEPARTURE' ? h.lsd : h.last)) + '</span>)</div><div><span' + srcAttr(SRC.per_place, csvDetail(h, 'arrival_kst', null, k)) + '>' + esc(csvClock(h.arr)) + '</span></div>';
    }
    if (h.cut_before) html += '<div>route reached earlier by the reconstruction</div><div><span' + srcAttr(SRC.per_place, csvDetail(h, 'route_cut_before_departure', null, k) + ' (score flag, RESULTS.md §5)') + '>' + esc(h.cut_before) + '</span>' + (h.first_cut ? ' <span class="muted">(first cut <span' + srcAttr(SRC.per_place, csvDetail(h, 'route_first_cut_by_reconstruction_kst', null, k)) + '>' + esc(csvClock(h.first_cut)) + '</span>)</span>' : '') + '</div>';
    html += '</div>';
    // actions
    var canRoute = !!rt;
    html += '<div class="btns">' +
      '<button type="button" class="primary" id="checkBtn"' + (canRoute ? '' : ' disabled') + ' title="re-walk the witness road against the closures (C)">Check it</button>' +
      '<button type="button" id="laterBtn"' + (canRoute ? '' : ' disabled') + ' title="same road, leaving 60 s later (L)">One minute later</button>' +
      '<button type="button" id="driveBtn"' + (canRoute ? '' : ' disabled') + ' title="drive the witness road (chase view), about 30 s (D)">Drive it ▶</button></div>';
    if (!canRoute) {
      html += '<div class="note">' + (routesAvailable() ? 'No witness road at this issue hour (' + esc(STATE_TXT[h.state] || h.state) + ').' : 'Witness roads for this stand-in are not in the scene data (' + esc(SCENE_JS) + ' built.runs).') + '</div>';
    }
    html += '<div id="verdict"></div>';
    // the same place and screen under every R(h) arm (per_place.csv rows); a row click switches the arm
    var order = S.standin_order || Object.keys(S.hourly);
    html += '<div class="sec"><h4>This screen under each R(h) (' + horizonSpan() + ')</h4><table class="hours arms">';
    order.forEach(function (a) {
      var ha = hourly(p.id, k, a); if (!ha) return;
      var ca = armClass(a, k);
      html += '<tr data-arm="' + esc(a) + '" class="' + (a === st.standin ? 'cur' : '') + '"><td class="an"><span' + armSrc(a, k) + '>' + esc(shortLabel(a)) + '</span>' + (ca ? '<div class="cl"><span' + armSrc(a, k) + '>' + esc((CLS_TXT[ca.cls] || ca.cls).replace(/ \(.*\)$/, '')) + '</span>' + (ca.n_fires && ca.n_fires < 28 ? ' · <span' + srcAttr(SRC.margin_numbers, 'table, fire_set all28, alpha 0.10, class ' + ca.cls + ': n_fires at 5 h and 8 h') + '>' + ca.n_fires + ' fires</span>' : '') + '</div>' : '<div class="cl">stand-in, not the frozen R(h)</div>') + '</td>' +
        '<td><span class="step ' + esc(ha.step) + '"' + srcAttr(SRC.per_place, csvDetail(ha, 'government_step', a, k)) + '>' + esc(ha.step === 'LEAVE_NOW' ? 'leave' : ha.step === 'NONE' ? '—' : 'vuln.') + '</span></td>' +
        '<td class="ck"><span' + srcAttr(SRC.per_place, csvDetail(ha, ha.state === 'LATEST_SAFE_DEPARTURE' ? 'latest_safe_departure_kst' : 'departure_state', a, k)) + '>' + esc(ha.state === 'LATEST_SAFE_DEPARTURE' ? csvClock(ha.lsd) : (ARM_STATE[ha.state] || placeClock(ha))) + '</span>' +
        (ha.cut_before === 'yes' ? '<div class="cutb"' + srcAttr(SRC.per_place, csvDetail(ha, 'route_cut_before_departure / route_first_cut_by_reconstruction_kst', a, k)) + '>reached ' + esc(csvClock(ha.first_cut)) + '</div>' : '') + '</td></tr>';
    });
    html += '</table><div class="note">Leave-by clock (latest safe departure) of this screen under each R(h); "reached" = the full record reached the road before that departure (RESULTS.md §5). Not a ranking: each row is a different R(h). <span' + srcAttr(SRC.results_md, 'section 2b and section 7: MEASURED+GUST (ERA5, secondary) is PROVISIONAL, ERA5 gusts only; MEASURED+GUST (KMA) uses KMA ASOS hourly gusts; its >= 20 m/s class rests on 9 fires; the margins were calibrated on 28 fires. Spread-class and all-hours margins failed at every issue hour 10-20 KST (research/kcf-margin/RESULTS.md); the gust >= 20 m/s R(5 h) failed from 12 to 20 KST (research/kcf-gust/RESULTS.md)') + '>MEASURED+GUST (ERA5, secondary) is PROVISIONAL (ERA5 gusts only); MEASURED+GUST (KMA) uses the KMA ASOS series; the ≥ 20 m/s class = 9 fires in both.</span> Click a row to switch (R).</div></div>';
    // planner strip
    var pl = S.planner && S.planner[p.id] && S.planner[p.id][k];
    if (pl && st.standin === 'RUNNING') {
      html += '<div class="sec"><h4>Planner screen at ' + issueSpan(k) + ' (<span' + srcAttr(pl.file, 'generator.step_min (make_planner_cache.py STEP = 1800 s)') + '>30-min</span> grid)</h4>';
      html += '<div class="strip head"><span></span>';
      for (var i = 0; i < 16; i++) html += '<span>' + (i % 4 === 0 ? esc(kst(3600 * k + i * (pl.offsets_step_s || 1800))) : '') + '</span>';
      html += '</div>';
      pl.shelters.forEach(function (row) {
        html += '<div class="strip"><span class="sh"' + srcAttr(pl.file, 'requests[].destinations / plans[].attempts verdicts for ' + p.id) + '>' + esc(shelterName(row[0])) + '</span>';
        for (var j = 0; j < 16; j++) {
          var ok = row[1].charAt(j) === '1';
          var best = pl.best && pl.best.shelter === row[0] && pl.best.off_s === j * (pl.offsets_step_s || 1800);
          html += '<i class="' + (ok ? 'ok' : '') + (best ? ' best' : '') + '" title="' + esc(kst(3600 * k + j * 1800)) + ': ' + (ok ? 'checked_route' : 'model_no_route') + '"></i>';
        }
        html += '</div>';
      });
      html += '<div class="note">Green = checked_route, grey = model_no_route, per departure time (' + '<span' + srcAttr(pl.file, 'plans[0].attempts') + '>' + esc(pl.file) + '</span>). Verdicts come from the F-3.1 field with stand-in closures, not from the Route-Check API.</div></div>';
    } else if (pl) {
      html += '<div class="note"' + srcAttr(SRC.planner_cache_dir, 'the only planner cache in research/kcf-replay') + '>The planner\'s 30-min screen exists for RUNNING only (planner_cache/RUNNING_8h).</div>';
    }
    // reported times (named places)
    var rep = S.reported && S.reported[p.id];
    if (rep) {
      html += '<div class="sec reported"><h4>Reported times — not outcomes of this replay</h4>';
      html += '<ul>';
      (rep.rows || []).forEach(function (r) {
        html += '<li' + srcAttr(SRC.sources_md, 'line ' + r.line + ' (quoted as written; reported, not an outcome)') + '><span class="rk">REPORTED</span><b>' + esc(r.kst) + '</b> ' + esc(r.what) + (r.place && r.place !== p.name ? ' <span class="muted">(' + esc(r.place) + ')</span>' : '') +
          '<div class="src">' + esc(r.source || '') + (r.flag ? ' · <b>' + esc(r.flag) + '</b>' : '') + (r.url ? ' · <a href="' + esc(r.url) + '" target="_blank" rel="noopener noreferrer">source</a>' : '') + '</div></li>';
      });
      html += '</ul><div class="note"' + srcAttr(SRC.named_timeline, 'column documented') + '>' + esc(rep.documented || '') + '</div>';
      html += '<div class="note">Every reported time is single-source and was re-read at its source on <span' + srcAttr(SRC.sources_md, 'line 1: documented times, re-read at source (2026-11-16)') + '>2026-11-16</span> (SOURCES.md). A reported time is what an outlet wrote, not a result of this model.</div></div>';
    }
    // hour table
    html += '<div class="sec"><h4>All <span' + srcAttr(SRC.hotspot_rule, 'Issue times: thirteen issue times') + '>13</span> screens (<span' + armSrc(st.standin, k) + '>' + esc(shortLabel()) + '</span>, ' + horizonSpan() + ')</h4><table class="hours"><tr><th>issue</th><th>step</th><th>leave-by / state</th><th>shelter</th></tr>';
    for (var kk = 0; kk < NK; kk++) {
      var hh = hourly(p.id, kk); if (!hh) continue;
      html += '<tr data-k="' + kk + '" class="' + (kk === k ? 'cur' : '') + '"><td>' + issueSpan(kk) + '</td><td><span class="step ' + esc(hh.step) + '"' + srcAttr(SRC.per_place, csvDetail(hh, 'government_step', null, kk)) + '>' + esc(hh.step === 'LEAVE_NOW' ? 'leave' : hh.step === 'NONE' ? '—' : 'vuln.') + '</span></td><td' + srcAttr(SRC.per_place, csvDetail(hh, hh.state === 'LATEST_SAFE_DEPARTURE' ? 'latest_safe_departure_kst' : 'departure_state', null, kk)) + '>' + esc(placeClock(hh)) + '</td><td>' + (hh.shelter ? shelterSpan(hh.shelter, hh, kk) : '') + '</td></tr>';
    }
    html += '</table></div>';
    $('panel').innerHTML = html;
    $('panelClose').addEventListener('click', home);
    if (canRoute) {
      $('checkBtn').addEventListener('click', function () { runCheck(0); });
      $('laterBtn').addEventListener('click', function () { runCheck(60); });
      $('driveBtn').addEventListener('click', function () { startDrive(); });
    }
    Array.prototype.forEach.call($('panel').querySelectorAll('tr[data-k]'), function (tr) {
      tr.addEventListener('click', function () { setTime(3600 * Number(tr.getAttribute('data-k'))); });
    });
    Array.prototype.forEach.call($('panel').querySelectorAll('tr[data-arm]'), function (tr) {
      tr.addEventListener('click', function () { if (tr.getAttribute('data-arm') !== st.standin) setStandin(tr.getAttribute('data-arm')); });
    });
    renderVerdict();
  }

  function renderVerdict() {
    var el = $('verdict'); if (!el) return;
    var c = st.check;
    if (!c || !st.place || c.placeId !== st.place.id || c.k !== kOf(st.s) || c.standin !== st.standin) { el.innerHTML = ''; return; }
    var r = c.result, k = c.k, rt = r.rt, routeKey = 'routes.' + c.standin + '["' + c.placeId + '"][' + k + ']';
    var html = '';
    if (!c.done) {
      html = '<div class="verdict"><div class="v">re-walking…</div><div class="muted"' + srcAttr(SCENE_JS, routeKey + ' → ' + 'e (graph edges of the witness)') + '>edge ' + Math.min(c.shownEdges, r.edges || rt.e.length) + ' of ' + rt.e.length + '</div></div>';
      el.innerHTML = html; return;
    }
    var dep = 3600 * k + r.depart;
    if (r.ok) {
      var match = r.arrival === rt.arr && c.offset === 0;
      html = '<div class="verdict pass"><div class="v">PASS</div>' +
        '<div>leave <b' + srcAttr(SCENE_JS, routeKey + ' → ' + 'ld (seconds after the issue hour) + offset ' + c.offset + ' s') + '>' + esc(kst(dep, true)) + '</b> → arrive <b' + srcAttr(SCENE_JS, routeKey + ' → ' + 're-walked: departure + sum of edge travel ticks (graph travel_ticks)') + '>' + esc(kst(3600 * k + r.arrival, true)) + '</b> KST at <span' + srcAttr(SCENE_JS, routeKey + ' → ' + 'sh (shelter of the witness)') + '>' + esc(shelterName(rt.sh)) + '</span></div>' +
        '<div class="muted"><span' + srcAttr(SCENE_JS, routeKey + ' → ' + 'e (graph edges of the witness)') + '>' + rt.e.length + ' edges</span> re-walked against the ' + issueSpan(k) + ' closures; dwell <span' + srcAttr(SRC.replay_py, 'DWELL = 120 (seconds at the shelter); also planner cache generator.default_dwell_s') + '>' + DWELL + ' s</span> ends before the shelter cell closes' + (r.shelterClose >= 0 ? ' (<span' + srcAttr(SCENE_JS, 'close.' + c.standin + '.' + st.place.region + '[' + k + '] for cell ' + rt.sh_cell) + '>' + esc(kst(3600 * k + r.shelterClose, true)) + '</span>)' : ' (not closed within 8 h)') + '.</div>';
      if (c.offset === 0) html += '<div class="' + (match ? 'match' : 'mismatch') + '">' + (match ? '✓ same arrival second as committed' : '✗ differs from committed') + ': arr = <span' + srcAttr(SCENE_JS, routeKey + ' → ' + 'arr (from out/runs, re-made by replay.py; checked against per_place.csv arrival_kst)') + '>' + fmtInt(rt.arr) + ' s</span> after ' + issueSpan(k) + ' (per_place.csv <span' + srcAttr(SRC.per_place, csvDetail(hourly(c.placeId, k, c.standin), 'arrival_kst', c.standin, k)) + '>' + esc(csvClock(hourly(c.placeId, k, c.standin).arr)) + '</span>)</div>';
      html += '</div>';
    } else {
      html = '<div class="verdict fail"><div class="v">FAIL</div>';
      var depA = srcAttr(SCENE_JS, routeKey + ' → ld + ' + c.offset + ' s (re-walk start)');
      var walkA = srcAttr(SCENE_JS, routeKey + ' → re-walked: start + edge travel ticks (graph travel_ticks)');
      var dwellA = srcAttr(SRC.replay_py, 'DWELL = 120 (seconds at the shelter)');
      if (r.overH) {
        html += '<div' + walkA + '>leaving <b>' + esc(kst(dep, true)) + '</b>, the vehicle arrives <b>' + esc(kst(3600 * k + r.arrival, true)) + '</b>, and arrival + the <span' + dwellA + '>' + DWELL + ' s</span> dwell ends after the <span' + srcAttr(SCENE_JS, 'horizon_s = 28800 (HOTSPOT_RULE.md, horizon H)') + '>8 h</span> horizon of the ' + issueSpan(k) + ' screen. No road cell on the way is closed.</div>';
      } else if (r.shelterCell) {
        html += '<div>arrives <span' + walkA + '>' + esc(kst(3600 * k + r.arrival, true)) + '</span>, but the shelter cell closes at <b' + srcAttr(SCENE_JS, 'close.' + c.standin + '.' + st.place.region + '[' + k + '] cell ' + r.cell) + '>' + esc(kst(3600 * k + r.closeAt, true)) + '</b>, before the <span' + dwellA + '>' + DWELL + ' s</span> dwell ends.</div>';
      } else {
        html += '<div>leaving <b' + depA + '>' + esc(kst(dep, true)) + '</b>, the vehicle would leave <span' + srcAttr(SCENE_JS, routeKey + ' → e[' + r.edge + '] segment in road cell ' + r.cell + ' (routeEdges seg, graph.json)') + '>road cell ' + r.cell + ' (edge ' + (r.edge + 1) + ' of ' + rt.e.length + ')</span> at <b' + walkA + '>' + esc(kst(3600 * k + r.leaveAt, true)) + '</b>; the ' + issueSpan(k) + ' screen closes that cell at <b' + srcAttr(SCENE_JS, 'close.' + c.standin + '.' + st.place.region + '[' + k + '] cell ' + r.cell + ' (T + h* where R(h*) = distance, HOTSPOT_RULE.md)') + '>' + esc(kst(3600 * k + r.closeAt, true)) + '</b>.</div>';
      }
      var hh0 = hourly(c.placeId, k, c.standin);
      if (hh0 && hh0.state === 'LATEST_SAFE_DEPARTURE') html += '<div class="muted">This tests this road only. The deadline field (F-3.1) says no road to any of the <span' + srcAttr(SRC.results_md, 'section 1: the planner\'s own 3 candidate shelters per place (replay.py K = 3)') + '>3</span> candidate shelters works after the latest safe departure.</div>';
      else html += '<div class="muted">This road is not cut within 8 h; its departure is the horizon cap, not a deadline (HOTSPOT_RULE.md).</div>';
      html += '</div>';
    }
    el.innerHTML = html;
  }

  // ------------------------------------------------------------------ sources panel
  var MAP_SOURCES = function () {
    var out = [
      [SRC.fire_discs, 'known fire area: every kept FIRMS detection and AHI hotspot, drawn as its disc (r = 375 m VIIRS, 1 km MODIS, 2 km AHI), before the issue hour (HOTSPOT_RULE.md)'],
      [SCENE_JS, isArm() ? 'closed road cells: close.' + st.standin + ' = issue + h* on the curve (0, 0), (5 h, R5), (8 h, R8) of that hour\'s class, computed with measured_arms.py (closure_s) from ' + SRC.fire_discs + ' on the routing grid (graph.json, release research-final-20261015)'
        : 'closed road cells: close.' + st.standin + ' = issue + h* where R(h*) = distance, computed with replay.py (closure_s) from ' + SRC.fire_discs + ' on the routing grid (graph.json, release research-final-20261015)'],
      [SRC.per_place, 'map labels: latest_safe_departure_kst / departure_state, government_step (dot colour), standin = ' + st.standin + ', horizon 8h'],
      ['planner/public/kcf-scene/data/terrain.js', 'terrain: Terrain Tiles (Mapzen, AWS Open Data), Terrarium z5–12'],
      ['planner/public/kcf-scene/data/basemap.js', 'roads, water, towns: OpenStreetMap (ODbL) via planner/research-map and planner/data/osm']
    ];
    if (st.place) out.push([SCENE_JS, 'witness road: routes.' + st.standin + ' + routeEdges (graph edges of the F-3.1 witness, re-made by replay.py' + (st.standin === 'RUNNING' ? '; geometry identical to the planner cache route)' : ')')]);
    if (isArm()) {
      out.push([SRC.measured_rule, 'MEASURED arms: class per issue hour, closure curve, step rule (frozen before any outcome)']);
      out.push([SRC.margin_numbers, 'R(5 h), R(8 h) per class (table, fire set all28, alpha 0.10), asserted by measured_arms.py']);
      var gsi = standinInfo();
      if (gsi.gust_hours) out.push([gsi.gust_hours, (gsi.gust_source === 'KMA ASOS' ? 'KMA ASOS (primary series)' : 'ERA5 (secondary series, PROVISIONAL)') + ' next-8 h maximum gust per issue hour']);
    }
    return out;
  };
  function renderSources() {
    var groups = {}, order = [];
    function add(path, detail) { if (!groups[path]) { groups[path] = []; order.push(path); } if (detail && groups[path].indexOf(detail) < 0) groups[path].push(detail); }
    Array.prototype.forEach.call(document.querySelectorAll('[data-src]'), function (el) {
      if (!el.offsetParent && el.id !== 'standinBtn') return;
      add(el.getAttribute('data-src'), el.getAttribute('data-detail'));
    });
    MAP_SOURCES().forEach(function (x) { add(x[0], x[1]); });
    var n = 0, body = '';
    order.forEach(function (p) {
      body += '<div class="p">' + esc(p) + '</div>';
      var ds = groups[p];
      ds.slice(0, 4).forEach(function (d) { body += '<div class="d">' + esc(d) + '</div>'; n++; });
      if (ds.length > 4) body += '<div class="d">… ' + (ds.length - 4) + ' more</div>';
    });
    $('sources').innerHTML = '<div class="hd" id="sourcesHd">' + (st.sourcesOpen ? '▾' : '▸') + ' Sources of what is on screen (' + order.length + ' files) · S</div><div class="bd">' + body +
      '<div class="d">Every file above is committed. Built ' + esc((S.built && S.built.commit || '').slice(0, 10)) + ' by ' + esc(SRC.build_scene) + '; check: research/kcf-replay/scene/VERIFY.json.</div></div>';
    $('sources').classList.toggle('collapsed', !st.sourcesOpen);
    $('sourcesHd').addEventListener('click', function () { st.sourcesOpen = !st.sourcesOpen; renderSources(); });
  }

  // ------------------------------------------------------------------ crumbs, about
  function renderCrumbs() {
    Array.prototype.forEach.call(document.querySelectorAll('#crumbs button[data-level]'), function (b) {
      var lv = b.getAttribute('data-level');
      b.classList.toggle('on', lv === st.view);
      b.disabled = (lv === 'place' && !st.place) || (lv === 'drive' && !(st.place && routeOf(st.place.id, kOf(st.s))));
    });
    Array.prototype.forEach.call(document.querySelectorAll('#bookmarks button'), function (b) {
      b.classList.toggle('on', !!st.place && b.getAttribute('data-id') === st.place.id);
    });
  }
  function renderAbout() {
    var si = standinInfo();
    $('about').innerHTML = '<button class="close" type="button" id="aboutClose" style="float:right;background:none;border:0;color:#aab3c2;font-size:18px;cursor:pointer">×</button>' +
      '<h2>What this scene is</h2>' +
      '<p' + srcAttr(SRC.results_md, 'opening paragraph') + '>"This is a reconstruction of what a screen would have shown. It is not a claim about outcomes. It does not judge anyone\'s decisions, and it names no victims. Every number below depends on a stand-in for R(h)." — research/kcf-replay/RESULTS.md</p>' +
      '<p' + srcAttr(SRC.hotspot_rule, 'whole rule; frozen in commit 796e91c') + '><b>Known fire area</b>: FIRMS VIIRS/MODIS detections and Himawari-9 AHI hotspots time-stamped strictly before each issue hour (rule frozen first: HOTSPOT_RULE.md, commit 796e91c). Delivery latency is not modelled. ' +
      '<b>Road cell closure</b> = issue time + h*, where R(h*) = the cell\'s distance to the known fire area (RUNNING: distance / 8.2 km/h; WORST: (distance − 3 km) / 8.2 km/h; ORDINARY: distance / 0.341 km/h; <span' + srcAttr(SRC.measured_rule, 'R(h) values; closure curve through (0 h, 0 km), (5 h, R5), (8 h, R8), beyond 8 h never (part below 5 h ASSUMED linear)') + '>MEASURED arms: the curve through (0, 0), (5 h, R5), (8 h, R8) of the issue hour\'s class, never beyond R8</span>), permanent within that screen\'s 8 h horizon; each hourly screen recomputes every closure from its own known fire area, so on the next screen a cell far from new detections can show open again until its new closure time. <b>Government step</b>: R(5 h) ≥ distance → 위험구역 (read here as "leave now"; this reading is the replay\'s own); R(8 h) ≥ distance → 잠재적 위험구역, vulnerable first. ' +
      '<b>Latest safe departure</b>: F-3.1 deadline field over the planner road graph, 3 candidate shelters per place.</p>' +
      '<p' + srcAttr(SRC.results_md, 'sections 2 (stand-ins) and 2b (MEASURED arms); section 7 (limits)') + '>R(h) now: <b>' + esc(isArm() ? armText(st.standin, kOf(st.s)) : (si.label || st.standin)) + '</b> — ' + esc(si.basis || '') + '. Six R(h) arms (R cycles them): RUNNING, WORST and ORDINARY are labelled stand-ins; <b>MEASURED</b>, <b>MEASURED+GUST (KMA)</b> and <b>MEASURED+GUST (ERA5, secondary)</b> are the frozen R(h) of research/kcf-margin (10 % target, 28 GOFER fires), one class per issue hour for all 174 places, picked by the prior-3 h spread of the known fire area or by the maximum gust over the next 8 h: from the KMA ASOS hourly series (primary) or from ERA5 (secondary, <b>PROVISIONAL</b>, ERA5 gusts only). The ≥ 20 m/s class rests on 9 fires in both. The curve below 5 h is assumed linear. On this fire the spread-class and all-hours margins failed at every issue hour from 10 to 20 KST (research/kcf-margin/RESULTS.md), and the gust ≥ 20 m/s R(5 h) from 12 to 20 KST (research/kcf-gust/RESULTS.md). Each arm is its own R(h): not a ranking.</p>' +
      '<p' + srcAttr('hardware/field_logger_demo/sessions/sessions.json', '4 sessions, all sim/*.wfg in area sim_city; also hardware/phone_export/samples (synthetic test walks); HOTSPOT_RULE.md: within a screen a closure is permanent') + '><b>Not in this scene:</b> the crossing view (vehicle, flame wall, verdict) and a REOPENED event. The repository has no vehicle-unit or crossing log for this event (the only logger recordings are synthetic: four simulated city sessions and the phone exporter\'s test walks), and the frozen rule has no reopening event: within a screen a closed cell stays closed.</p>' +
      '<p><b>Keys</b>: <kbd>←</kbd>/<kbd>→</kbd> issue hour · <kbd>Space</kbd> play · <kbd>1</kbd>–<kbd>6</kbd> bookmarks · <kbd>C</kbd> check it · <kbd>L</kbd> one minute later · <kbd>D</kbd> drive · <kbd>Esc</kbd> back · <kbd>H</kbd> region · <kbd>R</kbd> R(h) arm · <kbd>S</kbd> sources · <kbd>?</kbd> this box. URL: <code>?lite</code> for slow machines.</p>' +
      '<p class="note">Terrain: Terrain Tiles (Mapzen, AWS Open Data). Roads, water, names: © OpenStreetMap contributors (ODbL). MapLibre GL JS (BSD-3-Clause). Pretendard, Noto Sans (SIL OFL). Scene data built from committed files by research/kcf-replay/scene/build_scene.py; checks in research/kcf-replay/scene/VERIFY.json.</p>';
    $('aboutClose').addEventListener('click', function () { $('about').hidden = true; });
  }

  // ------------------------------------------------------------------ actions
  function refreshAll() {
    var k = kOf(st.s);
    setPlaces(k);
    if (!st.drive) { setFire(3600 * k); setCells(k, st.s - 3600 * k); }
    renderClock(); renderSummary(); renderPanel(); renderSliderMarks(); renderCrumbs(); renderLegend(); renderStandinBtn(); renderSources();
    if (!$('about').hidden) renderAbout();
    showRoute();
  }
  function setTime(s, opts) {
    s = Math.max(0, Math.min(43200, Math.round(s)));
    var kPrev = kOf(st.s);
    st.s = s;
    var k = kOf(s);
    if (st.drive) return;
    if (k !== kPrev || (opts && opts.full)) {
      if (st.check && st.check.k !== k) { st.check = null; clearWalk(); }
      refreshAll();
    } else {
      setCells(k, s - 3600 * k);
      renderClock();
      if (!(opts && opts.light)) renderSliderMarks();
    }
  }
  function setStandin(name) {
    if (!S.hourly[name]) return;
    var wasDriving = !!st.drive;
    if (wasDriving) { // leave the drive first: its road and closures belong to the old stand-in
      stopDrive(true);
      st.view = st.place ? 'place' : 'region';
      map.setTerrain({ source: 'dem', exaggeration: st.place ? EXAG.place : EXAG.region });
    }
    st.standin = name; st.check = null; clearWalk();
    map.getSource('cells').setData(buildCellsFC());
    lastCellKey = null; lastPlacesKey = null;
    refreshAll();
    if (wasDriving && st.place) {
      var cam = cameraFor(st.place, routeOf(st.place.id, kOf(st.s)));
      if (cam) map.flyTo({ center: cam.center, zoom: Math.min(cam.zoom, 14.2), pitch: 58, bearing: cam.bearing, duration: TOUR ? 0 : 1600 });
    }
  }
  function cycleStandin() {
    var names = Object.keys(S.standins || S.hourly);
    var order = (S.standin_order || ['RUNNING', 'MEASURED', 'MEASURED_GUST_KMA', 'MEASURED_GUST', 'WORST', 'ORDINARY']).filter(function (n) { return names.indexOf(n) >= 0 && S.hourly[n]; });
    setStandin(order[(order.indexOf(st.standin) + 1) % order.length]);
  }
  function showRoute() {
    var p = st.place, k = kOf(st.s);
    var feats = [], marks = [];
    if (p) {
      marks.push({ type: 'Feature', properties: { kind: 'place' }, geometry: { type: 'Point', coordinates: [p.lon, p.lat] } });
      var rt = routeOf(p.id, k);
      if (rt) {
        feats.push({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: routeCoords(p.region, rt) } });
        var sh = S.shelters[rt.sh];
        if (sh) marks.push({ type: 'Feature', properties: { kind: 'shelter', label: '대피소 · ' + shelterName(rt.sh) }, geometry: { type: 'Point', coordinates: sh.entry || [sh.lon, sh.lat] } });
      }
      if (st.check && st.check.done && !st.check.result.ok && st.check.result.cell != null) {
        var i = cellIndex[p.region].get(st.check.result.cell);
        if (i !== undefined) marks.push({ type: 'Feature', properties: { kind: 'failcell' }, geometry: { type: 'LineString', coordinates: S.roadCells[p.region].ring[i] } });
      }
    }
    map.getSource('route').setData({ type: 'FeatureCollection', features: feats });
    map.getSource('mark').setData({ type: 'FeatureCollection', features: marks });
  }
  function clearWalk() { if (map.getSource('walk')) map.getSource('walk').setData(emptyFC()); }
  function setWalk(coordsUpTo) {
    map.getSource('walk').setData(coordsUpTo.length >= 2 ? { type: 'FeatureCollection', features: [{ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: coordsUpTo } }] } : emptyFC());
  }

  function cameraFor(p, rt) {
    var pts = [[p.lon, p.lat]];
    if (rt) pts = pts.concat(routeCoords(p.region, rt));
    var b = new maplibregl.LngLatBounds(pts[0], pts[0]);
    pts.forEach(function (c) { b.extend(c); });
    var cam = map.cameraForBounds(b, { padding: { top: 140, bottom: 170, left: 330, right: 440 }, bearing: map.getBearing(), maxZoom: 14.2 });
    return cam;
  }
  function selectPlace(idOrName, opts) {
    var p = placeById[idOrName] || placeByName[idOrName];
    if (!p) return false;
    stopDrive(true);
    st.place = p; st.view = 'place'; st.check = null; clearWalk();
    map.setTerrain({ source: 'dem', exaggeration: EXAG.place });
    refreshAll();
    if (!(opts && opts.noCamera)) {
      var cam = cameraFor(p, routeOf(p.id, kOf(st.s)));
      if (cam) map.flyTo({ center: cam.center, zoom: Math.min(cam.zoom, 14.2), pitch: 58, bearing: cam.bearing, duration: TOUR ? 0 : 2200, essential: true });
    }
    return true;
  }
  function home() {
    stopDrive(true);
    if (st.playing) togglePlay();
    var d0 = S.default_standin || 'RUNNING';
    if (st.standin !== d0 && S.hourly[d0]) { st.standin = d0; map.getSource('cells').setData(buildCellsFC()); lastCellKey = null; lastPlacesKey = null; }
    st.place = null; st.view = 'region'; st.check = null; clearWalk();
    map.setTerrain({ source: 'dem', exaggeration: EXAG.region });
    refreshAll();
    map.fitBounds(bounds0, { padding: { top: 80, bottom: 150, left: 40, right: 40 }, pitch: 52, bearing: -8, duration: TOUR ? 0 : 2000 });
  }
  function back() {
    if (!$('about').hidden) { $('about').hidden = true; return; }
    if (st.drive) { stopDrive(); return; }
    if (st.place) { home(); }
  }

  // check it: compute the whole re-walk at once, then reveal it edge by edge (or at once with instant)
  var checkAnim = null;
  function runCheck(offset, opts) {
    var p = st.place; if (!p) return null;
    var k = kOf(st.s), rt = routeOf(p.id, k); if (!rt) return null;
    var result = rewalk(p, k, rt.ld + (offset || 0));
    st.check = { placeId: p.id, k: k, standin: st.standin, offset: offset || 0, result: result, done: false, shownEdges: 0 };
    if (checkAnim) cancelAnimationFrame(checkAnim);
    var coords = routeCoords(p.region, rt);
    var nEdges = (result.edge != null) ? result.edge + 1 : rt.e.length;
    var chk = st.check;
    function show(frac) {
      if (st.check !== chk) return; // interrupted (new hour, place, stand-in or drive)
      var ne = Math.max(1, Math.round(frac * nEdges));
      st.check.shownEdges = ne;
      setWalk(coords.slice(0, Math.min(coords.length, ne + 1)));
      if (frac >= 1) { st.check.done = true; showRoute(); }
      renderVerdict(); renderSources();
    }
    st.check.show = show;
    if (opts && opts.instant) { show(1); return result; }
    if (opts && opts.manual) { show(0); return result; }
    var t0 = performance.now(), dur = 1800;
    (function step() {
      var f = Math.min(1, (performance.now() - t0) / dur);
      if (st.check !== chk) { checkAnim = null; return; }
      show(f);
      if (f < 1) checkAnim = requestAnimationFrame(step); else checkAnim = null;
    })();
    return result;
  }

  // ------------------------------------------------------------------ level 3: drive along the witness road (chase view)
  function buildDrive(p, k) {
    var rt = routeOf(p.id, k); if (!rt) return null;
    var E = S.routeEdges[p.region];
    var pts = [], times = [], dist = [], t = rt.ld, d = 0;
    rt.e.forEach(function (ei, j) {
      var e = E[ei], c = e.c;
      if (j === 0) { pts.push(c[0]); times.push(t); dist.push(0); }
      // chords: u..v; spread the edge's ticks along its points by length
      var L = 0, segL = [];
      for (var i = 1; i < c.length; i++) { var l = distM(c[i - 1], c[i]); segL.push(l); L += l; }
      var acc = 0;
      for (var q = 1; q < c.length; q++) {
        acc += segL[q - 1];
        pts.push(c[q]); times.push(t + (L > 0 ? e.D * acc / L : e.D)); d += segL[q - 1]; dist.push(d);
      }
      t += e.D;
    });
    var dur = rt.arr - rt.ld;
    // about 30 s of playback: a whole-number speed-up, or a labelled slow-down when the road takes under 30 s
    var speed = dur >= 30 ? Math.max(1, Math.round(dur / 30)) : Math.max(0.05, Math.round(dur / 30 * 100) / 100);
    // closures of the issue-k screen in cells within about 3 km of the route (what the chase view can show), sorted
    var W = 180, Sx = 90, E2 = -180, N = -90;
    pts.forEach(function (c) { W = Math.min(W, c[0]); E2 = Math.max(E2, c[0]); Sx = Math.min(Sx, c[1]); N = Math.max(N, c[1]); });
    var rings = S.roadCells[p.region].ring, cl = S.close[st.standin][p.region][k], closeTimes = [];
    for (var ci = 0; ci < cl.length; ci++) {
      if (cl[ci] < 0) continue;
      var r0 = rings[ci][0], r2 = rings[ci][2], cx = (r0[0] + r2[0]) / 2, cy = (r0[1] + r2[1]) / 2;
      if (cx >= W - 0.035 && cx <= E2 + 0.035 && cy >= Sx - 0.028 && cy <= N + 0.028) closeTimes.push(cl[ci]);
    }
    closeTimes.sort(function (a, b) { return a - b; });
    var hk = hourly(p.id, k);
    // map layers follow the drive in steps of about 1/60 of it (at least 20 s of scene time): a few updates per second
    var quantum = Math.max(20, Math.ceil(dur / 60));
    // detection discs near the route, to say when the vehicle is inside one (reconstruction, not the screen's input)
    var near = S.discs.rows.filter(function (d) { return d[1] >= W - 0.05 && d[1] <= E2 + 0.05 && d[2] >= Sx - 0.04 && d[2] <= N + 0.04; });
    return { cutBefore: hk && hk.cut_before, firstCut: hk && hk.first_cut, hrow: hk, nearDiscs: near, inFire: null,
      state: hk && hk.state, place: p, k: k, rt: rt, pts: pts, times: times, dist: dist, total: d, dur: dur, speed: speed, tau: rt.ld, closeTimes: closeTimes, quantum: quantum,
      eye: null, bearing: null, playStart: null, done: false, standin: st.standin };
  }
  function posAtTime(dv, tau) {
    var T = dv.times, i = Math.max(0, Math.min(T.length - 2, upperBound(T, tau) - 1));
    var f = T[i + 1] > T[i] ? (tau - T[i]) / (T[i + 1] - T[i]) : 1; f = Math.max(0, Math.min(1, f));
    var a = dv.pts[i], b = dv.pts[i + 1];
    return { p: [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f], d: dv.dist[i] + (dv.dist[i + 1] - dv.dist[i]) * f, i: i };
  }
  function posAtDist(dv, d) {
    var D = dv.dist; if (d >= dv.total) return dv.pts[dv.pts.length - 1];
    var i = Math.max(0, Math.min(D.length - 2, upperBound(D, d) - 1));
    var f = D[i + 1] > D[i] ? (d - D[i]) / (D[i + 1] - D[i]) : 1;
    var a = dv.pts[i], b = dv.pts[i + 1];
    return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
  }
  function elevAt(ll) { var e = map.queryTerrainElevation(ll); return (e == null || isNaN(e)) ? null : e; }
  var EYE_M = Number(Q.get('eye')) || 38, BACK_M = 115, AHEAD_M = 260;
  function offset(ll, bearingDeg, m) { // move m metres from ll along bearing (local flat approximation)
    var br = bearingDeg * Math.PI / 180, dlat = m * Math.cos(br) / 111320, dlon = m * Math.sin(br) / (111320 * Math.cos(ll[1] * Math.PI / 180));
    return [ll[0] + dlon, ll[1] + dlat];
  }
  function bearingOf(a, b) {
    var y = (b[0] - a[0]) * Math.cos(a[1] * Math.PI / 180), x = b[1] - a[1];
    return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
  }
  function driveFrame(dv, tau, opts) {
    dv.tau = tau;
    var now = 3600 * dv.k + tau;
    var pos = posAtTime(dv, tau);
    // heading: towards the road 150 m ahead, smoothed so short chords do not jitter the view
    var hb = bearingOf(pos.p, posAtDist(dv, Math.min(dv.total, pos.d + 150)));
    if (pos.d + 5 >= dv.total && dv.heading != null) hb = dv.heading;
    if (dv.heading == null || (opts && opts.snap)) dv.heading = hb;
    else { var db = ((hb - dv.heading + 540) % 360) - 180; dv.heading = (dv.heading + db * 0.15 + 360) % 360; }
    // chase camera: BACK_M behind the vehicle along the heading, EYE_M above the highest ground near camera and vehicle
    var camLL = offset(pos.p, dv.heading, -BACK_M), lookLL = offset(pos.p, dv.heading, AHEAD_M);
    var gV = elevAt(pos.p) || 0, gC = Math.max(elevAt(camLL) || 0, elevAt(offset(pos.p, dv.heading, -BACK_M / 2)) || 0);
    var eyeTarget = Math.max(gV + EYE_M, gC + 15);
    dv.eye = (dv.eye == null || (opts && opts.snap)) ? eyeTarget : dv.eye + (eyeTarget - dv.eye) * 0.12;
    // aim so the vehicle sits about 11 degrees below the view centre, whatever the ground does
    var angV = Math.atan2(dv.eye - gV, BACK_M) * 180 / Math.PI, a = Math.max(2, angV - 11) * Math.PI / 180;
    var lookAlt = dv.eye - Math.tan(a) * (BACK_M + AHEAD_M);
    var cam = map.calculateCameraOptionsFromTo(maplibregl.LngLat.convert(camLL), dv.eye, maplibregl.LngLat.convert(lookLL), lookAlt);
    if (cam) { cam.pitch = Math.min(LITE ? 72 : 82, cam.pitch); map.jumpTo(cam); }
    // fire: detections time-stamped before this moment; closures: the issue-k screen's (both stepped by dv.quantum)
    var tq = tau >= dv.rt.arr ? tau : dv.rt.ld + Math.floor((tau - dv.rt.ld) / dv.quantum) * dv.quantum;
    // sticky: the first moment the vehicle is inside a detection disc time-stamped before that moment
    if (dv.inFire == null) {
      for (var di = 0; di < dv.nearDiscs.length; di++) {
        var dd = dv.nearDiscs[di];
        if (dd[0] < now && distM(pos.p, [dd[1], dd[2]]) <= dd[3]) { dv.inFire = { at: now, disc: dd }; break; }
      }
    }
    setFire(3600 * dv.k + tq);
    var nClosed = upperBound(dv.closeTimes, tq);
    if (nClosed !== dv.nClosed) { dv.nClosed = nClosed; lastCellKey = null; setCells(dv.k, tq); }
    // the travelled road: redrawn when the vehicle reaches a new vertex (a draped source; not every frame)
    if (pos.i !== dv.walkI || tau >= dv.rt.arr) { dv.walkI = pos.i; setWalk(dv.pts.slice(0, pos.i + 1).concat([pos.p])); }
    // the vehicle is a DOM marker, so moving it does not re-drape the terrain
    if (!vehicleMarker) { var el = document.createElement('div'); el.className = 'vehicle'; vehicleMarker = new maplibregl.Marker({ element: el }); }
    vehicleMarker.setLngLat(pos.p);
    if (!vehicleMarker._map) vehicleMarker.addTo(map);
    st.drive = dv;
    renderHud(dv, pos);
    renderClock();
  }
  function renderHud(dv, pos) {
    var frac = dv.dur > 0 ? (dv.tau - dv.rt.ld) / dv.dur : 1;
    var routeKey = 'routes.' + dv.standin + '["' + dv.place.id + '"][' + dv.k + ']';
    var html = '<div class="meta">' + esc(dv.place.label) + ' → <span' + srcAttr(SCENE_JS, routeKey + ' → ' + 'sh') + '>' + esc(shelterName(dv.rt.sh)) + '</span> · witness road of the ' + issueSpan(dv.k) + ' screen · <span' + armSrc(dv.standin, dv.k) + '>' + esc(isArm(dv.standin) ? armText(dv.standin, dv.k) : (standinInfo(dv.standin).label || dv.standin)) + '</span></div>' +
      '<div class="clk"' + srcAttr(SCENE_JS, routeKey + ' → ' + 'clock = departure ld + committed edge travel ticks (graph travel_ticks)') + '>' + esc(kst(3600 * dv.k + dv.tau, true)) + ' KST</div>' +
      '<div class="bar"><i style="width:' + (100 * Math.max(0, Math.min(1, frac))).toFixed(1) + '%"></i></div>' +
      '<div class="meta">left <span' + srcAttr(SCENE_JS, routeKey + ' → ' + 'ld') + '>' + esc(kst(3600 * dv.k + dv.rt.ld, true)) + '</span> (' + (dv.state === 'LATEST_SAFE_DEPARTURE' ? 'latest safe departure' : 'last departure inside the 8 h horizon: a cap, not a deadline') + ') · arrives <span' + srcAttr(SCENE_JS, routeKey + ' → ' + 'arr') + '>' + esc(kst(3600 * dv.k + dv.rt.arr, true)) + '</span> · <span' + srcAttr(APP_JS, 'presentation setting, not data: playback = (arr - ld) / 30 s, rounded') + '>playback ×' + dv.speed + (dv.speed < 1 ? ' (slowed: this road takes ' + dv.dur + ' s)' : dv.speed === 1 ? ' (real time)' : '') + '</span> · <span' + srcAttr(APP_JS, 'presentation setting, not data: BACK_M, EYE_M; terrain: data/terrain.js z12 (about 30 m)') + '>chase view ' + BACK_M + ' m behind and ' + EYE_M + ' m above the vehicle, over a 30 m terrain model</span></div>' +
      '<div class="meta">fire: detections time-stamped before this moment (reconstruction; delivery latency not modelled) · violet: cells the ' + issueSpan(dv.k) + ' screen has closed by now</div>' +
      (3600 * dv.k + dv.tau > discS[discS.length - 1] ? '<div class="meta" style="color:#ffb48a"' + srcAttr(SRC.fire_discs, 'last disc t_utc 2025-03-25T17:58:00Z = 02:58 KST 26 Mar; RESULTS.md section 5: the reconstruction ends with the data') + '>The fire record ends at 02:58 KST, 26 March: no detection after that is shown, which does not mean the fire stopped.</div>' : '');
    var warnFire = dv.inFire || dv.cutBefore === 'yes';
    if (warnFire) {
      html += '<div class="warn">';
      if (dv.inFire) html += '<span' + srcAttr(SRC.fire_discs, dv.inFire.disc[4] + ' disc, t_utc = issue 12:00 KST + ' + dv.inFire.disc[0] + ' s, r = ' + dv.inFire.disc[3] + ' m') + '>Since ' + esc(kst(dv.inFire.at, true)) + ' the vehicle is inside a ' + esc(String(dv.inFire.disc[4]).indexOf('AHI') === 0 ? 'Himawari hotspot (fire within 2 km)' : 'satellite fire detection') + ' disc detected before that moment.</span> ';
      if (dv.cutBefore === 'yes') html += '<span' + srcAttr(SRC.per_place, csvDetail(dv.hrow, 'route_cut_before_departure / route_first_cut_by_reconstruction_kst', dv.standin, dv.k)) + '>The full record reached this road at ' + esc(csvClock(dv.firstCut)) + ', before this departure (RESULTS.md §5 counts it).</span> ';
      html += 'The ' + issueSpan(dv.k) + ' screen used only detections before ' + issueSpan(dv.k) + '; this drive shows its projection, not an outcome.</div>';
    }
    if (dv.done) html += '<div class="end' + (warnFire ? ' muted-end' : '') + '"' + srcAttr(SCENE_JS, routeKey + ' → ' + 'arr, sh') + '>The ' + esc(issueLabel(dv.k)) + ' screen\'s projection: arrival at ' + esc(shelterName(dv.rt.sh)) + ' ' + esc(kst(3600 * dv.k + dv.rt.arr, true)) + ' KST (the committed arrival second' + (warnFire ? '; see the warning above' : '') + '). Esc to go back.</div>';
    $('hud').innerHTML = html;
    var sig = (dv.done ? 'd' : '') + (3600 * dv.k + dv.tau > discS[discS.length - 1] ? 'e' : '') + (dv.inFire ? 'f' : '');
    if (sig !== dv.srcSig) { dv.srcSig = sig; renderSources(); }
  }
  var driveRaf = null, vehicleMarker = null;
  function startDrive(opts) {
    var p = st.place; if (!p) return null;
    var k = kOf(st.s);
    var dv = buildDrive(p, k); if (!dv) return null;
    if (st.playing) togglePlay();
    stopDrive(true);
    st.check = null; clearWalk();
    st.view = 'drive'; st.drive = dv;
    document.body.classList.add('driving');
    $('hud').hidden = false;
    map.resize(); // the map stops above the compact time bar while driving
    map.setTerrain({ source: 'dem', exaggeration: EXAG.drive });
    // keep the centre elevation the chase camera sets: by default MapLibre re-clamps the centre to the ground when it
    // renders, which moves the camera after jumpTo and leaves the vehicle marker where the old camera would draw it
    map.setCenterClampedToGround(false);
    map.setLayoutProperty('mark-label', 'text-anchor', 'bottom'); map.setLayoutProperty('mark-label', 'text-offset', [0, -1.0]);
    setFireOpacity(true);
    lastFireKey = null; lastCellKey = null;
    var sh0 = S.shelters[dv.rt.sh];
    map.getSource('mark').setData({ type: 'FeatureCollection', features: sh0 ? [{ type: 'Feature', properties: { kind: 'shelter', label: '대피소 · ' + shelterName(dv.rt.sh) }, geometry: { type: 'Point', coordinates: sh0.entry || [sh0.lon, sh0.lat] } }] : [] });
    renderCrumbs();
    if (opts && opts.manual) { driveFrame(dv, dv.rt.ld, { snap: true }); renderSources(); return dv; }
    // approach: put the camera at the start, give tiles a moment, then play
    driveFrame(dv, dv.rt.ld, { snap: true });
    renderSources();
    var started = null;
    return new Promise(function (resolve) {
      dv.resolve = resolve;
      map.once('idle', function () {
        if (st.drive !== dv) return resolve(null);
        started = performance.now();
        (function step() {
          if (st.drive !== dv) return;
          var el = (performance.now() - started) / 1000;
          var tau = Math.min(dv.rt.arr, dv.rt.ld + el * dv.speed);
          driveFrame(dv, tau);
          if (tau < dv.rt.arr) driveRaf = requestAnimationFrame(step);
          else { dv.done = true; renderHud(dv); renderSources(); driveRaf = null; resolve(dv); }
        })();
      });
    });
  }
  function driveSeek(frac) { // tour / tests: deterministic position along the drive
    var dv = st.drive; if (!dv) return;
    var tau = dv.rt.ld + Math.max(0, Math.min(1, frac)) * dv.dur;
    dv.done = frac >= 1;
    driveFrame(dv, tau);
    if (dv.done) renderHud(dv);
  }
  function stopDrive(silent) {
    if (driveRaf) cancelAnimationFrame(driveRaf); driveRaf = null;
    var dv = st.drive;
    if (!dv) return;
    st.drive = null;
    document.body.classList.remove('driving');
    $('hud').hidden = true;
    if (vehicleMarker) vehicleMarker.remove();
    map.setCenterClampedToGround(true);
    map.setLayoutProperty('mark-label', 'text-anchor', 'top'); map.setLayoutProperty('mark-label', 'text-offset', [0, 1.0]);
    clearWalk(); // the travelled-road line belongs to the drive only
    setFireOpacity(false);
    map.resize();
    if (dv.resolve) dv.resolve(null);
    if (!silent) {
      st.view = 'place';
      map.setTerrain({ source: 'dem', exaggeration: EXAG.place });
      lastFireKey = null; lastCellKey = null;
      refreshAll();
      var cam = cameraFor(st.place, routeOf(st.place.id, kOf(st.s)));
      if (cam) map.flyTo({ center: cam.center, zoom: Math.min(cam.zoom, 14.2), pitch: 58, bearing: cam.bearing, duration: 1600 });
    } else {
      lastFireKey = null; lastCellKey = null;
      renderSources();
    }
  }

  // ------------------------------------------------------------------ play
  var playRaf = null;
  function togglePlay() {
    if (st.drive) return;
    st.playing = !st.playing;
    $('playBtn').textContent = st.playing ? '❚❚' : '▶';
    if (!st.playing) { if (playRaf) cancelAnimationFrame(playRaf); playRaf = null; return; }
    if (st.s >= 43200) setTime(0);
    var last = performance.now();
    (function step() {
      if (!st.playing) return;
      var now = performance.now(), dt = (now - last) / 1000; last = now;
      setTime(st.s + dt * 1200, { light: true }); // 1 hour per 3 s
      if (st.s >= 43200) { st.playing = false; $('playBtn').textContent = '▶'; renderSliderMarks(); return; }
      playRaf = requestAnimationFrame(step);
    })();
  }

  // ------------------------------------------------------------------ input wiring
  function wire() {
    var sl = $('slider'), pending = null;
    sl.addEventListener('input', function () {
      pending = Number(sl.value);
      if (!wire._raf) wire._raf = requestAnimationFrame(function () { wire._raf = null; if (pending != null) setTime(pending); pending = null; });
    });
    // like the arrow keys: the issue hour does not change under a drive (Esc first)
    $('prevBtn').addEventListener('click', function () { if (!st.drive) setTime(3600 * kOf(st.s - 1)); });
    $('nextBtn').addEventListener('click', function () { if (!st.drive) setTime(3600 * Math.min(NK - 1, kOf(st.s) + 1)); });
    $('playBtn').addEventListener('click', togglePlay);
    $('standinBtn').addEventListener('click', cycleStandin);
    $('aboutBtn').addEventListener('click', function () { if ($('about').hidden) renderAbout(); $('about').hidden = !$('about').hidden; });
    Array.prototype.forEach.call(document.querySelectorAll('#crumbs button[data-level]'), function (b) {
      b.addEventListener('click', function () {
        var lv = b.getAttribute('data-level');
        if (lv === 'region') home();
        else if (lv === 'place' && st.place) { if (st.drive) stopDrive(); else selectPlace(st.place.id); }
        else if (lv === 'drive' && st.place) startDrive();
      });
    });
    map.on('click', 'places-circle', function (e) { if (e.features && e.features[0]) selectPlace(e.features[0].properties.id); });
    map.on('click', 'places-label', function (e) { if (e.features && e.features[0]) selectPlace(e.features[0].properties.id); });
    var tip = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10, className: 'kcf-tip' });
    map.on('mousemove', 'places-circle', function (e) {
      map.getCanvas().style.cursor = 'pointer';
      var f = e.features && e.features[0]; if (!f || st.drive) return;
      var p = placeById[f.properties.id], k = kOf(st.s), h = hourly(p.id, k); if (!h) return;
      tip.setLngLat([p.lon, p.lat]).setHTML('<b>' + esc(p.label) + '</b><br><span class="step ' + esc(stepClass(h)) + '"' + srcAttr(SRC.per_place, csvDetail(h, 'government_step', null, k)) + '>' + esc((STEP_TXT[h.step] || [h.step])[0]) + '</span> <span' + srcAttr(SRC.per_place, csvDetail(h, h.state === 'LATEST_SAFE_DEPARTURE' ? 'latest_safe_departure_kst' : 'departure_state', null, k)) + '>' + esc(h.state === 'LATEST_SAFE_DEPARTURE' ? 'leave by ' + csvClock(h.lsd) : placeClock(h)) + '</span><br><small>per_place.csv line ' + (h.row + 1) + ' · ' + esc(issueLabel(k)) + ' screen · click for the place view</small>').addTo(map);
    });
    map.on('mouseleave', 'places-circle', function () { map.getCanvas().style.cursor = ''; tip.remove(); });
    document.addEventListener('keydown', function (e) {
      if (e.target && /INPUT|TEXTAREA/.test(e.target.tagName) && e.target.type !== 'range') return;
      var key = e.key;
      if (key === 'ArrowLeft') { e.preventDefault(); if (!st.drive) setTime(3600 * kOf(st.s - 1)); }
      else if (key === 'ArrowRight') { e.preventDefault(); if (!st.drive) setTime(3600 * Math.min(NK - 1, kOf(st.s) + 1)); }
      else if (key === ' ') { e.preventDefault(); togglePlay(); }
      else if (/^[1-6]$/.test(key) && S.named && S.named[Number(key) - 1]) selectPlace(S.named[Number(key) - 1].id);
      else if (key === 'c' || key === 'C') { if (st.place && !st.drive) runCheck(0); }
      else if (key === 'l' || key === 'L') { if (st.place && !st.drive) runCheck(60); }
      else if (key === 'd' || key === 'D') { if (st.place && !st.drive) startDrive(); }
      else if (key === 'Escape') back();
      else if (key === 'h' || key === 'H') home();
      else if (key === 'r' || key === 'R') cycleStandin();
      else if (key === 's' || key === 'S') { st.sourcesOpen = !st.sourcesOpen; renderSources(); }
      else if (key === '?') { if ($('about').hidden) renderAbout(); $('about').hidden = !$('about').hidden; }
    });
  }

  // ------------------------------------------------------------------ tour (deterministic, for the recorded fallback)
  // tour.seek(t) puts the scene in the state of tour time t (seconds) without animations, so a recorder can capture
  // frame by frame at any speed. Story: region 12:00 -> 18:00; one bookmarked place; check it; one minute later;
  // chase-view drive; back to the region.
  var TOUR_PLAN = null;
  function lerp(a, b, f) { return a + (b - a) * f; }
  function ease(f) { f = Math.max(0, Math.min(1, f)); return f < 0.5 ? 2 * f * f : 1 - Math.pow(-2 * f + 2, 2) / 2; }
  function lerpCam(A, B, f) {
    var db = ((B.bearing - A.bearing + 540) % 360) - 180;
    return { center: [lerp(A.center[0], B.center[0], f), lerp(A.center[1], B.center[1], f)], zoom: lerp(A.zoom, B.zoom, f), pitch: lerp(A.pitch, B.pitch, f), bearing: A.bearing + db * f };
  }
  function tourPlan() {
    if (TOUR_PLAN) return TOUR_PLAN;
    var pid = Q.get('tourPlace') || (S.named && S.named[1] && S.named[1].id), p = placeById[pid] || placeByName[pid];
    var k = Q.has('tourIssue') ? Number(Q.get('tourIssue')) : 4;
    var c0 = map.cameraForBounds(new maplibregl.LngLatBounds(bounds0[0], bounds0[1]), { padding: { top: 80, bottom: 150, left: 40, right: 40 }, bearing: -8 });
    var region = { center: [c0.center.lng, c0.center.lat], zoom: c0.zoom, pitch: 52, bearing: -8 };
    var near = { center: [lerp(region.center[0], p.lon, 0.55), lerp(region.center[1], p.lat, 0.55)], zoom: region.zoom + 0.7, pitch: 55, bearing: 4 };
    var pc = cameraFor(p, routeOf(p.id, k));
    var placeCam = { center: [pc.center.lng, pc.center.lat], zoom: Math.min(pc.zoom, 14.2), pitch: 58, bearing: 4 };
    TOUR_PLAN = { p: p, k: k, region: region, near: near, placeCam: placeCam, duration: 90 };
    return TOUR_PLAN;
  }
  var tourState = { phase: null };
  function caption(html) { var c = $('caption'); c.hidden = !html; if (html && c.innerHTML !== html) c.innerHTML = html; }
  function tourSeek(t) {
    var P = tourPlan(), p = P.p, k = P.k;
    function ensurePlace() { if (kOf(st.s) !== k || st.s !== 3600 * k) setTime(3600 * k, { full: true }); if (!st.place || st.place.id !== p.id) selectPlace(p.id, { noCamera: true }); }
    function enter(phase, fn) { if (tourState.phase !== phase) { tourState.phase = phase; fn(); } }
    function arm(name) { if (st.standin !== name && S.hourly[name]) setStandin(name); }
    // leaving the drive by seeking back: stopDrive(true) keeps the drive's terrain, layers and view, so restore the place's
    function leaveDrive() { var was = !!st.drive; stopDrive(true); if (was) { st.view = 'place'; map.setTerrain({ source: 'dem', exaggeration: EXAG.place }); lastFireKey = null; lastCellKey = null; refreshAll(); } }
    var ARM2 = (S.standin_order || [])[1], h2 = ARM2 ? hourly(p.id, k, ARM2) : null, h1 = hourly(p.id, k, 'RUNNING');
    function captions() {
    if (t < 22) caption('<b>1 · REGION</b>known fire area = satellite detections before each issue hour · violet road cells close when R(h) reaches them · every place: government step and leave-by clock');
    else if (t < 44 || !h2) caption('<b>2 · PLACE</b>' + esc(p.name) + ': shelter, witness road on the terrain, latest safe departure · "Check it" re-walks the road against the ' + esc(issueLabel(k)) + ' closures' + (t >= 38 ? ' · one minute later: same road, 60 s later' : ''));
    else if (t < 50) caption('<b>2 · PLACE</b>R → <span' + armSrc(ARM2, k) + '>' + esc(shortLabel(ARM2)) + ' (frozen margin)</span>: the ' + esc(issueLabel(k)) + ' screen gives ' + esc(p.name) + ' <span' + srcAttr(SRC.per_place, csvDetail(h2, 'government_step / departure_state', ARM2, k)) + '>' + esc(h2.step === 'NONE' ? 'no step' : (STEP_TXT[h2.step] || [h2.step])[0]) + ', ' + esc(placeClock(h2)) + '</span>' +
      (h2.cut_before === 'yes' ? ' · the full record reached its road at <span' + srcAttr(SRC.per_place, csvDetail(h2, 'route_first_cut_by_reconstruction_kst', ARM2, k)) + '>' + esc(csvClock(h2.first_cut)) + '</span>, before that departure' : '') +
      (h1 && ARM2 !== 'RUNNING' ? ' · under RUNNING: <span' + srcAttr(SRC.per_place, csvDetail(h1, h1.state === 'LATEST_SAFE_DEPARTURE' ? 'latest_safe_departure_kst' : 'departure_state', 'RUNNING', k)) + '>' + esc(h1.state === 'LATEST_SAFE_DEPARTURE' ? 'leave by ' + csvClock(h1.lsd) : placeClock(h1)) + '</span>' : '') + ' · each R(h) is its own: not a ranking');
    else caption('<b>3 · ROAD</b>drive along the witness road from the latest safe departure (chase view' + (st.drive ? ', playback ×' + st.drive.speed : '') + ') · fire = detections time-stamped before each moment · violet = cells the ' + esc(issueLabel(k)) + ' screen has closed');
    }
    if (t < 22) {
      enter('region', function () { stopDrive(true); arm('RUNNING'); st.place = null; st.view = 'region'; st.check = null; clearWalk(); map.setTerrain({ source: 'dem', exaggeration: EXAG.region }); refreshAll(); });
      var f = t < 3 ? 0 : (t - 3) / 17;
      setTime(Math.min(3600 * k, 3600 * k * Math.max(0, Math.min(1, f))), { full: true });
      map.jumpTo(lerpCam(P.region, P.near, ease(Math.max(0, (t - 8) / 14))));
    } else if (t < 27) {
      enter('fly', function () { leaveDrive(); arm('RUNNING'); ensurePlace(); });
      map.jumpTo(lerpCam(P.near, P.placeCam, ease((t - 22) / 5)));
    } else if (t < 50) {
      enter('place', function () { leaveDrive(); ensurePlace(); map.jumpTo(P.placeCam); });
      if (t < 44 || !h2) arm('RUNNING'); else arm(ARM2);
      if (t >= 31 && t < 38) {
        if (!st.check || st.check.offset !== 0) runCheck(0, { manual: true });
        st.check.show(Math.min(1, (t - 31) / 3));
      } else if (t >= 38 && t < 44) {
        if (!st.check || st.check.offset !== 60) runCheck(60, { manual: true });
        st.check.show(Math.min(1, (t - 38) / 2.5));
      }
    } else if (t < 86) {
      enter('drive', function () { arm('RUNNING'); ensurePlace(); st.check = null; clearWalk(); startDrive({ manual: true }); });
      driveSeek(Math.max(0, Math.min(1, (t - 53) / 30)));
    } else {
      enter('end', function () { if (!st.drive) { arm('RUNNING'); ensurePlace(); startDrive({ manual: true }); } driveSeek(1); });
    }
    captions();
    renderSources(); // after the caption: it lists the files behind what is on screen, the caption included
    return waitIdle();
  }
  function waitIdle() {
    return new Promise(function (res) {
      var done = false;
      map.once('idle', function () { if (!done) { done = true; res(); } });
      map.triggerRepaint();
      setTimeout(function () { if (!done) { done = true; res(); } }, 20000);
    });
  }

  // ------------------------------------------------------------------ boot
  var readyResolve;
  var ready = new Promise(function (r) { readyResolve = r; });
  window.KCF_APP = {
    ready: ready, timings: timings, state: st, map: map,
    setTime: function (s) { setTime(s, { full: true }); },
    setIssue: function (k) { setTime(3600 * k, { full: true }); },
    setStandin: setStandin, selectPlace: selectPlace, home: home, back: back,
    check: function (offset) { return runCheck(offset || 0, { instant: true }); },
    rewalk: function (placeId, k, depart, standin) { return rewalk(placeById[placeId], k, depart, standin); },
    drive: function (opts) { return opts && opts.manual ? startDrive({ manual: true }) : startDrive(); },
    driveSeek: driveSeek, stopDrive: stopDrive, idle: waitIdle,
    tour: { duration: 90, seek: tourSeek, plan: function () { return tourPlan(); } },
    sources: function () { renderSources(); return Array.prototype.map.call(document.querySelectorAll('#sources .p'), function (e) { return e.textContent; }); }
  };

  renderTicks(); renderBookmarks(); renderStandinBtn(); renderLegend(); renderAbout(); wire();
  var fontReady = loadUiFont();
  map.on('load', function () {
    timings.map_load_ms = Math.round(performance.now() - T0);
    // Hangul labels are drawn with the local UI font (localIdeographFontFamily): set label data once it is loaded
    fontReady.then(function () {
      timings.font_ms = Math.round(performance.now() - T0);
      fontsLoaded = true;
      map.getSource('towns').setData((BM && BM.towns) || emptyFC());
      lastPlacesKey = null; setPlaces(kOf(st.s));
    });
    map.getSource('fire').setData(buildFireFC());
    map.getSource('cells').setData(buildCellsFC());
    // deep links: ?t=18:00 ?place=옥류리 ?standin=WORST
    var t = Q.get('t'); if (t) { var s = parseKstToS(t); if (s != null) st.s = Math.max(0, Math.min(43200, s)); }
    var si = Q.get('standin'); if (si) si = si.replace(/[ +]/g, '_'); if (si && S.hourly[si]) { st.standin = si; map.getSource('cells').setData(buildCellsFC()); }
    refreshAll();
    var pl = Q.get('place'); if (pl) selectPlace(pl);
    map.once('idle', function () {
      timings.first_idle_ms = Math.round(performance.now() - T0);
      fontReady.then(function () {
        $('loading').classList.add('gone');
        if (SOFT) {
          var n = document.createElement('div'); n.id = 'notice';
          n.innerHTML = 'No GPU in use (' + esc(GL.renderer) + '): drawing is slow on this machine' + (LITE ? ', lite mode is on' : '') + '. Turn on hardware acceleration, or play the <a href="kcf_scene_tour_90s.mp4" style="color:#ffd98a">90-s recording</a>. <button type="button">×</button>';
          document.body.appendChild(n);
          n.querySelector('button').addEventListener('click', function () { n.remove(); });
          if (!TOUR) setTimeout(function () { if (n.parentNode) n.remove(); }, 15000); else n.remove();
        }
        timings.ready_ms = Math.round(performance.now() - T0);
        readyResolve(timings);
      });
    });
  });
})();
