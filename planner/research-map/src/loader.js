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
if (!window.THREE) { document.getElementById('loading').textContent = tr('3D 라이브러리를 불러오지 못했습니다. 인터넷 연결을 확인하거나 오프라인 판(vendor 폴더 포함)을 여세요.', 'Could not load the 3D library. Check the connection or open the offline build (with its vendor folder).'); return; }
// regions/<name> as a script file, or (single-file build) from an inert text block that is run only when needed
const load = name => new Promise(ok => {
  const inline = document.getElementById('wfg:' + name);
  if (inline) { try { (0, eval)(inline.textContent); ok(true); } catch (e) { ok(false); } return; }
  const s = document.createElement('script'); s.src = 'regions/' + name; s.onload = () => ok(true); s.onerror = () => ok(false); document.head.appendChild(s);
});
window.__wfgLoad = load;
// region data and its pre-built terrain load in parallel; the terrain is optional (drawn in the page without it)
const texReady = load(`${RID}.tex.js`);
load(`${RID}.js`).then(async ok => {
  if (!ok) { document.getElementById('loading').textContent = tr('지역 데이터를 불러오지 못했습니다: ', 'Could not load region data: ') + RID; return; }
  await texReady; main(window.WFG_REGIONS[RID]);
});
function main(B) {
__MAIN__
}
})();
