import { Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { OriginBadge } from "@/components/ui/origin-badge";
import { useDeleteField } from "@/features/platform/queries";
import type { FieldRecord } from "@/services/api/types";
import { formatArea } from "@/utils/format";
import { FieldFormDialog } from "./FieldFormDialog";

interface FieldsListProps {
  fields: FieldRecord[];
  showFarm?: boolean;
}

/** One markup for all widths: a grid row on desktop, stacked on phones. */
export function FieldsList({ fields, showFarm = false }: FieldsListProps) {
  const remove = useDeleteField();
  return (
    <ul className="divide-y divide-border" aria-label="Fields">
      {fields.map((f) => (
        <li
          key={f.id}
          className="grid gap-2 px-5 py-4 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1.2fr)_auto_auto] md:items-center md:gap-6"
        >
          <div className="min-w-0">
            <p className="truncate font-medium text-ink">{f.name}</p>
            {showFarm && <p className="truncate text-sm text-muted">{f.farm_name}</p>}
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm text-ink-soft">
            <span className="tabular">{formatArea(f.area)}</span>
            <OriginBadge origin={f.area.data_origin} />
          </div>
          <p className="text-sm text-muted">
            {f.active_cycle_count === 0
              ? "No crop growing"
              : `${f.active_cycle_count} crop${f.active_cycle_count > 1 ? "s" : ""} growing`}
          </p>
          <div className="flex gap-1 md:justify-end">
            <FieldFormDialog
              field={f}
              trigger={
                <Button variant="ghost" size="sm" aria-label={`Edit ${f.name}`}>
                  <Pencil aria-hidden />
                  <span className="md:sr-only">Edit</span>
                </Button>
              }
            />
            <ConfirmDialog
              title={`Delete ${f.name}?`}
              description="This removes the field. Fields with crop cycles cannot be deleted."
              confirmLabel="Delete field"
              onConfirm={() => remove.mutateAsync(f.id)}
              trigger={
                <Button variant="ghost" size="sm" aria-label={`Delete ${f.name}`}>
                  <Trash2 aria-hidden />
                  <span className="md:sr-only">Delete</span>
                </Button>
              }
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
