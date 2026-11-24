import { useState } from "react";
import { useLocale, useTr } from "@/i18n/useT";
import { ErrorState, LoadingRows } from "@/components/ui/feedback";
import type { Explanation } from "@/services/api/cropHealth";
import { errorMessage } from "@/utils/format";
import { diseaseName } from "./labels";
import { useExplanation } from "./queries";

type CamMap = Explanation["maps"][number];

/**
 * Class activation map over the analysed photo. The grid covers only the model's centre
 * crop (crop_box), so it is positioned there; outside it the model saw nothing.
 * Single-hue sequential scale (transparent -> warm), with a legend; opacity is adjustable.
 */
function Overlay({ m, opacity, index }: { m: CamMap; opacity: number; index: number }) {
  const tr = useTr();
  const locale = useLocale();
  const [l, t, w, h] = m.crop_box.map((v) => `${(v * 100).toFixed(2)}%`);
  const rows = m.grid.length, cols = m.grid[0]?.length ?? 0;
  return (
    <figure className="flex flex-col gap-1.5">
      <div className="relative overflow-hidden rounded-[var(--radius-input)] bg-surface"
        style={{ aspectRatio: `${m.image.width} / ${m.image.height}` }}>
        <img src={m.image.url} alt={`Analysed photo ${index + 1}`} className="absolute inset-0 size-full object-fill" />
        <div aria-hidden className="absolute grid outline outline-1 outline-dashed outline-white/80"
          style={{ left: l, top: t, width: w, height: h,
            gridTemplateColumns: `repeat(${cols}, 1fr)`, gridTemplateRows: `repeat(${rows}, 1fr)`, opacity }}>
          {m.grid.flatMap((row, r) => row.map((v, c) => (
            <span key={`${r}-${c}`} style={{ backgroundColor: `rgba(217, 72, 15, ${Math.min(1, Math.max(0, v)) * 0.85})` }} />
          )))}
        </div>
      </div>
      <figcaption className="flex flex-col gap-1 text-xs text-muted">
        <span>{tr(`Photo ${index + 1}. Dashed box = area the model analysed.`, `تصویر ${index + 1}۔ نقطہ دار خانہ = وہ حصہ جس کا ماڈل نے تجزیہ کیا۔`)}</span>
        {m.focus && <span className="text-sm text-ink" lang={locale}>{locale === "ur" ? m.focus.text_ur : m.focus.text_en}</span>}
      </figcaption>
    </figure>
  );
}

export function HeatmapPanel({ caseId, scope = "owner" }: { caseId: string; scope?: "owner" | "review" }) {
  const q = useExplanation(caseId, scope);
  const tr = useTr();
  const locale = useLocale();
  const [opacity, setOpacity] = useState(0.6);
  if (q.isPending) return <LoadingRows rows={2} label="Loading explanation" />;
  if (q.isError) return <ErrorState message={errorMessage(q.error)} onRetry={() => q.refetch()} />;
  const e = q.data;
  if (!e.available) return null;
  return (
    <section aria-labelledby="cam-title" className="flex flex-col gap-3 border-t border-border pt-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="cam-title" className="text-sm font-semibold text-ink">
          {tr("Where the model looked", "ماڈل نے کہاں دیکھا")}{e.target_class ? `: ${diseaseName(e.target_class, locale)}` : ""}
        </h3>
        <label className="flex items-center gap-2 text-xs text-muted">
          {tr("Heatmap strength", "ہیٹ میپ کی شدت")}
          <input type="range" min={0} max={1} step={0.1} value={opacity}
            onChange={(ev) => setOpacity(Number(ev.target.value))} className="accent-[var(--color-primary)]" />
        </label>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {e.maps.map((m, i) => <Overlay key={m.image.id} m={m} opacity={opacity} index={i} />)}
      </div>
      <div className="flex items-center gap-2 text-xs text-muted" aria-label="Heatmap legend">
        <span>{tr("Low", "کم")}</span>
        <span aria-hidden className="h-2 w-24 rounded-full" style={{ background: "linear-gradient(to right, rgba(217,72,15,0), rgba(217,72,15,0.85))" }} />
        <span>{tr("High: regions that raised the score for this class", "زیادہ: وہ حصے جنہوں نے اس نتیجے کو بڑھایا")}</span>
      </div>
      <p className="text-xs text-muted">
        {tr(`Red areas are where the model found the visual evidence for its answer. ${e.note} Method: class activation map (equal to Grad-CAM for this model's final layer; ${e.model_name} ${e.model_version}). It is not proof of the cause, does not mark disease boundaries and does not measure severity. SHAP is not used: it explains tabular inputs, and this model uses only the photo.`,
          "سرخ حصے وہ ہیں جہاں ماڈل کو اپنے جواب کے لیے نشانات ملے۔ یہ وجہ کا ثبوت نہیں، بیماری کی حد یا شدت نہیں بتاتا۔ طریقہ: کلاس ایکٹیویشن میپ (اس ماڈل کے لیے Grad-CAM کے برابر)۔ SHAP استعمال نہیں ہوا کیونکہ یہ ماڈل صرف تصویر استعمال کرتا ہے۔")}
      </p>
    </section>
  );
}
