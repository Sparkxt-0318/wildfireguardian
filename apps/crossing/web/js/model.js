// Pure helpers of the crossing web UI (no DOM, no three.js): State access, number formatting and the verdict the
// panel shows. Runs in the browser and in node (tests/test_web_static.py runs it on synthetic States).
//
// The UI never makes a decision. It shows the effective verdict the crossing app sends, except that it shows
// CLOSED itself (fail closed) when it cannot trust what it has: no State yet, socket closed, the last State older
// than UI_STALE_S on the browser clock, an unknown schema or verdict, missing verdict timing for a non-CLOSED
// verdict, or the 5 s verdict expiry reached by the local countdown between pushes.

import { F, SENSORS } from "./fields.js";

export const SCHEMA = "crossing.state/1";
export const UI_STALE_S = 2.0;          // browser-side: a State older than this is not shown as a go verdict
export const VERDICTS = ["CLOSED", "CROSS FAST", "SPRAY THEN RE-CHECK", "REOPENED"];

// Text, not colour alone: every verdict has a label, a glyph and an instruction line.
export const VERDICT_STYLE = {
  "CLOSED": { cls: "v-closed", glyph: "✖", say: "Do not cross." },
  "CROSS FAST": { cls: "v-go", glyph: "▶▶", say: "Advisory: within the PLACEHOLDER dose limit at or above the minimum speed." },
  "SPRAY THEN RE-CHECK": { cls: "v-spray", glyph: "◆", say: "Spray, stop, wait for a new verdict." },
  "REOPENED": { cls: "v-reopen", glyph: "✔", say: "Road behind reported reopened." },
};

// Plain-language text for reason codes (codes are shown too). Reason codes are display only: the verdict shown is
// the app's verdict state (or CLOSED forced by the browser); no reason code, known or unknown, can make it a go.
// Codes this UI does not know are shown as sent (humanised) and marked "code not known to this UI".
export const REASON_TEXT = {
  LINK_DOWN: "no data link to the roof unit",
  SENSOR_NOT_FRESH: "a required sensor is not fresh",
  SENSOR_FAULT: "a required sensor reports a fault",
  INPUT_TIME_MISSING: "no time stamp for a required input",
  INPUT_TOO_OLD: "a required input is too old",
  INPUT_TIME_IN_FUTURE: "an input time stamp is in the future",
  VALUE_INVALID: "an input value is invalid or out of range (PLACEHOLDER range)",
  VALUE_MISSING: "a required input value is missing",
  INPUTS_MALFORMED: "decision inputs malformed",
  VEHICLE_INVALID: "vehicle profile invalid",
  GNSS_NO_FIX: "no GNSS fix",
  RADAR_UNKNOWN: "radar cannot judge (no baseline, moving or stale)",
  FLAME_NOT_CONFIRMED: "flame not confirmed by radar AND thermal",
  FLAME_UNKNOWN: "flame status unknown",
  FLAME_RADAR_INCONSISTENT: "flame status inconsistent with the radar",
  FLAME_EVIDENCE_TOO_SHORT: "flame confirmed for too short a time",
  NEAR_EDGE_NOT_OBSERVED: "flame base (near edge) on the path not observed",
  NO_FAR_ECHO: "no solid radar echo beyond the flame",
  DEPTH_INVALID: "flame depth unknown",
  INTENSITY_INVALID: "fire intensity unknown",
  DOSE_INVALID: "dose could not be computed",
  DOSE_OVER_LIMIT: "dose over the PLACEHOLDER limit even at max safe speed",
  DOSE_WITHIN_LIMIT: "dose within the PLACEHOLDER limit",
  DOSE_WITHIN_SPRAY_MARGIN: "dose within the PLACEHOLDER spray margin only",
  NO_WATER_FOR_SPRAY: "vehicle has no water for spraying",
  INTAKE_AIR_OVER_LIMIT: "intake air over the PLACEHOLDER vehicle limit",
  PLATE_DISC_OVER_TEMP: "flux disc at or over its 70 °C limit (user-set): PETG tabs at risk, plate flux not used",
  FLAME_PRESENT: "flame still present",
  FLAME_PIXELS_PRESENT: "flame-temperature pixels still in view",
  PLATE_FLUX_ABOVE_REOPEN: "plate flux above the PLACEHOLDER reopen threshold",
  REOPEN_HOLD_NOT_MET: "quiet for less than the PLACEHOLDER hold time",
  REOPEN_CROSSING_NOT_IN_VIEW: "the crossed road is not in the sensor view",
  REOPEN_CONDITIONS_HELD: "quiet for the full PLACEHOLDER hold time after passing",
  VERDICT_EXPIRED: "verdict older than 5 s",
  NO_VERDICT: "no verdict yet",
  UNSPECIFIED: "no reason given",
  INTERNAL_ERROR: "app internal error",
  UI_NO_STATE: "browser has no State from the app",
  UI_SOCKET_CLOSED: "browser not connected to the app",
  UI_STATE_STALE: "browser State too old",
  UI_BAD_SCHEMA: "unknown State schema",
  UI_BAD_VERDICT: "unknown verdict",
  UI_NO_TIMING: "verdict timing missing",
  UI_EXPIRED: "verdict expired (browser countdown)",
};

