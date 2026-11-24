import { ArrowUpRight, Layers, Map, Sprout, Stethoscope } from "lucide-react";
import { Link } from "react-router";

const ACTIONS = [
  { to: "/farms", label: "Manage farms", text: "Add or edit a farm", icon: Map },
  { to: "/fields", label: "Manage fields", text: "Areas in acres or hectares", icon: Layers },
  { to: "/crop-cycles", label: "Record a crop", text: "Plan or start a crop cycle", icon: Sprout },
  { to: "/crop-doctor", label: "Crop Doctor", text: "See what is coming next", icon: Stethoscope },
];

/** Only links to pages that work today. */
export function QuickActions() {
  return (
    <section aria-labelledby="quick-actions">
      <h2 id="quick-actions" className="mb-3 text-sm font-semibold text-ink">
        Quick actions
      </h2>
      <ul className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
        {ACTIONS.map(({ to, label, text, icon: Icon }) => (
          <li key={to}>
            <Link
              to={to}
              className="group flex h-full items-center gap-3 rounded-[var(--radius-card)] border border-border bg-card p-4 shadow-[var(--shadow-card)] transition-colors hover:border-primary/40"
            >
              <span className="grid size-10 shrink-0 place-items-center rounded-[10px] bg-primary-soft text-primary-dark">
                <Icon aria-hidden className="size-5" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-medium text-ink">{label}</span>
                <span className="block truncate text-sm text-muted">{text}</span>
              </span>
              <ArrowUpRight
                aria-hidden
                className="size-4 shrink-0 text-muted transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
              />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
