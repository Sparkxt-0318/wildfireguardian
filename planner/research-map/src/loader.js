(() => {
'use strict';
const RIDX = window.WFG_REGION_INDEX || [];
const hp0 = new URLSearchParams(location.hash.slice(1));
const stored = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
let RID = hp0.get('region') || stored('wfg3d.region') || 'uiseong_andong_2025';
if (!RIDX.some(r => r.id === RID)) RID = 'uiseong_andong_2025';
const EN = (hp0.get('lang') || stored('wfg3d.lang') || 'ko') === 'en';
const tr = (ko, en) => EN ? en : ko;
document.documentElement.lang = EN ? 'en' : 'ko';
if (EN) {
  document.querySelectorAll('[data-en]').forEach(e => { e.innerHTML = e.dataset.en; });
  document.querySelectorAll('[data-en-title]').forEach(e => { e.title = e.dataset.enTitle; });
  document.querySelectorAll('[data-en-aria]').forEach(e => { e.setAttribute('aria-label', e.dataset.enAria); });
  document.querySelector('.lightbox figcaption').innerHTML = '<span></span><button type="button">Close</button>';
}
if (!window.THREE || !window.THREE.OrbitControls) { startupError(tr('3D 라이브러리를 불러오지 못했습니다. 오프라인 판의 vendor 폴더를 확인하세요.', '3D libraries unavailable. Check the offline build vendor folder.')); return; }
// regions/<name> as a script file, or (single-file build) from an inert text block that is run only when needed
// Bound remote/optional resources so a stalled venue connection cannot trap the opening screen.
const withDeadline = (promise, ms, fallback) => new Promise(resolve => {
  let done = false; const finish = value => { if (done) return; done = true; clearTimeout(timer); resolve(value); };
  const timer = setTimeout(() => finish(fallback), ms); Promise.resolve(promise).then(finish, () => finish(fallback));
});
function startupError(error) {
  const ld = document.getElementById('loading'); if (!ld) return;
  ld.className = 'loading'; ld.style.backgroundImage = ''; ld.textContent = tr('지도를 시작하지 못했습니다. 연결을 확인한 뒤 다시 시도해 주세요. ', 'The map could not start. Check the connection and retry. ') + (error && error.message || error || '');
  const retry = document.createElement('button'); retry.type = 'button'; retry.className = 'btn'; retry.textContent = tr('다시 열기', 'Retry'); retry.onclick = () => location.reload(); ld.appendChild(retry);
}
const load = (name, timeout = 12000) => new Promise(ok => {
  const inline = document.getElementById('wfg:' + name);
  if (inline) { try { (0, eval)(inline.textContent); ok(true); } catch (e) { ok(false); } return; }
  const s = document.createElement('script'); let settled = false;
  const finish = value => { if (settled) return; settled = true; clearTimeout(timer); s.onload = s.onerror = null; if (!value) s.remove(); ok(value); };
  const timer = setTimeout(() => finish(false), timeout);
  s.src = 'regions/' + name; s.onload = () => finish(true); s.onerror = () => finish(false); document.head.appendChild(s);
});
window.__wfgLoad = load;
// region data and its pre-built terrain load in parallel; the terrain is optional (drawn in the page without it). The terrain
// images start downloading as soon as their small index file is in, not after the region data.
const img = src => new Promise((ok, no) => {
  const im = new Image(); let settled = false; im.decoding = 'async';
  const finish = error => { if (settled) return; settled = true; clearTimeout(timer); im.onload = im.onerror = null; error ? no(error) : ok(im); };
  const timer = setTimeout(() => { finish(new Error('Image load timed out')); im.src = ''; }, 6000);
  im.onload = () => finish(null); im.onerror = () => finish(new Error('Image load failed')); im.src = src;
});
// a picture of the opening view (tools/bake_textures.mjs) stands in for the map while it starts, when the link asks for that view
// (desktop only: the picture is taken at desktop size, and phones and lite=1 use a different camera distance)
const DEFAULT_VIEW = [...hp0.keys()].every(k => ['region', 'lang', 'tab'].includes(k)) && !matchMedia('(max-width: 860px)').matches;
const texReady = load(`${RID}.tex.js`, 6000).then(ok => { const t = ok && (window.WFG_TEX || {})[RID];
  const ld = document.getElementById('loading');
  const show = t && t.poster && DEFAULT_VIEW && ld;
  if (show) { ld.classList.add('poster'); ld.innerHTML = `<span>${tr('3D 지형 준비 중…', 'Preparing the 3D view…')}</span>`; }
  // the poster goes first (it is small and is what you see); the terrain images follow it
  const first = show ? img(t.poster).then(im => { ld.style.backgroundImage = `url("${im.src}")`; }, () => ld.classList.remove('poster')) : Promise.resolve();
  if (t) window.__wfgImg = Object.fromEntries(['ground', 'hs', 'ctxReal', 'mask'].map(k => { const p = first.then(() => img(t[k])); p.catch(() => { }); return [k, p]; }));
  return show ? first.then(() => new Promise(ok => requestAnimationFrame(() => setTimeout(ok, 0)))) : null; });
// opened from disk, files arrive at once and parsing the region data would hold the poster back: start it once the poster is up
const gate = location.protocol === 'file:' ? texReady : Promise.resolve();
const ctxP = gate.then(() => load(`${RID}.ctx.js`, 8000)).then(ok => ok ? (window.WFG_CTX || {})[RID] : null);
gate.then(() => load(`${RID}.js`, 18000)).then(async ok => {
  if (!ok) { startupError(tr('지역 데이터: ', 'Region data: ') + RID); return; }
  // the surrounding-terrain heights follow; the first frame does not wait for them
  window.__wfgCtx = ctxP;
  await texReady; main(window.WFG_REGIONS[RID]);
}).catch(startupError);
function main(B) {
__MAIN__
}
})();
