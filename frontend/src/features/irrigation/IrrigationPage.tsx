import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FieldGate, FieldPicker } from "@/features/intelligence/FieldPicker";
import { useWaterDemand } from "@/features/intelligence/queries";
import { useSelectedField } from "@/features/intelligence/useSelectedField";
import { DailyChart } from "@/features/weather/DailyChart";
import { WaterDemandCard } from "@/features/weather/WaterDemandCard";
import { formatDate } from "@/utils/format";

const dash = (v: number | null) => (v == null ? "—" : String(v));
const range = (lo: number | null, hi: number | null) =>
  lo == null || hi == null ? "—" : lo === hi ? String(lo) : `${lo}–${hi}`;

/** FAO-56 crop water demand per field. Estimates only: no schedule, no equipment control. */
export function IrrigationPage() {
  const sel = useSelectedField();
  return (
    <>
      <PageHeader
        title="Smart Irrigation"
        description="Crop water demand ETc = Kc × ET0 (FAO-56) from the field's growing crop and the forecast. An estimate, not measured soil moisture."
        actions={sel.field && (
          <FieldPicker value={sel.fieldId} onChange={sel.setFieldId} fields={sel.fields.data?.items ?? []} />
        )}
      />
      <FieldGate sel={sel}>
        <div className="grid gap-4">
          <WaterDemandCard fieldId={sel.fieldId} />
          <DailyBreakdown fieldId={sel.fieldId} />
          <NotIncluded />
        </div>
      </FieldGate>
    </>
  );
}

function DailyBreakdown({ fieldId }: { fieldId: string }) {
  const q = useWaterDemand(fieldId);
  if (!q.isSuccess || q.data.status !== "ok" || q.data.daily.length === 0) return null;
  const u = q.data.units;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Day by day</CardTitle>
        <CardDescription>
          Kc is a range where FAO-56 gives one; ETc is shown as the matching range. Days the provider
          did not return stay empty.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <DailyChart range title="Crop water demand" unit={u.etc ?? "mm/day"} points={q.data.daily.map((d) => ({
          label: formatDate(d.date), low: d.etc_low_mm, high: d.etc_high_mm,
          tooltip: `${formatDate(d.date)}: ETc ${range(d.etc_low_mm, d.etc_high_mm)} ${u.etc ?? "mm/day"}`,
        }))} />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">Daily crop water demand</caption>
            <thead className="text-left text-muted">
              <tr>
                <th className="py-1 pr-3">Date</th><th className="pr-3">Stage</th><th className="pr-3">Kc</th>
                <th className="pr-3">ET0 ({u.et0 ?? "mm/day"})</th><th className="pr-3">ETc ({u.etc ?? "mm/day"})</th><th>Gross rain ({u.rain ?? "mm"})</th>
              </tr>
            </thead>
            <tbody>
              {q.data.daily.map((d) => (
                <tr key={d.date} className="border-t border-border text-ink tabular">
                  <td className="py-1 pr-3">{formatDate(d.date)}</td>
                  <td className="pr-3">{d.stage?.replaceAll("_", " ") ?? "—"}</td>
                  <td className="pr-3">{range(d.kc_low, d.kc_high)}</td>
                  <td className="pr-3">{dash(d.et0_mm)}</td>
                  <td className="pr-3">{range(d.etc_low_mm, d.etc_high_mm)}</td>
                  <td>{dash(d.rain_mm)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function NotIncluded() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Not included in this estimate</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="list-disc pl-5 text-sm text-muted">
          <li>Effective rainfall is not subtracted; forecast rain is gross rain only.</li>
          <li>No irrigation schedule, depth or volume is calculated yet.</li>
          <li>Soil moisture is not measured; no sensor or pump is connected or controlled.</li>
          <li>Crop coefficients exist only for tomato and cotton (FAO-56 Tables 11-12, pending expert review).</li>
        </ul>
      </CardContent>
    </Card>
  );
}

export { IrrigationPage as Component };
