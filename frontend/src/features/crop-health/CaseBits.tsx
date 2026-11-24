import { ImageOff } from "lucide-react";
import { Link } from "react-router";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { CaseListItem, CaseStatus, InferenceStatus } from "@/services/api/cropHealth";
import { formatDate } from "@/utils/format";
import { CASE_STATUS_LABEL, INFERENCE_LABEL } from "./labels";
import { useL } from "@/i18n/useT";

type Tone = NonNullable<BadgeProps["tone"]>;

const INFERENCE_TONE: Record<InferenceStatus, Tone> = {
  not_started: "neutral",
  queued: "info",
  running: "info",
  completed: "success",
  failed: "danger",
  model_unavailable: "warning",
};

const STATUS_TONE: Record<CaseStatus, Tone> = {
  submitted: "neutral",
  retake: "warning",
  unsure: "warning",
  accepted: "success",
  out_of_scope: "warning",
  expert_review: "info",
  closed: "neutral",
};

export function InferenceBadge({ status }: { status: InferenceStatus }) {
  const l = useL();
  return <Badge tone={INFERENCE_TONE[status]}>{l(INFERENCE_LABEL[status])}</Badge>;
}

export function CaseStatusBadge({ status }: { status: CaseStatus }) {
  const l = useL();
  return <Badge tone={STATUS_TONE[status]}>{l(CASE_STATUS_LABEL[status])}</Badge>;
}

export function CaseCard({ c }: { c: CaseListItem }) {
  return (
    <li>
      <Link to={`/crop-doctor/cases/${c.id}`}
        className="flex h-full gap-4 rounded-[var(--radius-card)] border border-border bg-card p-3 shadow-[var(--shadow-card)] transition-colors hover:border-primary/40">
        {c.thumb_url ? (
          <img src={c.thumb_url} alt="" className="size-20 shrink-0 rounded-[var(--radius-input)] object-cover" />
        ) : (
          <span className="grid size-20 shrink-0 place-items-center rounded-[var(--radius-input)] bg-surface text-muted">
            <ImageOff aria-hidden className="size-6" />
          </span>
        )}
        <span className="flex min-w-0 flex-1 flex-col gap-1.5 py-0.5">
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="tabular font-semibold text-ink">{c.reference}</span>
            <InferenceBadge status={c.inference_status} />
          </span>
          <span className="truncate text-sm text-ink-soft">
            {c.crop.name} · {c.field.name} · {c.farm.name}
          </span>
          <span className="text-sm text-muted">
            {formatDate(c.created_at.slice(0, 10))} · {c.image_count} photo{c.image_count === 1 ? "" : "s"}
            {c.submission_count > 1 && ` · ${c.submission_count - 1} follow-up${c.submission_count > 2 ? "s" : ""}`}
          </span>
        </span>
      </Link>
    </li>
  );
}
