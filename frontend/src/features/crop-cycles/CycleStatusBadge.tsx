import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { CycleStatus } from "@/services/api/types";
import { STATUS_LABEL } from "@/utils/format";

const TONE: Record<CycleStatus, NonNullable<BadgeProps["tone"]>> = {
  planned: "info",
  active: "success",
  harvested: "neutral",
  abandoned: "warning",
};

export function CycleStatusBadge({ status }: { status: CycleStatus }) {
  return <Badge tone={TONE[status]}>{STATUS_LABEL[status]}</Badge>;
}
