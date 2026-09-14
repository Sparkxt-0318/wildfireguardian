import type { Danger } from "../api/client";
import { useI18n } from "../i18n";
import { DangerIconGlyph } from "./Icons";

/**
 * Compact danger chip: color + icon + word, never color alone (spec §1.2).
 * The word comes from the API's own label fields.
 */
export function DangerBadge({ danger, size = 28 }: { danger: Danger; size?: number }) {
  const { pick } = useI18n();
  const bg =
    danger.level === "SAFE"
      ? "var(--safe)"
      : danger.level === "WATCH"
        ? "var(--watch)"
        : "var(--go)";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        background: bg,
        color: "#fff",
        borderRadius: "var(--radius)",
        padding: "6px 14px",
        fontWeight: 800,
        fontSize: "var(--fs-body)",
      }}
    >
      <DangerIconGlyph level={danger.level} size={size} />
      {pick(danger, "label")}
    </span>
  );
}
