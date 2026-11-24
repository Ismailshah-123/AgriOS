import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: ReactNode;
  /** Heading level that fits the surrounding outline (h2 under a page title). */
  as?: "h2" | "h3";
}

export function EmptyState({ icon: Icon, title, description, action, as: Heading = "h2" }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
      <span className="grid size-12 place-items-center rounded-full bg-primary-soft text-primary-dark">
        <Icon aria-hidden className="size-6" />
      </span>
      <Heading className="text-base font-semibold text-ink">{title}</Heading>
      <p className="max-w-sm text-sm text-muted">{description}</p>
      {action}
    </div>
  );
}
