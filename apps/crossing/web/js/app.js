// Entry point of the crossing web UI. Connects to WS /ws (State JSON, crossing.state/1), renders the panel and,
// when WebGL works, the 3D view. The 3D module (and with it three.js) is imported dynamically so a missing WebGL
// or a failed module load leaves the panel and the verdict working.
//
// Fail closed in the browser: the verdict box shows CLOSED whenever the State is missing, older than 2 s on the
// browser clock, from a closed socket, malformed, or past its 5 s expiry (model.shownVerdict). Re-checked every
// 100 ms, not only when a message arrives.

import { F } from "./fields.js";
import { sv } from "./model.js";
import { renderVerdict, renderPanel } from "./panel.js";

const $ = (id) => document.getElementById(id);

const client = { hasState: false, wsOpen: false, rxAt: null, sinceRxS: null, parseErrors: 0, messages: 0 };
let state = null;
let view = null;
let ws = null;
let backoff = 500;

// ------------------------------------------------------------------------------------------------ socket
function connect() {
  const url = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws";
  try {
    ws = new WebSocket(url);
  } catch (e) {
    scheduleReconnect();
    return;
  }
  ws.onopen = () => { client.wsOpen = true; backoff = 500; renderAll(); };
  ws.onmessage = (ev) => {
    let s;
    try { s = JSON.parse(ev.data); } catch (e) { client.parseErrors += 1; return; }
    if (!s || typeof s !== "object") { client.parseErrors += 1; return; }
    state = s;
    client.hasState = true;
    client.rxAt = performance.now();
    client.messages += 1;
    renderAll();
  };
  ws.onclose = () => { client.wsOpen = false; renderAll(); scheduleReconnect(); };
  ws.onerror = () => { try { ws.close(); } catch (e) { /* closing anyway */ } };
}

function scheduleReconnect() {
  setTimeout(connect, backoff);
  backoff = Math.min(5000, backoff * 2);
}

function updateClock() {
  client.sinceRxS = client.rxAt === null ? null : (performance.now() - client.rxAt) / 1000;
}

// The verdict last rendered into the panel ("state|override"): the 100 ms tick re-renders the panel at once when
// the shown verdict changes (e.g. the browser forces CLOSED on a stale State), so go-only figures such as the
// minimum speed never stay on screen next to a CLOSED box.
let panelShownKey = null;
const shownKey = (shown) => String(shown.state) + "|" + (shown.override ? "1" : "0");

function renderAll() {
  updateClock();
  const shown = renderVerdict(state, client);
  panelShownKey = shownKey(shown);
  try {
    renderPanel(state, client, shown);
  } catch (e) {
    $("action-result").textContent = "panel error: " + e;
  }
  if (view) {
    try { view.update(state); } catch (e) { $("action-result").textContent = "3D view error: " + e; }
  }
  syncSelectors();
  syncReplay();
  window.__crossingUi = { shown: shown.state, override: shown.override, codes: shown.codes, messages: client.messages,
                          parseErrors: client.parseErrors, view: view ? view.info() : null };
}

let ticks = 0;
function tick() {
  ticks += 1;
  if (ticks % 10 === 0) { renderAll(); return; }      // panel (link line, ages) at 1 Hz even without messages
  updateClock();
  const shown = renderVerdict(state, client);
  if (shownKey(shown) !== panelShownKey) { renderAll(); return; }   // shown verdict changed: panel follows now
  if (window.__crossingUi) Object.assign(window.__crossingUi, { shown: shown.state, override: shown.override, codes: shown.codes });
}

// ------------------------------------------------------------------------------------------------ 3D view
function webglAvailable() {
  if (new URLSearchParams(location.search).has("nowebgl")) return false;
  try {
    const c = document.createElement("canvas");
    return !!(window.WebGLRenderingContext && (c.getContext("webgl2") || c.getContext("webgl")));
  } catch (e) {
    return false;
  }
}

async function startView() {
  const why = $("view-fallback-why");
  if (!webglAvailable()) {
    $("view-fallback").hidden = false;
    $("legend").hidden = true;
    $("btn-reset-view").disabled = true;
    why.textContent = "WebGL is not available in this browser.";
    return;
  }
  try {
    const mod = await import("./scene.js");
    view = mod.createScene($("view"), $("labels"));
    if (state) view.update(state);
    $("btn-reset-view").onclick = () => view && view.resetView();
  } catch (e) {
    view = null;
    $("view-fallback").hidden = false;
    $("legend").hidden = true;
    $("btn-reset-view").disabled = true;
    why.textContent = "The 3D view could not start: " + e;
  }
}

