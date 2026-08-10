import { useEffect, useRef, useState } from "react";
import { useI18n } from "../i18n";
import { speak, stop, ttsSupported } from "../lib/tts";
import { IconSpeaker, IconStop } from "./Icons";

/**
 * The 🔊 read-aloud button every card carries (spec §7).
 * Speaks the given text in the current UI language; press again to stop.
 */
export function ReadAloud({ text }: { text: string }) {
  const { t, speechLang } = useI18n();
  const [speaking, setSpeaking] = useState(false);
  const speakingRef = useRef(false);

  useEffect(() => {
    // If the surrounding screen unmounts while THIS button's speech is
    // playing, stop it (ref, not state — the cleanup closure is stale).
    return () => {
      if (speakingRef.current) stop();
    };
  }, []);

  if (!ttsSupported()) return null;

  const onClick = () => {
    if (speakingRef.current) {
      stop();
      speakingRef.current = false;
      setSpeaking(false);
      return;
    }
    const ok = speak(text, speechLang, () => {
      speakingRef.current = false;
      setSpeaking(false);
    });
    if (ok) {
      speakingRef.current = true;
      setSpeaking(true);
    }
  };

  return (
    <button
      type="button"
      className={`read-aloud${speaking ? " speaking" : ""}`}
      onClick={onClick}
      aria-label={speaking ? t("read_aloud_stop") : t("read_aloud")}
      aria-pressed={speaking}
    >
      {speaking ? <IconStop size={30} /> : <IconSpeaker size={30} />}
    </button>
  );
}
