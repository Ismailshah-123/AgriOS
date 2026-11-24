import { ArrowLeft, Layers, Pencil, Plus, Trash2 } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState, LoadingRows } from "@/components/ui/feedback";
import { FieldFormDialog } from "@/features/fields/FieldFormDialog";
import { FieldsList } from "@/features/fields/FieldsList";
import { useDeleteFarm, useFarm, useFields } from "@/features/platform/queries";
import { ApiError } from "@/services/api/client";
import type { Farm } from "@/services/api/types";
import { errorMessage, formatHectares, PROVINCE_LABEL } from "@/utils/format";
import { FarmFormDialog } from "./FarmFormDialog";

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="tabular font-medium text-ink">{value}</dd>
    </div>
  );
}

function FarmSummary({ farm }: { farm: Farm }) {
  const location =
    farm.latitude !== null && farm.longitude !== null
      ? `${farm.latitude.toFixed(2)}, ${farm.longitude.toFixed(2)} (approximate)`
      : "Not set";
  return (
    <Card className="p-5">
      <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <Detail label="Province" value={farm.province ? PROVINCE_LABEL[farm.province] : "Not set"} />
        <Detail label="District" value={farm.district ?? "Not set"} />
        <Detail label="Location" value={location} />
        <Detail label="Total field area" value={formatHectares(farm.total_area_ha)} />
      </dl>
      {farm.notes && <p className="mt-5 border-t border-border pt-4 text-sm text-ink-soft">{farm.notes}</p>}
    </Card>
  );
}

export function FarmDetailPage() {
  const { farmId = "" } = useParams();
  const navigate = useNavigate();
  const farm = useFarm(farmId);
  const fields = useFields(farmId);
  const remove = useDeleteFarm();

  if (farm.isPending) return <LoadingRows label="Loading farm" />;
  if (farm.isError) {
    const notFound = farm.error instanceof ApiError && farm.error.status === 404;
    return (
      <Card>
        <ErrorState
          title={notFound ? "Farm not found" : "Could not load this farm"}
          message={notFound ? "It may have been deleted, or the link is wrong." : errorMessage(farm.error)}
          onRetry={notFound ? undefined : () => void farm.refetch()}
        />
      </Card>
    );
  }

  const addField = (
    <FieldFormDialog
      farmId={farmId}
      trigger={
        <Button size="sm">
          <Plus aria-hidden />
          Add field
        </Button>
      }
    />
  );

  return (
    <>
      <Link to="/farms" className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-muted hover:text-ink">
        <ArrowLeft aria-hidden className="size-4" />
        My Farms
      </Link>
      <PageHeader
        title={farm.data.name}
        actions={
          <>
            <FarmFormDialog
              farm={farm.data}
              trigger={
                <Button variant="secondary">
                  <Pencil aria-hidden />
                  Edit
                </Button>
              }
            />
            <ConfirmDialog
              title={`Delete ${farm.data.name}?`}
              description="Farms that still have fields cannot be deleted. Remove the fields first."
              confirmLabel="Delete farm"
              onConfirm={async () => {
                await remove.mutateAsync(farm.data.id);
                navigate("/farms", { replace: true });
              }}
              trigger={
                <Button variant="secondary" aria-label="Delete farm">
                  <Trash2 aria-hidden />
                  <span className="hidden sm:inline">Delete</span>
                </Button>
              }
            />
          </>
        }
      />
      <div className="flex flex-col gap-6">
        <FarmSummary farm={farm.data} />
        <Card>
          <CardHeader className="flex-row items-center justify-between border-b border-border pb-4">
            <CardTitle>Fields</CardTitle>
            {addField}
          </CardHeader>
          {fields.isPending ? (
            <LoadingRows label="Loading fields" />
          ) : fields.isError ? (
            <ErrorState as="h3" message={errorMessage(fields.error)} onRetry={() => void fields.refetch()} />
          ) : fields.data.items.length === 0 ? (
            <EmptyState
              as="h3"
              icon={Layers}
              title="No fields on this farm yet"
              description="Add each field with its area. Crop cycles are then recorded per field."
              action={addField}
            />
          ) : (
            <FieldsList fields={fields.data.items} />
          )}
        </Card>
      </div>
    </>
  );
}
