import { useQuery } from "@tanstack/react-query";
import { Banknote, LandPlot, TrendingDown, TrendingUp, UserCheck } from "lucide-react";
import { Link } from "react-router";
import { BarList } from "@/components/charts/BarList";
import { ColumnChart } from "@/components/charts/ColumnChart";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, Skeleton } from "@/components/ui/feedback";
import { StatTile } from "@/components/ui/stat-tile";
import { CASE_STATUS_LABEL } from "@/features/crop-health/labels";
import { analyticsApi, type Analytics } from "@/services/api/analytics";
import type { CaseStatus } from "@/services/api/cropHealth";
import { CATEGORY_LABEL, pkr, type ExpenseCategory } from "@/services/api/economics";
import { errorMessage, formatHectares } from "@/utils/format";

const monthFmt = new Intl.DateTimeFormat("en-GB", { month: "short", year: "2-digit" });

function ChartCard({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle><CardDescription>{description}</CardDescription></CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

/** Dashboard analytics: every figure is a count or sum of the user's own records (GET /analytics). */
export function AnalyticsSection() {
  const q = useQuery({ queryKey: ["analytics"], queryFn: analyticsApi.get });
  if (q.isPending) {
    return (
      <div role="status" aria-label="Loading analytics" className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-28 rounded-[var(--radius-card)]" />)}
      </div>
    );
  }
  if (q.isError) return <Card><ErrorState title="Could not load analytics" message={errorMessage(q.error)} onRetry={() => q.refetch()} /></Card>;
  return <AnalyticsBody a={q.data} />;
}

function AnalyticsBody({ a }: { a: Analytics }) {
  const e = a.economics;
  const area = a.area_by_crop.reduce((s, r) => s + r.area_ha, 0);
  const loss = Number(e.profit_pkr) < 0;
  const statuses = (Object.entries(a.cases.by_status) as [CaseStatus, number][]).filter(([, n]) => n > 0);
  return (
    <section aria-labelledby="analytics-title" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="analytics-title" className="text-lg font-semibold text-ink">Farm analytics</h2>
        <p className="text-xs text-muted">From your records only · amounts in PKR · area in hectares</p>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <StatTile icon={LandPlot} label="Growing area" value={formatHectares(area)}
          detail={`${a.area_by_crop.reduce((s, r) => s + r.cycles, 0)} growing crop cycles`} />
        <StatTile icon={Banknote} label="Recorded costs" value={pkr(e.total_cost_pkr)} detail={`Revenue ${pkr(e.total_revenue_pkr)}`} />
        <StatTile icon={loss ? TrendingDown : TrendingUp} label={loss ? "Loss" : "Profit"} value={pkr(e.profit_pkr)}
          detail={<Link className="underline" to="/economics">Revenue minus recorded costs</Link>} />
        <StatTile icon={UserCheck} label="With an expert" value={a.pending_expert_reviews}
          detail={<Link className="underline" to="/crop-doctor/cases">Crop Doctor cases awaiting review</Link>} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2 [&>*]:min-w-0">
        <ChartCard title="Growing area by crop" description="Active crop cycles; cycle area if recorded, otherwise field area.">
          <BarList label="Growing area by crop" emptyText="No crop is marked as growing."
            data={a.area_by_crop.map((r) => ({ key: r.crop, label: r.crop, value: r.area_ha, display: formatHectares(r.area_ha), detail: `${r.cycles} cycle${r.cycles === 1 ? "" : "s"}` }))} />
        </ChartCard>
        <ChartCard title="Crop Doctor cases per month" description="Cases you created, last 6 months.">
          <ColumnChart label="Crop Doctor cases per month"
            data={a.cases.by_month.map((m) => ({ key: m.month, label: monthFmt.format(new Date(`${m.month}-01T00:00:00`)), value: m.cases, display: `${m.cases} case${m.cases === 1 ? "" : "s"}` }))} />
        </ChartCard>
        <ChartCard title="Crop Doctor cases by status" description="Model results and expert outcomes are tracked separately on each case.">
          <BarList label="Crop Doctor cases by status" emptyText="No Crop Doctor cases yet."
            data={statuses.map(([s, n]) => ({ key: s, label: CASE_STATUS_LABEL[s], value: n, display: String(n) }))} />
        </ChartCard>
        <ChartCard title="Costs by category" description="All recorded expenses across crop cycles.">
          <BarList label="Costs by category" emptyText="No expenses recorded yet."
            data={Object.entries(e.cost_by_category_pkr).map(([c, v]) => ({ key: c, label: CATEGORY_LABEL[c as ExpenseCategory] ?? c, value: Number(v), display: pkr(v) }))} />
        </ChartCard>
      </div>
      {e.cycles.length > 0 && (
        <ChartCard title="Profit by crop cycle" description="Cycles with recorded costs or sales, lowest profit first.">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">Profit by crop cycle</caption>
              <thead className="text-left text-muted"><tr><th className="py-1 pr-3">Crop cycle</th><th className="pr-3 text-right">Cost</th><th className="pr-3 text-right">Revenue</th><th className="text-right">Profit / loss</th></tr></thead>
              <tbody>
                {e.cycles.map((c) => (
                  <tr key={c.crop_cycle_id} className="border-t border-border text-ink">
                    <td className="py-1.5 pr-3">{c.crop} · {c.field}</td>
                    <td className="tabular pr-3 text-right">{pkr(c.cost_pkr)}</td>
                    <td className="tabular pr-3 text-right">{pkr(c.revenue_pkr)}</td>
                    <td className="tabular text-right font-medium">{pkr(c.profit_pkr)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ChartCard>
      )}
    </section>
  );
}
