import { ChevronRight, MapPin, Map, Plus, Search } from "lucide-react";
import { useDeferredValue, useState } from "react";
import { Link } from "react-router";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState, LoadingRows } from "@/components/ui/feedback";
import { Input } from "@/components/ui/input";
import { useFarms } from "@/features/platform/queries";
import type { Farm } from "@/services/api/types";
import { errorMessage, formatHectares, PROVINCE_LABEL } from "@/utils/format";
import { FarmFormDialog } from "./FarmFormDialog";

function place(farm: Farm): string {
  const parts = [farm.district, farm.province ? PROVINCE_LABEL[farm.province] : null];
  return parts.filter(Boolean).join(", ") || "Location not set";
}

function FarmCard({ farm }: { farm: Farm }) {
  return (
    <li>
      <Link
        to={`/farms/${farm.id}`}
        className="group flex h-full flex-col gap-4 rounded-[var(--radius-card)] border border-border bg-card p-5 shadow-[var(--shadow-card)] transition-colors hover:border-primary/40"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold text-ink">{farm.name}</h2>
            <p className="mt-1 flex items-center gap-1.5 truncate text-sm text-muted">
              <MapPin aria-hidden className="size-3.5 shrink-0" />
              {place(farm)}
            </p>
          </div>
          <ChevronRight
            aria-hidden
            className="size-5 shrink-0 text-muted transition-transform group-hover:translate-x-0.5"
          />
        </div>
        <dl className="mt-auto grid grid-cols-2 gap-3 border-t border-border pt-4 text-sm">
          <div>
            <dt className="text-muted">Fields</dt>
            <dd className="tabular font-semibold text-ink">{farm.field_count}</dd>
          </div>
          <div>
            <dt className="text-muted">Total area</dt>
            <dd className="tabular font-semibold text-ink">{formatHectares(farm.total_area_ha)}</dd>
          </div>
        </dl>
      </Link>
    </li>
  );
}

export function FarmsPage() {
  const [search, setSearch] = useState("");
  const q = useDeferredValue(search.trim());
  const farms = useFarms(q || undefined);

  const addButton = (
    <FarmFormDialog
      trigger={
        <Button>
          <Plus aria-hidden />
          Add farm
        </Button>
      }
    />
  );

  return (
    <>
      <PageHeader
        title="My Farms"
        description="The farms you manage. Open a farm to see and manage its fields."
        actions={addButton}
      />
      <div className="relative mb-5 max-w-sm">
        <Search aria-hidden className="pointer-events-none absolute top-3 left-3 size-5 text-muted" />
        <Input
          type="search"
          aria-label="Search farms"
          placeholder="Search farms"
          className="pl-10"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      {farms.isPending ? (
        <Card>
          <LoadingRows label="Loading farms" />
        </Card>
      ) : farms.isError ? (
        <Card>
          <ErrorState message={errorMessage(farms.error)} onRetry={() => void farms.refetch()} />
        </Card>
      ) : farms.data.items.length === 0 ? (
        <Card>
          {q ? (
            <EmptyState icon={Search} title="No matching farms" description={`Nothing matches "${q}".`} />
          ) : (
            <EmptyState
              icon={Map}
              title="Add your first farm"
              description="Start with a farm. You can then add its fields and the crops growing on them."
              action={addButton}
            />
          )}
        </Card>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-label="Farms">
          {farms.data.items.map((farm) => (
            <FarmCard key={farm.id} farm={farm} />
          ))}
        </ul>
      )}
    </>
  );
}
