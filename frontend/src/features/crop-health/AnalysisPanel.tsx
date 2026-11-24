import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, FlaskConical, Info, RefreshCw, ScanSearch } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { InlineError } from "@/components/ui/feedback";
import { SpeakButton } from "@/features/voice/VoiceControls";
import { useLocale, useTr } from "@/i18n/useT";
import { cropHealthApi, type Analysis, type ModelInfo } from "@/services/api/cropHealth";
import { errorMessage } from "@/utils/format";
import { InferenceBadge } from "./CaseBits";
import { HeatmapPanel } from "./HeatmapPanel";
import { AVAILABILITY_LABEL, diseaseName } from "./labels";
import { useRetryAnalysis } from "./queries";

const pct = (v: number) => `${Math.round(v * 100)}%`;

/** Held-out evaluation of the MODEL (not of this photo), from the registered package. */
function ModelPerformance({ info }: { info: ModelInfo }) {
  const tr = useTr();
  const m = info.metrics_summary;
  if (!m?.test) return null;
  const row = (label: string, s?: { n: number; accuracy: number; macro_f1: number }) =>
    s && (
      <li className="flex flex-wrap justify-between gap-2">
        <span>{label} <span className="text-muted">(n = {s.n.toLocaleString()})</span></span>
        <span className="tabular">{tr("accuracy", "درستگی")} {pct(s.accuracy)} · macro-F1 {s.macro_f1.toFixed(3)}</span>
      </li>
    );
  return (
    <details className="rounded-[var(--radius-input)] border border-border p-3 text-sm">
      <summary className="flex cursor-pointer items-center gap-2 font-medium text-ink">
        <FlaskConical aria-hidden className="size-4" />{tr("How good is this model? (test results)", "یہ ماڈل کتنا درست ہے؟ (ٹیسٹ نتائج)")}
      </summary>
      <ul className="mt-2 flex flex-col gap-1 text-ink-soft">
        {row(tr("Internal test set (lab-style photos)", "اندرونی ٹیسٹ سیٹ (لیب جیسی تصاویر)"), m.test)}
        {row(tr("External field photos (PlantDoc / PlantWild)", "بیرونی کھیت کی تصاویر (PlantDoc / PlantWild)"), m.external_test)}
      </ul>
      <p className="mt-2 text-xs text-muted">
        {tr("These numbers describe the model on photos it never saw during training. They are not the confidence of your photo, which is shown above.",
          "یہ اعداد اس ماڈل کی کارکردگی ہیں اُن تصاویر پر جو تربیت میں استعمال نہیں ہوئیں۔ یہ آپ کی تصویر کا اعتماد نہیں ہے، جو اوپر دکھایا گیا ہے۔")}
        {" "}{tr("Supported crop:", "معاون فصل:")} {info.supported_crops.join(", ")} · {info.classes.length} {tr("classes", "اقسام")}.
      </p>
    </details>
  );
}

/**
 * Shows analysis state honestly. A result block renders ONLY when inference completed
 * with a registered model; otherwise the status and its explanation are shown.
 */
