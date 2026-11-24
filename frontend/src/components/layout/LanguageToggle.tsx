import { Languages } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/auth-context";
import { authApi } from "@/services/api/platform";

/** One tap between English and Urdu. Saved to the profile, so it follows the user. */
export function LanguageToggle() {
  const { user, setUser } = useAuth();
  const [busy, setBusy] = useState(false);
  if (!user) return null;
  const next = user.locale === "ur" ? "en" : "ur";
  return (
    <Button variant="ghost" size="sm" disabled={busy} lang={next}
      aria-label={next === "ur" ? "اردو میں دیکھیں (Switch to Urdu)" : "Switch to English (انگریزی میں دیکھیں)"}
      onClick={async () => {
        setBusy(true);
        try {
          setUser(await authApi.updateProfile({ locale: next }));
        } finally {
          setBusy(false);
        }
      }}>
      <Languages aria-hidden />
      {next === "ur" ? "اردو" : "English"}
    </Button>
  );
}
