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
if (window.WFG_REGIONS && window.WFG_REGIONS[RID]) { main(window.WFG_REGIONS[RID]); return; }   // single-file build: data already inline
// region data and its pre-built terrain images load in parallel; the images are optional (drawn in the page without them)
const load = src => new Promise(ok => { const s = document.createElement('script'); s.src = src; s.onload = () => ok(true); s.onerror = () => ok(false); document.head.appendChild(s); });
const texReady = window.WFG_TEX && window.WFG_TEX[RID] ? Promise.resolve(true) : load(`regions/${RID}.tex.js`);
load(`regions/${RID}.js`).then(async ok => {
  if (!ok) { document.getElementById('loading').textContent = tr('지역 데이터를 불러오지 못했습니다: ', 'Could not load region data: ') + RID; return; }
  await texReady; main(window.WFG_REGIONS[RID]);
});
function main(B) {
__MAIN__
}
})();
