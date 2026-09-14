#!/usr/bin/env node
/**
 * Bundle the REAL production build into one self-contained HTML file that runs
 * with no server, no network, and no install.
 *
 * WHAT THIS IS, AND WHAT IT IS NOT
 * --------------------------------
 * This is the app from `src/`, compiled by Vite, byte-for-byte. It is NOT a
 * mock-up or a second implementation. The only thing replaced is the *transport*:
 * `fetch` and `EventSource` are answered from `demo-fixtures.json`, which holds
 * responses **recorded from the real gateway** running the committed synthetic
 * scenario (see `app/backend/scripts/capture_demo_fixtures.py`).
 *
 * So the danger level, the card selection and their order, the spread rings, the
 * route and its warnings are all the backend's own output. No triage rule is
 * reimplemented here — a second copy of those rules is exactly the thing that
 * would let the demo and the shipped app tell a resident different things.
 *
 * The three things the harness itself decides, all of them scaffolding:
 *   1. which recorded frame to serve (the time slider and place picker);
 *   2. `generated_utc`, rewritten to a deterministic demo clock so the screens
 *      refetch when the scenario time changes (they key off that field), and so
 *      the displayed time tracks the scenario rather than the capture run;
 *   3. a blank grid basemap, because map tiles are a network resource and this
 *      file has no network. The overlays are the recorded geometry.
 *
 * Usage:
 *   node scripts/make-offline-demo.mjs                  # both outputs
 *   node scripts/make-offline-demo.mjs --out path.html  # standalone only
 */

import { readFileSync, writeFileSync, readdirSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HERE, "..");
const REPO = resolve(FRONTEND, "..", "..");
const DIST = join(FRONTEND, "dist");

const args = process.argv.slice(2);
const outFlag = args.indexOf("--out");
const STANDALONE_OUT =
  outFlag >= 0 ? resolve(args[outFlag + 1]) : join(REPO, "marketing", "demo", "resident_app_offline.html");
const ARTIFACT_OUT = join(REPO, "marketing", "demo", "resident_app_offline.artifact.html");

// ---------------------------------------------------------------------------
// Inputs
// ---------------------------------------------------------------------------

function readDistAsset(ext) {
  const dir = join(DIST, "assets");
  const name = readdirSync(dir).find((f) => f.endsWith(ext));
  if (!name) throw new Error(`no ${ext} in ${dir} — run \`npm run build\` first`);
  return readFileSync(join(dir, name), "utf8");
}

let appCss, appJs, fixturesRaw;
try {
  appCss = readDistAsset(".css");
  appJs = readDistAsset(".js");
} catch (e) {
  console.error(`STOP: ${e.message}`);
  process.exit(2);
}
try {
  fixturesRaw = readFileSync(join(FRONTEND, "demo-fixtures.json"), "utf8");
} catch {
  console.error(
    "STOP: demo-fixtures.json missing — run:\n" +
      "  cd app/backend && python3 scripts/capture_demo_fixtures.py",
  );
  process.exit(2);
}

const fixtures = JSON.parse(fixturesRaw);
if (fixtures.mode !== "demo" || fixtures.synthetic !== true) {
  console.error("STOP: fixtures are not the labelled synthetic demo capture");
  process.exit(2);
}

// A seamless 256 px grid tile: the basemap is a network resource and this file
// has no network, so the map gets honest graph paper instead of a fake terrain.
const TILE_SVG =
  `<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256">` +
  `<rect width="256" height="256" fill="%23EFF2E9"/>` +
  `<path d="M0 0H256M0 0V256" stroke="%23DFE5D6" stroke-width="2"/>` +
  `<path d="M0 64H256M0 128H256M0 192H256M64 0V256M128 0V256M192 0V256" ` +
  `stroke="%23E6EBDE" stroke-width="1"/></svg>`;
const TILE_URL = `data:image/svg+xml;utf8,${TILE_SVG}`;

// ---------------------------------------------------------------------------
// The transport shim (runs as a classic script, before the deferred module)
// ---------------------------------------------------------------------------

