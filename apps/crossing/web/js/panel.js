// Side panel of the crossing web UI: writes the State into the DOM. No three.js here, so the panel keeps working
// when WebGL or the 3D module is unavailable. All State reads go through sv()/el() with fields.js paths.

import { F } from "./fields.js";
import { sv, el, num, fmt, fmtRange, shownVerdict, healthLights, doseFraction, reasonText, isKnownReason, ramp } from "./model.js";

const $ = (id) => document.getElementById(id);

function setText(id, text) {
  const n = $(id);
  if (n && n.textContent !== text) n.textContent = text;
}

function statusSpan(text, kind) {
  const s = document.createElement("span");
  s.className = kind === "ok" ? "st-ok" : kind === "warn" ? "st-warn" : "st-bad";
  s.textContent = text;
  return s;
}

function setNodes(id, nodes) {
  const n = $(id);
  if (!n) return;
  n.replaceChildren(...nodes.map((x) => (typeof x === "string" ? document.createTextNode(x) : x)));
}

const BOOL = (v) => (v === true ? "yes" : v === false ? "no" : "—");

export function renderVerdict(state, client) {
  const v = shownVerdict(state, client);
  const box = $("verdict-box");
  box.className = "verdict " + v.style.cls;
  setText("verdict-glyph", v.style.glyph);
  setText("verdict-state", v.state);
  setText("verdict-say", v.style.say);
  const ex = num(v.expiresInS);
  setText("verdict-expiry", ex === null ? "expires —" : (ex > 0 ? "expires in " + ex.toFixed(1) + " s" : "expired"));
  const ov = $("verdict-override");
  ov.hidden = !v.override;
  if (v.override) ov.textContent = "CLOSED shown by the browser" + (v.decided ? " (app said " + v.decided + ")" : "");
  // crew instructions for some CLOSED reasons (e.g. face the crossed road); advisory, never a go
  const acts = Array.isArray(v.actions) ? v.actions : [];
  const act = $("verdict-action");
  act.hidden = acts.length === 0;
  setText("verdict-action", acts.join(" "));
  // SIMULATED / REPLAY next to the verdict itself (the 3D watermark is not enough: the view can be unavailable)
  const sim = !!state && sv(state, F.sim) === true;
  const replay = !!state && sv(state, F.mode) === "replay";
  const tag = $("verdict-sim");
  tag.hidden = !(sim || replay);
  setText("verdict-sim", sim ? (replay ? "SIMULATED DATA (replay)" : "SIMULATED DATA") : replay ? "REPLAY: recorded data, not live" : "");
  const ul = $("verdict-reasons");
  const items = v.codes.map((c, i) => {
    const li = document.createElement("li");
    if (!isKnownReason(c)) li.className = "unknown-reason";
    li.append(document.createTextNode(v.reasons[i] + " "));
    const code = document.createElement("code");
    code.textContent = c;
    li.append(code);
    return li;
  });
  ul.replaceChildren(...items);
  return v;
}

