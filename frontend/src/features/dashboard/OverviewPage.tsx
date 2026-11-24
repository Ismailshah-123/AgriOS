import { CalendarClock, Layers, Map, Sprout } from "lucide-react";
import { Card } from "@/components/ui/card";
import { ErrorState, Skeleton } from "@/components/ui/feedback";
import { StatTile } from "@/components/ui/stat-tile";
import { useAuth } from "@/features/auth/auth-context";
import { useOverview } from "@/features/platform/queries";
import { errorMessage, formatHectares } from "@/utils/format";
import { AnalyticsSection } from "./AnalyticsSection";
import { QuickActions } from "./QuickActions";
import {
  ActiveCycles,
  GettingStarted,
  IntelligenceStatus,
  RecentChanges,
  Upcoming,
} from "./sections";

function greeting(now = new Date()): string {
  const h = now.getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

/** Every number on this page comes from GET /overview. Nothing is estimated. */
export function OverviewPage() {
  const { user } = useAuth();
  const overview = useOverview();
  const firstName = user?.full_name.split(/\s+/)[0] ?? "";
  const counts = overview.data?.counts;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-1.5">
        <p className="text-sm font-medium text-muted">{greeting()}</p>
        <h1 className="text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
          Welcome, {firstName}
        </h1>
        {counts && counts.farms > 0 && (
          <p className="text-muted">
            {plural(counts.farms, "farm")} · {plural(counts.fields, "field")} ·{" "}
            {formatHectares(counts.total_area_ha)} recorded
          </p>
        )}
      </div>

      {overview.isPending ? (
        <div role="status" aria-label="Loading overview" className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-32 rounded-[var(--radius-card)]" />
          ))}
        </div>
      ) : overview.isError ? (
        <Card>
          <ErrorState
            title="Could not load your overview"
            message={errorMessage(overview.error)}
            onRetry={() => void overview.refetch()}
          />
        </Card>
      ) : (
        <>
          <GettingStarted counts={overview.data.counts} />
          <section aria-label="Farm summary" className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
            <StatTile icon={Map} label="Farms" value={overview.data.counts.farms} />
            <StatTile
              icon={Layers}
              label="Fields"
              value={overview.data.counts.fields}
              detail={`${formatHectares(overview.data.counts.total_area_ha)} in total`}
            />
            <StatTile icon={Sprout} label="Growing now" value={overview.data.counts.cycles_by_status.active} />
            <StatTile
              icon={CalendarClock}
              label="Planned cycles"
              value={overview.data.counts.cycles_by_status.planned}
            />
          </section>
          <div className="grid gap-6 lg:grid-cols-2 [&>*]:min-w-0">
            <ActiveCycles cycles={overview.data.active_cycles} />
            <Upcoming items={overview.data.upcoming} />
          </div>
          {overview.data.counts.farms > 0 && <AnalyticsSection />}
          <div className="grid gap-6 lg:grid-cols-2 [&>*]:min-w-0">
            <IntelligenceStatus data={overview.data.intelligence} />
            <RecentChanges items={overview.data.recent_changes} />
          </div>
        </>
      )}
      <QuickActions />
    </div>
  );
}
