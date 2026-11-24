import { useQuery } from "@tanstack/react-query";
import { BrainCircuit, Clock3, Layers, Library, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { StatTile } from "@/components/ui/stat-tile";
import { useAuth } from "@/features/auth/auth-context";
import { knowledgeApi } from "@/services/api/knowledge";
import { cn } from "@/utils/cn";
import { AnalyticsPanel } from "./AnalyticsPanel";
import { AskPanel } from "./AskPanel";
import { SourcesPanel } from "./SourcesPanel";
import { useL } from "@/i18n/useT";

type Tab = "ask" | "sources" | "analytics";

/** FR8 Knowledge Intelligence Center: cited answers from licence-verified sources only. */
export function KnowledgePage() {
  const l = useL();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const canAnalyse = isAdmin || user?.role === "expert";
  const [tab, setTab] = useState<Tab>("ask");
  const stats = useQuery({ queryKey: ["knowledge", "stats"], queryFn: knowledgeApi.stats });
  const tabs: { key: Tab; label: string }[] = [
    { key: "ask", label: l("Ask") },
    { key: "sources", label: l("Sources") },
    ...(canAnalyse ? [{ key: "analytics" as const, label: l("Analytics") }] : []),
  ];
  const s = stats.data;
  const llm = s?.providers.llm;
  return (
    <>
      <PageHeader title={l("Agricultural Knowledge")}
        description={l("Ask in English or Urdu. Answers come only from licence-verified sources, cite every passage, and say so when the sources do not cover a question.")} />
      <div className="grid gap-4">
        {s && (
          <section aria-label="Knowledge library" className="grid grid-cols-2 gap-3 xl:grid-cols-4">
            <StatTile icon={Library} label={l("Registered sources")} value={Object.values(s.sources_by_status).reduce((a, b) => a + b, 0)} />
            <StatTile icon={ShieldCheck} label={l("Licence verified")} value={s.searchable_sources} detail="Only these are searched" />
            <StatTile icon={Layers} label={l("Indexed passages")} value={s.chunks} detail={`${s.embedded_chunks} with semantic vectors · ${s.sources_with_chunks} source${s.sources_with_chunks === 1 ? "" : "s"}`} />
            <StatTile icon={Clock3} label={l("Awaiting licence review")} value={s.sources_by_status.unverified ?? 0} detail={s.ingestion.failed ? `${s.ingestion.failed} failed to index` : undefined} />
            <p className="col-span-full flex flex-wrap items-center gap-x-2 text-xs text-muted">
              <BrainCircuit aria-hidden className="size-3.5" />
              {llm?.enabled ? `Answers written by ${llm.model} (${llm.provider}${llm.external ? ", external service" : ", local"}) from retrieved passages, then checked for citations and grounding.` : "No language model configured: answers are quoted passages only."}
              {s.providers.embeddings.enabled ? ` Semantic search: ${s.providers.embeddings.model}.` : " Keyword search only."}
              {s.last_indexed_at && ` Last indexed ${new Date(s.last_indexed_at).toLocaleString()}.`}
            </p>
          </section>
        )}
        <div role="tablist" aria-label="Knowledge sections" className="flex gap-1 border-b border-border">
          {tabs.map((t) => (
            <button key={t.key} type="button" role="tab" id={`ktab-${t.key}`} aria-selected={tab === t.key} aria-controls={`kpanel-${t.key}`}
              onClick={() => setTab(t.key)}
              className={cn("-mb-px border-b-2 px-4 py-2 text-sm font-medium", tab === t.key ? "border-primary text-primary-dark" : "border-transparent text-muted hover:text-ink")}>
              {t.label}
            </button>
          ))}
        </div>
        <div role="tabpanel" id={`kpanel-${tab}`} aria-labelledby={`ktab-${tab}`}>
          {tab === "ask" && <AskPanel searchable={s?.searchable_sources ?? 0} />}
          {tab === "sources" && <SourcesPanel isAdmin={isAdmin} />}
          {tab === "analytics" && canAnalyse && <AnalyticsPanel />}
        </div>
      </div>
    </>
  );
}

export { KnowledgePage as Component };
