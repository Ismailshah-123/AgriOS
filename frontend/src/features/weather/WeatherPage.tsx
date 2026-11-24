import { AlertTriangle, CloudOff, Droplets, MapPin, Wind } from "lucide-react";
import { Link } from "react-router";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState, LoadingRows } from "@/components/ui/feedback";
import { OriginBadge } from "@/components/ui/origin-badge";
import { FieldGate, FieldPicker } from "@/features/intelligence/FieldPicker";
import { useSelectedField } from "@/features/intelligence/useSelectedField";
import { useWeather } from "@/features/intelligence/queries";
import type { WeatherIndicator, WeatherReport } from "@/services/api/intelligence";
import { errorMessage, formatDate } from "@/utils/format";
import { DailyChart } from "./DailyChart";
import { WaterDemandCard } from "./WaterDemandCard";

const LEVEL_TONE = { info: "info", watch: "warning", warning: "danger" } as const;
const n = (v: number | null | undefined, unit: string) => (v == null ? "—" : `${v} ${unit}`);
const day = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric" });

export function WeatherPage() {
  const sel = useSelectedField();
  return (
    <>
      <PageHeader
        title="Weather Intelligence"
        description="Forecast for the selected field's farm location, with cited agricultural risk indicators. Weather risk is never a disease diagnosis."
        actions={
          sel.field && (
            <FieldPicker value={sel.fieldId} onChange={sel.setFieldId} fields={sel.fields.data?.items ?? []} />
          )
        }
      />
      <FieldGate sel={sel}>
        <WeatherBody fieldId={sel.fieldId} />
      </FieldGate>
    </>
  );
}

function WeatherBody({ fieldId }: { fieldId: string }) {
  const q = useWeather(fieldId);
  if (q.isPending) return <Card><LoadingRows label="Loading weather" /></Card>;
  if (q.isError) {
    return <Card><ErrorState message={errorMessage(q.error)} onRetry={() => q.refetch()} /></Card>;
  }
  const w = q.data;
  if (w.status === "unavailable") return <Unavailable w={w} />;
  return (
    <div className="grid gap-4">
      <SourceBar w={w} />
      <div className="grid gap-4 lg:grid-cols-3">
        <CurrentCard w={w} />
        <div className="grid gap-4 lg:col-span-2">
          <RiskCards indicators={w.indicators} notEvaluated={w.not_evaluated} />
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Daily temperature range ({w.units.temperature})</CardTitle>
            <CardDescription>Forecast minimum to maximum, 2 m air temperature.</CardDescription>
          </CardHeader>
          <CardContent>
            <DailyChart range title="Temperature" unit={w.units.temperature ?? "°C"} points={w.daily.map((d) => ({
              label: day(d.date), low: d.temperature_min_c, high: d.temperature_max_c,
              tooltip: `${formatDate(d.date)}: ${n(d.temperature_min_c, "°C")} to ${n(d.temperature_max_c, "°C")}`,
            }))} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Daily rainfall ({w.units.precipitation})</CardTitle>
            <CardDescription>Forecast total per day (gross, not effective rain).</CardDescription>
          </CardHeader>
          <CardContent>
            <DailyChart title="Rainfall" unit="mm" points={w.daily.map((d) => ({
              label: day(d.date), high: d.precipitation_sum_mm,
              tooltip: `${formatDate(d.date)}: ${n(d.precipitation_sum_mm, "mm")} (chance ${n(d.precipitation_probability_max_pct, "%")})`,
            }))} />
          </CardContent>
        </Card>
      </div>
      <DailyTable w={w} />
      <HourlyTable w={w} />
      <WaterDemandCard fieldId={fieldId} />
      <p className="text-xs text-muted">{w.disclaimer}</p>
    </div>
  );
}

function Unavailable({ w }: { w: WeatherReport }) {
  const noLocation = w.reason === "location_missing";
  return (
    <Card>
      <EmptyState
        icon={noLocation ? MapPin : CloudOff}
        title={noLocation ? "This farm has no location yet" : "Weather is unavailable right now"}
        description={
          noLocation
            ? `Add approximate coordinates to ${w.location.farm_name} to get a forecast. AgriOS never guesses a location.`
            : `The weather provider could not be reached (${w.reason}). No cached forecast is recent enough to show, and no values are invented.`
        }
        action={noLocation ? <Button asChild><Link to={`/farms/${w.location.farm_id}`}>Edit farm location</Link></Button> : undefined}
      />
    </Card>
  );
}

function SourceBar({ w }: { w: WeatherReport }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-border bg-card px-4 py-3 text-sm">
      <OriginBadge origin="retrieved" />
      <span className="text-ink">
        {w.location.farm_name} ({w.location.latitude}, {w.location.longitude})
      </span>
      <span className="text-muted">
        Updated {w.retrieved_at ? new Date(w.retrieved_at).toLocaleString() : "—"} ({w.age_minutes} min ago)
      </span>
      {w.status === "stale" && (
        <Badge tone="warning"><AlertTriangle aria-hidden className="size-3" /> Stale: provider unreachable, showing last forecast</Badge>
      )}
      {w.provider && (
        <span className="text-muted">
          Source: <a className="underline" href={w.provider.url} target="_blank" rel="noreferrer">{w.provider.name}</a> · {w.provider.licence}
        </span>
      )}
    </div>
  );
}

