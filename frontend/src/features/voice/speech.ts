/**
 * Urdu/English voice via the browser Web Speech API (docs/03-architecture/URDU_VOICE_PLAN.md,
 * option A). Recognition runs in the browser vendor's cloud (Google for Chrome, Microsoft for
 * Edge) and needs a connection; synthesis uses voices installed on the device. Nothing is
 * faked: when the API or an Urdu voice is missing, callers get `supported: false` / a reason.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/features/auth/auth-context";

type Rec = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start: () => void;
  stop: () => void;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
};
type RecCtor = new () => Rec;

function recognitionCtor(): RecCtor | null {
  const w = window as unknown as { SpeechRecognition?: RecCtor; webkitSpeechRecognition?: RecCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/** BCP-47 tag from the profile locale. */
export function useSpeechLang(): string {
  return useAuth().user?.locale === "ur" ? "ur-PK" : "en-US";
}

const ERRORS: Record<string, { en: string; ur: string }> = {
  "not-allowed": { en: "Microphone permission was denied. Allow it in the browser, or type instead.", ur: "مائیکروفون کی اجازت نہیں ملی۔ براؤزر میں اجازت دیں یا لکھ کر بھیجیں۔" },
  "service-not-allowed": { en: "Voice input is blocked in this browser. Please type instead.", ur: "اس براؤزر میں آواز بند ہے۔ لکھ کر بھیجیں۔" },
  network: { en: "Voice input needs an internet connection. Please type instead.", ur: "آواز کے لیے انٹرنیٹ چاہیے۔ لکھ کر بھیجیں۔" },
  "no-speech": { en: "No speech was heard. Tap the microphone and speak again.", ur: "آواز سنائی نہیں دی۔ مائیکروفون دبا کر دوبارہ بولیں۔" },
  "audio-capture": { en: "No microphone was found on this device.", ur: "اس ڈیوائس پر مائیکروفون نہیں ملا۔" },
};

export function useSpeechInput(onText: (text: string) => void) {
  const lang = useSpeechLang();
  const ctor = typeof window === "undefined" ? null : recognitionCtor();
  const rec = useRef<Rec | null>(null);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const stop = useCallback(() => rec.current?.stop(), []);
  const start = useCallback(() => {
    if (!ctor) return;
    setError(null);
    const r = new ctor();
    r.lang = lang;
    r.interimResults = false;
    r.continuous = false;
    r.onresult = (e) => {
      const text = Array.from(e.results).filter((x) => x.isFinal).map((x) => x[0]?.transcript ?? "").join(" ").trim();
      if (text) onText(text);
    };
    r.onerror = (e) => {
      const m = ERRORS[e.error];
      setError(m ? (lang.startsWith("ur") ? m.ur : m.en) : `Voice input stopped (${e.error}). Please type instead.`);
    };
    r.onend = () => setListening(false);
    rec.current = r;
    setListening(true);
    r.start();
  }, [ctor, lang, onText]);

  useEffect(() => () => rec.current?.stop(), []);
  return { supported: ctor !== null, listening, error, start, stop, lang };
}

function voiceFor(lang: string): SpeechSynthesisVoice | null {
  const prefix = lang.split("-")[0]!;
  const voices = window.speechSynthesis?.getVoices() ?? [];
  return voices.find((v) => v.lang === lang) ?? voices.find((v) => v.lang.startsWith(prefix)) ?? null;
}

/** `langOverride` ("en" | "ur") speaks text in its own language, e.g. an Urdu answer. */
export function useSpeak(langOverride?: string) {
  const profileLang = useSpeechLang();
  const lang = langOverride === "ur" ? "ur-PK" : langOverride === "en" ? "en-US" : profileLang;
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;
  const [speaking, setSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const stop = useCallback(() => {
    if (supported) window.speechSynthesis?.cancel();
    setSpeaking(false);
  }, [supported]);

  const speak = useCallback((text: string) => {
    if (!supported) return;
    const voice = voiceFor(lang);
    if (!voice) {
      // Never read Urdu text with an English voice: it would be unintelligible.
      setError(lang.startsWith("ur") ? "اس ڈیوائس پر اردو آواز موجود نہیں۔ متن پڑھیں۔" : "No voice for this language is installed on this device.");
      return;
    }
    setError(null);
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.voice = voice;
    u.lang = voice.lang;
    u.onend = () => setSpeaking(false);
    u.onerror = () => setSpeaking(false);
    setSpeaking(true);
    window.speechSynthesis.speak(u);
  }, [lang, supported]);

  useEffect(() => () => { if (supported) window.speechSynthesis?.cancel(); }, [supported]);
  return { supported, speaking, error, speak, stop };
}
