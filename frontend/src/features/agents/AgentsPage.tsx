import { Bot, Send } from "lucide-react";
import { useState, type FormEvent } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState, InlineError, LoadingRows } from "@/components/ui/feedback";
import { Textarea } from "@/components/ui/input";
import { FieldPicker } from "@/features/intelligence/FieldPicker";
import { useSelectedField } from "@/features/intelligence/useSelectedField";
import { useAgentRun, useAgentRuns, usePendingActions, useRunAgent } from "@/features/intelligence/queries";
import { errorMessage } from "@/utils/format";
import { MicButton } from "@/features/voice/VoiceControls";
import { AgentActivity, AgentCatalogueCard, DecisionHistory } from "./ActionHistory";
import { Approvals, CardList, RunView } from "./RunView";

const PROMPTS = [
  "Give me a complete condition report for my tomato field",
  "Will it rain this week?",
  "What does the soil test say?",
  "How much water does the crop need?",
  "Explain the source of the late blight indicator",
];

export function AgentsPage() {
  const sel = useSelectedField();
  const [message, setMessage] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const run = useRunAgent();
  const history = useAgentRuns();
  const pending = usePendingActions();
  const shown = useAgentRun(selected);
  const current = run.data && run.data.id === selected ? run.data : shown.data;

  function submit(e?: FormEvent) {
    e?.preventDefault();
    const text = message.trim();
    if (text.length < 2) return;
    run.mutate(
      { message: text, ...(sel.fieldId ? { field_id: sel.fieldId } : {}) },
      { onSuccess: (r) => { setSelected(r.id); setMessage(""); } },
    );
  }

  return (
    <>
      <PageHeader
        title="AI Agents"
        description="Six agricultural agents read your farm records through allow-listed tools. Every step is shown; changes run only after you approve them."
        actions={sel.field && (
          <FieldPicker value={sel.fieldId} onChange={sel.setFieldId} fields={sel.fields.data?.items ?? []} />
        )}
      />
      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <div className="grid content-start gap-4">
          <Card className="p-4">
            <form onSubmit={submit} className="grid gap-2">
              <label htmlFor="agent-msg" className="text-sm font-semibold text-ink">Ask the agents</label>
              <Textarea
                id="agent-msg" rows={2} maxLength={500} value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) submit(e); }}
                placeholder="e.g. Give me a complete condition report for my tomato field"
              />
              <div className="flex flex-wrap items-center gap-2">
                {PROMPTS.map((p) => (
                  <button key={p} type="button" onClick={() => setMessage(p)}
                    className="rounded-full border border-border px-3 py-1 text-xs text-muted hover:text-ink">
                    {p}
                  </button>
                ))}
                <Button type="submit" className="ml-auto" disabled={run.isPending || message.trim().length < 2}>
                  <Send aria-hidden />{run.isPending ? "Working…" : "Send"}
                </Button>
              </div>
              <MicButton onText={(t) => setMessage((m) => (m ? `${m} ` : "") + t)} />
              {run.isError && <InlineError message={errorMessage(run.error)} />}
            </form>
          </Card>
          {run.isPending && <Card><LoadingRows label="Agents are running tools" /></Card>}
          {!run.isPending && current && <RunView run={current} />}
          {!run.isPending && !current && selected && shown.isPending && <Card><LoadingRows label="Loading run" /></Card>}
          {!run.isPending && !selected && (
            <Card>
              <EmptyState icon={Bot} title="No conversation selected"
                description="Ask a question or pick a previous run. Answers come from your records, the weather provider and cited methods; no language model writes them." />
            </Card>
          )}
        </div>
        <aside aria-label="Approvals and history" className="grid content-start gap-4">
          <CardList title="Pending approvals">
            {pending.isError && <ErrorState message={errorMessage(pending.error)} onRetry={() => pending.refetch()} />}
            {pending.isSuccess && pending.data.length === 0 && <p className="text-sm text-muted">Nothing waiting for approval.</p>}
            {pending.isSuccess && pending.data.length > 0 && <Approvals actions={pending.data} />}
          </CardList>
          <CardList title="History">
            {history.isPending && <LoadingRows rows={3} label="Loading history" />}
            {history.isError && <ErrorState message={errorMessage(history.error)} onRetry={() => history.refetch()} />}
            {history.isSuccess && history.data.items.length === 0 && <p className="text-sm text-muted">No runs yet.</p>}
            <ul className="grid gap-1">
              {history.data?.items.map((h) => (
                <li key={h.id}>
                  <button type="button" onClick={() => setSelected(h.id)}
                    aria-current={h.id === selected ? "true" : undefined}
                    className="w-full rounded-md px-2 py-1 text-left text-sm hover:bg-surface aria-[current=true]:bg-primary-soft">
                    <span className="line-clamp-1 text-ink">{h.message}</span>
                    <span className="text-xs text-muted">{h.intent.replace("_", " ")} · {h.status} · {new Date(h.created_at).toLocaleString()}</span>
                  </button>
                </li>
              ))}
            </ul>
          </CardList>
          <AgentActivity />
          <DecisionHistory />
          <AgentCatalogueCard />
        </aside>
      </div>
    </>
  );
}

export { AgentsPage as Component };