function CurrentCard({ w }: { w: WeatherReport }) {
  const c = w.current;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Current conditions</CardTitle>
        <CardDescription>{c?.time ? `Model time ${c.time} (${w.timezone})` : "No current observation"}</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div><dt className="text-muted">Temperature</dt><dd className="text-2xl font-semibold text-ink">{n(c?.temperature_c, "°C")}</dd></div>
          <div><dt className="text-muted">Humidity</dt><dd className="text-2xl font-semibold text-ink">{n(c?.relative_humidity_pct, "%")}</dd></div>
          <div><dt className="flex items-center gap-1 text-muted"><Wind aria-hidden className="size-3.5" />Wind</dt><dd className="text-ink">{n(c?.wind_speed_kmh, "km/h")}</dd></div>
          <div><dt className="flex items-center gap-1 text-muted"><Droplets aria-hidden className="size-3.5" />Rain now</dt><dd className="text-ink">{n(c?.precipitation_mm, "mm")}</dd></div>
        </dl>
      </CardContent>
    </Card>
  );
}

function RiskCards({ indicators, notEvaluated }: {
  indicators: WeatherIndicator[];
  notEvaluated: { indicator: string; reason: string }[];
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Agricultural risk indicators</CardTitle>
        <CardDescription>Deterministic rules with a cited basis. Indicators describe weather only.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        {indicators.length === 0 && <p className="text-sm text-muted">No indicator was triggered for this forecast.</p>}
        {indicators.map((i) => (
          <article key={i.id} className="rounded-md border border-border p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={LEVEL_TONE[i.level]}>{i.level}</Badge>
              <h3 className="text-sm font-semibold text-ink">{i.id.replaceAll("_", " ")}</h3>
              {i.time_window && <span className="text-xs text-muted">{formatDate(i.time_window.start)} – {formatDate(i.time_window.end)}</span>}
            </div>
            <p className="mt-1 text-sm text-ink">{i.message}</p>
            <details className="mt-1 text-xs text-muted">
              <summary className="cursor-pointer">Basis, source and limitations</summary>
              <p className="mt-1">{i.basis}</p>
              <p className="mt-1">Source: {i.source} ({i.review_status.replaceAll("_", " ")})</p>
              {i.limitations && <p className="mt-1">Limitation: {i.limitations}</p>}
            </details>
          </article>
        ))}
        {notEvaluated.length > 0 && (
          <p className="text-xs text-muted">
            Not evaluated: {notEvaluated.map((x) => `${x.indicator.replaceAll("_", " ")} (${x.reason})`).join("; ")}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function DailyTable({ w }: { w: WeatherReport }) {
  return (
    <Card>
      <CardHeader><CardTitle>7-day forecast</CardTitle></CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-muted">
            <tr><th className="py-1 pr-3">Date</th><th className="pr-3">Min / max</th><th className="pr-3">Rain</th><th className="pr-3">Chance</th><th className="pr-3">Max wind</th><th>ET0 (FAO-56)</th></tr>
          </thead>
          <tbody>
            {w.daily.map((d) => (
              <tr key={d.date} className="border-t border-border text-ink">
                <td className="py-1 pr-3">{formatDate(d.date)}</td>
                <td className="pr-3">{n(d.temperature_min_c, "")} / {n(d.temperature_max_c, "°C")}</td>
                <td className="pr-3">{n(d.precipitation_sum_mm, "mm")}</td>
                <td className="pr-3">{n(d.precipitation_probability_max_pct, "%")}</td>
                <td className="pr-3">{n(d.wind_speed_max_kmh, "km/h")}</td>
                <td>{n(d.et0_fao_mm, "mm")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function HourlyTable({ w }: { w: WeatherReport }) {
  const next = w.hourly.slice(0, 24).filter((_, i) => i % 3 === 0);
  if (next.length === 0) return null;
  return (
    <Card>
      <CardHeader><CardTitle>Next 24 hours (3-hourly)</CardTitle></CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-muted">
            <tr><th className="py-1 pr-3">Time</th><th className="pr-3">Temp</th><th className="pr-3">Humidity</th><th className="pr-3">Rain</th><th>Chance</th></tr>
          </thead>
          <tbody>
            {next.map((h) => (
              <tr key={h.time} className="border-t border-border text-ink">
                <td className="py-1 pr-3">{h.time.replace("T", " ")}</td>
                <td className="pr-3">{n(h.temperature_c, "°C")}</td>
                <td className="pr-3">{n(h.relative_humidity_pct, "%")}</td>
                <td className="pr-3">{n(h.precipitation_mm, "mm")}</td>
                <td>{n(h.precipitation_probability_pct, "%")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

export { WeatherPage as Component };
