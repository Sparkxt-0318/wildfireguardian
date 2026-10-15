// Device segment (spec section 3C): the connect card, the device page (header, four tiles, the test recording, the
// checks and the results), the P menu, the connection check, the Wi-Fi pull and the battery calibration form. The
// page only shows what the backend reports; it never completes a test step on its own.
import { esc, comma, fixed, mmss, localClock, bus, toast } from './util.js';
import { t, getLang, modeName } from './i18n.js';
import { get, post } from './api.js';
import { DeviceStream } from './devstream.js';
import { keyFooter } from './replay.js';
import { watermarkHTML } from './trackview.js';

const USB_ICON = '<svg width="20" height="12" viewBox="0 0 20 12"><rect x="1" y="1" width="18" height="10" rx="5" fill="none" stroke-width="1.6"/><rect class="f" x="5.5" y="4.6" width="9" height="2.8" rx="1.4"/></svg>';
const RESERVE = 32768;
const START_MIN_FREE = RESERVE + 8192;
const MARK = { ok: '<i class="m ok">✓</i>', info: '<i class="m info"><b></b></i>', wait: '<i class="m wait"></i>', bad: '<i class="m bad">✕</i>', run: '<i class="m run"></i>' };

function hoursLeft(free) { return Math.max(0, (free - RESERVE) / 48 / 3600); }
function sess(name) { return String(name || '').replace(/\.wfg$/, ''); }

// The short codes of the backend (app/main.py _call, the manager) as sentences; null for anything else.
export function errText(m) {
  m = m || '';
  if (m === 'pull.recording') return t('pull.recording');
  if (m.startsWith('busy')) return t('err.busy');
  if (m === 'not connected') return t('err.not_connected');
  if (m === 'fs.error') return t('fs.error');
  if (m === 'format.error') return t('connect.format');
  if (m === 'cal.bad_input') return t('cal.bad_input');
  if (m.startsWith('timeout:')) {
    const cmd = /no reply to (\S+)/.exec(m);
    return cmd ? t('err.timeout', { cmd: cmd[1] }) : t('err.timeout_any');
  }
  if (m.startsWith('lost:')) return t('err.lost');
  if (m.startsWith('port:')) return t('err.port', { err: m.slice(5).trim() });
  return null;
}

export class DeviceScreen {
  constructor(root, actions) {
    this.root = root;
    this.actions = actions;
    this.snap = null;
    this.sel = 0;
    this.sheet = null;
    this.noPortSince = performance.now();
    this.liveOverlay = false;
    root.innerHTML = `
      <div class="dleft"><div class="dl-body"></div><div class="wm hidden"></div></div>
      <section class="con">
        <div class="conh"><div><b class="ct"></b><span class="sub"></span></div><div class="chips"></div></div>
        <div class="prog"><div></div></div>
        <div class="lines top"></div>
        <div class="keys"></div>
        <div class="wm hidden"></div>
      </section>`;
    this.$ = { body: root.querySelector('.dl-body'), ct: root.querySelector('.ct'), sub: root.querySelector('.conh .sub'),
      chips: root.querySelector('.conh .chips'), lines: root.querySelector('.lines'), keys: root.querySelector('.keys'),
      wmL: root.querySelector('.dleft .wm'), wmR: root.querySelector('.con .wm') };
    this.stream = new DeviceStream(this.$.lines);
    this.timer = setInterval(() => this._tick(), 500);
    bus.on('lang', () => { this.stream.rebuild(); this.render(); });
  }

  // ------------------------------------------------------------------ data from the backend
  setSnapshot(snap, full = false) {
    const prev = this.snap;
    this.snap = snap;
    this.snapAt = performance.now();
    if (full && snap.stream) this.stream.load(snap.stream);
    if (snap.timing) this.stream.pollS = snap.timing.status_fast;
    const likely = (snap.ports || []).filter(p => p.likely);
    if (likely.length) this.noPortSince = null; else if (this.noPortSince === null) this.noPortSince = performance.now();
    if (prev && prev.result !== snap.result && snap.result && this.visible) bus.emit('device-result', snap.result);
    this.render();
    if (this.sheet && this.sheet.kind === 'cc') this._renderCC();
  }

  addLine(ev) { this.stream.add(ev); }

  remask(lines) { this.stream.remask(lines); }

  get connected() { return this.snap && this.snap.conn && this.snap.conn.state === 'connected'; }

  // ------------------------------------------------------------------ rendering
  render() {
    const s = this.snap;
    if (!s) return;
    this.$.ct.textContent = t('stream.title');
    const c = s.conn;
    this.$.sub.textContent = c.state === 'connected' || c.state === 'connecting' || c.state === 'checking'
      ? t('chip.port', { port: c.port }) : t('dev.not_connected');
    const chips = [];
    if (this.connected) {
      chips.push(s.mode === 'live' ? t('chip.live') : t('chip.basic'));
      if (!s.fs_error) chips.push(t('chip.poll', { s: s.view_visible ? s.timing.status_fast : s.timing.status_slow }));
    }
    if (this.stream.raw) chips.push(t('chip.raw'));
    this.$.chips.innerHTML = chips.map(x => `<span class="chip sm">${esc(x)}</span>`).join('');
    const sim = !!s.double && c.simulated;
    for (const w of [this.$.wmL, this.$.wmR]) { w.classList.toggle('hidden', !sim); if (sim) w.innerHTML = watermarkHTML(t('double.label')); }
    let keys;
    if (!this.connected) { this._connectCard(); keys = t('keys.connect'); }
    else if (s.mode === 'live' && !this.liveOverlay && !s.fs_error) { this._live(); keys = t('keys.device'); }
    else { this._page(); keys = s.result && !this._testRunning() ? t('keys.result') : t('keys.device'); }
    this.$.keys.innerHTML = keyFooter(keys);
  }

