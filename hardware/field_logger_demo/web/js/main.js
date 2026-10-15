// App shell: start screen, the two segments (Device, Replay), the summary, the keys (spec section 8) and export mode.
import { $, esc, bus, toast } from './util.js';
import { loadI18n, setLang, toggleLang, t, getLang } from './i18n.js';
import { get, openSocket } from './api.js';
import { StartScreen } from './start.js';
import { Booth, keyFooter } from './replay.js';
import { Summary } from './summary.js';
import { DeviceScreen } from './device.js';
import { LiveView } from './live.js';
import { DevPanel } from './devpanel.js';

const params = new URLSearchParams(location.search);
const state = { screen: 'start', segment: 'replay', library: [], booth: null, summary: null, device: null, dev: null, speed: 30, help: null };

function setVh() { document.documentElement.style.setProperty('--vh', `${window.innerHeight}px`); }
window.addEventListener('resize', setVh);
setVh();

async function main() {
  await loadI18n();
  setLang(params.get('lang') === 'en' ? 'en' : 'ko');
  if (params.get('export') === 'summary') return exportMode();
  state.start = new StartScreen($('#scr-start'), {
    device: () => show('device'),
    replay: (k) => replayKey(k),
    replayFirst: () => { const e = state.library.find(x => x.key); if (e) replayKey(e.key); },
  });
  state.booth = new Booth($('#scr-booth'));
  state.summary = new Summary($('#scr-summary'));
  state.live = new LiveView();
  state.device = new DeviceScreen($('#scr-device'), {
    replayFile: (f) => replayQuery(`file=${encodeURIComponent(f)}`),
    currentSegment: () => state.screen === 'device' ? 'device' : 'replay',
    renderLive: (container, snap) => state.live.render(container, snap),
  });
  state.devpanel = new DevPanel();
  for (const b of document.querySelectorAll('#seg button')) b.addEventListener('click', () => show(b.dataset.seg === 'device' ? 'device' : 'booth'));
  bus.on('lang', relabel);
  bus.on('speed', (s) => { state.speed = s; navChips(); });
  bus.on('replay-ended', (p) => { if (state.screen === 'booth' && p.metrics) showSummary(p); });
  bus.on('ws:snapshot', (ev) => onDevice(ev.state, true));
  bus.on('ws:state', (ev) => onDevice(ev.state, false));
  bus.on('ws:line', (ev) => state.device.addLine(ev));
  bus.on('ws:remask', (ev) => state.device.remask(ev.lines));
  bus.on('ws:ports', () => {});
  bus.on('ws-closed', () => { if (state.dev) navChips(); });
  bus.on('device-result', () => {});
  document.addEventListener('keydown', onKey);
  window.addEventListener('beforeunload', (e) => {
    const d = state.dev;
    if (d && d.status && d.status.state === 'RECORDING' && d.profile && d.profile.conncheck && d.profile.conncheck.close) { e.preventDefault(); e.returnValue = ''; }
  });
  relabel();
  await loadLibrary();
  openSocket();
  show('start');
}

async function loadLibrary() {
  try {
    const r = await get('/api/library');
    state.library = r.entries;
    state.start.setLibrary(r.entries);
  } catch (e) { toast(t('err.server'), true, 8000); }
}

function onDevice(snap, full) {
  const prev = state.dev;
  state.dev = snap;
  state.device.setSnapshot(snap, full);
  state.start.setDevice(snap);
  state.devpanel.update(snap);
  if (prev && prev.conn.state === 'connected' && snap.conn.state === 'lost') toast(t('dev.disconnected'), true, 5000);
  if (prev && prev.result !== snap.result && snap.result && snap.result.file && !snap.result.device_test && state.screen === 'device') loadLibrary();
  navChips();
}

