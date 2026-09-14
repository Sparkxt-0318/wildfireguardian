import type { Situation } from "../api/client";
import { DangerBadge } from "../components/DangerBadge";
import { GuidanceCard } from "../components/GuidanceCard";
import { IconPhone } from "../components/Icons";
import { useI18n } from "../i18n";

/**
 * Guide: every triaged card, each with read-aloud; call-119 uses a tel: link
 * (inside GuidanceCard). A standing 119 button sits at the end so the number
 * is always one tap away even when the card set has no contact card.
 */
export function GuideScreen({
  situation,
  onOpenMap,
  onOpenRoute,
}: {
  situation: Situation;
  onOpenMap: () => void;
  onOpenRoute: () => void;
}) {
  const { t } = useI18n();
  const hasCallCard = situation.cards.some(
    (c) => c.action.type === "call",
  );

  return (
    <div className="screen-pad">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1 className="section-title">{t("guide_title")}</h1>
        <DangerBadge danger={situation.danger} />
      </div>
      {situation.cards.length === 0 && (
        <p className="big-state-sub">{t("guide_empty")}</p>
      )}
      {situation.cards.map((card) => (
        <GuidanceCard
          key={card.id}
          card={card}
          onOpenMap={onOpenMap}
          onOpenRoute={onOpenRoute}
        />
      ))}
      {!hasCallCard && (
        <a
          className="btn-big-secondary btn-call"
          href="tel:119"
          style={{ marginTop: 16 }}
        >
          <IconPhone size={28} />
          {t("call_119")}
        </a>
      )}
    </div>
  );
}
