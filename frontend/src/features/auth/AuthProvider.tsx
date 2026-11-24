import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { refreshAccessToken, tokenStore } from "@/services/api/client";
import { authApi } from "@/services/api/platform";
import type { TokenResponse, User } from "@/services/api/types";
import { AuthContext, type AuthContextValue, type AuthStatus } from "./auth-context";

/**
 * Session lifecycle. On start it tries a silent refresh (httpOnly cookie) to restore the
 * session; the access token stays in memory only.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<User | null>(null);

  const endSession = useCallback(() => {
    tokenStore.set(null);
    setUser(null);
    setStatus("anonymous");
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    tokenStore.onSessionLost(endSession);
    let cancelled = false;
    void (async () => {
      const token = await refreshAccessToken();
      if (cancelled) return;
      if (!token) {
        setStatus("anonymous");
        return;
      }
      try {
        const me = await authApi.me();
        if (!cancelled) {
          setUser(me);
          setStatus("authenticated");
        }
      } catch {
        if (!cancelled) endSession();
      }
    })();
    return () => {
      cancelled = true;
      tokenStore.onSessionLost(null);
    };
  }, [endSession]);

  const accept = useCallback((res: TokenResponse) => {
    tokenStore.set(res.access_token);
    setUser(res.user);
    setStatus("authenticated");
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      login: async (email, password) => accept(await authApi.login({ email, password })),
      register: async (full_name, email, password) =>
        accept(await authApi.register({ full_name, email, password })),
      logout: async () => {
        await authApi.logout().catch(() => undefined);
        endSession();
      },
      setUser,
    }),
    [status, user, accept, endSession],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}