  _testRunning() { const tst = this.snap.test; return tst && (tst.phase === 'running' || tst.phase === 'pulling'); }

  _ports() {
    const ps = this.snap.ports || [];
    return ps.filter(p => p.likely).concat(ps.filter(p => !p.likely));
  }

  _connectCard() {
    const s = this.snap, c = s.conn;
    const ports = this._ports();
    if (this.sel >= ports.length) this.sel = Math.max(0, ports.length - 1);
    const likely = ports.filter(p => p.likely), other = ports.filter(p => !p.likely);
    const row = (p, i) => {
      const desc = p.simulated ? t('connect.simulated') : (p.usb ? [p.chip ? `WCH ${p.chip}` : (p.description || ''), p.vidpid ? `USB ${p.vidpid}` : ''].filter(Boolean).join(' · ') : t('connect.notusb'));
      return `<div class="prow${i === this.sel ? ' sel' : ''}${p.likely ? '' : ' dim'}" data-i="${i}"><span class="pico${p.likely ? '' : ' off'}">${p.likely ? USB_ICON : ''}</span>`
        + `<div><div class="pname">${esc(p.device)}</div><div class="pdesc">${esc(desc)}</div></div>${p.likely ? `<span class="ptag">${esc(t('connect.likely'))}</span>` : ''}</div>`;
    };
    let list = likely.map((p, i) => row(p, i)).join('');
    if (other.length) list += `<div class="plabel">${esc(t('connect.other'))}</div>` + other.map((p, j) => row(p, likely.length + j)).join('');
    const noport = !likely.length && this.noPortSince !== null && performance.now() - this.noPortSince > 10000;
    if (!ports.length || noport) list += `<div class="noport">${esc(noport ? t('connect.noport') : t('start.none'))}</div>`;
    let note = '', cls = '';
    const prof = this._profileForSel(ports[this.sel]);
    if (c.state === 'connecting') note = t('connect.connecting');
    else if (c.error === 'noreply') { note = t('connect.noreply'); cls = 'err'; }
    else if (c.error === 'open_failed') { note = t('connect.open_failed', { err: c.detail || '' }); cls = 'err'; }
    else if (c.error === 'format') { note = t('connect.format'); cls = 'err'; }
    else if (c.error === 'download') { note = t('connect.download'); cls = 'err'; }
    else if (c.state === 'lost') { note = prof && prof.reconnect_ok ? t('connect.lost_auto') : t('connect.lost'); cls = 'strong'; }
    else if (prof && prof.conncheck) note = prof.rule_connect_first ? t('connect.measured_rule') : t('connect.measured_safe', { method: t(`cc.method.${prof.open_method || 'default'}`), date: (prof.conncheck.date || '').slice(0, 10) });
    else note = t('connect.caution');
    const btn = c.state === 'lost' ? t('connect.reconnect') : t('connect.button');
    const html = `<div class="cwrap">
      <img src="img/device.png" class="cimg" alt="">
      <h2 class="ctitle">${esc(t('connect.title'))}</h2>
      <p class="csub">${esc(t('connect.sub'))}</p>
      <div class="ports"><div class="ph"><b>${esc(t('connect.ports'))}</b><span>${esc(t('connect.ports_note'))}</span></div>${list}</div>
      <div class="cbtns"><button class="btn fill b-conn"${!ports.length || c.state === 'connecting' ? ' disabled' : ''}>${esc(btn)}<span class="kc inv">Enter</span></button>
        <span class="clink b-wifi">${esc(t('connect.wifi'))} ›</span></div>
      <p class="cnote ${cls}">${esc(note)}</p></div>`;
    // unchanged: leave the DOM alone (no flicker of the image, hover and focus stay)
    if (html === this._lastConnect && this.$.body.querySelector(':scope > .cwrap')) return;
    this._lastConnect = html;
    this._parts = null;
    this.$.body.innerHTML = html;
    for (const r of this.$.body.querySelectorAll('.prow')) {
      r.addEventListener('click', () => { this.sel = +r.dataset.i; this.render(); });
      r.addEventListener('dblclick', () => { this.sel = +r.dataset.i; this.connect(); });
    }
    this.$.body.querySelector('.b-conn').addEventListener('click', () => this.connect());
    this.$.body.querySelector('.b-wifi').addEventListener('click', () => this.openWifi());
  }

  _profileForSel(p) {
    const prof = this.snap.profile;
    if (prof && p && (prof.last_port === p.device)) return prof;
    return null;
  }

  // ------------------------------------------------------------------ the device page
  _header() {
    const s = this.snap, h = s.hello || {};
    const st = (s.status && s.status.state) || (h.state) || 'IDLE';
    const rec = st === 'RECORDING';
    const pill = rec ? `<span class="spill"><i class="dot live"></i>${esc(t('rec.recording_s', { session: sess(s.status && s.status.session) }))}</span>`
      : `<span class="spill"><i class="dot ${st === 'IDLE' ? 'grey' : 'red'}"></i>${esc(t(`rec.${st}`))}</span>`;
    const name = h.device ? `WFG-${h.device}` : '-';
    return `<div class="dhead"><img src="img/device.png" class="dthumb" alt="">
      <div><div class="dname">${esc(name)}</div><div class="dboard">${esc(h.board || '')}</div>
      <div class="dfw">${esc(t('dev.fw', { fw: h.fw || '-', fmt: h.fmt || '-', port: s.conn.port }))}</div></div>
      <div class="dright">${pill}<button class="btn quiet b-disc">${esc(t('dev.disconnect'))}</button></div></div>`;
  }

