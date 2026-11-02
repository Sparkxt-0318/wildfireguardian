/**
 * One printable origin card (A5 or A4 portrait, one page): status as icon + text, the leave-by time
 * in large type, the message lines, "공식 대피 명령이 우선합니다", the data time with the replay note,
 * "모델 기반 계획 정보 · 실시간 아님", the limitations and the planner footer. Body text is ≥ 14 pt
 * (lastmile.css); every string comes from the CardContent built by the templates.
 */
import { VerdictIcon } from '../shared/VerdictIcon';
import type { CardContent } from './compose';

export type CardSize = 'a5' | 'a4';

export interface FieldCardProps {
  card: CardContent;
  size: CardSize;
  originId: string;
  current?: boolean;
}

export function FieldCard({ card, size, originId, current }: FieldCardProps) {
  return (
    <article
      className={`wfgl-card wfgl-card--${size}`}
      lang={card.lang}
      data-card-origin={originId}
      data-card-size={size}
      data-card-status={card.statusIcon}
      data-current={current ? 'true' : 'false'}
      aria-label={`${card.docTitle} — ${card.title}`}
    >
      <header className="wfgl-card__head">
        <span className="wfgl-card__doc">{card.docTitle}</span>
        <span className="wfgl-card__sep" aria-hidden="true">
          ·
        </span>
        <span>{card.regionName}</span>
        <span className="wfgl-card__sep" aria-hidden="true">
          ·
        </span>
        <span className="wfgl-card__fire" data-fire-input="true">
          {card.fireInputLabel}
        </span>
        {card.badges.map((b) => (
          <span key={b} className="wfgl-card__badge" data-badge={b}>
            {b}
          </span>
        ))}
      </header>
      <h1 className="wfgl-card__title">
        {card.title}
        {card.category ? <span className="wfgl-card__cat">{card.category}</span> : null}
      </h1>
      <div className={`wfgl-card__status wfgl-card__status--${card.statusIcon}`} data-status-text="true">
        <VerdictIcon verdict={card.statusIcon} size={30} />
        <span>{card.statusText}</span>
      </div>
      {card.big ? (
        <div className="wfgl-card__big" data-leave-by={card.big.time}>
          <span className="wfgl-card__biglabel">{card.big.label}</span>
          <span className="wfgl-card__bigtime">{card.big.time}</span>
          <span className="wfgl-card__bigsub">{card.big.sub}</span>
        </div>
      ) : null}
      <ul className="wfgl-card__lines">
        {card.lines.map((l, i) => (
          <li key={i} data-role={l.role}>
            {l.text}
          </li>
        ))}
      </ul>
      <div className="wfgl-card__bottom">
        <p className="wfgl-card__official" data-official="true">
          {card.official}
        </p>
        <p className="wfgl-card__data" data-data-time="true">
          {card.dataLine}
        </p>
        <p className="wfgl-card__model" data-model-line="true">
          {card.modelLine}
        </p>
        <p className="wfgl-card__limits">{card.limits}</p>
        <footer className="wfgl-card__foot">
          <span className="wfgl-card__footrule">{card.footer}</span>
          <span className="wfgl-card__meta">{card.meta}</span>
        </footer>
      </div>
    </article>
  );
}

export default FieldCard;