// Crew instructions shown in the verdict box for some CLOSED reasons. Matched on the code (before ":") by name, so
// renamed codes from the decision module still get the instruction where the meaning is unambiguous. Advisory.
export const REASON_ACTIONS = [
  { re: /^REOPEN_.*(NOT_IN_VIEW|OUT_OF_VIEW|NOT_VISIBLE|NOT_OBSERVED)|^(CROSSING|CROSSED_ROAD)_.*(NOT_IN_VIEW|OUT_OF_VIEW|NOT_VISIBLE)/,
    say: "Face the crossed road: turn the vehicle so the sensor head looks at the road just crossed. REOPENED needs it in view." },
  { re: /^NEAR_EDGE_.*(NOT_OBSERVED|NOT_SEEN|NOT_IN_VIEW|MISSING)/,
    say: "Keep the flame base on the road in the sensor view; no crossing verdict without it." },
  { re: /^PLATE_DISC_OVER_TEMP$/,
    say: "Flux disc over 70 °C: PETG tabs at risk. Move away from the heat and let the disc cool." },
  { re: /^FLAME_.*(TOO_SHORT|NOT_PERSISTENT|NOT_STABLE)/,
    say: "Hold position and wait for a new verdict; the flame has not been seen long enough." },
];

function codeKey(code) {
  return String(code).split(":")[0];
}

// Distinct crew instruction lines for a list of reason codes (empty if none applies).
export function reasonActions(codes) {
  const out = [];
  for (const c of Array.isArray(codes) ? codes : []) {
    const k = codeKey(c);
    for (const a of REASON_ACTIONS) if (a.re.test(k) && out.indexOf(a.say) < 0) out.push(a.say);
  }
  return out;
}

export function isKnownReason(code) {
  return Object.prototype.hasOwnProperty.call(REASON_TEXT, codeKey(code));
}

function walk(obj, parts) {
  let o = obj;
  for (const p of parts) {
    if (o === null || o === undefined || typeof o !== "object" || Array.isArray(o)) return undefined;
    if (!Object.prototype.hasOwnProperty.call(o, p)) return undefined;
    o = o[p];
  }
  return o;
}

function clean(path, vars) {
  let p = path.endsWith("?") ? path.slice(0, -1) : path;
  if (vars) for (const k of Object.keys(vars)) p = p.split("{" + k + "}").join(vars[k]);
  return p;
}

// State value at a fields.js path; undefined if any part is missing ("no data").
export function sv(state, path, vars) {
  return walk(state, clean(path, vars).split("."));
}

// Value of one list element at the part of a "[]" path after the last "[].".
export function el(item, path) {
  const p = clean(path);
  const i = p.lastIndexOf("[].");
  return walk(item, (i >= 0 ? p.slice(i + 3) : p).split("."));
}

