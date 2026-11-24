import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Card } from "./card";

interface StatTileProps {
  icon: LucideIcon;
  label: string;
  value: ReactNode;
  detail?: ReactNode;
}

/** One real metric. Callers pass values from the API only, never placeholders. */
export function StatTile({ icon: Icon, label, value, detail }: StatTileProps) {
  return (
    <Card className="flex flex-col gap-3 p-4 sm:p-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-medium text-muted">{label}</p>
        <span className="grid size-9 place-items-center rounded-[10px] bg-primary-soft text-primary-dark">
          <Icon aria-hidden className="size-[18px]" />
        </span>
      </div>
      <p className="tabular text-2xl font-semibold tracking-tight text-ink">{value}</p>
      {detail && <div className="text-sm text-muted">{detail}</div>}
    </Card>
  );
}
