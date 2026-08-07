import type { AppConfig } from "../api/client";
import { useI18n } from "../i18n";

/**
 * Persistent honesty label when serving the bundled demo scenario (spec §1.5).
 * Uses the server's own banner text when provided; bilingual fallback otherwise.
 */
export function DemoBanner({ config }: { config: AppConfig | null }) {
  const { lang, t } = useI18n();
  if (!config || config.mode !== "demo") return null;
  const serverText =
    lang === "ko" ? config.demo_banner_ko : config.demo_banner_en;
  return (
    <div className="demo-banner" role="status">
      {serverText || t("demo_banner_fallback")}
    </div>
  );
}
