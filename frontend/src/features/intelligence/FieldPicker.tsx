import { Map } from "lucide-react";
import { Link } from "react-router";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState, LoadingRows } from "@/components/ui/feedback";
import { Select } from "@/components/ui/input";
import type { FieldRecord } from "@/services/api/types";
import { errorMessage } from "@/utils/format";
import type { useSelectedField } from "./useSelectedField";

export function FieldPicker({ value, onChange, fields }: {
  value: string;
  onChange: (id: string) => void;
  fields: FieldRecord[];
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-muted">
      <span>Field</span>
      <Select
        aria-label="Field"
        className="min-w-56"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {fields.map((f) => (
          <option key={f.id} value={f.id}>
            {f.name} — {f.farm_name}
          </option>
        ))}
      </Select>
    </label>
  );
}

/** Shared loading / error / no-field states for field-scoped intelligence pages. */
export function FieldGate({ sel, children }: {
  sel: ReturnType<typeof useSelectedField>;
  children: React.ReactNode;
}) {
  if (sel.fields.isPending) return <Card><LoadingRows label="Loading fields" /></Card>;
  if (sel.fields.isError) {
    return (
      <Card>
        <ErrorState message={errorMessage(sel.fields.error)} onRetry={() => sel.fields.refetch()} />
      </Card>
    );
  }
  if (!sel.field) {
    return (
      <Card>
        <EmptyState
          icon={Map}
          title="Add a field first"
          description="Soil tests, weather and agent reports are attached to a field."
          action={<Button asChild><Link to="/fields">Go to Fields</Link></Button>}
        />
      </Card>
    );
  }
  return <>{children}</>;
}
