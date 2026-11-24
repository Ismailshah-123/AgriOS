import { NavLink } from "react-router";
import { MODULES, NAV_GROUPS, STATUS_LABEL, type ModuleDef } from "@/app/modules";
import { useAuth } from "@/features/auth/auth-context";
import { useT } from "@/i18n/useT";
import { cn } from "@/utils/cn";

interface SidebarNavProps {
  onNavigate?: () => void;
}

function NavItem({ module, onNavigate }: { module: ModuleDef; onNavigate?: () => void }) {
  const { key, path, label, icon: Icon, status } = module;
  const t = useT();
  return (
    <NavLink
      to={path}
      end={path === "/"}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "group flex h-10 items-center gap-3 rounded-[var(--radius-input)] px-3 text-sm font-medium transition-colors",
          isActive
            ? "bg-primary-soft text-primary-dark"
            : "text-ink-soft hover:bg-surface hover:text-ink",
        )
      }
    >
      <Icon aria-hidden className="size-[18px] shrink-0" />
      <span className="truncate">{t(`nav.${key}`, label)}</span>
      {status !== "available" && (
        <span
          className={cn(
            "ms-auto rounded-full px-2 py-0.5 text-[11px] font-medium",
            status === "preview" ? "bg-accent-soft text-warning" : "bg-surface text-muted",
          )}
        >
          {t(`status.${status}`, STATUS_LABEL[status])}
        </span>
      )}
    </NavLink>
  );
}

/** Grouped module navigation. Status pills keep planned modules honest. */
export function SidebarNav({ onNavigate }: SidebarNavProps) {
  const role = useAuth().user?.role;
  const t = useT();
  const visible = (m: ModuleDef) => !m.roles || (role !== undefined && m.roles.includes(role));
  return (
    <nav aria-label="Main" className="flex flex-col gap-5">
      {NAV_GROUPS.map((group) => (
        <div key={group} className="flex flex-col gap-0.5">
          {group !== "Overview" && (
            <p className="px-3 pb-1.5 text-[11px] font-semibold tracking-wider text-muted uppercase">
              {t(`group.${group}`, group)}
            </p>
          )}
          {MODULES.filter((m) => m.group === group && visible(m)).map((m) => (
            <NavItem key={m.key} module={m} onNavigate={onNavigate} />
          ))}
        </div>
      ))}
    </nav>
  );
}
