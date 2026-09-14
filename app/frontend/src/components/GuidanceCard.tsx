import type { Card } from "../api/client";
import { useI18n } from "../i18n";
import { CardIconGlyph, IconPhone } from "./Icons";
import { ReadAloud } from "./ReadAloud";

/**
 * One triaged guidance card (spec §5.1 / §6): icon + title + body, a
 * read-aloud button, and — when the API attaches an action — one action
 * control. `call` actions are real tel: links.
 */
export function GuidanceCard({
  card,
  onOpenMap,
  onOpenRoute,
}: {
  card: Card;
  onOpenMap: () => void;
  onOpenRoute: () => void;
}) {
  const { t, pick } = useI18n();
  const title = pick(card, "title");
  const body = pick(card, "body");

  let actionEl = null;
  if (card.action.type === "call" && card.action.value) {
    actionEl = (
      <a
        className="btn-big-secondary btn-call"
        href={`tel:${card.action.value}`}
        style={{ marginTop: 12 }}
      >
        <IconPhone size={28} />
        {t("call_119").replace("119", card.action.value)}
      </a>
    );
  } else if (card.action.type === "open_map") {
    actionEl = (
      <button
        type="button"
        className="btn-big-secondary"
        style={{ marginTop: 12 }}
        onClick={onOpenMap}
      >
        {t("open_map_action")}
      </button>
    );
  } else if (card.action.type === "open_route") {
    actionEl = (
      <button
        type="button"
        className="btn-big-secondary"
        style={{ marginTop: 12 }}
        onClick={onOpenRoute}
      >
        {t("open_route_action")}
      </button>
    );
  }

  return (
    <article className={`card kind-${card.kind}`}>
      <div className="card-head">
        <span className="card-icon" style={{ color: "var(--ink-secondary)" }}>
          <CardIconGlyph icon={card.icon} size={44} />
        </span>
        <h2 className="card-title">{title}</h2>
        <ReadAloud text={`${title}. ${body}`} />
      </div>
      <p className="card-body">{body}</p>
      {actionEl}
    </article>
  );
}
