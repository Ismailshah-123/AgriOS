import { ArrowLeft, Plus, Search, Stethoscope } from "lucide-react";
import { useDeferredValue, useState } from "react";
import { Link } from "react-router";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState, LoadingRows } from "@/components/ui/feedback";
import { FormField } from "@/components/ui/form-field";
import { Input, Select } from "@/components/ui/input";
import { useCrops } from "@/features/platform/queries";
import type { CaseFilters, InferenceStatus } from "@/services/api/cropHealth";
import { errorMessage } from "@/utils/format";
import { CaseCard } from "../CaseBits";
import { INFERENCE_LABEL } from "../labels";
import { useCaseList } from "../queries";

export function CaseHistoryPage() {
  const [search, setSearch] = useState("");
  const [inference, setInference] = useState<InferenceStatus | "">("");
  const [cropId, setCropId] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const q = useDeferredValue(search.trim());
  const crops = useCrops();

  const filters: CaseFilters = {
    q: q || undefined,
    inference_status: inference || undefined,
    crop_id: cropId || undefined,
    created_from: from || undefined,
    created_to: to || undefined,
  };
  const list = useCaseList(filters);
  const items = list.data?.pages.flatMap((p) => p.items) ?? [];
  const filtered = Boolean(q || inference || cropId || from || to);

  return (
    <>
      <Link to="/crop-doctor" className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-muted hover:text-ink">
        <ArrowLeft aria-hidden className="size-4" />
        Crop Doctor
      </Link>
      <PageHeader title="Case history" description="All your crop health assessments, newest first."
        actions={<Button asChild><Link to="/crop-doctor/new"><Plus aria-hidden />New assessment</Link></Button>} />
      <Card className="mb-5 p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div className="relative lg:col-span-2">
            <FormField label="Search">
              <Input type="search" placeholder="Reference, crop, field or farm" value={search}
                onChange={(e) => setSearch(e.target.value)} className="pl-10" />
            </FormField>
            <Search aria-hidden className="pointer-events-none absolute bottom-3 left-3 size-5 text-muted" />
          </div>
          <FormField label="Analysis status">
            <Select value={inference} onChange={(e) => setInference(e.target.value as InferenceStatus | "")}>
              <option value="">Any</option>
              {Object.entries(INFERENCE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </Select>
          </FormField>
          <FormField label="Crop">
            <Select value={cropId} onChange={(e) => setCropId(e.target.value)}>
              <option value="">Any crop</option>
              {crops.data?.map((c) => <option key={c.id} value={c.id}>{c.name_en}</option>)}
            </Select>
          </FormField>
          <div className="grid grid-cols-2 gap-3 sm:col-span-2 lg:col-span-1 lg:grid-cols-1">
            <FormField label="From"><Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></FormField>
            <FormField label="To"><Input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></FormField>
          </div>
        </div>
      </Card>

      {list.isPending ? (
        <Card><LoadingRows label="Loading cases" /></Card>
      ) : list.isError ? (
        <Card><ErrorState message={errorMessage(list.error)} onRetry={() => void list.refetch()} /></Card>
      ) : items.length === 0 ? (
        <Card>
          {filtered ? (
            <EmptyState icon={Search} title="No matching cases" description="Try a different search or clear some filters." />
          ) : (
            <EmptyState icon={Stethoscope} title="No cases yet"
              description="Your crop health assessments will be listed here."
              action={<Button asChild><Link to="/crop-doctor/new">Start an assessment</Link></Button>} />
          )}
        </Card>
      ) : (
        <>
          <ul aria-label="Cases" className="grid gap-3 md:grid-cols-2">
            {items.map((c) => <CaseCard key={c.id} c={c} />)}
          </ul>
          {list.hasNextPage && (
            <div className="mt-5 flex justify-center">
              <Button variant="secondary" disabled={list.isFetchingNextPage} onClick={() => void list.fetchNextPage()}>
                {list.isFetchingNextPage ? "Loading…" : "Load more cases"}
              </Button>
            </div>
          )}
        </>
      )}
    </>
  );
}