  _tiles() {
    const s = this.snap;
    const vb = s.vbat;
    const valid = vb && vb.valid;
    const cal = vb && vb.cal;
    const bcap = valid ? [t('tile.usb'), cal === '1.000' || !cal ? t('tile.uncal') : t('tile.cal', { cal })].join(' · ') : '';
    const batt = valid ? `<div class="v">${esc(fixed(vb.vbat_mv / 1000, 2))}<small>V</small></div><div class="c">${esc(bcap)}</div>`
      : `<div class="v na">${esc(t('tile.no_value'))}</div><div class="c">${esc(s.vbat_unknown ? t('note.vbat_unknown') : '')}</div>`;
    const st = s.status || {};
    const free = st.free, total = st.total;
    const used = free !== undefined && total ? (total - free) / total * 100 : 0;
    const stor = free !== undefined && free !== null
      ? `<div class="v">${esc(fixed(free / 1e6, 2))}<small>MB / ${esc(fixed(total / 1e6, 2))}</small></div><div class="bar"><i style="width:${Math.max(used, 1.2).toFixed(1)}%"></i></div><div class="c">${esc(t('tile.hours', { h: fixed(hoursLeft(free), 1) }))}</div>`
      : `<div class="v na">${esc(t('tile.no_value'))}</div>`;
    let ses;
    if (st.state === 'RECORDING') {
      const d = s.rec_started_ms ? mmss((Date.now() - s.rec_started_ms) / 1000) : null;
      const cap = s.rec_before_connect || !d ? t('tile.since_before', { session: sess(st.session) }) : t('tile.since', { session: sess(st.session), d });
      ses = `<div class="v">${esc(comma(st.seq))}<small>${esc(t('tile.records_unit'))}</small></div><div class="c">${esc(cap)}</div>`;
    } else if (s.result && s.result.session) {
      ses = `<div class="v">${esc(comma(s.result.records))}<small>${esc(t('tile.records_unit'))}</small></div><div class="c">${esc(`${sess(s.result.session)} · ${mmss(s.result.duration_s)}`)}</div>`;
    } else {
      ses = `<div class="v na">${esc(s.last_session ? sess(s.last_session) : t('tile.none'))}</div><div class="c">${esc(s.last_session ? t('tile.last', { session: sess(s.last_session) }) : '')}</div>`;
    }
    const mode = st.mode ? `<div class="v">${esc(modeName(st.mode))}</div>` : `<div class="v na">-</div>`;
    return `<div class="tiles4">
      <div class="t4"><div class="l">${esc(t('tile.battery'))}</div>${batt}${this.connected && !s.fs_error ? `<button class="tb b-cal">${esc(t('tile.cal_button'))}</button>` : ''}</div>
      <div class="t4"><div class="l">${esc(t('tile.storage'))}</div>${stor}</div>
      <div class="t4"><div class="l">${esc(t('tile.session'))}</div>${ses}</div>
      <div class="t4"><div class="l">${esc(t('tile.mode'))}</div>${mode}<div class="c">${esc(t('tile.mode_hint'))}</div></div></div>`;
  }

  _page() {
    const s = this.snap;
    let main;
    const showResult = !s.fs_error && s.result && !this._testRunning();
    if (s.fs_error) {
      main = `<div class="fsbox"><h3>${esc(t('fs.error'))}</h3><p>${esc(t('stream.fs'))}</p></div>`;
    } else if (showResult) {
      main = this._resultCard();
    } else {
      main = `<div class="cards2"><div class="dcard tcard">${this._testCard()}</div><div class="dcard ccard">${this._checksCard()}</div></div>`;
    }
    const prof = s.profile || {};
    const ccSub = prof.rule_connect_first ? `<span class="rule">${esc(t('conn.rule'))}</span>` : esc(t('tools.conn_sub'));
    // the three quiet buttons sit under the cards (under the results only when the window has room: app.css, .rcard)
    const tools = s.fs_error ? '' : `<div class="tools3">
      <button class="tl3 b-cc"><b>${esc(t('tools.conn'))}<i>›</i></b><span>${ccSub}</span></button>
      <button class="tl3 b-cal2"><b>${esc(t('tools.cal'))}<i>›</i></b><span>${esc(t('tools.cal_sub'))}</span></button>
      <button class="tl3 b-wifi2"><b>${esc(t('tools.wifi'))}<i>›</i></b><span>${esc(t('tools.wifi_sub'))}</span></button></div>`;
    let bnote = `<div class="bnote"><i class="info-i">i</i>${esc(s.mode === 'live' ? t('dev.live_note') : t('dev.basic'))}</div>`;
    if (s.export_mode) bnote = `<div class="bnote"><i class="info-i">i</i>${esc(t('dev.export_mode'))}</div>`;
    this._renderParts({ head: this._header(), tiles: this._tiles(), main, tools, note: bnote });
  }

  // The page is five parts; a part's DOM is replaced only when its HTML changed, so the page does not flicker when
  // the backend reports every second (the image, the buttons' hover and the keyboard focus stay as they are).
  _renderParts(parts) {
    let page = this.$.body.querySelector(':scope > .dpage');
    if (!page || !this._parts) {
      this.$.body.innerHTML = `<div class="dpage">${Object.keys(parts).map(k => `<div class="dpart" data-part="${k}"></div>`).join('')}</div>`;
      page = this.$.body.firstElementChild;
      this._parts = {};
      this._lastConnect = null;
    }
    for (const [k, html] of Object.entries(parts)) {
      if (this._parts[k] === html) continue;
      const box = page.querySelector(`:scope > [data-part="${k}"]`);
      box.innerHTML = html;
      this._parts[k] = html;
      this._bind(box);
    }
  }

