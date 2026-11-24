import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Camera, Send, ShieldAlert } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InlineError, LoadingRows } from "@/components/ui/feedback";
import { Select, Textarea } from "@/components/ui/input";
import { OriginBadge } from "@/components/ui/origin-badge";
import { AnswerText, Citations } from "@/features/knowledge/AnswerCard";
import { MicButton, SpeakButton } from "@/features/voice/VoiceControls";
import { useLocale, useTr } from "@/i18n/useT";
import { cropHealthApi } from "@/services/api/cropHealth";
import { knowledgeApi, warningText, type AskResult } from "@/services/api/knowledge";
import { errorMessage } from "@/utils/format";

function Reply({ r }: { r: AskResult }) {
  const tr = useTr();
  const sec = r.meta.sections;
  const photoSent = r.meta.photo_sent;
  const ur = r.language === "ur";
  const block = (title: string, text: string, badge?: ReactNode) =>
    text ? (
      <section className="flex flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2"><h4 className="text-sm font-semibold text-ink">{title}</h4>{badge}</div>
        <div dir={ur ? "rtl" : "ltr"} lang={ur ? "ur" : "en"}><AnswerText text={text} /></div>
      </section>
    ) : null;
  return (
    <article className="flex flex-col gap-3 rounded-[var(--radius-card)] border border-border bg-card p-4" aria-label={tr("Assistant answer", "معاون کا جواب")}>
      <p className="self-end rounded-[var(--radius-card)] bg-primary-soft px-3 py-2 text-sm text-primary-dark" dir="auto">{r.question}</p>
      {r.status === "abstained" && <p className="flex gap-2 text-sm"><ShieldAlert aria-hidden className="size-5 text-warning" />{tr("No verified source covers this question. Please ask an expert.", "کوئی تصدیق شدہ ذریعہ اس سوال کا احاطہ نہیں کرتا۔ براہِ کرم ماہر سے پوچھیں۔")}</p>}
      {sec ? (
        <>
          {block(tr("What the AI sees in the photo", "AI کو تصویر میں کیا نظر آتا ہے"), sec.seen_in_photo,
            <Badge tone="warning">{tr("AI description, not verified, not a diagnosis", "AI کی وضاحت — غیر تصدیق شدہ، تشخیص نہیں")}</Badge>)}
          {block(tr("What it means", "اس کا مطلب"), sec.explanation, <OriginBadge origin="retrieved" />)}
          {block(tr("What to check next", "آگے کیا دیکھیں"), sec.next_steps)}
        </>
      ) : r.answer && <div dir={ur ? "rtl" : "ltr"}><AnswerText text={r.answer} /></div>}
      {r.meta.warnings.length > 0 && (
        <ul className="text-xs text-warning">{r.meta.warnings.map((w) => <li key={w}>• {w === "no_validated_diagnosis_expert_review_advised"
          ? tr("There is no validated diagnosis for this case: ask an expert (button above).", "اس کیس کی کوئی تصدیق شدہ تشخیص نہیں: ماہر سے رجوع کریں۔")
          : w === "vision_model_unavailable" ? tr("The image AI is not available; answered from the case record only.", "تصویری AI دستیاب نہیں؛ جواب صرف کیس ریکارڈ سے دیا گیا۔")
          : w === "llm_disabled" ? tr("No language model configured: quoted passages only.", "کوئی لینگویج ماڈل نہیں: صرف حوالہ جات۔") : warningText(w)}</li>)}</ul>
      )}
      <Citations items={r.citations} />
      <div className="flex flex-wrap items-center gap-2 border-t border-border pt-2 text-xs text-muted">
        {r.answer && <SpeakButton text={r.meta.speech_text} label="Listen" lang={r.language} />}
        <span>{r.llm_model ? `${r.llm_provider}/${r.llm_model}` : tr("no language model", "کوئی لینگویج ماڈل نہیں")}{photoSent ? tr(" · photo sent to the AI service", " · تصویر AI سروس کو بھیجی گئی") : ""} · {r.total_ms} ms</span>
      </div>
    </article>
  );
}

