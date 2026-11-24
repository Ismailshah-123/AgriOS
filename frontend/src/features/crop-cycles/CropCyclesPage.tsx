import { Layers, Pencil, Plus, Sprout, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState, LoadingRows } from "@/components/ui/feedback";
import { useCycles, useDeleteCycle, useFields } from "@/features/platform/queries";
import type { CropCycle, CycleStatus } from "@/services/api/types";
import { cn } from "@/utils/cn";
import { errorMessage, formatDate, SEASON_LABEL, STATUS_LABEL } from "@/utils/format";
import { CycleFormDialog } from "./CycleFormDialog";
import { CycleStatusBadge } from "./CycleStatusBadge";

const FILTERS: (CycleStatus | "all")[] = ["all", "active", "planned", "harvested", "abandoned"];

function CycleRow({ cycle }: { cycle: CropCycle }) {
  const remove = useDeleteCycle();
  const title = `${cycle.crop.name_en}${cycle.variety ? ` (${cycle.variety})` : ""}`;
  return (
    <li className="grid gap-3 px-5 py-4 md:grid-cols-[minmax(0,1.5fr)_minmax(0,1.6fr)_auto] md:items-center md:gap-6">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="truncate font-medium text-ink">{title}</p>
          <CycleStatusBadge status={cycle.status} />
        </div>
        <p className="truncate text-sm text-muted">
          {cycle.field_name} · {cycle.farm_name}
          {cycle.season && ` · ${SEASON_LABEL[cycle.season]}`}
        </p>
      </div>
      <dl className="grid grid-cols-3 gap-3 text-sm">
        <div>
          <dt className="text-muted">Sown</dt>
          <dd className="tabular text-ink">{formatDate(cycle.sowing_date)}</dd>
        </div>
        <div>
          <dt className="text-muted">Expected harvest</dt>
          <dd className="tabular text-ink">{formatDate(cycle.expected_harvest_date)}</dd>
        </div>
        <div>
          <dt className="text-muted">Harvested</dt>
          <dd className="tabular text-ink">{formatDate(cycle.harvest_date)}</dd>
        </div>
      </dl>
      <div className="flex gap-1 md:justify-end">
        <CycleFormDialog
          cycle={cycle}
          trigger={
            <Button variant="ghost" size="sm" aria-label={`Edit ${title} on ${cycle.field_name}`}>
              <Pencil aria-hidden />
              <span className="md:sr-only">Edit</span>
            </Button>
          }
        />
        <ConfirmDialog
          title={`Delete this ${cycle.crop.name_en} cycle?`}
          description={`The crop cycle on ${cycle.field_name} will be removed. This cannot be undone.`}
          confirmLabel="Delete cycle"
          onConfirm={() => remove.mutateAsync(cycle.id)}
          trigger={
            <Button variant="ghost" size="sm" aria-label={`Delete ${title} on ${cycle.field_name}`}>
              <Trash2 aria-hidden />
              <span className="md:sr-only">Delete</span>
            </Button>
          }
        />
      </div>
    </li>
  );
}

export function CropCyclesPage() {
  const [status, setStatus] = useState<CycleStatus | "all">("all");
  const fields = useFields();
  const cycles = useCycles(status === "all" ? {} : { status });
  const hasFields = (fields.data?.items.length ?? 0) > 0;

  const addButton = (
    <CycleFormDialog
      trigger={
        <Button disabled={!hasFields}>
          <Plus aria-hidden />
          Start crop cycle
        </Button>
      }
    />
  );

  if (fields.isSuccess && !hasFields) {
    return (
      <>
        <PageHeader title="Crop Cycles" description="Each crop grown on a field, from planning to harvest." />
        <Card>
          <EmptyState
            icon={Layers}
            title="Add a field first"
            description="A crop cycle is recorded on a field. Add a farm and its fields to begin."
            action={
              <Button asChild>
                <Link to="/fields">Go to Fields</Link>
              </Button>
            }
          />
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Crop Cycles"
        description="Each crop grown on a field, from planning to harvest. Future crop health checks, irrigation plans and costs attach to a cycle."
        actions={addButton}
      />
      <Card>
        <div role="group" aria-label="Filter by status" className="flex gap-1 overflow-x-auto border-b border-border px-3 py-2.5">
          {FILTERS.map((f) => (
            <button
              key={f}
              type="button"
              aria-pressed={status === f}
              onClick={() => setStatus(f)}
              className={cn(
                "h-9 shrink-0 rounded-full px-3.5 text-sm font-medium transition-colors",
                status === f ? "bg-primary-soft text-primary-dark" : "text-muted hover:bg-surface hover:text-ink",
              )}
            >
              {f === "all" ? "All" : STATUS_LABEL[f]}
            </button>
          ))}
        </div>
        {cycles.isPending ? (
          <LoadingRows label="Loading crop cycles" />
        ) : cycles.isError ? (
          <ErrorState message={errorMessage(cycles.error)} onRetry={() => void cycles.refetch()} />
        ) : cycles.data.items.length === 0 ? (
          <EmptyState
            icon={Sprout}
            title={status === "all" ? "No crop cycles yet" : `No ${STATUS_LABEL[status].toLowerCase()} cycles`}
            description="Record what is planned or growing on each field, with its sowing and harvest dates."
            action={status === "all" ? addButton : undefined}
          />
        ) : (
          <ul className="divide-y divide-border" aria-label="Crop cycles">
            {cycles.data.items.map((c) => (
              <CycleRow key={c.id} cycle={c} />
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