  _bind(root) {
    const on = (sel, fn) => { for (const e of root.querySelectorAll(sel)) e.addEventListener('click', fn); };
    on('.b-disc', () => this.disconnect());
    on('.b-cal', () => this.openCal());
    on('.b-cal2', () => this.openCal());
    on('.b-cc', () => this.openCC());
    on('.b-wifi2', () => this.openWifi());
    on('.b-test', () => this.testStart());
    on('.b-tcancel', () => this.testCancel());
    on('.b-replay', () => this.replayResult());
    on('.b-again', () => this.testStart());
    on('.b-rcc', () => this.openCC());
    for (const x of root.querySelectorAll('.b-scr')) x.addEventListener('click', () => this.screen(x.dataset.v === '1'));
  }

  _testCard() {
    const s = this.snap, tst = s.test;
    const head = `<div class="dch"><b>${esc(t('test.title'))}</b><span><span class="kc">T</span> ${esc(t('test.meta'))}</span></div>`;
    if (!tst || tst.phase === 'cancelled' || (tst.phase === 'done' && !s.result)) {
      let msg = '';
      if (tst && tst.phase === 'cancelled') msg = `<p class="intro">${esc(t('test.cancelled'))}</p>`;
      return `${head}<div class="steps"><p class="intro">${esc(t('test.intro'))}</p>${msg}
        <p class="intro"><button class="btn fill small b-test">${esc(t('test.start'))}<span class="kc inv">T</span></button></p></div>
        <div class="hint">${esc(t('test.hint'))}</div>`;
    }
    const st = tst.steps;
    const el = tst.elapsed !== null && tst.elapsed !== undefined ? tst.elapsed + (tst.phase === 'running' ? (performance.now() - this.snapAt) / 1000 : 0) : null;
    const titles = ['test.s1', 'test.s2', 'test.s3', 'test.s4', 'test.s5'];
    const html = st.map((x, i) => {
      const cls = x.st === 'running' ? 'now' : x.st;
      const circ = x.st === 'done' ? '✓' : (x.st === 'failed' ? '✕' : (x.st === 'skipped' ? '-' : String(i + 1)));
      let d = '', extra = '';
      const at = x.at ? localClock(x.at) : '';
      if (i === 0) {
        if (x.st === 'done') d = x.variant === 'already' ? t('test.already', { session: sess(x.session) }) : t('test.s1_done', { t: at, session: sess(x.session) });
        else d = t('test.s1_hint');
        if (tst.note === 'full' && x.st !== 'done') extra = `<div class="note">${esc(t('test.full'))}</div>`;
      } else if (i === 1) {
        if (x.st === 'done') d = t('test.s2_done', { t: at, n: x.n, loc: x.located ? t('test.loc_yes') : t('test.loc_no') });
        else if (x.st === 'skipped') d = t('test.skipped');
      } else if (i === 2) {
        if (x.st === 'done') d = t('test.s3_detail', { el: '0:30', n: comma(x.n) });
        else if (x.st === 'skipped') d = t('test.skipped');
        else if (el !== null) {
          extra = `<div class="pbar"><i style="width:${Math.min(100, el / (tst.wait_s || 30) * 100).toFixed(0)}%"></i></div>`;
          d = t('test.s3_detail', { el: mmss(Math.min(el, tst.wait_s || 30)), n: comma(tst.records) });
        }
      } else if (i === 3) {
        if (x.st === 'done') d = x.reason === 'idle' ? t('test.s4_idle', { t: at }) : t('test.s4_done', { t: at });
        else d = t('test.s4_hint');
      } else if (i === 4) {
        if (x.st === 'running' || (x.st === 'now' && tst.phase === 'pulling')) d = t('test.s5_running');
        else if (x.st === 'done') d = t('test.s5_done', { t: at });
        else if (x.st === 'failed') d = t('test.s5_failed', { err: x.error || tst.error || '' });
        else d = t('test.s5_hint');
      }
      return `<div class="step ${cls}${i === 4 ? ' last' : ''}"><span class="c">${circ}</span><div><div class="tt">${esc(t(titles[i]))}</div>${extra}<div class="d${x.st === 'failed' ? ' err' : ''}">${esc(d)}</div></div></div>`;
    }).join('');
    let foot = esc(t('test.hint'));
    if (tst.note === 'export_on') foot = `<b>${esc(t('test.export_on'))}</b>`;
    else if (tst.phase === 'interrupted') foot = `<b>${esc(t('test.interrupted'))}</b>`;
    else if (tst.restarted) foot = `<b>${esc(t('test.restarted'))}</b>`;
    const cancel = tst.phase === 'running' ? `<button class="btn quiet b-tcancel">${esc(t('test.cancel'))}</button>` : '';
    return `${head}<div class="steps">${html}</div><div class="hint" style="display:flex;justify-content:space-between;align-items:center;gap:10px"><span>${foot}</span>${cancel}</div>`;
  }