const SHIM = /* js */ `
(function () {
  "use strict";
  var F = window.__WFG_DEMO__;
  var TILE = ${JSON.stringify(TILE_URL)};
  var LS = { place: "wfgdemo.place", t: "wfgdemo.t" };

  // ---- harness state ------------------------------------------------------
  function places() { return F.places; }
  function placeById(id) {
    for (var i = 0; i < F.places.length; i++) if (F.places[i].id === id) return F.places[i];
    return F.places[0];
  }
  var state = {
    place: placeById(localStorage.getItem(LS.place) || "ahead"),
    ti: Math.min(Math.max(parseInt(localStorage.getItem(LS.t) || "6", 10) || 0, 0), F.times.length - 1)
  };

  // The app reads its home coordinate from this preference at mount, so the
  // marker on the map and the coordinate in every request agree with the
  // place the viewer picked.
  localStorage.setItem("wfg.home", JSON.stringify({
    lat: state.place.lat, lon: state.place.lon, label: state.place.label_ko
  }));

  function curT() { return F.times[state.ti]; }
  function nearestPlaceId(lat, lon) {
    if (!isFinite(lat) || !isFinite(lon)) return state.place.id;
    var best = state.place.id, bestD = Infinity;
    for (var i = 0; i < F.places.length; i++) {
      var p = F.places[i], d = (p.lat - lat) * (p.lat - lat) + (p.lon - lon) * (p.lon - lon);
      if (d < bestD) { bestD = d; best = p.id; }
    }
    return best;
  }
  function nearestTime(t) {
    var best = F.times[0], bestD = Infinity;
    for (var i = 0; i < F.times.length; i++) {
      var d = Math.abs(F.times[i] - t);
      if (d < bestD) { bestD = d; best = F.times[i]; }
    }
    return best;
  }

  // Deterministic demo clock: the screens refetch when generated_utc changes,
  // and this makes the displayed time track scenario time instead of the
  // moment the fixtures happened to be recorded.
  var CLOCK0 = Date.UTC(2026, 2, 25, 9, 0, 0);
  function stamp(t) { return new Date(CLOCK0 + t * 60000).toISOString().replace(/\\.\\d+Z$/, "Z"); }
  function situationFor(pid, t) {
    var s = F.by_place_t[pid + "|" + t];
    if (!s) return null;
    var out = JSON.parse(JSON.stringify(s.situation));
    out.generated_utc = stamp(t);
    return out;
  }

  // ---- fetch --------------------------------------------------------------
  function resolveRequest(path, search) {
    var q = new URLSearchParams(search || "");
    var pid = q.has("lat") ? nearestPlaceId(parseFloat(q.get("lat")), parseFloat(q.get("lon"))) : state.place.id;
    var t = q.has("t") ? nearestTime(parseInt(q.get("t"), 10)) : curT();
    var frame = F.by_place_t[pid + "|" + t] || {};
    switch (path) {
      case "/v1/health":    return { ok: true, mode: "demo", time_utc: stamp(t) };
      case "/v1/config":    { var c = JSON.parse(JSON.stringify(F.static["/v1/config"])); c.tile_url = TILE; return c; }
      case "/v1/situation": return situationFor(pid, t);
      case "/v1/spread":    return frame.spread || null;
      case "/v1/route":     return frame.route || null;
      case "/v1/fires":     return (F.by_t[t] || {}).fires || null;
      case "/v1/history":   return (F.by_t[t] || {}).history || null;
      case "/v1/shelters":  return (F.by_place[pid] || {}).shelters || null;
      case "/v1/billing/status": return F.static["/v1/billing/status"];
      case "/v1/billing/checkout":
        // Exactly what the gateway answers with no Stripe keys configured.
        return { __status: 503, body: {
          error: "billing_not_configured",
          detail_ko: "이 체험판에서는 결제를 사용할 수 없습니다.",
          detail_en: "Payments are not available in this offline demo."
        } };
      default: return null;
    }
  }

  function jsonResponse(body, status) {
    var text = JSON.stringify(body);
    if (typeof Response === "function") {
      return new Response(text, {
        status: status, headers: { "Content-Type": "application/json; charset=utf-8" }
      });
    }
    return { ok: status < 400, status: status, json: function () { return Promise.resolve(body); },
             text: function () { return Promise.resolve(text); } };
  }

  var realFetch = window.fetch ? window.fetch.bind(window) : null;
  window.fetch = function (input, init) {
    var url = typeof input === "string" ? input : (input && input.url) || "";
    var qi = url.indexOf("?");
    var path = (qi >= 0 ? url.slice(0, qi) : url).replace(/^https?:\\/\\/[^/]+/, "");
    if (path.indexOf("/v1/") === 0) {
      var res = resolveRequest(path, qi >= 0 ? url.slice(qi + 1) : "");
      if (res && res.__status) return Promise.resolve(jsonResponse(res.body, res.__status));
      if (res === null) return Promise.resolve(jsonResponse(
        { error: "not_in_demo_fixtures", detail_ko: "체험판에 없는 요청입니다.",
          detail_en: "This request is not part of the offline demo." }, 404));
      return Promise.resolve(jsonResponse(res, 200));
    }
    return realFetch ? realFetch(input, init) : Promise.reject(new Error("offline"));
  };

  // ---- EventSource --------------------------------------------------------
  // A working stream, so the app exercises its real SSE path rather than its
  // error fallback. Pushes a situation whenever the harness time changes.
  var streams = [];
  function FakeES(url) {
    this.url = url; this.readyState = 1; this._listeners = {};
    var q = new URLSearchParams((url.split("?")[1] || ""));
    this.pid = nearestPlaceId(parseFloat(q.get("lat")), parseFloat(q.get("lon")));
    streams.push(this);
    var self = this;
    setTimeout(function () { self.push(); }, 0);
  }
  FakeES.prototype.addEventListener = function (type, fn) {
    (this._listeners[type] = this._listeners[type] || []).push(fn);
  };
  FakeES.prototype.removeEventListener = function (type, fn) {
    var l = this._listeners[type] || [];
    var i = l.indexOf(fn); if (i >= 0) l.splice(i, 1);
  };
  FakeES.prototype.push = function () {
    if (this.readyState !== 1) return;
    var s = situationFor(this.pid, curT());
    if (!s) return;
    var ev = { data: JSON.stringify(s), type: "situation" };
    (this._listeners.situation || []).forEach(function (fn) { try { fn(ev); } catch (e) {} });
  };
  FakeES.prototype.close = function () {
    this.readyState = 2;
    var i = streams.indexOf(this); if (i >= 0) streams.splice(i, 1);
  };
  window.EventSource = FakeES;

  // Never register the service worker here: it would cache this harness.
  if (navigator.serviceWorker && navigator.serviceWorker.register) {
    navigator.serviceWorker.register = function () { return Promise.reject(new Error("demo")); };
  }

  // ---- harness UI ---------------------------------------------------------
  function fmtT(t) {
    var h = Math.floor(t / 60), m = t % 60;
    return h + "시간 " + (m < 10 ? "0" : "") + m + "분";
  }
  function levelOf(pid, t) {
    var s = F.by_place_t[pid + "|" + t];
    return s ? s.situation.danger.level : "";
  }

  function build() {
    var bar = document.getElementById("wfg-controls");
    if (!bar) return;
    var opts = places().map(function (p) {
      return '<option value="' + p.id + '"' + (p.id === state.place.id ? " selected" : "") +
             ">" + p.label_ko + " · " + p.label_en + "</option>";
    }).join("");
    bar.innerHTML =
      '<div class="ctl-row">' +
        '<label class="ctl-lab" for="wfg-place">내 위치 · Where you are</label>' +
        '<select id="wfg-place" class="ctl-sel">' + opts + "</select>" +
      "</div>" +
      '<div class="ctl-row">' +
        '<label class="ctl-lab" for="wfg-time">산불 발생 후 경과 시간 · Time since ignition</label>' +
        '<div class="ctl-time">' +
          '<button id="wfg-play" class="ctl-btn" aria-label="Play">▶</button>' +
          '<input id="wfg-time" class="ctl-range" type="range" min="0" max="' + (F.times.length - 1) + '" value="' + state.ti + '">' +
          '<span id="wfg-tval" class="ctl-val"></span>' +
        "</div>" +
      "</div>" +
      '<p class="ctl-note" id="wfg-note"></p>';

    var sel = document.getElementById("wfg-place");
    var range = document.getElementById("wfg-time");
    var tval = document.getElementById("wfg-tval");
    var note = document.getElementById("wfg-note");
    var play = document.getElementById("wfg-play");

    function paint() {
      tval.textContent = fmtT(curT());
      var lv = levelOf(state.place.id, curT());
      var word = lv === "GO" ? "대피 EVACUATE" : lv === "WATCH" ? "주의 CAUTION" : "안전 SAFE";
      note.textContent = "이 화면은 실제 앱입니다 — 응답은 기록된 가상 시나리오입니다. " +
                         "현재 판정: " + word +
                         "   ·   The real app, answering from a recorded synthetic scenario.";
      note.setAttribute("data-level", lv);
    }
    function apply() {
      localStorage.setItem(LS.t, String(state.ti));
      paint();
      streams.forEach(function (s) { s.push(); });
    }
    range.addEventListener("input", function () { state.ti = parseInt(range.value, 10); apply(); });
    sel.addEventListener("change", function () {
      localStorage.setItem(LS.place, sel.value);
      localStorage.setItem(LS.t, String(state.ti));
      location.reload();   // the app reads its home coordinate once, at mount
    });
    var timer = null;
    play.addEventListener("click", function () {
      if (timer) { clearInterval(timer); timer = null; play.textContent = "▶"; return; }
      play.textContent = "⏸";
      timer = setInterval(function () {
        state.ti = (state.ti + 1) % F.times.length;
        range.value = String(state.ti);
        apply();
      }, 1400);
    });
    paint();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build);
  else build();
})();
`;

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

