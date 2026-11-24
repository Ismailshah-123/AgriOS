import { AlertTriangle, FlaskConical, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState, LoadingRows } from "@/components/ui/feedback";
import { OriginBadge } from "@/components/ui/origin-badge";
import { FieldGate, FieldPicker } from "@/features/intelligence/FieldPicker";
import { useSelectedField } from "@/features/intelligence/useSelectedField";
import { useDeleteSoil, useSoilList, useSoilSummary } from "@/features/intelligence/queries";
import { DailyChart } from "@/features/weather/DailyChart";
import { useState } from "react";
import { Select } from "@/components/ui/input";
import type { SoilDetail, SoilSummary } from "@/services/api/intelligence";
import { errorMessage, formatDate } from "@/utils/format";
import { SOIL_MEASURES } from "./measures";
import { SoilFormDialog } from "./SoilFormDialog";

const TONE = { info: "info", watch: "warning", warning: "danger" } as const;

export function SoilPage() {
  const sel = useSelectedField();
  return (
    <>
      <PageHeader
        title="Soil Intelligence"
        description="Soil tests per field with cited interpretation. Missing values stay missing; no fertilizer doses are generated."
        actions={sel.field && (
          <div className="flex flex-wrap items-center gap-3">
            <FieldPicker value={sel.fieldId} onChange={sel.setFieldId} fields={sel.fields.data?.items ?? []} />
            <SoilFormDialog fieldId={sel.fieldId} />
          </div>
        )}
      />
      <FieldGate sel={sel}>
        <SoilBody fieldId={sel.fieldId} />
      </FieldGate>
    </>
  );
}