/** Ask the AI assistant about this case. The model's result stays the diagnosis. */
export function AssistantPanel({ caseId }: { caseId: string }) {
  const tr = useTr();
  const locale = useLocale();
  const qc = useQueryClient();
  const [language, setLanguage] = useState<"en" | "ur">(locale);
  const [question, setQuestion] = useState("");
  const [sendPhoto, setSendPhoto] = useState(false);
  const hist = useQuery({ queryKey: ["cases", caseId, "assistant"], queryFn: () => cropHealthApi.assistantHistory(caseId) });
  const stats = useQuery({ queryKey: ["knowledge", "stats"], queryFn: knowledgeApi.stats, staleTime: 60_000 });
  const vision = stats.data?.providers.vision;
  const ask = useMutation({
    mutationFn: (q?: string) => cropHealthApi.askAssistant(caseId, { question: q, language, send_photo: sendPhoto }),
    onSuccess: () => { setQuestion(""); void qc.invalidateQueries({ queryKey: ["cases", caseId, "assistant"] }); },
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    if (question.trim().length >= 3) ask.mutate(question.trim());
  }
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2"><Bot aria-hidden className="size-5 text-primary" /><CardTitle>{tr("Ask the AI assistant about this case", "اس کیس کے بارے میں AI معاون سے پوچھیں")}</CardTitle></div>
        <CardDescription>{tr("Explains the result in English or Urdu using verified sources, with citations, and can read it aloud. The diagnosis remains the trained model's result above; the assistant never gives pesticide or fertilizer doses.",
          "تصدیق شدہ ذرائع کی مدد سے انگریزی یا اردو میں نتیجہ سمجھاتا ہے اور سنا بھی سکتا ہے۔ تشخیص اوپر دیا گیا تربیت یافتہ ماڈل کا نتیجہ ہی ہے؛ معاون کبھی دوا یا کھاد کی مقدار نہیں بتاتا۔")}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {hist.isPending && <LoadingRows rows={2} label={tr("Loading", "لوڈ ہو رہا ہے")} />}
        {hist.data?.map((r) => <Reply key={r.id} r={r} />)}
        {ask.isPending && <LoadingRows rows={3} label={tr("The assistant is preparing an answer", "معاون جواب تیار کر رہا ہے")} />}
        <form onSubmit={submit} className="flex flex-col gap-3">
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex flex-col gap-1 text-xs text-muted">{tr("Answer language", "جواب کی زبان")}
              <Select value={language} onChange={(e) => setLanguage(e.target.value as "en" | "ur")}>
                <option value="en">English</option><option value="ur">اردو</option>
              </Select></label>
            <label className="flex max-w-md items-start gap-2 text-sm text-ink-soft">
              <input type="checkbox" className="mt-1" checked={sendPhoto} disabled={vision ? !vision.enabled : false} onChange={(e) => setSendPhoto(e.target.checked)} />
              <span><Camera aria-hidden className="me-1 inline size-4" />{tr("Also let the AI look at my photo", "AI کو میری تصویر بھی دیکھنے دیں")}
                <span className="block text-xs text-muted">{tr(`The photo is sent to an external AI service (${vision?.model ?? "Groq"}). Leave unticked to keep it private.`, `تصویر ایک بیرونی AI سروس (${vision?.model ?? "Groq"}) کو بھیجی جائے گی۔ نجی رکھنے کے لیے نشان نہ لگائیں۔`)}</span></span>
            </label>
          </div>
          <Button type="button" variant="secondary" className="self-start" disabled={ask.isPending} onClick={() => ask.mutate(undefined)}>
            <Bot aria-hidden />{tr("Explain my result", "میرا نتیجہ سمجھائیں")}
          </Button>
          <label htmlFor="cd-q" className="text-sm font-medium text-ink">{tr("Or ask your own question", "یا اپنا سوال پوچھیں")}</label>
          <Textarea id="cd-q" dir="auto" rows={2} maxLength={600} value={question} onChange={(e) => setQuestion(e.target.value)}
            placeholder={tr("e.g. How does this disease spread? Can it affect my other plants?", "مثلاً یہ بیماری کیسے پھیلتی ہے؟ کیا یہ دوسرے پودوں کو متاثر کر سکتی ہے؟")} />
          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" disabled={question.trim().length < 3 || ask.isPending}><Send aria-hidden />{tr("Ask", "پوچھیں")}</Button>
            <MicButton onText={(t) => setQuestion(t)} />
          </div>
          {ask.isError && <InlineError message={errorMessage(ask.error)} />}
        </form>
      </CardContent>
    </Card>
  );
}
