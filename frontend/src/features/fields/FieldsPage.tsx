import { Layers, Map, Plus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState, LoadingRows } from "@/components/ui/feedback";
import { Select } from "@/components/ui/input";
import { useFarms, useFields } from "@/features/platform/queries";
import { errorMessage } from "@/utils/format";
import { FieldFormDialog } from "./FieldFormDialog";
import { FieldsList } from "./FieldsList";

export function FieldsPage() {
  const [farmId, setFarmId] = useState("");
  const farms = useFarms();
  const fields = useFields(farmId || undefined);
  const hasFarms = (farms.data?.items.length ?? 0) > 0;

  const addButton = (
    <FieldFormDialog
      farmId={farmId || undefined}
      trigger={
        <Button disabled={!hasFarms}>
          <Plus aria-hidden />
          Add field
        </Button>
      }
    />
  );

  return (
    <>
      <PageHeader
        title="Fields"
        description="Every field across your farms. Areas are stored in hectares and shown in the unit you entered."
        actions={hasFarms ? addButton : undefined}
      />
      {farms.isSuccess && !hasFarms ? (
        <Card>
          <EmptyState
            icon={Map}
            title="Add a farm first"
            description="Fields belong to a farm. Create your first farm, then add its fields."
            action={
              <Button asChild>
                <Link to="/farms">Go to My Farms</Link>
              </Button>
            }
          />
        </Card>
      ) : (
        <Card>
          <div className="flex flex-col gap-3 border-b border-border px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
            <label className="flex items-center gap-3 text-sm font-medium text-ink">
              Farm
              <Select
                className="h-10 w-56"
                value={farmId}
                onChange={(e) => setFarmId(e.target.value)}
              >
                <option value="">All farms</option>
                {farms.data?.items.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                  </option>
                ))}
              </Select>
            </label>
            {fields.isSuccess && (
              <p className="text-sm text-muted">
                {fields.data.items.length} field{fields.data.items.length === 1 ? "" : "s"}
              </p>
            )}
          </div>
          {fields.isPending ? (
            <LoadingRows label="Loading fields" />
          ) : fields.isError ? (
            <ErrorState message={errorMessage(fields.error)} onRetry={() => void fields.refetch()} />
          ) : fields.data.items.length === 0 ? (
            <EmptyState
              icon={Layers}
              title="No fields yet"
              description="Add a field with its area to start tracking crop cycles on it."
              action={addButton}
            />
          ) : (
            <FieldsList fields={fields.data.items} showFarm={!farmId} />
          )}
        </Card>
      )}
    </>
  );
}
