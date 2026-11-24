import { useMutation, useQuery } from "@tanstack/react-query";
import { BookOpen, Copy, ExternalLink, FileText, ShieldAlert, ThumbsDown, ThumbsUp } from "lucide-react";
import { Fragment, useState, type ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { ErrorState, LoadingRows } from "@/components/ui/feedback";
import { OriginBadge } from "@/components/ui/origin-badge";
import { SpeakButton } from "@/features/voice/VoiceControls";
import { knowledgeApi, openSourceFile, warningText, type AskResult, type Citation, type FarmContext } from "@/services/api/knowledge";
import { errorMessage } from "@/utils/format";
import { useL } from "@/i18n/useT";

const STATUS: Record<string, { label: string; tone: "success" | "info" | "warning" | "danger" | "neutral" }> = {
  answered: { label: "Grounded answer", tone: "success" },
  extractive: { label: "Quoted passages", tone: "info" },
  abstained: { label: "No verified guidance", tone: "warning" },
  clarify: { label: "Needs more detail", tone: "neutral" },
  error: { label: "Error", tone: "danger" },
};
const QUALITY: Record<string, string> = {
  multiple_sources: "Supported by passages from several sources",
  single_source_multiple_passages: "Supported by several passages of one source",
  single_passage: "Supported by a single passage",
  none: "No supporting passage",
};

/** Minimal, safe rendering: paragraphs, "- " bullets, **bold**, [S1] markers as chips. */
function Inline({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*|\[(?:S\d+|F)\])/g);
  return (
    <>
      {parts.map((p, i) => {
        if (/^\*\*[^*]+\*\*$/.test(p)) return <strong key={i}>{p.slice(2, -2)}</strong>;
        if (/^\[(S\d+|F)\]$/.test(p)) {
          return <sup key={i} className="mx-0.5 rounded bg-primary-soft px-1 text-[0.7rem] font-semibold text-primary-dark">{p.slice(1, -1)}</sup>;
        }
        return <Fragment key={i}>{p}</Fragment>;
      })}
    </>
  );
}

export function AnswerText({ text }: { text: string }) {
  const blocks = text.split(/\n{2,}/);
  return (
    <div className="flex flex-col gap-2 text-sm leading-relaxed text-ink">
      {blocks.map((b, i) => {
        const lines = b.split("\n").filter((l) => l.trim());
        if (lines.length && lines.every((l) => /^\s*[-*•]\s+/.test(l))) {
          return <ul key={i} className="list-disc ps-5">{lines.map((l, j) => <li key={j}><Inline text={l.replace(/^\s*[-*•]\s+/, "")} /></li>)}</ul>;
        }
        if (lines.every((l) => l.startsWith(">"))) {
          return <blockquote key={i} className="border-s-2 border-border-strong ps-3 text-ink-soft">{lines.map((l, j) => <p key={j}><Inline text={l.replace(/^>\s?/, "")} /></p>)}</blockquote>;
        }
        return <p key={i}><Inline text={lines.join(" ")} /></p>;
      })}
    </div>
  );
}