// ------------------------------------------------------------------------------------------------ API calls
async function api(method, path, body) {
  const opt = { method, headers: {} };
  if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  const r = await fetch(path, opt);
  let data = null;
  try { data = await r.json(); } catch (e) { data = null; }
  return { ok: r.ok, status: r.status, data };
}

function say(text) { $("action-result").textContent = text; }

async function loadSelectors() {
  try {
    const v = await api("GET", "/api/vehicles");
    const sel = $("sel-vehicle");
    if (v.ok && v.data && v.data.vehicles) {
      sel.replaceChildren(...Object.keys(v.data.vehicles).map((k) => {
        const o = document.createElement("option");
        const p = v.data.vehicles[k] || {};
        o.value = k;
        o.textContent = (p.label || k) + (typeof p.length_m === "number" ? " (" + p.length_m + " m)" : "");
        return o;
      }));
      sel.value = v.data.selected;
      sel.disabled = false;
    }
  } catch (e) { say("could not load vehicles: " + e); }
  try {
    const f = await api("GET", "/api/fuels");
    const sel = $("sel-fuel");
    if (f.ok && f.data && Array.isArray(f.data.fuels)) {
      sel.replaceChildren(...f.data.fuels.map((x) => {
        const o = document.createElement("option");
        o.value = x.code;
        o.textContent = x.code + (x.name ? ": " + x.name : "");
        return o;
      }));
      sel.value = f.data.selected;
      sel.disabled = false;
    }
  } catch (e) { say("could not load fuels: " + e); }
}

function syncSelectors() {
  const vs = $("sel-vehicle"), fs = $("sel-fuel");
  const vn = sv(state, F.vehName), fc = sv(state, F.fuelCode);
  if (document.activeElement !== vs && typeof vn === "string" && vs.value !== vn && [...vs.options].some((o) => o.value === vn)) vs.value = vn;
  if (document.activeElement !== fs && typeof fc === "string" && fs.value !== fc && [...fs.options].some((o) => o.value === fc)) fs.value = fc;
}

function wireControls() {
  $("sel-vehicle").addEventListener("change", async (e) => {
    const r = await api("POST", "/api/vehicle", { name: e.target.value });
    say(r.ok ? "vehicle set: " + e.target.value + " (PLACEHOLDER limits)" : "vehicle refused: " + JSON.stringify(r.data));
    e.target.blur();
  });
  $("sel-fuel").addEventListener("change", async (e) => {
    const r = await api("POST", "/api/fuel", { code: e.target.value });
    say(r.ok ? "fuel set: " + e.target.value : "fuel refused: " + JSON.stringify(r.data));
    e.target.blur();
  });
  $("btn-baseline").addEventListener("click", async () => {
    let r = await api("POST", "/api/baseline", { action: "capture", force: false });
    if (r.ok && r.data && r.data.ok === false) {
      const msg = "Baseline refused: " + (r.data.reason || "") + "\n\nForce it anyway? A baseline taken with flame in view or " +
        "while moving can hide the radar flame effect. The verdict then stays CLOSED (fails closed), but the crossing cannot be judged.";
      if (window.confirm(msg)) r = await api("POST", "/api/baseline", { action: "capture", force: true });
    }
    say("baseline: " + (r.data ? (r.data.ok ? "captured" : "refused") + (r.data.reason ? " (" + r.data.reason + ")" : "") : "HTTP " + r.status));
  });
  $("btn-baseline-clear").addEventListener("click", async () => {
    const r = await api("POST", "/api/baseline", { action: "clear" });
    say(r.ok ? "baseline cleared" : "clear failed: HTTP " + r.status);
  });
  $("btn-mark").addEventListener("click", async () => {
    const raw = $("measured-m").value.trim();
    const m = raw === "" ? null : Number(raw);
    if (m !== null && !(Number.isFinite(m) && m >= 0)) { say("measured depth must be a number >= 0 or empty"); return; }
    const r = await api("POST", "/api/mark_crossing", { measured_m: m });
    const d = r.data || {};
    say("mark crossing: " + (d.ok ? "pair stored" : "not stored") + (d.reason ? " (" + d.reason + ")" : "") +
        (typeof d.measured_m === "number" ? ", measured " + d.measured_m.toFixed(2) + " m" : "") +
        (typeof d.predicted_m === "number" ? ", predicted " + d.predicted_m.toFixed(2) + " m" : "") + (d.sim ? " [SIMULATED store]" : ""));
  });
}