  _checksCard() {
    const s = this.snap, h = s.hello || {}, st = s.status || {};
    const rows = [];
    rows.push(['ok', t('check.usb'), t('check.usb_v', { ms: h.ms ?? '-' })]);
    rows.push([s.format_error ? 'bad' : 'ok', t('check.format'), t('check.format_v', { fmt: h.fmt || '-', size: h.recsize || '-' })]);
    rows.push(['info', t('check.restart'), s.restart_on_open === null || s.restart_on_open === undefined ? t('check.restart_unknown') : (s.restart_on_open ? t('check.restart_yes') : t('check.restart_no'))]);
    if (st.free !== undefined && st.free !== null) rows.push([st.free >= START_MIN_FREE ? 'ok' : 'bad', t('check.storage'), t('check.storage_v', { mb: fixed(st.free / 1e6, 2) })]);
    const vb = s.vbat;
    rows.push([vb && vb.valid ? 'ok' : 'bad', t('check.battery'), vb && vb.valid ? `${t('check.battery_v', { v: fixed(vb.vbat_mv / 1000, 2) })}${vb.cal === '1.000' ? ` · ${t('tile.uncal')}` : ''}` : t('tile.no_value')]);
    if (s.events_seen > 0) rows.push(['ok', t('check.button'), t('check.button_v', { n: s.events_seen })]);
    const html = rows.map(([m, n, v]) => `<div class="ck">${MARK[m]}<span class="n">${esc(n)}</span><span class="v">${esc(v)}</span></div>`).join('');
    return `<div class="dch"><b>${esc(t('check.title'))}</b><span>${esc(t('check.meta', { n: rows.length }))}</span></div>${html}
      <div class="ck later">${MARK.wait}<span class="n">${esc(t('check.later', { list: t('check.later_list') }))}</span></div>`;
  }

  _rowText(r, res) {
    const p = r.p || {};
    switch (r.id) {
      case 'file': return r.variant === 'ok' ? t('res.file.ok', { sha: p.sha, ok: p.ok, total: p.total }) : t('res.file.bad', { ok: p.ok, total: p.total, bad: res.bad || '-' });
      case 'ended': return r.variant === 'other' ? t('res.ended.other', { reason: p.reason, words: t(`end.${p.reason}`) }) : t(`res.ended.${r.variant}`);
      case 'spacing': return t(`res.spacing.${r.variant}`, { n: comma(p.n), max: p.max, at: p.at });
      case 'gnss': return t(`res.gnss.${r.variant}`, { nmea: comma(p.nmea), bad: comma(p.bad) });
      case 'position': return t(`res.position.${r.variant}`, { n: comma(p.n), sats: p.sats, hdop: p.hdop === null || p.hdop === undefined ? '-' : fixed(p.hdop, 1) });
      case 'button': return t(`res.button.${r.variant}`, { n: p.n });
      case 'battery': {
        if (r.variant !== 'ok') return t('res.battery.none');
        const parts = [t('res.battery.ok', { v: fixed(p.v, 2) })];
        if (p.usb) parts.push(t('tile.usb'));
        if (p.uncal) parts.push(t('tile.uncal'));
        return parts.join(' · ');
      }
      case 'storage': return t(`res.storage.${r.variant}`, { mb: p.mb, h: p.h });
      default: return t(`res.${r.id}.${r.variant}`);
    }
  }

