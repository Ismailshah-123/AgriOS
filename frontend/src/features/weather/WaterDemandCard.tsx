import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, LoadingRows } from "@/components/ui/feedback";
import { OriginBadge } from "@/components/ui/origin-badge";
import { useWaterDemand } from "@/features/intelligence/queries";
import { errorMessage } from "@/utils/format";

const MISSING_LABEL: Record<string, string> = {
  active_crop_cycle: "an active crop cycle on this field",
  "crop_cycle.sowing_date": "the sowing / transplanting date of the crop cycle",
  "weather:location_missing": "farm coordinates",
};

/** FAO-56 ETc estimate. Labelled inferred; never shown as soil moisture or an irrigation order. */
export function WaterDemandCard({ fieldId }: { fieldId: string }) {
  const q = useWaterDemand(fieldId);
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle>Crop water demand (ETc)</CardTitle>
          <OriginBadge origin="inferred" />
        </div>
        <CardDescription>ETc = Kc × ET0 (FAO-56). An estimate of crop water use, not measured soil moisture.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-2 text-sm">
        {q.isPending && <LoadingRows rows={2} label="Loading water demand" />}
        {q.isError && <ErrorState message={errorMessage(q.error)} onRetry={() => q.refetch()} />}
        {q.isSuccess && q.data.status !== "ok" && (
          <p className="text-ink">
            Cannot estimate yet. Missing:{" "}
            {q.data.missing_information.map((m) => MISSING_LABEL[m] ?? m.replaceAll("_", " ")).join(", ")}.
          </p>
        )}
        {q.isSuccess && q.data.status === "ok" && q.data.totals && (
          <>
            <p className="text-ink">
              {q.data.crop}, stage <strong>{q.data.current_stage?.replaceAll("_", " ")}</strong> (day {q.data.days_after_planting} after planting).
              Next {q.data.totals.days} days: estimated demand{" "}
              <strong>{q.data.totals.etc_low_mm}–{q.data.totals.etc_high_mm} mm</strong> (ET0 {q.data.totals.et0_mm} mm), forecast gross rain{" "}
              {q.data.totals.gross_rain_mm ?? "—"} mm.
            </p>
            <details className="text-xs text-muted">
              <summary className="cursor-pointer">Method, source and limitations</summary>
              <p className="mt-1">{q.data.source}</p>
              <ul className="mt-1 list-disc pl-4">{q.data.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
            </details>
          </>
        )}
      </CardContent>
    </Card>
  );
}