export function AnalysisPanel({ caseId, analysis }: { caseId: string; analysis: Analysis }) {
  const retry = useRetryAnalysis(caseId);
  const tr = useTr();
  const locale = useLocale();
  const info = useQuery({ queryKey: ["models", "info"], queryFn: cropHealthApi.modelInfo, staleTime: 60_000 });
  const r = analysis.result;
  const name = r?.predicted_class ? diseaseName(r.predicted_class, locale) : "";
  const decisionText: Record<string, string> = {
    unsure: tr("The model is not sure. No diagnosis is given. Take a clearer, closer photo of one affected leaf in daylight, or ask an expert.",
      "ماڈل کو یقین نہیں ہے، اس لیے کوئی تشخیص نہیں دی گئی۔ دن کی روشنی میں ایک متاثرہ پتے کی صاف اور قریب سے تصویر لیں، یا ماہر سے پوچھیں۔"),
    out_of_scope: tr("This photo does not look like the tomato leaves the model was trained on (it may be another crop, not a plant, or unclear). No diagnosis is given.",
      "یہ تصویر اُن ٹماٹر کے پتوں جیسی نہیں جن پر ماڈل تربیت یافتہ ہے (ممکن ہے کوئی اور فصل ہو، پودا نہ ہو، یا تصویر صاف نہ ہو)۔ کوئی تشخیص نہیں دی گئی۔"),
  };
  const speech = r?.decision === "accepted" && name
    ? tr(`Most likely: ${name}. Confidence for this photo ${pct(r.calibrated_confidence)}.`, `زیادہ امکان: ${name}۔ اس تصویر کے لیے اعتماد ${pct(r.calibrated_confidence)}۔`)
    : r ? decisionText[r.decision] ?? "" : "";
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-3">
        <CardTitle>{tr("AI analysis", "مصنوعی ذہانت کا تجزیہ")}</CardTitle>
        <InferenceBadge status={analysis.inference_status} />
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {!r && (
          <div className="flex gap-3 rounded-[var(--radius-input)] bg-surface-raised p-4">
            <ScanSearch aria-hidden className="mt-0.5 size-5 shrink-0 text-muted" />
            <div className="flex flex-col gap-1.5 text-sm">
              <p className="text-ink" role="status">{analysis.message}</p>
              <p className="text-muted">
                {tr("Model status:", "ماڈل کی حالت:")} <Badge tone="neutral">{AVAILABILITY_LABEL[analysis.model_availability]}</Badge>
              </p>
            </div>
          </div>
        )}
        {r && (
          <div className="flex flex-col gap-3">
            {r.decision === "accepted" && r.predicted_class ? (
              <div>
                <p className="text-sm text-muted">{tr("Most likely", "زیادہ امکان")}</p>
                <p className="text-2xl font-semibold text-ink">{name}</p>
                <p className="text-sm text-ink-soft">
                  {tr("Confidence for this photo:", "اس تصویر کے لیے اعتماد:")} <strong className="tabular">{pct(r.calibrated_confidence)}</strong>
                  <span className="text-muted"> {tr("(the model's calibrated estimate; not a guarantee)", "(ماڈل کا کیلیبریٹڈ اندازہ؛ ضمانت نہیں)")}</span>
                </p>
                {r.predicted_class !== "healthy" && (
                  <p className="mt-1 text-xs text-muted">{tr("Severity is not estimated: no validated severity method exists.", "شدت کا اندازہ نہیں لگایا جاتا: اس کا کوئی تصدیق شدہ طریقہ موجود نہیں۔")}</p>
                )}
              </div>
            ) : (
              <div className="flex gap-3 rounded-[var(--radius-input)] bg-warning-soft p-4 text-sm text-ink" role="status">
                <AlertTriangle aria-hidden className="mt-0.5 size-5 shrink-0 text-warning" />
                {decisionText[r.decision] ?? tr("No definitive diagnosis.", "کوئی حتمی تشخیص نہیں۔")}
              </div>
            )}
            {speech && <SpeakButton text={speech} label="Listen" />}
            {/* Out of scope: the photo is unlike the training data, so class probabilities are not meaningful. */}
            {r.shortlist.length > 0 && r.decision !== "out_of_scope" && (
              <div>
                <p className="mb-1.5 text-sm font-medium text-ink">{tr("Possibilities considered (this photo)", "زیر غور امکانات (اس تصویر کے لیے)")}</p>
                <ul className="flex flex-col gap-1.5">
                  {r.shortlist.map((s) => (
                    <li key={String(s.label)} className="flex items-center gap-3 text-sm">
                      <span className="w-44 truncate text-ink-soft">{diseaseName(String(s.label), locale)}</span>
                      <span className="h-2 flex-1 overflow-hidden rounded-full bg-border" aria-hidden>
                        <span className="block h-full bg-primary/70" style={{ width: pct(Number(s.probability)) }} />
                      </span>
                      <span className="tabular w-10 text-end text-muted">{pct(Number(s.probability))}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {info.data && <ModelPerformance info={info.data} />}
            <p className="flex gap-2 text-sm text-muted">
              <Info aria-hidden className="mt-0.5 size-4 shrink-0" />
              <span>{r.limits_note} {tr("Model", "ماڈل")} {r.model_name} {r.model_version} · {tr("analysed", "تجزیہ")} {new Date(r.analysed_at).toLocaleString()}.</span>
            </p>
            {r.explanation_available ? <HeatmapPanel caseId={caseId} /> : r.decision !== "out_of_scope" && (
              <p className="border-t border-border pt-4 text-sm text-muted">
                {tr("No heatmap for this result: this model version does not provide a validated explanation map.",
                  "اس نتیجے کے لیے ہیٹ میپ دستیاب نہیں: یہ ماڈل ورژن تصدیق شدہ وضاحتی نقشہ فراہم نہیں کرتا۔")}
              </p>
            )}
          </div>
        )}
        {retry.isError && <InlineError message={errorMessage(retry.error)} />}
        {analysis.can_retry && (
          <Button variant="secondary" className="self-start" disabled={retry.isPending} onClick={() => retry.mutate()}>
            <RefreshCw aria-hidden />
            {retry.isPending ? tr("Requesting…", "درخواست بھیجی جا رہی ہے…") : tr("Request analysis again", "دوبارہ تجزیہ کریں")}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
