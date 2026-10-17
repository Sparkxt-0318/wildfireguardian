/**
 * Minimal i18n: Korean first, English toggle.
 *
 *   const t = useT();
 *   t('timeline.legend');                       // current language
 *   t('deadline.at', { time: '18:10' });        // "{time}" placeholders
 *
 * Other modules (e.g. src/features/**) may add their own strings with `registerStrings`.
 * A missing key falls back to Korean, then to the key itself (never throws).
 */
import { useCallback } from 'react';
import { create } from 'zustand';
import { STRINGS } from './strings';

export type Lang = 'ko' | 'en';

export type TFunction = (key: string, vars?: Record<string, string | number>) => string;

type Dict = Record<string, string>;

const extra: Record<Lang, Dict> = { ko: {}, en: {} };

/** Adds (or overrides) strings for one or both languages. */
export function registerStrings(dicts: Partial<Record<Lang, Dict>>): void {
  for (const lang of ['ko', 'en'] as const) {
    const d = dicts[lang];
    if (d) Object.assign(extra[lang], d);
  }
}

function lookup(lang: Lang, key: string): string | undefined {
  return extra[lang][key] ?? STRINGS[lang][key];
}

function interpolate(s: string, vars?: Record<string, string | number>): string {
  if (!vars) return s;
  return s.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m));
}

/** Non-React translation (pure). */
export function translate(lang: Lang, key: string, vars?: Record<string, string | number>): string {
  const s = lookup(lang, key) ?? lookup('ko', key) ?? key;
  return interpolate(s, vars);
}

function initialLang(): Lang {
  try {
    const v = typeof localStorage !== 'undefined' ? localStorage.getItem('wfg.planner.lang') : null;
    return v === 'en' ? 'en' : 'ko';
  } catch {
    return 'ko';
  }
}

interface LangState {
  lang: Lang;
  setLang: (lang: Lang) => void;
}

export const useLangStore = create<LangState>((set) => ({
  lang: initialLang(),
  setLang: (lang) => {
    try {
      localStorage.setItem('wfg.planner.lang', lang);
    } catch {
      /* storage unavailable: language just isn't remembered */
    }
    if (typeof document !== 'undefined') document.documentElement.lang = lang;
    set({ lang });
  },
}));

export function useLang(): Lang {
  return useLangStore((s) => s.lang);
}

/** Translation function bound to the current UI language. */
export function useT(): TFunction {
  const lang = useLang();
  return useCallback((key: string, vars?: Record<string, string | number>) => translate(lang, key, vars), [lang]);
}
