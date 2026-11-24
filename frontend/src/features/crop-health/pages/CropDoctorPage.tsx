import { ClipboardList, Clock3, History, Plus, ScanSearch, Stethoscope } from "lucide-react";
import { Link } from "react-router";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState, LoadingRows, Skeleton } from "@/components/ui/feedback";
import { StatTile } from "@/components/ui/stat-tile";
import { OfflineDrafts } from "@/features/offline/OfflineDrafts";
import { errorMessage } from "@/utils/format";
import { CaseCard } from "../CaseBits";
import { AVAILABILITY_LABEL } from "../labels";
import { useCaseList, useCaseSummary } from "../queries";
import { useL } from "@/i18n/useT";

/** Crop Doctor overview. Every number comes from GET /cases/summary. */
export function CropDoctorPage() {
  const l = useL();
  const summary = useCaseSummary();
  const recent = useCaseList({}, 6);
  const items = recent.data?.pages.flatMap((p) => p.items) ?? [];
  const modelReady = summary.data?.model_availability === "ready";

  return (
    <>
      <PageHeader title={l("Crop Doctor")}
        description={l("Photograph a crop problem, keep a record of it, and get an analysis when a validated model is available.")}
        actions={
          <Button asChild>
            <Link to="/crop-doctor/new"><Plus aria-hidden />{l("New assessment")}</Link>
          </Button>
        } />
      <div className="flex flex-col gap-6">
        <OfflineDrafts />
        {summary.isPending ? (
          <div role="status" aria-label="Loading summary" className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3">
            {[0, 1, 2].map((i) => <Skeleton key={i} className="h-32 rounded-[var(--radius-card)]" />)}
          </div>
        ) : summary.isError ? (
          <Card><ErrorState message={errorMessage(summary.error)} onRetry={() => void summary.refetch()} /></Card>
        ) : (
          <section aria-label="Case summary" className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3">
            <StatTile icon={ClipboardList} label={l("All cases")} value={summary.data.total} />
            <StatTile icon={Clock3} label={l("Awaiting analysis")} value={summary.data.awaiting_analysis} />
            <StatTile icon={History} label={l("Need follow-up")} value={summary.data.needs_follow_up} />
          </section>
        )}

        {summary.isSuccess && !modelReady && (
          <Card className="border-warning/30 bg-warning-soft/50 p-5">
            <div className="flex gap-3">
              <ScanSearch aria-hidden className="mt-0.5 size-5 shrink-0 text-warning" />
              <div className="flex flex-col gap-1">
                <p className="font-medium text-ink">
                  {l("Analysis model:")} <Badge tone="warning">{l(AVAILABILITY_LABEL[summary.data.model_availability])}</Badge>
                </p>
                <p className="text-sm text-ink-soft">
                  You can submit cases and photos now. They are saved and will be analysed once an
                  evaluated model is installed. No diagnosis is shown until then.
                </p>
              </div>
            </div>
          </Card>
        )}

        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <div className="flex flex-col gap-1">
              <CardTitle>{l("Recent cases")}</CardTitle>
              <CardDescription>{l("Your latest crop health assessments.")}</CardDescription>
            </div>
            <Link to="/crop-doctor/cases" className="text-sm font-medium text-primary-dark hover:underline">All cases</Link>
          </CardHeader>
          <CardContent>
            {recent.isPending ? (
              <LoadingRows rows={2} label="Loading recent cases" />
            ) : recent.isError ? (
              <ErrorState as="h3" message={errorMessage(recent.error)} onRetry={() => void recent.refetch()} />
            ) : items.length === 0 ? (
              <EmptyState as="h3" icon={Stethoscope} title={l("No assessments yet")}
                description="Start an assessment for a growing crop. Add clear photos and what you have noticed."
                action={<Button asChild variant="secondary"><Link to="/crop-doctor/new">{l("Start an assessment")}</Link></Button>} />
            ) : (
              <ul aria-label="Recent cases" className="grid gap-3 md:grid-cols-2">
                {items.map((c) => <CaseCard key={c.id} c={c} />)}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