export function renderPanel(state, client, shown) {
  const s = state || {};
  const go = shown && !shown.override && (shown.state === "CROSS FAST" || shown.state === "SPRAY THEN RE-CHECK");

  // banner, watermark
  const adv = sv(s, F.advisory);
  if (typeof adv === "string" && adv) setText("advisory-text", adv);
  const sim = sv(s, F.sim) === true;
  const replay = sv(s, F.mode) === "replay";
  $("sim-badge").hidden = !(sim || replay);
  setText("sim-badge", sim ? (replay ? "SIMULATED DATA: REPLAY" : "SIMULATED DATA") : replay ? "REPLAY: NOT LIVE" : "SIMULATED DATA");
  $("sim-watermark").hidden = !sim;

  // crossing figures: only meaningful for a go verdict that is currently shown
  const ms = num(sv(s, F.minSpeed)), mk = num(sv(s, F.minSpeedKmh));
  setText("min-speed", go && ms !== null ? fmt(ms, 1, "m/s") + "  (" + fmt(mk !== null ? mk : ms * 3.6, 1, "km/h") + ")" +
    (shown.state === "SPRAY THEN RE-CHECK" ? "  = max safe speed (PLACEHOLDER)" : "") : "—");
  setText("time-in-flame", fmt(sv(s, F.timeInFlame), 1, "s"));
  const dose = sv(s, F.dose), lim = sv(s, F.doseLimit);
  setText("dose", fmt(dose, 0) + " / " + fmt(lim, 0, "TDU"));
  const frac = doseFraction(dose, lim);
  const bar = $("dose-bar");
  bar.style.width = frac === null ? "0%" : Math.min(100, (frac / 1.5) * 100).toFixed(1) + "%";
  bar.className = "bar-fill" + (frac !== null && frac > 1 ? " over" : "");
  $("dose-bar-wrap").setAttribute("aria-label", frac === null ? "dose unknown" : "dose " + (frac * 100).toFixed(0) + " % of the placeholder limit");
  const note = sv(s, F.placeholderNote);
  setText("dose-note", typeof note === "string" && /PLACEHOLDER/.test(note) ? "PLACEHOLDER limit: set by fire service" :
    "PLACEHOLDER limit: set by fire service (app sent no placeholder note)");
  const qd = num(sv(s, F.qInFlame)), dmax = num(sv(s, F.doseAtMax));
  setText("dose-fds", "FDS C064 reference dose: " + fmt(sv(s, F.doseFdsRef), 0, "TDU") + " (reference only, never decides)" +
    (qd !== null ? ". In-flame flux used (conservative ends): " + fmt(qd, 0, "kW/m²") : "") +
    (dmax !== null ? ". Dose at max safe speed: " + fmt(dmax, 0, "TDU") : ""));

  // flame and geometry
  const fst = sv(s, F.flameStatus);
  setNodes("flame-status", fst === undefined ? ["—"] : [statusSpan(String(fst), fst === "FLAME" ? "warn" : fst === "UNKNOWN" ? "bad" : "ok"),
    " " + (sv(s, F.flameReason) || "")]);
  const tv = sv(s, F.thermalValid);
  setText("flame-thermal", tv === undefined ? "—" : (tv ? (sv(s, F.thermalAtBearing) === true ? "flame on path" : "no flame on path") +
    ", " + fmt(sv(s, F.thermalFlamePixels), 0) + " px ≥ " + fmt(sv(s, F.thermalTflame), 0, "°C") + " (PLACEHOLDER threshold), max " + fmt(sv(s, F.thermalTmax), 0, "°C") : "invalid frame"));
  const rst = sv(s, F.radarStatus);
  setNodes("flame-radar", rst === undefined ? ["—"] : [statusSpan(String(rst), rst === "UNKNOWN" ? "bad" : rst === "FLAME_EFFECT" ? "warn" : "ok"),
    " " + (sv(s, F.radarReason) || "")]);
  const ne = sv(s, F.nearEdge);
  setText("near-edge", sv(s, F.geoValid) !== true || num(ne) === null ? (sv(s, F.geoReason) ? "none (" + sv(s, F.geoReason) + ")" : "—")
    : fmt(ne, 1, "m") + "  [" + fmtRange(sv(s, F.nearEdgeLo), sv(s, F.nearEdgeHi), 1, "m") + "]" + (sv(s, F.occluded) === true ? "  base hidden behind a crest" : ""));
  const fh = sv(s, F.flameHeight);
  setText("flame-height", num(fh) === null ? "—" : fmt(fh, 2, "m") + "  [" + fmtRange(sv(s, F.flameHeightLo), sv(s, F.flameHeightHi), 2, "m") + "]");
  const lvl = num(sv(s, F.depthLevel));
  setText("depth", sv(s, F.depthValid) === true
    ? fmt(sv(s, F.depthM), 2, "m") + "  [" + (lvl !== null ? Math.round(lvl * 100) + " %: " : "") + fmtRange(sv(s, F.depthLo), sv(s, F.depthHi), 2, "m") + "]" +
      (sv(s, F.depthCalibrated) === true ? "  calibrated" : "  UNCALIBRATED") +
      (Array.isArray(sv(s, F.depthFlags)) && sv(s, F.depthFlags).length ? "; " + sv(s, F.depthFlags).join("; ") : "")
    : "invalid" + (sv(s, F.depthReason) ? " (" + sv(s, F.depthReason) + ")" : ""));
  // DEPTH-HI rule: the dose uses this upper end (>= the largest valid estimator upper end), not the combined hi
  const hd = num(sv(s, F.depthHiDecision)), hdFrom = sv(s, F.depthHiFrom);
  const disagree = Array.isArray(sv(s, F.depthFlags)) && sv(s, F.depthFlags).some((f) => typeof f === "string" && f.startsWith("ESTIMATORS_DISAGREE"));
  setText("depth-hi-decision", sv(s, F.depthValid) === true && hd !== null
    ? fmt(hd, 2, "m") + (typeof hdFrom === "string" && hdFrom ? "  (from " + hdFrom + ")" : "") + (disagree ? "  ESTIMATORS DISAGREE" : "")
    : "—");
  setText("far-echo", num(sv(s, F.farEcho)) === null ? "none" : fmt(sv(s, F.farEcho), 1, "m") + " (horizontal)");
  const ss = sv(s, F.slopeSource);
  setText("slope-source", typeof ss === "string" ? ss.toUpperCase() + (ss === "imu" ? "  (no DEM: IMU plane)" : ss === "dem" ? "  (DEM road profile)" : "") : "—");
  setText("imu", fmt(sv(s, F.imuPitch), 1, "°") + " / " + fmt(sv(s, F.imuRoll), 1, "°"));

  const rows = estimatorRows(s).map((cells) => {
    const tr = document.createElement("tr");
    for (const c of cells) { const td = document.createElement("td"); td.textContent = c; tr.append(td); }
    return tr;
  });
  $("est-table").tBodies[0].replaceChildren(...rows);

  renderThumb(s);

  // heat flux
  setText("plate-q", num(sv(s, F.fluxQ)) === null ? "—" + (sv(s, F.fluxReason) ? " (" + sv(s, F.fluxReason) + ")" : "") : fmt(sv(s, F.fluxQ), 2, "kW/m²"));
  setText("plate-dose", fmt(sv(s, F.fluxDose), 1, "TDU") + (sv(s, F.fluxDoseComplete) === false ? " (lower bound: gaps)" : ""));
  setText("intake", fmt(sv(s, F.tcAir), 1, "°C") + " / limit " + fmt(sv(s, F.vehIntakeLimit), 0, "°C") + " (PLACEHOLDER)");
  setText("intensity", fmt(sv(s, F.intensity), 0, "kW/m"));
  setText("heat-in-cf", fmt(sv(s, F.heatInFlameCf), 1, "kW/m²"));
  setText("heat-in-fds", fmt(sv(s, F.heatInFlameFds), 1, "kW/m²"));
  setText("heat-at-label", num(sv(s, F.heatAtD)) === null ? "at vehicle" : "at " + fmt(sv(s, F.heatAtD), 1, "m"));
  setText("heat-at-cf", fmt(sv(s, F.heatAtCf), 2, "kW/m²"));
  setText("heat-at-fds", fmt(sv(s, F.heatAtFds), 2, "kW/m²"));
  const hl = sv(s, F.heatLabel);
  setText("heat-label", (typeof hl === "string" ? hl : "FDS C064 reference, not a measurement") +
    (sv(s, F.heatValid) === false && sv(s, F.heatReason) ? ". No heat values: " + sv(s, F.heatReason) : ". Central depth and intensity; the decision uses the conservative ends."));

  // health
  // the browser's own view first: a closed socket or an old State makes everything below "as of" that State
  const since = num(client.sinceRxS);
  const stale = since === null || since > 2.0;
  const wsTxt = (client.wsOpen ? "browser ↔ app: connected" : "browser ↔ app: NOT CONNECTED") +
    (since === null ? ", no State yet" : since > 1.0 ? ", last State " + since.toFixed(0) + " s ago" : "");
  const lu = sv(s, F.linkUp);
  const piTxt = (lu === true ? "app ↔ roof unit: up" : "app ↔ roof unit: DOWN") +
    (lu !== true && sv(s, F.linkReason) ? " (" + sv(s, F.linkReason) + ")" : "") + (stale && lu === true ? " (as of the last State)" : "");
  const uid = sv(s, F.unitId);
  setNodes("link-status", [statusSpan(wsTxt, client.wsOpen && !stale ? "ok" : "bad"), "  ",
    statusSpan(piTxt, lu === true && !stale ? "ok" : "bad"),
    uid ? "  unit " + uid : ""]);
  const lights = healthLights(s).map((h0) => {
    // without a current State the browser cannot vouch for any sensor
    const h = stale || !client.wsOpen ? Object.assign({}, h0, { ok: false, label: "NO CURRENT STATE",
      reason: "browser has no current State" }) : h0;
    const li = document.createElement("li");
    const dot = document.createElement("span");
    dot.className = "dot " + (h.ok ? "ok" : "bad");
    dot.setAttribute("aria-hidden", "true");
    const nm = document.createElement("span");
    nm.className = "nm";
    nm.textContent = h.name;
    const st = statusSpan(h.label, h.ok ? "ok" : "bad");
    const why = document.createElement("span");
    why.className = "why";
    why.textContent = h.ok ? (h.age !== null ? h.age.toFixed(1) + " s" : "") : h.reason;
    why.title = h.reason + (h.pi ? " (Pi says " + h.pi + ")" : "");
    li.append(dot, nm, st, why);
    return li;
  });
  $("health").replaceChildren(...lights);
  const fix = sv(s, F.gnssFix);
  setText("gnss-line", "GNSS fix " + (fix === undefined || fix === null ? "—" : fix) + ", " + fmt(sv(s, F.gnssSats), 0) + " sats, speed " +
    fmt(sv(s, F.gnssSpeed), 1, "m/s") + " (" + fmt(sv(s, F.gnssSpeedKmh), 0, "km/h") + ")" + (sv(s, F.gnssMoving) === true ? ", moving" : ""));
  setText("reopen-line", "Reopen: passed " + BOOL(sv(s, F.reopenPassed)) + ", quiet " + fmt(sv(s, F.reopenQuiet), 0, "s") + " of " +
    fmt(sv(s, F.reopenHold), 0, "s") + " (PLACEHOLDER hold)");

  // step 9 routing link (only with --sim-link). Fail closed: a disabled link or a CLOSED the routing API refused is
  // shown in red; the crew must not assume the road is closed in routing.
  const slOn = sv(s, F.simlinkEnabled) === true;
  const slNode = $("simlink-line");
  if (slNode) slNode.hidden = !slOn;
  if (slOn) {
    const parts = [];
    if (sv(s, F.simlinkBlocked) === true) parts.push(statusSpan("Routing link DISABLED: " + (sv(s, F.simlinkBlockedReason) || "blocked"), "bad"), " ");
    const nc = sv(s, F.simlinkNotClosed);
    const ncN = Array.isArray(nc) ? nc.length : 0;
    if (ncN > 0) parts.push(statusSpan("ROAD NOT CLOSED IN ROUTING: " + ncN + " closure" + (ncN > 1 ? "s" : "") + " refused by the routing API", "bad"), " ");
    const rr = sv(s, F.simlinkReopenRefused);
    const rrN = Array.isArray(rr) ? rr.length : 0;
    if (rrN > 0) parts.push(statusSpan("REOPEN NOT APPLIED IN ROUTING: " + rrN + " reopen" + (rrN > 1 ? "s" : "") + " refused by the routing API (road may still be closed there)", "bad"), " ");
    if (sv(s, F.simlinkHandshakeRefused) === true) parts.push(statusSpan("routing API REFUSED the connection (token missing or wrong?)", "bad"), " ");
    const q = num(sv(s, F.simlinkQueued)), held = num(sv(s, F.simlinkHeld));
    parts.push(statusSpan("routing API " + (sv(s, F.simlinkConnected) === true ? "connected" : "NOT connected"), sv(s, F.simlinkConnected) === true ? "ok" : "bad"),
      ", closures held " + (held === null ? "—" : held) + (q ? ", " + q + " not yet confirmed by the API" : ""));
    setNodes("simlink-line", parts);
  }

  // vehicle, fuel, calibration
  const L = sv(s, F.vehLength), W = sv(s, F.vehWidth), H = sv(s, F.vehHeight);
  setText("vehicle-line", (sv(s, F.vehLabel) || "—") + ": " + fmt(L, 1) + " × " + fmt(W, 1) + " × " + fmt(H, 1, "m") +
    ", max safe speed " + fmt(sv(s, F.vehMaxSpeed), 1, "m/s") + " (PLACEHOLDER), water " + BOOL(sv(s, F.vehHasWater)));
  setText("fuel-line", (sv(s, F.fuelCode) || "—") + ": " + (sv(s, F.fuelName) || ""));
  setText("cal-line", "Calibration: " + (sv(s, F.calStatus) || "—"));
  const bp = sv(s, F.radarBaselinePresent);
  setText("baseline-line", "Radar baseline: " + (bp === true ? "present" : bp === false ? "none (" + (sv(s, F.radarBaselineReason) || "not captured") + ")" : "—") +
    (sv(s, F.radarMoving) === true ? "; vehicle moving" : ""));

  const errs = num(sv(s, F.errorsCount));
  setText("footer", "mode " + (sv(s, F.mode) || "—") + ", source " + (sv(s, F.source) || "—") + ", session " + (sv(s, F.unitSession) || "—") +
    ", verdict " + (sv(s, F.verdictId) || "—") + ", app UTC " + (sv(s, F.utc) || "—") + (errs ? ", pipeline errors " + errs : "") + (sv(s, F.simlinkEnabled) === true ? ", sim-link on" : "") +
    ". Advisory for trained crews. Not verified on hardware; not an operational system.");
}

