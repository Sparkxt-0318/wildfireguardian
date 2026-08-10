import type { Situation } from "../api/client";
import { useI18n } from "../i18n";
import { DangerIconGlyph } from "./Icons";
import { ReadAloud } from "./ReadAloud";

/**
 * Full-bleed danger header: color + icon + word (hero, 40px) + one-line
 * reason — all straight from the API (spec §1.2, §7).
 */
export function StatusHeader({ situation }: { situation: Situation }) {
  const { lang, pick } = useI18n();
  const { danger } = situation;
  // The word in the other language, small, so a mixed household reads it too.
  const otherLabel = lang === "ko" ? danger.label_en : danger.label_ko;

  return (
    <header className={`status-header level-${danger.level}`}>
      <span className="status-icon">
        <DangerIconGlyph level={danger.level} size={72} />
      </span>
      <h1 className="status-word">{pick(danger, "label")}</h1>
      <p className="status-word-sub">{otherLabel}</p>
      <p className="status-reason">{pick(danger, "reason")}</p>
      <div style={{ marginTop: 12, display: "flex", justifyContent: "center" }}>
        <ReadAloud
          text={`${pick(danger, "label")}. ${pick(danger, "reason")}`}
        />
      </div>
    </header>
  );
}
