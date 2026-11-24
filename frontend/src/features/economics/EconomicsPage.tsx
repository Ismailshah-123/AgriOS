import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Sprout, Trash2, Wallet } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState, LoadingRows } from "@/components/ui/feedback";
import { Select } from "@/components/ui/input";
import { OriginBadge } from "@/components/ui/origin-badge";
import { useCycles } from "@/features/platform/queries";
import { BarList } from "@/components/charts/BarList";
import { ColumnChart } from "@/components/charts/ColumnChart";
import { CATEGORY_LABEL, economicsApi, kg, pkr, type CycleEconomics, type ExpenseCategory } from "@/services/api/economics";
import { errorMessage, formatDate } from "@/utils/format";
import { ExpenseDialog, HarvestDialog } from "./RecordDialogs";

/** FR10: expenses and harvest/sales per crop cycle; every figure comes from these records. */
export function EconomicsPage() {
  const cycles = useCycles({ limit: 100 });
  const [picked, setPicked] = useState("");
  const items = cycles.data?.items ?? [];
  const cycleId = picked || items[0]?.id || "";
  return (
    <>
      <PageHeader
        title="Farm Economics"
        description="Costs, harvest and sales per crop cycle in Pakistani rupees (PKR). Totals are calculated only from what you record."
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
          <Card>
            <EmptyState icon={Sprout} title="Add a crop cycle first" description="Costs and harvests are recorded against a crop cycle."
              action={<Button asChild><Link to="/crop-cycles">Go to Crop Cycles</Link></Button>} />
          </Card>
        ) : <CycleEconomicsView cycleId={cycleId} />}
    </>
  );
}

function CycleEconomicsView({ cycleId }: { cycleId: string }) {
  const q = useQuery({ queryKey: ["economics", cycleId], queryFn: () => economicsApi.forCycle(cycleId) });
  if (q.isPending) return <Card><LoadingRows label="Loading economics" /></Card>;
  if (q.isError) return <Card><ErrorState message={errorMessage(q.error)} onRetry={() => q.refetch()} /></Card>;
  const d = q.data;
  return (
    <div className="grid gap-4">
      <Summary d={d} />
      <Card>
        <CardHeader><CardTitle>Costs by category</CardTitle><CardDescription>This crop cycle, PKR.</CardDescription></CardHeader>
        <CardContent>
          <BarList label="Costs by category for this crop cycle" emptyText="No expenses recorded for this crop cycle."
            data={Object.entries(d.summary.cost_by_category_pkr).sort((x, y) => Number(y[1]) - Number(x[1]))
              .map(([c, v]) => ({ key: c, label: CATEGORY_LABEL[c as ExpenseCategory] ?? c, value: Number(v), display: pkr(v) }))} />
        </CardContent>
      </Card>
      {d.expenses.length > 0 && <CostsByMonth d={d} />}
      <div className="grid gap-4 lg:grid-cols-2 [&>*]:min-w-0">
        <ExpensesCard d={d} />
        <HarvestsCard d={d} />
      </div>
      <Card>
        <CardHeader><CardTitle>How these figures are calculated</CardTitle></CardHeader>
        <CardContent className="grid gap-3 text-sm text-muted sm:grid-cols-2">
          <ul className="list-disc pl-5">{d.definitions.map((x) => <li key={x}>{x}</li>)}</ul>
          <ul className="list-disc pl-5">{d.limitations.map((x) => <li key={x}>{x}</li>)}</ul>
        </CardContent>
      </Card>
    </div>
  );
}

const monthFmt = new Intl.DateTimeFormat("en-GB", { month: "short", year: "2-digit" });

/** Recorded costs summed per calendar month (from the expense dates; no gaps filled). */
function CostsByMonth({ d }: { d: CycleEconomics }) {
  const sums = new Map<string, number>();
  for (const e of d.expenses) {
    const m = e.incurred_on.slice(0, 7);
    sums.set(m, (sums.get(m) ?? 0) + Number(e.amount_pkr));
  }
  const months = [...sums.keys()].sort();
  return (
    <Card>
      <CardHeader><CardTitle>Costs per month</CardTitle><CardDescription>Months with recorded expenses, PKR.</CardDescription></CardHeader>
      <CardContent>
        <ColumnChart label="Costs per month" data={months.map((m) => ({
          key: m, label: monthFmt.format(new Date(`${m}-01T00:00:00`)), value: sums.get(m)!, display: pkr(sums.get(m)!.toFixed(2)),
        }))} />
      </CardContent>
    </Card>
  );
}

function Tile({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-[var(--radius-card)] border border-border bg-card p-4">
      <p className="text-sm text-muted">{label}</p>
      <p className="tabular mt-1 text-lg font-semibold text-ink">{value}</p>
      {detail && <p className="mt-0.5 text-xs text-muted">{detail}</p>}
    </div>
  );
}

