import { useEffect, useState } from "react";
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

  useEffect(() => {
    // If the surrounding screen unmounts mid-speech, stop talking.
    return () => {
      if (speaking) stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!ttsSupported()) return null;

  const onClick = () => {
    if (speaking) {
      stop();
      setSpeaking(false);
      return;
    }
    const ok = speak(text, speechLang, () => setSpeaking(false));
    if (ok) setSpeaking(true);
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