const STAGE_CSS = /* css */ `
:root{
  --stage-bg:#10150F; --stage-panel:#1B221A; --stage-ink:#E9EFE6; --stage-ink-2:#A3B29C;
  --stage-line:#2C352A; --stage-accent:#7FD1A2;
}
/* ⚠ THE STAGE MUST NOT STYLE THE APP.
   Everything here is inlined into ONE document with the app's own stylesheet,
   so a body colour or body font-family in the harness silently wins over the
   app's :root declarations and the thing on screen stops being the
   thing that ships. It already happened twice: the app name inherited the
   stage's pale-on-dark ink and rendered near-invisible on cream, and the
   harness font stack displaced "Noto Sans KR" as first choice. So the body
   rule carries background and box model only, stage chrome names its own
   colour and font, and #root restates the app's tokens as a backstop. */
html,body{margin:0;padding:0;background:var(--stage-bg);}
body{min-height:100vh;}
.stage-head,.controls{
  font-family:'Noto Sans KR',system-ui,-apple-system,'Segoe UI','Apple SD Gothic Neo','Malgun Gothic',sans-serif;
  color:var(--stage-ink);
}
.stage{max-width:1100px;margin:0 auto;padding:24px 20px 48px;display:flex;flex-direction:column;align-items:center;gap:20px}
/* Wide: phone and controls side by side, so the time slider is never below the
   fold — it is the whole point of the page. Narrow: controls fall underneath. */
.stage-main{display:flex;gap:26px;align-items:flex-start;justify-content:center;flex-wrap:wrap;width:100%}
.stage-head{text-align:center;max-width:64ch}
.stage-head h1{font-size:clamp(20px,3vw,28px);margin:0 0 6px;letter-spacing:-.01em;text-wrap:balance}
.stage-head p{margin:0;color:var(--stage-ink-2);font-size:15px;line-height:1.55}
.stage-head code{background:var(--stage-panel);border:1px solid var(--stage-line);border-radius:5px;padding:1px 5px;font-size:13px}

/* The phone. The app inside keeps its own light theme — that is the product's
   deliberate choice for elderly eyes, not an omission. */
.device{
  position:relative;width:400px;max-width:100%;height:760px;max-height:78vh;
  border:10px solid #05100A;border-radius:42px;overflow:hidden;background:#FAFAF7;
  box-shadow:0 30px 70px rgba(0,0,0,.55);flex:none;
}
#root{
  height:100%;overflow-y:auto;overflow-x:hidden;position:relative;
  color:var(--ink);background:var(--page);   /* the app's own tokens, restated */
}
/* keep the app's fixed tab bar inside the frame */
#root .app-shell{min-height:100%;height:100%}
#root .tabbar{position:absolute}

.controls{
  width:100%;max-width:400px;background:var(--stage-panel);border:1px solid var(--stage-line);
  border-radius:14px;padding:16px 18px;display:flex;flex-direction:column;gap:14px
}
.ctl-row{display:flex;flex-direction:column;gap:7px}
.ctl-lab{font-size:12px;letter-spacing:.13em;text-transform:uppercase;color:var(--stage-ink-2);font-weight:700}
.ctl-sel{
  font-family:inherit;font-size:15px;padding:11px 12px;border-radius:9px;
  background:#111811;color:var(--stage-ink);border:1px solid var(--stage-line);width:100%
}
.ctl-time{display:flex;align-items:center;gap:12px}
.ctl-btn{
  width:44px;height:44px;flex:none;border-radius:50%;border:none;cursor:pointer;
  background:var(--stage-accent);color:#08130C;font-size:16px;font-family:inherit
}
.ctl-range{flex:1;accent-color:var(--stage-accent);height:30px}
.ctl-val{font-variant-numeric:tabular-nums;font-weight:700;min-width:104px;text-align:right;font-size:15px}
.ctl-note{
  margin:0;font-size:13px;line-height:1.5;color:var(--stage-ink-2);
  border-left:3px solid var(--stage-line);padding-left:10px
}
.ctl-note[data-level="GO"]{border-left-color:#EF6B6B;color:#F3C9C9}
.ctl-note[data-level="WATCH"]{border-left-color:#E0A343;color:#EBD6AE}
.ctl-note[data-level="SAFE"]{border-left-color:var(--stage-accent);color:#BFE3CE}
.ctl-sel:focus-visible,.ctl-range:focus-visible,.ctl-btn:focus-visible{outline:3px solid var(--stage-accent);outline-offset:2px}
@media (max-width:520px){ .device{height:70vh} }
`;

