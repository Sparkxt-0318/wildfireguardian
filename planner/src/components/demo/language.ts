/**
 * First visit of the public static demo: use the browser's preferred language — Korean when any
 * preferred language is Korean, otherwise English — unless the user already chose one (stored by
 * the language toggle) or the link says ?lang=ko|en (handled later by initApp). Booth modes keep
 * the Korean default.
 */
import { useLangStore, type Lang } from '../../i18n';

const LANG_KEY = 'wfg.planner.lang';

export function preferredLanguage(languages: readonly string[] | undefined): Lang {
  return (languages ?? []).some((l) => /^ko(\b|-|_|$)/i.test(String(l))) ? 'ko' : 'en';
}

export function applyFirstVisitLanguage(): void {
  try {
    if (typeof localStorage !== 'undefined' && localStorage.getItem(LANG_KEY)) return;
  } catch {
    /* storage blocked: decide from the browser for this visit */
  }
  if (typeof navigator === 'undefined') return;
  const langs = navigator.languages?.length ? navigator.languages : navigator.language ? [navigator.language] : [];
  const lang = preferredLanguage(langs);
  if (useLangStore.getState().lang !== lang) useLangStore.getState().setLang(lang);
}