// Depth-estimator table rows: [name (kind), value, 90 % range, status]. "used" only for an estimator named in
// depth.used of a VALID combined depth (fail closed: depth.used missing / not a list, or the combined depth invalid,
// means no row says "used"). A valid estimator the combination left out says why it was not used.
export function estimatorRows(state) {
  const s = state || {};
  const usedList = sv(s, F.depthValid) === true && Array.isArray(sv(s, F.depthUsed)) ? sv(s, F.depthUsed) : [];
  const usedSet = new Set(usedList.filter((x) => typeof x === "string"));
  const ests = sv(s, F.estimators);
  return (Array.isArray(ests) ? ests : []).map((e) => {
    const kind = el(e, F.estKind);
    const name = String(el(e, F.estName));
    let status;
    if (el(e, F.estValid) !== true) status = String(el(e, F.estReason) || "invalid");
    else if (usedSet.has(name)) status = "used";
    else if (kind === "experimental") status = "valid, not used (experimental, off by default)";
    else if (kind === "ceiling") status = "valid, not used (ceiling; not trusted by calibration)";
    else status = "valid, not used";
    return [name + (kind && kind !== "estimate" ? " (" + kind + ")" : ""), fmt(el(e, F.estValue), 2, "m"),
      fmtRange(el(e, F.estLo), el(e, F.estHi), 2), status];
  });
}