function SourceViewer({ c }: { c: Citation }) {
  const [open, setOpen] = useState(false);
  const q = useQuery({ queryKey: ["knowledge", "chunk", c.chunk_id], queryFn: () => knowledgeApi.chunk(c.chunk_id), enabled: open });
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm"><BookOpen aria-hidden />Open source</Button>
      </DialogTrigger>
      <DialogContent title={c.title} description={`${c.publisher}${c.year ? ` (${c.year})` : ""} · licence: ${c.licence}`} className="max-w-2xl">
        <div className="flex flex-col gap-3 overflow-y-auto p-5 text-sm">
          {q.isPending && <LoadingRows rows={3} label="Loading passage" />}
          {q.isError && <ErrorState message={errorMessage(q.error)} onRetry={() => q.refetch()} />}
          {q.isSuccess && (
            <>
              {q.data.context.map((n) => (
                <div key={n.id} className={n.is_cited ? "rounded-[var(--radius-input)] border-2 border-primary p-3" : "rounded-[var(--radius-input)] border border-border p-3 text-ink-soft"}>
                  <p className="mb-1 text-xs text-muted">{n.is_cited ? "Cited passage" : "Nearby passage"}{n.page ? ` · p. ${n.page}` : ""}{n.section ? ` · ${n.section}` : ""}</p>
                  <p className="whitespace-pre-line">{n.text}</p>
                </div>
              ))}
              {q.data.source.attribution && <p className="text-xs text-muted">Attribution: {q.data.source.attribution}</p>}
              <div className="flex flex-wrap gap-2">
                {q.data.source.url && <Button asChild variant="secondary" size="sm"><a href={q.data.source.url} target="_blank" rel="noreferrer"><ExternalLink aria-hidden />Original page</a></Button>}
                {q.data.source.has_file && <Button variant="secondary" size="sm" onClick={() => void openSourceFile(q.data.source.id)}><FileText aria-hidden />Stored copy</Button>}
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function Citations({ items }: { items: Citation[] }) {
  if (!items.length) return null;
  const cited = items.filter((c) => c.cited);
  const other = items.filter((c) => !c.cited);
  const row = (c: Citation) => (
    <li key={c.chunk_id} className="rounded-[var(--radius-input)] border border-border p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={c.cited ? "success" : "neutral"}>{c.marker}</Badge>
        <span className="font-medium text-ink">{c.title}</span>
      </div>
      <p className="mt-1 text-xs text-muted">
        {c.publisher}{c.year ? ` (${c.year})` : ""}{c.page ? ` · p. ${c.page}` : ""}{c.section ? ` · ${c.section}` : ""} · licence: {c.licence} · {c.review_status.replaceAll("_", " ")}
      </p>
      <p className="mt-2 line-clamp-3 text-ink-soft">“{c.text}”</p>
      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
        <span>matched by {c.matched_by.join(" + ").replaceAll("_", " ")}{c.dense_score !== null ? ` · semantic ${c.dense_score.toFixed(2)}` : ""}</span>
        <SourceViewer c={c} />
      </div>
    </li>
  );
  return (
    <section aria-label="Sources" className="flex flex-col gap-2">
      <div className="flex items-center gap-2"><h3 className="text-sm font-semibold text-ink">Sources</h3><OriginBadge origin="retrieved" /></div>
      <ol className="flex flex-col gap-2">{cited.map(row)}</ol>
      {other.length > 0 && (
        <details className="text-sm"><summary className="cursor-pointer text-muted">Also retrieved, not cited ({other.length})</summary>
          <ol className="mt-2 flex flex-col gap-2">{other.map(row)}</ol></details>
      )}
    </section>
  );
}

function FarmRecords({ ctx }: { ctx: FarmContext }) {
  return (
    <section aria-label="Your farm records" className="rounded-[var(--radius-input)] bg-surface p-3 text-sm">
      <div className="mb-2 flex flex-wrap items-center gap-2"><h3 className="font-semibold text-ink">Your farm records used</h3><OriginBadge origin="farmer_entered" /></div>
      {ctx.empty ? <p className="text-muted">No fields are recorded yet.</p> : (
        <ul className="flex flex-col gap-1.5">
          {ctx.fields.map((f) => (
            <li key={`${f.farm}-${f.field}`}>
              <span className="font-medium">{f.field}</span> ({f.farm}, {f.area_ha} ha)
              {f.cycles.length > 0 && <> · {f.cycles.map((c) => `${c.crop} (${c.status}${c.days_after_sowing !== null ? `, day ${c.days_after_sowing}` : ""})`).join(", ")}</>}
              {f.latest_soil_test && <> · soil {f.latest_soil_test.sampled_on}: {Object.entries(f.latest_soil_test.values).map(([k, v]) => `${k} ${v}`).join(", ") || "no values"}</>}
            </li>
          ))}
        </ul>
      )}
      {ctx.economics && <p className="mt-1">Recorded expenses PKR {ctx.economics.recorded_expenses_pkr ?? "—"} · revenue PKR {ctx.economics.recorded_revenue_pkr ?? "—"}</p>}
      {ctx.missing.length > 0 && <p className="mt-1 text-warning">Missing: {ctx.missing.join("; ")}</p>}
    </section>
  );
}

export function AnswerCard({ r, followUp }: { r: AskResult; followUp?: ReactNode }) {
  const l = useL();
  const [rating, setRating] = useState<number | null>(r.feedback_rating);
  const [copied, setCopied] = useState(false);
  const fb = useMutation({ mutationFn: (v: 1 | -1) => knowledgeApi.feedback(r.id, v), onSuccess: (_, v) => setRating(v) });
  const st = STATUS[r.status] ?? STATUS.error!;
  const generated = r.status === "answered";
  const rtl = r.language === "ur";
  return (
    <article className="flex flex-col gap-3 rounded-[var(--radius-card)] border border-border bg-card p-4" aria-label="Answer">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={st.tone}>{l(st.label)}</Badge>
        {generated && <Badge tone="warning">{l("AI-written from cited sources")}</Badge>}
        {r.meta.escalate_to_expert && <Badge tone="danger">{l("Ask an expert")}</Badge>}
        <span className="text-xs text-muted">{QUALITY[r.meta.evidence_quality]}</span>
      </div>
      {r.status === "abstained" && <div className="flex gap-2 text-sm"><ShieldAlert aria-hidden className="size-5 shrink-0 text-warning" /><p role="status">{r.answer}</p></div>}
      {r.status !== "abstained" && r.answer && <div dir={rtl ? "rtl" : "ltr"} lang={rtl ? "ur" : undefined}><AnswerText text={r.answer} /></div>}
      {r.meta.warnings.length > 0 && (
        <ul className="flex flex-col gap-1 text-xs text-warning">{r.meta.warnings.map((w) => <li key={w}>• {warningText(w)}</li>)}</ul>
      )}
      {r.meta.farm_context && <FarmRecords ctx={r.meta.farm_context} />}
      <Citations items={r.citations} />
      <div className="flex flex-wrap items-center gap-1 border-t border-border pt-2">
        {r.answer && <SpeakButton text={r.meta.speech_text} label="Listen" />}
        {r.answer && (
          <Button variant="ghost" size="sm" onClick={() => { void navigator.clipboard?.writeText(r.answer ?? ""); setCopied(true); }}>
            <Copy aria-hidden />{copied ? l("Copied") : l("Copy")}
          </Button>
        )}
        <Button variant="ghost" size="sm" aria-pressed={rating === 1} onClick={() => fb.mutate(1)} disabled={fb.isPending}><ThumbsUp aria-hidden />{l("Helpful")}</Button>
        <Button variant="ghost" size="sm" aria-pressed={rating === -1} onClick={() => fb.mutate(-1)} disabled={fb.isPending}><ThumbsDown aria-hidden />{l("Not helpful")}</Button>
        {followUp}
      </div>
      <p className="text-xs text-muted">
        {r.meta.retrieval_method ?? "retrieval"} · {r.n_passages} passage{r.n_passages === 1 ? "" : "s"} · retrieval {r.retrieval_ms} ms · total {r.total_ms} ms
        {r.llm_model ? ` · ${r.llm_provider}/${r.llm_model} (${r.prompt_tokens ?? 0}+${r.completion_tokens ?? 0} tokens)` : " · no language model used"}
        {r.retrieval_query !== r.question ? ` · searched as: “${r.retrieval_query}”` : ""}
      </p>
    </article>
  );
}
