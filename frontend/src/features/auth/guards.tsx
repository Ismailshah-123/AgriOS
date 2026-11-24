import { Navigate, Outlet, useLocation } from "react-router";
import { BrandMark } from "@/components/layout/BrandMark";
import { useAuth } from "./auth-context";

function SessionCheck() {
  return (
    <div role="status" aria-label="Checking your session" className="grid min-h-dvh place-items-center">
      <div className="flex animate-pulse flex-col items-center gap-3">
        <BrandMark />
        <p className="text-sm text-muted">Checking your session…</p>
      </div>
    </div>
  );
}

/** Signed-in area. Unauthenticated visitors go to /login and come back afterwards. */
export function RequireAuth() {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "loading") return <SessionCheck />;
  if (status === "anonymous") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}

/**
 * Sign-in and registration pages. Once signed in, go to the page the visitor originally
 * asked for (set by RequireAuth), otherwise the Overview.
 */
export function PublicOnly() {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "loading") return <SessionCheck />;
  if (status === "authenticated") {
    const from = (location.state as { from?: string } | null)?.from;
    const safe = from?.startsWith("/") && !from.startsWith("//") ? from : "/";
    return <Navigate to={safe} replace />;
  }
  return <Outlet />;
}
