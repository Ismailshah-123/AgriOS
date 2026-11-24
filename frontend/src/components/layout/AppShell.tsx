import { LayoutDashboard, Layers, Menu, Sprout, Stethoscope, X } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router";
import { Button } from "@/components/ui/button";
import { useDocumentLanguage, useT } from "@/i18n/useT";
import { cn } from "@/utils/cn";
import { BrandMark } from "./BrandMark";
import { LanguageToggle } from "./LanguageToggle";
import { SidebarNav } from "./SidebarNav";
import { UserMenu } from "./UserMenu";

/** DESIGN.md section 3: five-item bottom bar on phones; "More" opens the full menu. */
const BOTTOM_TABS = [
  { to: "/", key: "bar.home", label: "Home", icon: LayoutDashboard },
  { to: "/fields", key: "bar.fields", label: "Fields", icon: Layers },
  { to: "/crop-doctor", key: "bar.doctor", label: "Doctor", icon: Stethoscope },
  { to: "/crop-cycles", key: "bar.cycles", label: "Cycles", icon: Sprout },
] as const;

/**
 * Desktop (lg+): fixed grouped sidebar + top bar with the account menu.
 * Tablet/phone: top bar, bottom tab bar, and a drawer with the full navigation.
 */
export function AppShell() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const close = () => setDrawerOpen(false);
  const t = useT();
  useDocumentLanguage();

  return (
    <div className="min-h-dvh bg-surface">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:start-3 focus:z-50 focus:rounded-md focus:bg-card focus:px-4 focus:py-2"
      >
        Skip to content
      </a>

      <aside className="fixed inset-y-0 start-0 hidden w-72 flex-col overflow-y-auto border-e border-border bg-card px-3 py-5 lg:flex">
        <div className="px-3 pb-7">
          <BrandMark />
        </div>
        <SidebarNav />
      </aside>

      <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-3 border-b border-border bg-card/95 px-4 backdrop-blur sm:px-6 lg:ms-72 lg:px-10">
        <div className="flex items-center gap-2 lg:hidden">
          <Button
            variant="ghost"
            size="icon"
            aria-label={drawerOpen ? t("menu.close", "Close menu") : t("menu.open", "Open menu")}
            aria-expanded={drawerOpen}
            aria-controls={drawerOpen ? "mobile-drawer" : undefined}
            onClick={() => setDrawerOpen((o) => !o)}
          >
            {drawerOpen ? <X aria-hidden /> : <Menu aria-hidden />}
          </Button>
          <BrandMark />
        </div>
        <div className="ms-auto flex items-center gap-1">
          <LanguageToggle />
          <UserMenu />
        </div>
      </header>

      {drawerOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div aria-hidden className="absolute inset-0 animate-fade-in bg-ink/30" onClick={close} />
          <div
            id="mobile-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Navigation"
            className="absolute inset-y-0 start-0 w-72 max-w-[85vw] overflow-y-auto bg-card px-3 py-5 shadow-[var(--shadow-overlay)]"
            onKeyDown={(e) => e.key === "Escape" && close()}
          >
            <div className="flex items-center justify-between px-3 pb-6">
              <BrandMark />
              <Button variant="ghost" size="icon" aria-label={t("menu.close", "Close menu")} onClick={close} autoFocus>
                <X aria-hidden />
              </Button>
            </div>
            <SidebarNav onNavigate={close} />
          </div>
        </div>
      )}

      <main id="main" className="pb-24 lg:ms-72 lg:pb-0">
        <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-10 lg:py-10">
          <Outlet />
        </div>
      </main>

      <nav
        aria-label="Quick"
        className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-border bg-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden"
      >
        {BOTTOM_TABS.map(({ to, key, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              cn(
                "flex h-16 flex-col items-center justify-center gap-1 text-xs font-medium",
                isActive ? "text-primary-dark" : "text-muted",
              )
            }
          >
            <Icon aria-hidden className="size-5" />
            {t(key, label)}
          </NavLink>
        ))}
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          className="flex h-16 flex-col items-center justify-center gap-1 text-xs font-medium text-muted"
          aria-expanded={drawerOpen}
        >
          <Menu aria-hidden className="size-5" />
          {t("bar.more", "More")}
        </button>
      </nav>
    </div>
  );
}
