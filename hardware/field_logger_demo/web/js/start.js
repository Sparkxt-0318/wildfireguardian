// Start screen (spec section 3A and 3C): the headline, two buttons, one quiet line from port detection, the device
// render and the saved recordings (keys 1 to 9).
import { esc, mmss, dateOnly, fixed } from './util.js';
import { t, getLang } from './i18n.js';

export class StartScreen {
  constructor(root, actions) {
    this.root = root;
    this.actions = actions;
    this.library = [];
    this.dev = null;
    root.innerHTML = `
      <div class="hero2">
        <h1></h1>
        <p class="lede"></p>
        <div class="ctas"><button class="btn fill b-dev"><span class="lbl"></span><span class="kc inv">D</span></button>
          <button class="btn line b-rep"><span class="lbl"></span><span class="kc">1</span></button></div>
        <div class="found"></div>
        <img src="img/device.png" class="dev" alt="">
        <div class="credit"></div>
      </div>
      <div class="lib"><div class="eyebrow2"></div><div class="cards"></div></div>`;
    root.querySelector('.b-dev').addEventListener('click', () => actions.device());
    root.querySelector('.b-rep').addEventListener('click', () => actions.replayFirst());
  }

  setLibrary(entries) { this.library = entries; this.render(); }
  setDevice(snap) { this.dev = snap; this.renderFound(); this.renderButtons(); }

  render() {
    const r = this.root;
    r.querySelector('h1').textContent = t('app.title');
    r.querySelector('.lede').textContent = t('start.sub');
    r.querySelector('.credit').textContent = t('start.credit');
    r.querySelector('.lib .eyebrow2').textContent = t('start.library');
    const keyed = this.library.filter(e => e.key).sort((a, b) => a.key - b.key);
    const cards = r.querySelector('.cards');
    if (!keyed.length) cards.innerHTML = `<div class="empty">${esc(t('start.empty'))}</div>`;
    else {
      cards.innerHTML = keyed.slice(0, 5).map(e => {
        const title = (getLang() === 'ko' ? e.title_ko : e.title_en) || e.file;
        let sub;
        if (e.missing) sub = t('start.card_missing');
        else if (e.sim) sub = t('start.card_sim');
        else if (e.source === 'gpx') sub = t('start.card_gpx');
        else sub = t('start.card_sub', { date: dateOnly(e.utc0, e.tz, getLang()), dur: durWords(e.duration_s) });
        return `<div class="sc glass${e.missing ? ' missing' : ''}" data-key="${e.key}"><span class="kc">${e.key}</span><div><b>${esc(title)}</b><span>${esc(sub)}</span></div></div>`;
      }).join('');
      for (const c of cards.querySelectorAll('.sc')) c.addEventListener('click', () => this.actions.replay(+c.dataset.key));
    }
    const first = keyed[0];
    r.querySelector('.b-rep .kc').textContent = first ? first.key : '1';
    this.renderButtons();
    this.renderFound();
  }

  renderButtons() {
    const connected = this.dev && this.dev.conn && this.dev.conn.state === 'connected';
    this.root.querySelector('.b-dev .lbl').textContent = connected ? t('start.device') : t('start.connect');
    this.root.querySelector('.b-rep .lbl').textContent = t('start.replay');
  }

  renderFound() {
    const f = this.root.querySelector('.found');
    const d = this.dev;
    if (!d) { f.innerHTML = ''; return; }
    const c = d.conn || {};
    if (c.state === 'connected') {
      const dev = d.hello && d.hello.device ? `WFG-${d.hello.device}` : (c.port || '');
      const state = t(`rec.${(d.status && d.status.state) || 'IDLE'}`);
      const v = d.vbat && d.vbat.valid ? fixed(d.vbat.vbat_mv / 1000, 2) : null;
      f.className = 'found ok';
      f.innerHTML = `<i class="dot"></i>${esc(v ? t('start.connected', { device: dev, state, v }) : t('start.connected_nobatt', { device: dev, state }))}`;
      return;
    }
    if (c.state === 'lost') {
      f.className = 'found';
      f.innerHTML = `<i class="dot red"></i>${esc(t('start.lost'))}`;
      return;
    }
    const likely = (d.ports || []).filter(p => p.likely);
    f.className = 'found';
    if (likely.length) {
      const chip = likely.map(p => (p.chip ? `WCH ${p.chip}` : (p.simulated ? t('connect.simulated') : ''))).filter(Boolean)[0];
      f.innerHTML = `<i class="dot grey"></i>${esc(chip ? t('start.found', { n: likely.length, chip }) : t('start.found_nochip', { n: likely.length }))}`;
    } else {
      f.innerHTML = `<i class="dot grey"></i>${esc(t('start.none'))}`;
    }
  }
}

function durWords(s) {
  const m = Math.round((s || 0) / 60);
  if (getLang() === 'ko') return m >= 1 ? `${m}분` : `${Math.round(s || 0)}초`;
  return m >= 1 ? `${m} min` : `${Math.round(s || 0)} s`;
}

export { mmss };