// ------------------------------------------------------------------ screens
function show(name) {
  state.screen = name;
  document.body.classList.toggle('light', name === 'summary');
  document.body.classList.toggle('dark', name !== 'summary');
  for (const s of document.querySelectorAll('.screen')) s.classList.remove('on');
  const id = { start: '#scr-start', booth: '#scr-booth', device: '#scr-device', summary: '#scr-summary' }[name];
  $(id).classList.add('on');
  $('#nav').classList.toggle('hidden', name === 'summary');
  $('#nav-title').textContent = name === 'start' ? '' : t('app.title');
  $('#seg').classList.toggle('off', name === 'start' || name === 'summary');
  $('#seg-device').classList.toggle('on', name === 'device');
  $('#seg-replay').classList.toggle('on', name === 'booth');
  state.device.visible = name === 'device';
  fetch('/api/device/view', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ visible: name === 'device' }) }).catch(() => {});
  if (name === 'booth') { state.booth.view.resize(); state.booth.lens.resize(); }
  if (name === 'device') state.device.render();
  if (name !== 'booth' && state.booth) state.booth.pause();
  navChips();
}

async function replayKey(k) {
  const e = state.library.find(x => x.key === k);
  if (!e) { toast(t('replay.none'), true); return; }
  await replayQuery(`key=${k}`);
}

async function replayQuery(q) {
  show('booth');
  try {
    await state.booth.load(q);
    state.booth.play();
  } catch (e) { toast(t('replay.missing', { file: q }), true, 6000); }
}

async function showSummary(p) {
  show('summary');
  await state.summary.render(p);
}

function relabel() {
  $('#seg-device').textContent = t('seg.device');
  $('#seg-replay').textContent = t('seg.replay');
  $('#nav-title').textContent = state.screen === 'start' ? '' : t('app.title');
  if (state.start) state.start.render();
  if (state.summary && state.screen === 'summary' && state.summary.p) state.summary.render(state.summary.p);
  if (state.devpanel && state.dev) state.devpanel.update(state.dev);
  navChips();
}

function navChips() {
  const d = state.dev;
  const conn = d && d.conn && d.conn.state;
  const chips = [];
  if (conn === 'connected') chips.push(`<span class="chip"><i class="dot"></i>${esc(t('dev.connected'))}</span>`);
  else if (conn === 'connecting' || conn === 'checking') chips.push(`<span class="chip"><i class="dot grey"></i>${esc(t('dev.connecting'))}</span>`);
  else if (conn === 'lost') chips.push(`<span class="chip"><i class="dot red"></i>${esc(t('dev.disconnected'))}</span>`);
  else chips.push(`<span class="chip"><i class="dot grey"></i>${esc(t('dev.not_connected'))}</span>`);
  if (state.screen === 'booth') chips.push(`<span class="chip">×${state.speed}</span>`);
  chips.push(`<button class="chip btn-chip" id="langchip">${esc(t('lang.chip'))}</button>`);
  $('#navchips').innerHTML = chips.join('');
  $('#langchip').addEventListener('click', toggleLang);
}

// ------------------------------------------------------------------ help (H)
function toggleHelp() {
  if (state.help) { state.help.remove(); state.help = null; return; }
  const rows = [['Space', 'help.space'], ['R', 'help.r'], ['← →', 'help.arrows'], ['+ −', 'help.speed'], ['1-9', 'help.num'], ['D', 'help.d'],
    ['Enter ↑↓', 'help.enter'], ['T', 'help.t'], ['I', 'help.i'], ['P', 'help.p'], ['L', 'help.l'], ['X', 'help.x'], ['E', 'help.e'], ['F', 'help.f'],
    ['H', 'help.h'], ['Esc', 'help.esc']];
  const back = document.createElement('div');
  back.className = 'sheet-back';
  back.innerHTML = `<div class="sheet help"><h2>${esc(t('help.title'))}</h2><div class="helpgrid">${rows.map(([k, key]) => `<span class="kc">${esc(k)}</span><span>${esc(t(key))}</span>`).join('')}</div>
    <div class="acts"><span class="sub">${esc(t('help.close'))}</span></div></div>`;
  back.addEventListener('click', toggleHelp);
  document.body.appendChild(back);
  state.help = back;
}