const STAGE_HTML = `
<div class="stage">
  <div class="stage-head">
    <h1>산불지킴이 · WildfireGuardian — the resident app, running</h1>
    <p>This is the real production build from <code>app/frontend</code>. Its answers come from responses recorded off the real gateway, so the danger level, the cards, the spread rings and the route are the backend's own output. Move the time slider to watch the fire approach.</p>
  </div>
  <div class="stage-main">
    <div class="device"><div id="root"></div></div>
    <div class="controls" id="wfg-controls"></div>
  </div>
</div>
`;

function page({ wrapped }) {
  const head =
    `<title>산불지킴이 · WildfireGuardian — live demo</title>\n` +
    `<style>${appCss}</style>\n<style>${STAGE_CSS}</style>`;
  const body =
    STAGE_HTML +
    `\n<script>window.__WFG_DEMO__=${fixturesRaw.trim()};</script>\n` +
    `<script>${SHIM}</script>\n` +
    `<script type="module">${appJs}</script>`;
  if (!wrapped) return `${head}\n${body}\n`;
  return (
    `<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n` +
    `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n` +
    `<meta name="theme-color" content="#10150F">\n${head}\n</head>\n<body>\n${body}\n</body>\n</html>\n`
  );
}

mkdirSync(dirname(STANDALONE_OUT), { recursive: true });
writeFileSync(STANDALONE_OUT, page({ wrapped: true }), "utf8");
writeFileSync(ARTIFACT_OUT, page({ wrapped: false }), "utf8");

const mib = (s) => (Buffer.byteLength(s, "utf8") / 1048576).toFixed(2);
console.log(`wrote ${STANDALONE_OUT} (${mib(page({ wrapped: true }))} MiB)`);
console.log(`wrote ${ARTIFACT_OUT} (${mib(page({ wrapped: false }))} MiB)`);
console.log(`  ${fixtures.times.length} scenario times x ${fixtures.places.length} places`);
