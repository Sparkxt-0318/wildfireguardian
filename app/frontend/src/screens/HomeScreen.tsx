import { useEffect, useState } from "react";
import {
  getHistory,
  type HistoryPoint,
  type Situation,
} from "../api/client";
import { BigButton } from "../components/BigButton";
import { DetectionTimeline } from "../components/DetectionTimeline";
import { GuidanceCard } from "../components/GuidanceCard";
import { IconSpeaker, IconStop } from "../components/Icons";
import { SpreadTimeline } from "../components/SpreadTimeline";
import { StatusHeader } from "../components/StatusHeader";
import { WindCompass } from "../components/WindCompass";
import { useI18n } from "../i18n";
import { formatClock, formatKm } from "../lib/format";
import { speak, stop, ttsSupported } from "../lib/tts";

/**
 * Home: full-bleed status, ONE giant primary action, then triaged cards.
 * Everything numeric on this screen came from the API (the truth rule).
 */
export function HomeScreen({
  situation,
  onOpenMap,
  onOpenRoute,
}: {
  situation: Situation;
  onOpenMap: () => void;
  onOpenRoute: () => void;
}) {
  const { t, lang, pick, speechLang } = useI18n();
  const [history, setHistory] = useState<HistoryPoint[] | null>(null);
  const [readingAll, setReadingAll] = useState(false);

  useEffect(() => {
    let alive = true;
    getHistory()
      .then((h) => {
        if (alive) setHistory(h);
      })
      .catch(() => {
        if (alive) setHistory(null); // chart simply not shown — no fabrication
      });
    return () => {
      alive = false;
    };
  }, [situation.generated_utc]);

  const { danger, fire, weather } = situation;
  const level = danger.level;

  // ONE giant primary button; label depends on the danger level (spec §1.3).
  const primaryLabel = level === "GO" ? t("home_btn_go") : t("home_btn_safe");
  const primarySub =
    level === "GO"
      ? lang === "ko"
        ? "See evacuation route"
        : "대피 경로 보기"
      : lang === "ko"
        ? "View map"
        : "지도 보기";
  const primaryAction = level === "GO" ? onOpenRoute : onOpenMap;

  // Whole-screen read-aloud: status + reason + every card, in UI language.
  const readAllText = [
    pick(danger, "label"),
    pick(danger, "reason"),
    ...situation.cards.map(
      (c) => `${pick(c, "title")}. ${pick(c, "body")}`,
    ),
  ].join(". ");

  const toggleReadAll = () => {
    if (readingAll) {
      stop();
      setReadingAll(false);
      return;
    }
    if (speak(readAllText, speechLang, () => setReadingAll(false))) {
      setReadingAll(true);
    }
  };

  return (
    <div>
      <StatusHeader situation={situation} />
      <div className="screen-pad">
        {ttsSupported() && (
          <button
            type="button"
            className="btn-big-secondary"
            style={{ width: "100%", marginTop: 16 }}
            onClick={toggleReadAll}
            aria-pressed={readingAll}
          >
            {readingAll ? <IconStop size={28} /> : <IconSpeaker size={28} />}
            {readingAll ? t("read_aloud_stop") : t("read_screen")}
          </button>
        )}

        <div style={{ marginTop: 16 }}>
          <BigButton level={level} onClick={primaryAction} sub={primarySub}>
            {primaryLabel}
          </BigButton>
        </div>

        {/* fire facts — only fields the API filled in */}
        {fire.active && (
          <section className="card" aria-label={t("fire_distance")}>
            <div className="row wrap" style={{ gap: 24 }}>
              {fire.distance_km !== null && (
                <div>
                  <div
                    style={{
                      fontSize: "var(--fs-small)",
                      color: "var(--ink-secondary)",
                      fontWeight: 700,
                    }}
                  >
                    {t("fire_distance")}
                  </div>
                  <div className="viz-value">
                    {formatKm(fire.distance_km)}
                    <span className="viz-unit"> {t("unit_km")}</span>
                  </div>
                </div>
              )}
              {fire.bearing_text_ko !== null && fire.bearing_text_en !== null && (
                <div>
                  <div
                    style={{
                      fontSize: "var(--fs-small)",
                      color: "var(--ink-secondary)",
                      fontWeight: 700,
                    }}
                  >
                    {t("fire_direction")}
                  </div>
                  <div className="viz-value" style={{ fontSize: "var(--fs-title)" }}>
                    {lang === "ko" ? fire.bearing_text_ko : fire.bearing_text_en}
                  </div>
                </div>
              )}
              <div>
                <div
                  style={{
                    fontSize: "var(--fs-small)",
                    color: "var(--ink-secondary)",
                    fontWeight: 700,
                  }}
                >
                  {t("fire_detections")}
                </div>
                <div className="viz-value">{fire.detections}</div>
              </div>
            </div>
          </section>
        )}

        {/* spread ETA — rendered only when the API sent eta_minutes */}
        <SpreadTimeline situation={situation} />
        {fire.active && !situation.prediction_available && (
          <p className="notice">{t("prediction_unavailable")}</p>
        )}

        {/* triaged guidance cards, server order */}
        {situation.cards.map((card) => (
          <GuidanceCard
            key={card.id}
            card={card}
            onOpenMap={onOpenMap}
            onOpenRoute={onOpenRoute}
          />
        ))}

        <WindCompass weather={weather} />
        {history && history.length >= 2 && (
          <DetectionTimeline history={history} />
        )}

        <p
          style={{
            fontSize: "var(--fs-small)",
            color: "var(--ink-muted)",
            textAlign: "center",
          }}
        >
          {t("updated_label")}: {formatClock(situation.generated_utc, lang)}
        </p>
        <p className="disclaimer" style={{ textAlign: "center" }}>
          {pick(situation, "disclaimer")}
        </p>
      </div>
    </div>
  );
}
