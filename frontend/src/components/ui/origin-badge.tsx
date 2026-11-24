import type { DataOrigin } from "@/services/api/types";
import { cn } from "@/utils/cn";
import { ORIGIN_LABEL } from "@/utils/format";

const TONE: Record<DataOrigin, string> = {
  measured: "bg-primary-soft text-primary-dark",
  farmer_entered: "bg-info-soft text-info",
  retrieved: "bg-[#f1ecfa] text-[#5b3c99]",
  inferred: "bg-warning-soft text-warning",
  simulated: "border border-dashed border-muted bg-surface text-muted uppercase",
};

/** Where a value came from (CLAUDE.md hard rule 3). Text, not colour, carries meaning. */
export function OriginBadge({ origin }: { origin: DataOrigin }) {
  return (
    <span
      className={cn("inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium", TONE[origin])}
      title={`Data origin: ${ORIGIN_LABEL[origin]}`}
    >
      {ORIGIN_LABEL[origin]}
    </span>
  );
}
