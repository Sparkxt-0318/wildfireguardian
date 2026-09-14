import { useI18n } from "../i18n";

/**
 * Large, obvious language switch. Both options always visible so the control
 * can be found in either language.
 */
export function LangToggle() {
  const { lang, setLang } = useI18n();
  return (
    <div
      className="row"
      role="group"
      aria-label="언어 / Language"
      style={{ gap: 8 }}
    >
      <button
        type="button"
        className={`btn-pill${lang === "ko" ? " selected" : ""}`}
        aria-pressed={lang === "ko"}
        onClick={() => setLang("ko")}
      >
        한국어
      </button>
      <button
        type="button"
        className={`btn-pill${lang === "en" ? " selected" : ""}`}
        aria-pressed={lang === "en"}
        onClick={() => setLang("en")}
      >
        English
      </button>
    </div>
  );
}
