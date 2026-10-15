// Development only (--dev-device-double): buttons that act on the simulated logger, and what its own screen would
// show. Everything here is labelled as simulated; the panel does not exist without the double.
import { esc } from './util.js';
import { t } from './i18n.js';
import { post } from './api.js';

export class DevPanel {
  constructor() {
    this.el = document.createElement('div');
    this.el.className = 'devpanel glass hidden';
    document.body.appendChild(this.el);
    this.min = true;
  }

  update(snap) {
    const d = snap && snap.double;
    this.el.classList.toggle('hidden', !d);
    this.el.classList.toggle('min', this.min);
    if (!d) return;
    const b = (act, label, body = {}, on = false) => `<button class="${on ? 'on' : ''}" data-a="${act}" data-b='${esc(JSON.stringify(body))}'>${esc(label)}</button>`;
    const gn = ['indoor', 'time', 'fix', 'nodata', 'cksum'].map(m => b('gnss', t(`dp.gnss.${m}`), { mode: m }, d.gnss === m)).join('');
    const rs = Object.keys(d.restart_on).map(k => b('restart', t(`dp.restart.${k}`), { [k]: !d.restart_on[k] }, d.restart_on[k])).join('');
    const top = `${d.state === 'RECORDING' ? 'REC' : (d.export_mode ? 'EXPORT' : d.state)} ${d.mode}${d.session ? ` ${d.session.replace('.wfg', '')} ${d.records}` : ''}`;
    const screen = d.powered ? (d.screen_on ? `${esc(top)}${d.banner ? `<br>${esc(d.banner)}` : ''}` : esc(t('dp.screen_off'))) : '-';
    this.el.innerHTML = `<h4><span>${esc(t('dp.title'))}</span><button data-min="1">${this.min ? '+' : '-'}</button></h4><div class="body${this.min ? ' hidden' : ''}">
      <div class="row"><span>${esc(t('dp.button'))}</span>${b('press', t('dp.short'), { kind: 'short' })}${b('press', t('dp.long'), { kind: 'long' })}${b('press', t('dp.very_long'), { kind: 'very_long' })}</div>
      <div class="row"><span>${esc(t('dp.cable'))}</span>${d.present ? b('unplug', t('dp.unplug')) : b('replug', t('dp.replug'))}${b('reset', t('dp.reset'))}${b('battery', t('dp.battery'), { on: !d.battery }, d.battery)}</div>
      <div class="row"><span>${esc(t('dp.gnss'))}</span>${gn}</div>
      <div class="row"><span>${esc(t('dp.restart'))}</span>${rs}</div>
      <div class="row"><span>${esc(t('dp.more'))}</span>${b('fill', t('dp.fill'), { on: d.free > 60000 }, d.free <= 60000)}${b('corrupt', t('dp.corrupt'))}${b(d.fs_ok ? 'fs_error' : 'fs_ok', d.fs_ok ? t('dp.fs_error') : t('dp.fs_ok'))}${b('download', t('dp.download'))}${b('samples', t('dp.samples'))}</div>
      <div class="scr">${esc(t('dp.screen'))}: ${screen}</div></div>`;
    for (const x of this.el.querySelectorAll('button[data-a]')) {
      x.addEventListener('click', () => post(`/api/device/double/${x.dataset.a}`, JSON.parse(x.dataset.b || '{}')).catch(() => {}));
    }
    this.el.querySelector('button[data-min]').addEventListener('click', () => { this.min = !this.min; this.update(snap); });
  }
}