function SoilBody({ fieldId }: { fieldId: string }) {
  const summary = useSoilSummary(fieldId);
  const list = useSoilList(fieldId);
  const remove = useDeleteSoil();
  if (summary.isPending) return <Card><LoadingRows label="Loading soil tests" /></Card>;
  if (summary.isError) {
    return <Card><ErrorState message={errorMessage(summary.error)} onRetry={() => summary.refetch()} /></Card>;
  }
  const s = summary.data;
  if (!s.latest) {
    return (
      <Card>
        <EmptyState
          icon={FlaskConical}
          title="No soil test for this field yet"
          description="Add a laboratory or field-kit result. AgriOS interprets only what was measured, with the source of every rule."
        />
      </Card>
    );
  }
  return (
    <div className="grid gap-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <LatestCard d={s.latest} />
        <InterpretationCard d={s.latest} />
      </div>
      <TrendCard trends={s.trends} />
      <Card>
        <CardHeader><CardTitle>Soil test history ({s.observations})</CardTitle></CardHeader>
        <CardContent className="overflow-x-auto">
          {list.isSuccess && (
            <table className="w-full text-sm">
              <thead className="text-left text-muted">
                <tr><th className="py-1 pr-3">Date</th><th className="pr-3">Origin</th><th className="pr-3">Lab</th><th className="pr-3">pH</th><th className="pr-3">EC (dS/m)</th><th className="pr-3">OM (%)</th><th><span className="sr-only">Actions</span></th></tr>
              </thead>
              <tbody>
                {list.data.map((o) => (
                  <tr key={o.id} className="border-t border-border text-ink">
                    <td className="py-1 pr-3">{formatDate(o.sampled_on)}</td>
                    <td className="pr-3"><OriginBadge origin={o.data_origin} /></td>
                    <td className="pr-3">{o.lab_name ?? "—"}</td>
                    <td className="pr-3">{o.ph ?? "—"}</td>
                    <td className="pr-3">{o.ec_ds_m ?? "—"}</td>
                    <td className="pr-3">{o.organic_matter_pct ?? "—"}</td>
                    <td className="whitespace-nowrap text-right">
                      <SoilFormDialog fieldId={fieldId} initial={o} />
                      <ConfirmDialog
                        title={`Delete the soil test of ${formatDate(o.sampled_on)}?`}
                        description="The test and its interpretation are removed from this field. The deletion is recorded in the audit log."
                        confirmLabel="Delete soil test"
                        onConfirm={() => remove.mutateAsync(o.id)}
                        trigger={
                          <Button variant="ghost" size="sm" aria-label={`Delete soil test of ${formatDate(o.sampled_on)}`}>
                            <Trash2 aria-hidden /><span className="md:sr-only">Delete</span>
                          </Button>
                        }
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

/** One measure at a time over test dates; only measures with >= 2 measured values. */
function TrendCard({ trends }: { trends: SoilSummary["trends"] }) {
  const available = SOIL_MEASURES.filter((m) => (trends[m.key] ?? []).length >= 2);
  const [key, setKey] = useState("");
  const m = available.find((x) => x.key === key) ?? available[0];
  if (!m) return null;
  const pts = trends[m.key] ?? [];
  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-2">
        <div>
          <CardTitle>{m.label} over time</CardTitle>
          <CardDescription>Each bar is one test ({m.unit}). Different lab methods can shift values; missing tests are not filled in.</CardDescription>
        </div>
        <Select aria-label="Soil measure" value={m.key} onChange={(e) => setKey(e.target.value)} className="w-auto">
          {available.map((x) => <option key={x.key} value={x.key}>{x.label}</option>)}
        </Select>
      </CardHeader>
      <CardContent>
        <DailyChart title={m.label} unit={m.unit} points={pts.map((p) => ({
          label: formatDate(p.sampled_on), high: p.value,
          tooltip: `${formatDate(p.sampled_on)}: ${m.label} ${p.value} ${m.unit} (${p.data_origin.replace("_", " ")})`,
        }))} />
      </CardContent>
    </Card>
  );
}

function LatestCard({ d }: { d: SoilDetail }) {
  const values = d as unknown as Record<string, number | null>;
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle>Latest test · {formatDate(d.sampled_on)}</CardTitle>
          <OriginBadge origin={d.data_origin} />
        </div>
        <CardDescription>
          {d.lab_name ?? "No laboratory"}{d.lab_reference ? ` · ref ${d.lab_reference}` : ""}
          {d.depth_from_cm != null && d.depth_to_cm != null ? ` · depth ${d.depth_from_cm}–${d.depth_to_cm} cm` : ""}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
          {SOIL_MEASURES.map((m) => (
            <div key={m.key}>
              <dt className="text-muted">{m.label}</dt>
              <dd className={values[m.key] == null ? "text-muted" : "text-ink"}>
                {values[m.key] == null ? "Not measured" : `${values[m.key]} ${m.unit}`}
              </dd>
            </div>
          ))}
          <div><dt className="text-muted">Texture</dt><dd className="text-ink">{d.texture?.replaceAll("_", " ") ?? "Not reported"}</dd></div>
        </dl>
      </CardContent>
    </Card>
  );
}

function InterpretationCard({ d }: { d: SoilDetail }) {
  const i = d.interpretation;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Interpretation</CardTitle>
        <CardDescription>
          General international classifications (USDA, FAO); not Pakistan-specific fertility tables.
          {d.crops_considered.length > 0 && ` Crop context: ${d.crops_considered.join(", ")}.`}
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-2 text-sm">
        {i.flags.map((f, k) => (
          <div key={k} className="rounded-md border border-border p-2">
            <Badge tone={TONE[f.level]}>{f.level}</Badge>{" "}
            <span className="text-ink">{f.message}</span>
            <p className="mt-1 text-xs text-muted">Source: {f.source}</p>
          </div>
        ))}
        {i.warnings.map((w) => (
          <p key={w.code} className="flex items-start gap-2 text-warning">
            <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" />{w.message}
          </p>
        ))}
        {i.not_evaluated.length > 0 && (
          <details className="text-xs text-muted">
            <summary className="cursor-pointer">Not interpreted ({i.not_evaluated.length})</summary>
            <ul className="mt-1 list-disc pl-4">
              {i.not_evaluated.map((n) => <li key={n.measure}>{n.measure.replaceAll("_", " ")}: {n.reason}</li>)}
            </ul>
          </details>
        )}
        <p className="text-xs text-muted">{i.dose_policy}</p>
      </CardContent>
    </Card>
  );
}

export { SoilPage as Component };
