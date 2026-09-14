import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ko, type MessageKey, type Messages } from "./ko";
import { en } from "./en";
import { getPref, setPref } from "../lib/prefs";

export type Lang = "ko" | "en";

const DICTS: Record<Lang, Messages> = { ko, en };

/** An API object carrying `<base>_ko` / `<base>_en` string fields (spec §5). */
type Bilingual<K extends string> = { [P in `${K}_ko` | `${K}_en`]: string };

export interface I18n {
  lang: Lang;
  /** BCP-47 speech-synthesis language for the current UI language. */
  speechLang: "ko-KR" | "en-US";
  setLang: (lang: Lang) => void;
  /** Translate a UI string key in the current language. */
  t: (key: MessageKey) => string;
  /** Both languages of a key — [current language first, other second].
   *  Used by the calm bilingual loading / error states. */
  pair: (key: MessageKey) => [string, string];
  /** Pick the `*_ko` / `*_en` variant of an API field for the current language. */
  pick: <K extends string>(obj: Bilingual<K>, base: K) => string;
}

const I18nContext = createContext<I18n | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    const saved = getPref("lang");
    return saved === "en" ? "en" : "ko"; // default: Korean (spec §1.6)
  });

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    setPref("lang", next);
  }, []);

  // Keep <html lang> in sync (index.html ships lang="ko") so screen readers
  // voice the UI in the selected language.
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const t = useCallback((key: MessageKey) => DICTS[lang][key], [lang]);

  const pair = useCallback(
    (key: MessageKey): [string, string] =>
      lang === "ko" ? [ko[key], en[key]] : [en[key], ko[key]],
    [lang],
  );

  const pick = useCallback(
    <K extends string>(obj: Bilingual<K>, base: K): string =>
      lang === "ko" ? obj[`${base}_ko`] : obj[`${base}_en`],
    [lang],
  );

  const value = useMemo<I18n>(
    () => ({
      lang,
      speechLang: lang === "ko" ? "ko-KR" : "en-US",
      setLang,
      t,
      pair,
      pick,
    }),
    [lang, setLang, t, pair, pick],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside <I18nProvider>");
  return ctx;
}

export type { MessageKey };
