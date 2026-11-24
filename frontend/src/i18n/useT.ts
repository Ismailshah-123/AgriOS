import { useEffect } from "react";
import { useAuth } from "@/features/auth/auth-context";
import { UR } from "./messages";
import { UR_BY_EN } from "./urByEn";

/** t(key, english): Urdu when the user's locale is "ur" and a string exists, else English. */
export function useT(): (key: string, english: string) => string {
  const locale = useAuth().user?.locale ?? "en";
  return (key, english) => (locale === "ur" ? (UR[key] ?? english) : english);
}

/** Keeps <html lang dir> in step with the user's language (RTL for Urdu). */
export function useDocumentLanguage(): void {
  const locale = useAuth().user?.locale ?? "en";
  useEffect(() => {
    const el = document.documentElement;
    el.lang = locale;
    el.dir = locale === "ur" ? "rtl" : "ltr";
  }, [locale]);
}

/** "en" | "ur" from the signed-in user's profile. */
export function useLocale(): "en" | "ur" {
  return useAuth().user?.locale === "ur" ? "ur" : "en";
}

/** Inline bilingual strings: tr("Upload", "اپ لوڈ"). Urdu PENDING native review (see messages.ts). */
export function useTr(): (en: string, ur: string) => string {
  const locale = useLocale();
  return (en, ur) => (locale === "ur" ? ur : en);
}

/** l("Choose a farm"): Urdu from i18n/urByEn.ts when the user's locale is Urdu, else English. */
export function useL(): (english: string) => string {
  const locale = useLocale();
  return (english) => (locale === "ur" ? (UR_BY_EN[english] ?? english) : english);
}