function Summary({ d }: { d: CycleEconomics }) {
  const s = d.summary;
  const loss = Number(s.profit_pkr) < 0;
  return (
    <section aria-label="Economics summary" className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      <Tile label="Total cost" value={pkr(s.total_cost_pkr)} detail={s.cost_per_acre_pkr ? `${pkr(s.cost_per_acre_pkr)} per acre` : "Field area not recorded"} />
      <Tile label="Revenue" value={pkr(s.revenue_pkr)} detail={`${kg(s.sold_kg)} sold · ${kg(s.unsold_kg)} unsold`} />
      <Tile label={loss ? "Loss" : "Profit"} value={pkr(s.profit_pkr)} detail="Revenue minus total cost" />
      <Tile label="Break-even price" value={s.break_even_price_pkr_per_kg ? `${pkr(s.break_even_price_pkr_per_kg)}/kg` : "—"}
        detail={s.break_even_yield_kg ? `Break-even yield ${kg(s.break_even_yield_kg)} at average price` : "Needs harvest and sales records"} />
    </section>
  );
}

function useRemove(cycleId: string, fn: (id: string) => Promise<unknown>) {
  const qc = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => qc.invalidateQueries({ queryKey: ["economics", cycleId] }) });
}

function DeleteButton({ label, onConfirm }: { label: string; onConfirm: () => Promise<unknown> }) {
  return (
    <ConfirmDialog title={`Delete ${label}?`} description="The record is removed from this crop cycle. The deletion is recorded in the audit log."
      confirmLabel="Delete" onConfirm={onConfirm}
      trigger={<Button variant="ghost" size="sm" aria-label={`Delete ${label}`}><Trash2 aria-hidden /><span className="md:sr-only">Delete</span></Button>} />
  );
}

function ExpensesCard({ d }: { d: CycleEconomics }) {
  const remove = useRemove(d.cycle.id, economicsApi.removeExpense);
  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
        <div><CardTitle>Expenses</CardTitle><CardDescription>{d.expenses.length} records</CardDescription></div>
        <ExpenseDialog cycleId={d.cycle.id} />
      </CardHeader>
      <CardContent className="overflow-x-auto">
        {d.expenses.length === 0 ? <EmptyState as="h3" icon={Wallet} title="No expenses yet" description="Add seed, fertilizer, labour and other costs." /> : (
          <table className="w-full text-sm">
            <caption className="sr-only">Expenses</caption>
            <thead className="text-left text-muted"><tr><th className="py-1 pr-3">Date</th><th className="pr-3">Category</th><th className="pr-3 text-right">Amount</th><th><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>
              {d.expenses.map((e) => (
                <tr key={e.id} className="border-t border-border text-ink">
                  <td className="py-1 pr-3">{formatDate(e.incurred_on)}</td>
                  <td className="pr-3">{CATEGORY_LABEL[e.category]}{e.note && <span className="block text-xs text-muted">{e.note}</span>}</td>
                  <td className="tabular pr-3 text-right">{pkr(e.amount_pkr)}</td>
                  <td className="whitespace-nowrap text-right">
                    <ExpenseDialog cycleId={d.cycle.id} initial={e} />
                    <DeleteButton label={`expense of ${formatDate(e.incurred_on)}`} onConfirm={() => remove.mutateAsync(e.id)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="mt-2 flex items-center gap-2 text-xs text-muted"><OriginBadge origin="farmer_entered" /> All amounts in PKR.</p>
      </CardContent>
    </Card>
  );
}

function HarvestsCard({ d }: { d: CycleEconomics }) {
  const remove = useRemove(d.cycle.id, economicsApi.removeHarvest);
  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
        <div><CardTitle>Harvest and sales</CardTitle><CardDescription>{kg(d.summary.harvested_kg)} harvested</CardDescription></div>
        <HarvestDialog cycleId={d.cycle.id} />
      </CardHeader>
      <CardContent className="overflow-x-auto">
        {d.harvests.length === 0 ? <EmptyState as="h3" icon={Sprout} title="No harvest recorded" description="Add each harvest lot; add the price when it is sold." /> : (
          <table className="w-full text-sm">
            <caption className="sr-only">Harvest and sales</caption>
            <thead className="text-left text-muted"><tr><th className="py-1 pr-3">Date</th><th className="pr-3 text-right">Quantity</th><th className="pr-3 text-right">Price/kg</th><th className="pr-3 text-right">Revenue</th><th><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>
              {d.harvests.map((h) => (
                <tr key={h.id} className="border-t border-border text-ink">
                  <td className="py-1 pr-3">{formatDate(h.recorded_on)}{h.buyer && <span className="block text-xs text-muted">{h.buyer}</span>}</td>
                  <td className="tabular pr-3 text-right">{kg(h.quantity_kg)}</td>
                  <td className="tabular pr-3 text-right">{h.price_pkr_per_kg ? pkr(h.price_pkr_per_kg) : "Not sold"}</td>
                  <td className="tabular pr-3 text-right">{pkr(h.revenue_pkr)}</td>
                  <td className="whitespace-nowrap text-right">
                    <HarvestDialog cycleId={d.cycle.id} initial={h} />
                    <DeleteButton label={`harvest of ${formatDate(h.recorded_on)}`} onConfirm={() => remove.mutateAsync(h.id)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

export { EconomicsPage as Component };