  _resultCard() {
    const res = this.snap.result;
    const c = res.counts;
    const okAll = c.bad === 0;
    const title = okAll && !c.wait ? t('result.ok') : t('result.attention', { n: c.bad + c.wait });
    const pulled = res.pulled ? localClock(res.pulled) : '';
    const sub = res.saved_status === 'same' ? t('result.same') : t('result.sub', { session: sess(res.session), n: comma(res.records), dur: mmss(res.duration_s), time: pulled });
    const rows = res.rows.map(r => {
      const ask = r.id === 'screen' && r.variant === 'ask'
        ? `<div class="ask"><button class="btn quiet b-scr" data-v="1">${esc(t('screen.yes'))}</button><button class="btn quiet b-scr" data-v="0">${esc(t('screen.no'))}</button></div>` : '';
      return `<div class="rr">${MARK[r.mark] || MARK.info}<div><div class="n">${esc(t(`res.${r.id}.title`))}</div><div class="v${r.mark === 'bad' ? ' err' : ''}">${esc(this._rowText(r, res))}</div>${ask}</div></div>`;
    });
    const half = Math.ceil(rows.length / 2);
    const count = c.wait ? t('result.count_wait', { n: res.total, p: c.ok, i: c.info, f: c.bad, w: c.wait }) : t('result.count', { n: res.total, p: c.ok, i: c.info, f: c.bad });
    const path = res.file ? res.file.replace(/^real\//, '').replace(/^sim\//, '') : (res.bad || '');
    const before = res.started_before ? `<p class="before">${esc(t('test.before_note'))}</p>` : '';
    // green only when every check passed; a question still open (the screen) is neither green nor red
    const mark = !okAll ? '<i class="big bad">!</i>' : c.wait ? '<i class="big wait">?</i>' : '<i class="big">✓</i>';
    return `<div class="rcard"><div class="rhero">${mark}<div><h3>${esc(title)}</h3><p>${esc(sub)}</p>${before}</div><span class="rcount">${esc(count)}</span></div>
      <div class="rgrid"><div>${rows.slice(0, half).join('')}</div><div>${rows.slice(half).join('')}</div></div>
      <div class="ract">${res.file ? `<button class="btn fill b-replay">${esc(t('result.replay'))}<span class="kc inv">Enter</span></button>` : ''}
        <button class="btn line b-again">${esc(t('result.again'))}<span class="kc">T</span></button><span class="clink b-rcc">${esc(t('result.conn'))} ›</span>
        <span class="saved">${esc(t('result.saved', { path }))}</span></div></div>`;
  }

  _live() {
    if (this.actions.renderLive) this.actions.renderLive(this.$.body, this.snap);
  }

  _tick() {
    if (!this.snap || !this.visible) return;
    // the clocks between the backend's reports: the 30 s bar of the test and the recording time on the tile
    const tst = this.snap.test;
    const live = this.connected && (tst && tst.phase === 'running' || this.snap.status && this.snap.status.state === 'RECORDING');
    if (live && !this.liveMapShown() && this.$.body.querySelector(':scope > .dpage')) this._page();
    if (!this.connected && this.noPortSince !== null) this.render();
  }

  liveMapShown() { return this.snap && this.snap.mode === 'live' && !this.liveOverlay && this.connected; }

  // ------------------------------------------------------------------ actions
  async _do(fn) {
    try { return await fn(); }
    catch (e) {
      const m = e.message || '';
      toast(errText(m) || t('err.generic', { err: m }), true, 6000);
      return null;
    }
  }

  async connect() {
    const ports = this._ports();
    const p = ports[this.sel];
    if (!p) return;
    await this._do(() => post('/api/device/connect', { port: p.device }));
  }

  async disconnect() {
    const s = this.snap;
    const recording = s.status && s.status.state === 'RECORDING';
    const prof = s.profile || {};
    if (recording && prof.conncheck && prof.conncheck.close) {
      // this board restarts when the port closes: ask first, in the page (Enter disconnects, Esc keeps the connection)
      const sh = this._openSheet('confirm', `<h2>${esc(t('dev.disconnect'))}</h2><p class="sub">${esc(t('dev.disconnect_ask'))}</p>
        <div class="acts"><button class="btn quiet b-keep">${esc(t('test.cancel'))}<span class="kc">Esc</span></button>
        <button class="btn fill small b-yes">${esc(t('dev.disconnect'))}<span class="kc inv">Enter</span></button></div>`);
      sh.yes = async () => { this.closeSheet(); await this._do(() => post('/api/device/disconnect')); };
      sh.box.querySelector('.b-keep').addEventListener('click', () => this.closeSheet());
      sh.box.querySelector('.b-yes').addEventListener('click', () => sh.yes());
      return;
    }
    await this._do(() => post('/api/device/disconnect'));
  }

  async testStart() { if (this.connected) await this._do(() => post('/api/device/test/start')); }
  async testCancel() { await this._do(() => post('/api/device/test/cancel')); }
  async screen(seen) { await this._do(() => post('/api/device/test/screen', { seen })); }

  replayResult() {
    const r = this.snap && this.snap.result;
    if (r && r.file) this.actions.replayFile(r.file);
  }

  move(d) {
    if (this.sheet && this.sheet.kind === 'pull') { this._pullMove(d); return; }
    if (this.connected) return;
    const n = this._ports().length;
    if (!n) return;
    this.sel = (this.sel + d + n) % n;
    this.render();
  }

  enter(shift = false) {
    if (this.sheet && this.sheet.kind === 'confirm') { this.sheet.yes(); return; }
    if (this.sheet && this.sheet.kind === 'pull') { this._pullChoose(shift); return; }
    if (!this.connected) { this.connect(); return; }
    if (this.snap.result && !this._testRunning()) this.replayResult();
  }

  toggleRaw() { this.stream.setRaw(!this.stream.raw); toast(this.stream.raw ? t('x.raw_masked') : t('x.raw_off'), false, 2500); this.render(); }

  toggleOverlay() {
    if (!(this.snap && this.snap.mode === 'live')) return;
    this.liveOverlay = !this.liveOverlay;
    this.render();
  }

  // ------------------------------------------------------------------ sheets
  closeSheet() {
    if (!this.sheet) return false;
    if (this.sheet.kind === 'wifi') clearInterval(this.sheet.timer);
    this.sheet.el.remove();
    this.sheet = null;
    return true;
  }

  _openSheet(kind, html, cls = '') {
    this.closeSheet();
    const back = document.createElement('div');
    back.className = 'sheet-back';
    back.innerHTML = `<div class="sheet ${cls}">${html}</div>`;
    back.addEventListener('click', (e) => { if (e.target === back && kind !== 'cc') this.closeSheet(); });
    document.body.appendChild(back);
    this.sheet = { kind, el: back, box: back.querySelector('.sheet') };
    return this.sheet;
  }

  // P: the device's sessions. Shift+P (force) downloads again even when the library has the same SHA-256.
  async openPull(force = false) {
    if (!this.connected) { toast(t('pull.not_connected'), true); return; }
    const sub = force ? t('pull.sub_force') : t('pull.sub');
    const sh = this._openSheet('pull', `<h2>${esc(t('pull.title'))}</h2><p class="sub">${esc(sub)}</p><div class="pbody"><p class="msg">${esc(t('pull.loading'))}</p></div>`);
    sh.force = !!force;
    const r = await this._do(() => get('/api/device/sessions'));
    if (!r || this.sheet !== sh) { if (this.sheet === sh) this.closeSheet(); return; }
    sh.items = r.sessions;
    sh.sel = Math.max(0, r.sessions.length - 1);
    this._renderPull();
  }

  _renderPull() {
    const sh = this.sheet;
    const body = sh.box.querySelector('.pbody');
    if (!sh.items.length) { body.innerHTML = `<p class="msg">${esc(t('pull.none'))}</p>`; return; }
    const rows = sh.items.map((x, i) => `<tr class="${i === sh.sel ? 'sel' : ''}" data-i="${i}"><td class="mono">${esc(sess(x.name))}</td><td>${esc(modeName(x.mode))}</td>`
      + `<td>${esc(comma(x.records))}</td><td>${esc(comma(x.size))} B</td><td>${esc(x.closed ? x.end_reason : t('pull.open_ended'))}</td>`
      + `<td class="${x.known ? 'known' : ''}">${x.known ? esc(t('pull.known')) : ''}</td></tr>`).join('');
    body.innerHTML = `<table class="ptable"><tr><th>${esc(t('pull.th_name'))}</th><th>${esc(t('pull.th_mode'))}</th><th>${esc(t('pull.th_rec'))}</th><th>${esc(t('pull.th_size'))}</th><th>${esc(t('pull.th_end'))}</th><th></th></tr>${rows}</table>`;
    for (const tr of body.querySelectorAll('tr[data-i]')) {
      tr.addEventListener('click', () => { sh.sel = +tr.dataset.i; this._renderPull(); });
      tr.addEventListener('dblclick', () => { sh.sel = +tr.dataset.i; this._pullChoose(false); });
    }
  }

  _pullMove(d) {
    const sh = this.sheet;
    if (!sh.items || !sh.items.length) return;
    sh.sel = (sh.sel + d + sh.items.length) % sh.items.length;
    this._renderPull();
  }

  async _pullChoose(force) {
    const sh = this.sheet;
    if (!sh.items || !sh.items.length || sh.busy) return;
    force = !!force || !!sh.force;
    const it = sh.items[sh.sel];
    sh.busy = true;
    sh.box.querySelector('.pbody').innerHTML = `<p class="msg">${esc(t('pull.running', { name: it.name }))}</p>`;
    const r = await this._do(() => post('/api/device/pull', { name: it.name, force }));
    this.closeSheet();
    if (!r) return;
    if (r.status === 'same') toast(t('pull.same'), false, 4000);
    const from = this.actions.currentSegment();
    if (from === 'replay' && r.file) this.actions.replayFile(r.file);
  }

  // connection check
  async openCC() {
    if (!this.connected) { toast(t('err.not_connected'), true); return; }
    const s = this.snap;
    if (!(s.conncheck && s.conncheck.phase === 'running')) {
      const r = await this._do(() => post('/api/device/conncheck/start'));
      if (!r) return;
    }
    this._openSheet('cc', '<div class="ccbody"></div>');
    this._renderCC();
  }

  _renderCC() {
    const sh = this.sheet;
    const cc = this.snap && this.snap.conncheck;
    if (!sh || !cc) return;
    const body = sh.box.querySelector('.ccbody');
    const cases = ['A', 'B', 'C'].map(k => {
      const r = cc.cases[k];
      let v = '';
      if (k === 'C' && cc.battery === false) v = t('cc.res.skipped');
      else if (r && r.st === 'running') v = MARK.run;
      else if (r && r.st === 'done') {
        const other = k === 'C' ? 'unplug' : 'close';
        const o = r.other === null || r.other === undefined ? t('cc.res.unknown') : t(`cc.res.${other}_${r.other ? 'yes' : 'no'}`);
        v = esc(`${t(`cc.res.open_${r.open ? 'yes' : 'no'}`)} · ${o}`);
      }
      return `<div class="case">${r && r.st === 'done' ? (r.open || r.other ? MARK.bad : MARK.ok) : MARK.wait}<span>${esc(t(`cc.case.${k}`))}</span><span class="r">${v}</span></div>`;
    }).join('');
    let prompt = '', acts = '';
    const p = cc.prompt;
    if (cc.phase === 'running') {
      if (p === 'battery') {
        prompt = `<div class="big-prompt">${esc(t('conn.cell'))}</div><p class="sub">${esc(t('cc.battery_note'))}</p>`;
        acts = `<button class="btn quiet b-no">${esc(t('cc.no'))}</button><button class="btn fill small b-yes">${esc(t('cc.yes'))}</button>`;
      } else if (p === 'start_rec') prompt = `<div class="big-prompt">${esc(t('cc.start_rec'))}</div>`;
      else if (p === 'stop_rec') prompt = `<div class="big-prompt">${esc(t('cc.stop_rec'))}</div>`;
      else if (p === 'unplug') prompt = `<div class="big-prompt">${esc(t('cc.unplug'))}</div>`;
      else if (p === 'replug') prompt = `<div class="big-prompt">${esc(t('cc.replug'))}</div>`;
      else if (p === 'pull') prompt = `<div class="big-prompt">${esc(t('cc.pull'))}</div>`;
      else prompt = `<div class="big-prompt">${esc(t('cc.case'))} · ${esc(t(`cc.case.${cc.case || 'A'}`))}</div>`;
      if (cc.wait) {
        const left = Math.max(0, Math.round((cc.wait.until - Date.now()) / 1000));
        prompt += `<p class="wait">${esc(t(`cc.wait.${cc.wait.why}`, { s: left }))}</p>`;
      }
      acts = `<button class="btn quiet b-cancel">${esc(t('cc.cancel'))}</button>` + acts;
    } else {
      if (cc.phase === 'done' && cc.result) {
        const r = cc.result;
        prompt = `<div class="big-prompt">${esc(r.rule ? t('cc.done_rule') : t('cc.done', { method: t(`cc.method.${r.open_method || 'default'}`) }))}</div><p class="sub">${esc(r.reconnect_ok ? t('cc.auto_yes') : t('cc.auto_no'))}</p>`;
        if (cc.sessions && cc.sessions.length) prompt += `<p class="sub">${esc(t('cc.sessions', { n: cc.sessions.length }))}: ${esc(cc.sessions.map(x => `${sess(x.name)} ${x.start_reason || ''}/${x.end_reason || ''}`).join(', '))}</p>`;
      } else if (cc.phase === 'failed') prompt = `<p class="msg err">${esc(t('cc.failed', { err: cc.error || '' }))}</p>`;
      else if (cc.phase === 'cancelled') prompt = `<p class="msg">${esc(t('cc.cancelled'))}</p>`;
      acts = `<button class="btn fill small b-close">${esc(t('cc.close'))}</button>`;
    }
    body.innerHTML = `<h2>${esc(t('cc.title'))}</h2><p class="sub">${esc(t('cc.sub'))}</p><div class="cases">${cases}</div>${prompt}<div class="acts">${acts}</div>`;
    const on = (sel, fn) => { const e = body.querySelector(sel); if (e) e.addEventListener('click', fn); };
    on('.b-yes', () => post('/api/device/conncheck/answer', { value: true }));
    on('.b-no', () => post('/api/device/conncheck/answer', { value: false }));
    on('.b-cancel', () => post('/api/device/conncheck/cancel'));
    on('.b-close', () => this.closeSheet());
    clearTimeout(this._ccTimer);
    if (cc.wait) this._ccTimer = setTimeout(() => this._renderCC(), 1000);
  }

  // Wi-Fi pull
  openWifi() {
    const sh = this._openSheet('wifi', `<h2>${esc(t('wifi.title'))}</h2>
      <p class="sub">1. ${esc(t('wifi.s1'))}</p><p class="sub">2. ${esc(t('wifi.s2'))}</p><p class="sub">3. ${esc(t('wifi.s3'))}</p>
      <div class="wbody"><p class="msg">${esc(t('wifi.waiting'))}</p></div><p class="sub">${esc(t('wifi.note'))}</p>
      <div class="acts"><button class="btn quiet b-close">${esc(t('wifi.close'))}</button></div>`);
    sh.box.querySelector('.b-close').addEventListener('click', () => this.closeSheet());
    const poll = async () => {
      if (this.sheet !== sh || sh.busy) return;
      let st;
      try { st = await get('/api/wifi/status'); } catch (e) { return; }
      if (this.sheet !== sh) return;
      const body = sh.box.querySelector('.wbody');
      if (!st.ok) { body.innerHTML = `<p class="msg">${esc(t('wifi.waiting'))}</p>`; sh.found = false; return; }
      if (!sh.found) {
        sh.found = true;
        let list;
        try { list = await get('/api/wifi/list'); } catch (e) { list = { sessions: [] }; }
        sh.items = list.sessions || [];
      }
      const s = st.status;
      const rows = (sh.items || []).map((x, i) => `<tr data-i="${i}"><td class="mono">${esc(sess(x.name))}</td><td>${esc(modeName(x.mode))}</td><td>${esc(comma(x.records))}</td><td>${esc(comma(x.size))} B</td>`
        + `<td>${esc(x.end_reason || '-')}</td><td class="${x.known ? 'known' : ''}">${x.known ? esc(t('pull.known')) : `<button class="btn quiet b-wp" data-i="${i}">${esc(t('wifi.pull'))}</button>`}</td></tr>`).join('');
      body.innerHTML = `<p class="msg">${esc(t('wifi.found', { device: `WFG-${s.device}`, fw: s.fw }))}</p>`
        + (rows ? `<table class="ptable">${rows}</table>` : `<p class="msg">${esc(t('wifi.none'))}</p>`);
      for (const b of body.querySelectorAll('.b-wp')) b.addEventListener('click', () => this._wifiPull(sh, sh.items[+b.dataset.i]));
    };
    poll();
    sh.timer = setInterval(poll, 2000);
  }

  async _wifiPull(sh, it) {
    sh.busy = true;
    sh.box.querySelector('.wbody').innerHTML = `<p class="msg">${esc(t('pull.running', { name: it.name }))}</p>`;
    try {
      const r = await post('/api/wifi/pull', { name: it.name });
      toast(t('wifi.pulled', { path: r.file }), false, 5000);
      it.known = r.file;
    } catch (e) { toast(t('wifi.failed', { err: errText(e.message) || e.message }), true, 8000); }
    sh.busy = false;
    sh.found = false;
  }

  // battery calibration (CALVBAT is sent only from here)
  openCal() {
    if (!this.connected) return;
    const vb = this.snap.vbat;
    const now = vb && vb.valid ? t('cal.now', { v: fixed(vb.vbat_mv / 1000, 3), cal: vb.cal || '-' }) : '';
    const sh = this._openSheet('cal', `<h2>${esc(t('cal.title'))}</h2><p class="sub">1. ${esc(t('cal.s1'))}</p><p class="sub">2. ${esc(t('cal.s2'))}</p>
      <p class="sub">${esc(now)}</p>
      <div class="formrow"><label>${esc(t('cal.input'))}</label><input type="text" inputmode="numeric" class="mv" placeholder="4100" autocomplete="off"></div>
      <p class="sub">${esc(t('cal.range'))}</p><div class="reply"></div>
      <div class="acts"><button class="btn quiet b-reset">${esc(t('cal.reset'))}</button><button class="btn quiet b-close">${esc(t('cal.close'))}</button><button class="btn fill small b-send">${esc(t('cal.send'))}</button></div>`);
    const input = sh.box.querySelector('.mv');
    const reply = sh.box.querySelector('.reply');
    const send = async (reset) => {
      const v = input.value.trim();
      if (!reset && !/^[1-9]\d{0,4}$/.test(v)) { reply.className = 'reply err'; reply.textContent = t('cal.bad_input'); return; }
      try {
        const r = await post('/api/device/calibrate', reset ? { reset: true } : { mv: v });
        reply.className = `reply${r.ok ? '' : ' err'}`;
        reply.textContent = `${t('cal.reply')}: ${r.reply || '-'}`;
      } catch (e) { reply.className = 'reply err'; reply.textContent = errText(e.message) || e.message; }
    };
    sh.box.querySelector('.b-send').addEventListener('click', () => send(false));
    sh.box.querySelector('.b-reset').addEventListener('click', () => send(true));
    sh.box.querySelector('.b-close').addEventListener('click', () => this.closeSheet());
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); send(false); } e.stopPropagation(); });
    setTimeout(() => input.focus(), 50);
  }
}

export { getLang };