// ------------------------------------------------------------------ keys (spec section 8)
function onKey(e) {
  if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) return;
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  const k = e.key;
  const dev = state.device;
  if (k === 'h' || k === 'H') { e.preventDefault(); toggleHelp(); return; }
  if (state.help) { if (k === 'Escape') { e.preventDefault(); toggleHelp(); } return; }
  if (k === 'Escape') {
    e.preventDefault();
    if (dev.closeSheet()) return;
    show('start');
    return;
  }
  if (k === 'l' || k === 'L') { e.preventDefault(); toggleLang(); return; }
  if (dev.sheet) {
    if (k === 'ArrowUp') { e.preventDefault(); dev.move(-1); }
    else if (k === 'ArrowDown') { e.preventDefault(); dev.move(1); }
    else if (k === 'Enter') { e.preventDefault(); dev.enter(e.shiftKey); }
    return;
  }
  if (k === 'd' || k === 'D') { e.preventDefault(); show('device'); return; }
  if (/^[1-9]$/.test(k)) { e.preventDefault(); replayKey(+k); return; }
  if (k === 'p' || k === 'P') { e.preventDefault(); dev.openPull(e.shiftKey); return; }
  if (state.screen === 'start') {
    if (k === 'Enter') { e.preventDefault(); show('device'); }
    return;
  }
  if (state.screen === 'summary') {
    if (k === 'r' || k === 'R') { e.preventDefault(); show('booth'); state.booth.restart(true); }
    else if (k === 'e' || k === 'E') { e.preventDefault(); state.booth.exportSummary(); }
    return;
  }
  if (state.screen === 'booth') {
    const b = state.booth;
    if (k === ' ') { e.preventDefault(); b.toggle(); }
    else if (k === 'r' || k === 'R') { e.preventDefault(); b.restart(true); }
    else if (k === 'ArrowLeft') { e.preventDefault(); b.seek(-10); }
    else if (k === 'ArrowRight') { e.preventDefault(); b.seek(10); }
    else if (k === '+' || k === '=') { e.preventDefault(); b.faster(); }
    else if (k === '-' || k === '_') { e.preventDefault(); b.slower(); }
    else if (k === 'x' || k === 'X') { e.preventDefault(); b.toggleHex(); }
    else if (k === 'e' || k === 'E') { e.preventDefault(); b.exportSummary(); }
    else if (k === 'f' || k === 'F') { e.preventDefault(); b.toggleFollow(); }
    return;
  }
  if (state.screen === 'device') {
    if (k === 'ArrowUp') { e.preventDefault(); dev.move(-1); }
    else if (k === 'ArrowDown') { e.preventDefault(); dev.move(1); }
    else if (k === 'Enter') { e.preventDefault(); dev.enter(e.shiftKey); }
    else if (k === 't' || k === 'T') { e.preventDefault(); dev.testStart(); }
    else if (k === 'x' || k === 'X') { e.preventDefault(); dev.toggleRaw(); }
    else if (k === 'i' || k === 'I') { e.preventDefault(); dev.toggleOverlay(); }
    else if ((k === 'f' || k === 'F') && dev.liveMapShown()) { e.preventDefault(); state.live.toggleFollow(); }
    else if ((k === 'r' || k === 'R') && dev.liveMapShown()) { e.preventDefault(); state.live.resetCamera(); }
  }
}

// ------------------------------------------------------------------ export mode (headless Chromium, key E)
async function exportMode() {
  document.body.classList.remove('dark');
  document.body.classList.add('light', 'export');
  $('#nav').classList.add('hidden');
  const scr = $('#scr-summary');
  scr.classList.add('on');
  const q = params.get('key') ? `key=${encodeURIComponent(params.get('key'))}` : `file=${encodeURIComponent(params.get('file') || '')}`;
  const p = await get(`/api/session?${q}`);
  const s = new Summary(scr, { exportMode: true });
  await s.render(p);
  if (document.fonts && document.fonts.ready) await document.fonts.ready;
  await new Promise(r => setTimeout(r, 250));
  window.__exportReady = true;
}

export { keyFooter, getLang };
if (params.has('test')) window.__app = state;
main();
