import { useQuery } from "@tanstack/react-query";
import { Activity, Clock3, SearchX, ThumbsUp } from "lucide-react";
import { BarList } from "@/components/charts/BarList";
import { ColumnChart } from "@/components/charts/ColumnChart";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, LoadingRows } from "@/components/ui/feedback";
import { StatTile } from "@/components/ui/stat-tile";
import { DOMAIN_LABEL, knowledgeApi } from "@/services/api/knowledge";
import { errorMessage } from "@/utils/format";

const STATUS_LABEL: Record<string, string> = {
  answered: "Grounded answer", extractive: "Quoted passages", abstained: "No verified guidance",
  clarify: "Asked for detail", error: "Error",
};
const bars = (rec: Record<string, number>, label: (k: string) => string = (k) => k) =>
  Object.entries(rec).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ key: k, label: label(k), value: v, display: String(v) }));

/** Measured telemetry only (knowledge_queries + ingestion). No accuracy percentages. */
export function AnalyticsPanel() {
  const q = useQuery({ queryKey: ["knowledge", "analytics"], queryFn: knowledgeApi.analytics });
  if (q.isPending) return <Card><LoadingRows rows={4} label="Loading analytics" /></Card>;
  if (q.isError) return <Card><ErrorState message={errorMessage(q.error)} onRetry={() => q.refetch()} /></Card>;
  const a = q.data;
  const ms = (v: number | null) => (v === null ? "—" : `${v} ms`);
  return (
    <div className="grid gap-4">
      <section aria-label="Retrieval activity" className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <StatTile icon={Activity} label="Questions asked" value={a.queries_total} />
        <StatTile icon={SearchX} label="No verified guidance" value={a.no_result_queries} detail="abstained (no supporting passage)" />
        <StatTile icon={Clock3} label="Retrieval latency" value={ms(a.latency_ms.retrieval_p50)} detail={`p95 ${ms(a.latency_ms.retrieval_p95)} · end-to-end p50 ${ms(a.latency_ms.total_p50)}`} />
        <StatTile icon={ThumbsUp} label="Feedback" value={`${a.feedback.helpful} / ${a.feedback.not_helpful}`} detail="helpful / not helpful" />
      </section>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card><CardHeader><CardTitle>Questions per day</CardTitle></CardHeader>
          <CardContent>{a.daily.length ? <ColumnChart label="Questions per day" data={a.daily.map((d) => ({ key: d.day, label: d.day.slice(5), value: d.queries, display: String(d.queries) }))} /> : <p className="text-sm text-muted">No questions yet.</p>}</CardContent></Card>
        <Card><CardHeader><CardTitle>Outcome</CardTitle></CardHeader>
          <CardContent><BarList label="Answer outcome" data={bars(a.by_status, (k) => STATUS_LABEL[k] ?? k)} emptyText="No questions yet." /></CardContent></Card>
        <Card><CardHeader><CardTitle>Question domains</CardTitle><CardDescription>Detected from the question (lexicon), or the chosen filter.</CardDescription></CardHeader>
          <CardContent><BarList label="Question domains" data={bars(a.by_domain, (k) => DOMAIN_LABEL[k] ?? k)} emptyText="No questions yet." /></CardContent></Card>
        <Card><CardHeader><CardTitle>Languages</CardTitle></CardHeader>
          <CardContent><BarList label="Question languages" data={bars(a.by_language, (k) => ({ en: "English", ur: "Urdu", "ur-Latn": "Roman Urdu" })[k] ?? k)} emptyText="No questions yet." /></CardContent></Card>
        <Card><CardHeader><CardTitle>Most retrieved sources</CardTitle><CardDescription>Passages returned with answers.</CardDescription></CardHeader>
          <CardContent><BarList label="Source usage" data={a.source_usage.map((s) => ({ key: s.title, label: s.title, value: s.citations, display: String(s.citations) }))} emptyText="No passages retrieved yet." /></CardContent></Card>
        <Card><CardHeader><CardTitle>Ingestion</CardTitle><CardDescription>Source index state and background jobs.</CardDescription></CardHeader>
          <CardContent className="grid gap-3">
            <BarList label="Sources by index state" data={bars(a.ingestion, (k) => k.replace("_", " "))} />
            <p className="text-xs text-muted">Jobs: {Object.entries(a.ingestion_jobs).map(([k, v]) => `${k} ${v}`).join(", ") || "none"} · LLM tokens used: {a.tokens.prompt.toLocaleString()} prompt + {a.tokens.completion.toLocaleString()} completion</p>
          </CardContent></Card>
      </div>
      <p className="text-xs text-muted">Not measured here: {a.not_tracked.join("; ")}. Retrieval quality is measured offline (docs/09-rag-knowledge/RAG_EVALUATION.md).</p>
    </div>
  );
}