function renderThumb(s) {
  const c = $("thumb");
  const ctx = c.getContext && c.getContext("2d");
  const w = num(sv(s, F.thumbW)), h = num(sv(s, F.thumbH)), pix = sv(s, F.thumbPix);
  if (!ctx) return;
  if (w === null || h === null || typeof pix !== "string") {
    ctx.clearRect(0, 0, c.width, c.height);
    setText("thumb-cap", "thermal thumbnail: no valid frame");
    return;
  }
  let bytes;
  try { bytes = Uint8Array.from(atob(pix), (ch) => ch.charCodeAt(0)); } catch (e) { bytes = null; }
  if (!bytes || bytes.length !== w * h) { setText("thumb-cap", "thermal thumbnail: malformed"); return; }
  if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
  const img = ctx.createImageData(w, h);
  for (let i = 0; i < w * h; i++) {
    const [r, g, b] = ramp(bytes[i] / 255);
    img.data[4 * i] = r; img.data[4 * i + 1] = g; img.data[4 * i + 2] = b; img.data[4 * i + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  setText("thumb-cap", "thermal " + w + "×" + h + " (max-pooled), " + fmt(sv(s, F.thumbTmin), 0, "°C") + " to " + fmt(sv(s, F.thumbTmax), 0, "°C"));
}

export { reasonText };