// ------------------------------------------------------------------------------------------------ replay
// Replay mode only: GET /api/replay -> {paused, speed, t, t_end, ended, ...}; POST /api/replay {"action": "play" |
// "pause"} or {"action": "speed", "speed": x} (crossing/server.py). Pausing is fail closed on the app side: the
// app marks the link down ("replay paused") and decides CLOSED; the UI only shows that. If the route is missing
// (older app) the controls stay disabled. The status is re-read every second while in replay mode.
let replayApi = null;    // null = not probed yet, undefined = probing, false = absent, object = status
let replayPolledAt = 0;

async function probeReplay() {
  try {
    const r = await api("GET", "/api/replay");
    replayApi = r.ok && r.data ? r.data : false;
  } catch (e) { replayApi = false; }
  replayPolledAt = performance.now();
  syncReplay();
}

function fmtT(x) {
  return typeof x === "number" && Number.isFinite(x) ? x.toFixed(1) + " s" : "?";
}

function syncReplay() {
  const isReplay = sv(state, F.mode) === "replay";
  $("replay-card").hidden = !isReplay;
  if (!isReplay) return;
  if (replayApi === null) { replayApi = undefined; probeReplay(); return; }
  if (replayApi === undefined) return;
  const pollMs = replayApi ? 1000 : 5000;           // absent / failed: try again now and then
  if (performance.now() - replayPolledAt > pollMs) { replayPolledAt = performance.now(); probeReplay(); }
  const on = !!replayApi;
  for (const id of ["btn-play", "btn-pause", "sel-speed"]) $(id).disabled = !on;
  const src = sv(state, F.source) || "";
  if (!on) {
    $("replay-line").textContent = "Replaying " + src + ". Play/pause/speed are not available: the app server has no /api/replay " +
      "endpoint (speed is set at start with --speed).";
    return;
  }
  const sel = $("sel-speed");
  const sp = typeof replayApi.speed === "number" ? String(replayApi.speed) : null;
  if (sp !== null && document.activeElement !== sel) {
    if (![...sel.options].some((o) => o.value === sp)) {
      const o = document.createElement("option");
      o.value = sp; o.textContent = sp;
      sel.append(o);
    }
    sel.value = sp;
  }
  $("btn-play").disabled = !replayApi.paused;
  $("btn-pause").disabled = !!replayApi.paused;
  const what = replayApi.ended ? "ended (Play starts it again)" : replayApi.paused ? "PAUSED" : "playing";
  $("replay-line").textContent = "Replay " + what + " at ×" + (sp || "?") + ", " + fmtT(replayApi.t) +
    (typeof replayApi.t_end === "number" ? " of " + fmtT(replayApi.t_end) : "") + ": " + src +
    (replayApi.paused ? ". Paused = no fresh data: the app shows CLOSED (link marked down)." : "") +
    (sv(state, F.sim) === true ? " SIMULATED data." : " Recorded data, not live.");
}

function wireReplay() {
  const send = async (body) => {
    let r;
    try { r = await api("POST", "/api/replay", body); } catch (e) { r = { ok: false, status: String(e), data: null }; }
    if (r.ok && r.data) replayApi = r.data;
    else say("replay control failed: HTTP " + r.status + (r.data && r.data.detail ? " (" + r.data.detail + ")" : ""));
    replayPolledAt = performance.now();
    syncReplay();
  };
  $("btn-play").addEventListener("click", () => send({ action: "play" }));
  $("btn-pause").addEventListener("click", () => send({ action: "pause" }));
  $("sel-speed").addEventListener("change", (e) => { send({ action: "speed", speed: Number(e.target.value) }); e.target.blur(); });
}

// ------------------------------------------------------------------------------------------------ start
renderVerdict(null, client);
wireControls();
wireReplay();
loadSelectors();
connect();
setInterval(tick, 100);
startView();