export function num(v) {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

// "12.3 m" or the dash for no data.
export function fmt(v, digits, unit) {
  const x = num(v);
  if (x === null) return "—";
  return x.toFixed(digits === undefined ? 1 : digits) + (unit ? " " + unit : "");
}

export function fmtRange(lo, hi, digits, unit) {
  const a = num(lo), b = num(hi);
  if (a === null && b === null) return "—";
  const d = digits === undefined ? 1 : digits;
  return (a === null ? "?" : a.toFixed(d)) + "–" + (b === null ? "∞" : b.toFixed(d)) + (unit ? " " + unit : "");
}

export function reasonText(code) {
  const c = String(code);
  const key = codeKey(c);
  const detail = c.length > key.length ? " (" + c.slice(key.length + 1) + ")" : "";
  if (isKnownReason(key)) return REASON_TEXT[key] + detail;
  // unknown code: shown generically, never interpreted (display only; the verdict state alone is shown)
  const words = /^[A-Z0-9_]+$/.test(key) ? key.toLowerCase().split("_").filter(Boolean).join(" ") : key;
  return (words || "reason") + detail + " [code not known to this UI]";
}

// Verdict to show, with the browser-side fail-closed overrides.
//   client = {hasState, wsOpen, sinceRxS (seconds since this State arrived, browser clock)}
// Returns {state, reasons[], codes[], actions[] (crew instructions), override (true if the UI forced CLOSED),
// expiresInS, style, decided}.
export function shownVerdict(state, client) {
  const forced = (code, detail) => {
    const codes = [detail ? code + ":" + detail : code];
    return { state: "CLOSED", codes, reasons: codes.map(reasonText), actions: [], override: true, expiresInS: null,
             style: VERDICT_STYLE["CLOSED"], decided: state ? sv(state, F.verdictState) : undefined };
  };
  if (!client || !client.hasState || !state || typeof state !== "object") return forced("UI_NO_STATE");
  if (!client.wsOpen) return forced("UI_SOCKET_CLOSED");
  const since = num(client.sinceRxS);
  if (since === null || since > UI_STALE_S) return forced("UI_STATE_STALE", since === null ? "unknown" : since.toFixed(1) + " s");
  if (sv(state, F.schema) !== SCHEMA) return forced("UI_BAD_SCHEMA", String(sv(state, F.schema)));
  const st = sv(state, F.verdictState);
  if (VERDICTS.indexOf(st) < 0) return forced("UI_BAD_VERDICT", String(st));
  const issued = num(sv(state, F.verdictIssued)), expires = num(sv(state, F.verdictExpires));
  const age = num(sv(state, F.verdictAge));
  let expiresInS = null;
  if (issued !== null && expires !== null && age !== null) expiresInS = (expires - issued) - age - since;
  if (st !== "CLOSED") {
    if (expiresInS === null) return forced("UI_NO_TIMING");
    if (expiresInS <= 0) return forced("UI_EXPIRED");
  }
  const reasons = sv(state, F.verdictReasons);
  const codes = Array.isArray(reasons) ? reasons.map(String) : [];
  return { state: st, codes, reasons: codes.map(reasonText), actions: reasonActions(codes), override: false, expiresInS,
           style: VERDICT_STYLE[st], decided: sv(state, F.verdictDecided) };
}

// Health lights: one entry per sensor, {name, ok, label, reason, age}. Missing health = not ok.
export function healthLights(state) {
  return SENSORS.map((name) => {
    const fresh = sv(state, F.sensorFresh, { sensor: name });
    const reason = sv(state, F.sensorReason, { sensor: name });
    const pi = sv(state, F.sensorPiStatus, { sensor: name });
    const ok = fresh === true;
    let why = typeof reason === "string" && reason ? reason : "";
    if (!ok && !why) why = fresh === undefined ? "no data" : "not fresh";
    return { name, ok, label: ok ? "OK" : (fresh === undefined ? "NO DATA" : "NOT FRESH"), reason: why,
             age: num(sv(state, F.sensorAge, { sensor: name })), pi: typeof pi === "string" ? pi : null };
  });
}

// Dose vs limit for the bar: fraction (may exceed 1), or null.
export function doseFraction(dose, limit) {
  const d = num(dose), l = num(limit);
  if (d === null || l === null || l <= 0) return null;
  return d / l;
}

// Interpolated ground height of the road profile at along-course distance s (linear, extrapolated with the end
// segments; flat 0 when no usable profile).
export function groundAt(sArr, dzArr, s) {
  if (!Array.isArray(sArr) || !Array.isArray(dzArr) || sArr.length < 2 || sArr.length !== dzArr.length) return 0;
  const n = sArr.length;
  const xs = [], ys = [];
  for (let i = 0; i < n; i++) {
    const a = num(sArr[i]), b = num(dzArr[i]);
    if (a !== null && b !== null && (xs.length === 0 || a > xs[xs.length - 1])) { xs.push(a); ys.push(b); }
  }
  if (xs.length < 2) return 0;
  let i = 1;
  if (s <= xs[0]) i = 1;
  else if (s >= xs[xs.length - 1]) i = xs.length - 1;
  else while (i < xs.length - 1 && xs[i] < s) i++;
  const t = (s - xs[i - 1]) / (xs[i] - xs[i - 1]);
  return ys[i - 1] + t * (ys[i] - ys[i - 1]);
}

// Temperature colour ramp for the thermal thumbnail (dark -> red -> yellow -> white), v in [0, 1].
export function ramp(v) {
  const x = Math.max(0, Math.min(1, v));
  const r = Math.min(255, Math.round(x * 3 * 255));
  const g = Math.min(255, Math.max(0, Math.round((x * 3 - 1) * 255)));
  const b = Math.min(255, Math.max(0, Math.round((x * 3 - 2) * 255)));
  return [r, g, b];
}
