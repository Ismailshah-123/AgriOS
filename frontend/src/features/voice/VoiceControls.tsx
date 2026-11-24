import { Mic, MicOff, RotateCcw, Square, Volume2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useT } from "@/i18n/useT";
import { useSpeak, useSpeechInput } from "./speech";

/** Microphone for a text box. The recognised text is added to the box for the farmer to check. */
export function MicButton({ onText }: { onText: (text: string) => void }) {
  const t = useT();
  const mic = useSpeechInput(onText);
  if (!mic.supported) {
    return <p className="text-xs text-muted">{t("voice.unsupported", "Voice input is not available in this browser; please type.")}</p>;
  }
  return (
    <div className="flex flex-col gap-1">
      <Button type="button" variant={mic.listening ? "danger" : "secondary"} size="sm" aria-pressed={mic.listening}
        onClick={mic.listening ? mic.stop : mic.start}>
        {mic.listening ? <MicOff aria-hidden /> : <Mic aria-hidden />}
        {mic.listening ? t("voice.listening", "Listening… tap to stop") : t("voice.speak", "Speak")}
      </Button>
      {mic.listening && <span role="status" className="text-xs text-danger">{t("voice.recording", "Recording")}</span>}
      {mic.error && <span role="alert" className="text-xs text-danger">{mic.error}</span>}
      <span className="text-[11px] text-muted">{t("voice.privacy", "Speech is converted to text by your browser's provider (Google or Microsoft).")}</span>
    </div>
  );
}

/** Play / stop / repeat a text aloud with an installed voice for the user's language. */
export function SpeakButton({ text, label = "Listen", lang }: { text: string; label?: string; lang?: string }) {
  const t = useT();
  const tts = useSpeak(lang);
  const [played, setPlayed] = useState(false);
  if (!tts.supported || !text) return null;
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      {tts.speaking ? (
        <Button type="button" variant="ghost" size="sm" onClick={tts.stop}><Square aria-hidden />{t("voice.stop", "Stop")}</Button>
      ) : (
        <Button type="button" variant="ghost" size="sm" onClick={() => { tts.speak(text); setPlayed(true); }}>
          {played ? <RotateCcw aria-hidden /> : <Volume2 aria-hidden />}
          {played ? t("voice.repeat", "Repeat") : t("voice.listen", label)}
        </Button>
      )}
      {tts.error && <span role="alert" className="text-xs text-danger">{tts.error}</span>}
    </span>
  );
}
