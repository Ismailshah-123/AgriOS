import { useQuery } from "@tanstack/react-query";
import { ShieldAlert, Sprout } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState, LoadingRows } from "@/components/ui/feedback";
import { Select } from "@/components/ui/input";
import { useCycles } from "@/features/platform/queries";
import { apiRequest } from "@/services/api/client";
import { errorMessage } from "@/utils/format";

interface Fertilizer {
  crop_cycle_id: string;
  crop_code: string;
  status: "refused";
  reason: "no_reviewed_source";
  message: string;
  escalation: "expert_review";
  doses: null;
  soil_test_note: string;
}

/** FR6: doses only from reviewed, cited tables. None are stored yet, so this page refuses. */
export function NutrientsPage() {
  const cycles = useCycles({ limit: 100 });
  const [picked, setPicked] = useState("");
  const items = cycles.data?.items ?? [];
  const cycleId = picked || items[0]?.id || "";
  const q = useQuery({
    queryKey: ["fertilizer", cycleId],
    queryFn: () => apiRequest<Fertilizer>(`/crop-cycles/${cycleId}/fertilizer`),
    enabled: Boolean(cycleId),
  });
  return (
    <>
      <PageHeader
        title="Nutrient Management"
        description="Fertilizer quantities only from stored, cited, reviewed requirement tables. Without one, no quantity is shown."
        actions={items.length > 0 && (
          <label className="flex items-center gap-2 text-sm text-muted">
            <span>Crop cycle</span>
            <Select aria-label="Crop cycle" className="min-w-56" value={cycleId} onChange={(e) => setPicked(e.target.value)}>
              {items.map((c) => <option key={c.id} value={c.id}>{c.crop.name_en} — {c.field_name} ({c.farm_name})</option>)}
            </Select>
          </label>
        )}
      />
      {cycles.isPending ? <Card><LoadingRows label="Loading crop cycles" /></Card>
        : cycles.isError ? <Card><ErrorState message={errorMessage(cycles.error)} onRetry={() => cycles.refetch()} /></Card>
        : !cycleId ? (
          <Card><EmptyState icon={Sprout} title="Add a crop cycle first" description="Nutrient needs depend on the crop."
            action={<Button asChild><Link to="/crop-cycles">Go to Crop Cycles</Link></Button>} /></Card>
        ) : q.isPending ? <Card><LoadingRows label="Checking reviewed sources" /></Card>
        : q.isError ? <Card><ErrorState message={errorMessage(q.error)} onRetry={() => q.refetch()} /></Card>
        : (
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2"><ShieldAlert aria-hidden className="size-5 text-warning" /><CardTitle>No verified fertilizer guidance</CardTitle></div>
              <CardDescription>No dose is shown.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 text-sm">
              <p className="text-ink" role="status">{q.data.message}</p>
              <p className="text-muted">{q.data.soil_test_note}</p>
              <div className="flex flex-wrap gap-2">
                <Button asChild variant="secondary"><Link to="/soil">View soil tests</Link></Button>
                <Button asChild variant="secondary"><Link to="/crop-doctor">Ask an expert through Crop Doctor</Link></Button>
              </div>
            </CardContent>
          </Card>
        )}
    </>
  );
}

export { NutrientsPage as Component };
