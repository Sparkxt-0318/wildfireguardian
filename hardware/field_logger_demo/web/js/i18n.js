// Korean / English (key L). Both files have the same keys (a test checks it). Text is plain unless a key's value
// carries markup on purpose (tl.summary uses <b> for the semibold part).
import { bus, esc } from './util.js';

const dicts = {};
let lang = 'ko';

export async function loadI18n() {
  const [ko, en] = await Promise.all(['ko', 'en'].map(l => fetch(`i18n/${l}.json`).then(r => r.json())));
  dicts.ko = ko; dicts.en = en;
}

export function getLang() { return lang; }

export function setLang(l) {
  lang = l === 'en' ? 'en' : 'ko';
  document.documentElement.lang = lang;
  document.body.classList.toggle('ko', lang === 'ko');
  document.body.classList.toggle('en', lang === 'en');
  document.title = t('app.title');
  bus.emit('lang', lang);
}

export function toggleLang() { setLang(lang === 'ko' ? 'en' : 'ko'); }

// t(name, {a: 1}) -> text with {a} replaced. Unknown keys return the key itself (visible, so they get fixed).
export function t(key, args = {}, l = lang) {
  let s = (dicts[l] && dicts[l][key]);
  if (s === undefined) s = (dicts.en && dicts.en[key]) ?? key;
  return s.replace(/\{(\w+)\}/g, (m, k) => (args[k] === undefined || args[k] === null ? '' : String(args[k])));
}

// same, with the arguments HTML-escaped (for keys that carry markup)
export function th(key, args = {}, l = lang) {
  const safe = {};
  for (const [k, v] of Object.entries(args)) safe[k] = esc(v);
  return t(key, safe, l);
}

export function has(key) { return dicts.ko && key in dicts.ko; }

export function modeName(m, l = lang) { return t(`mode.${m || 'UNKNOWN'}`, {}, l); }
