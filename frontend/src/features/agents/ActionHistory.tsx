import { Badge } from "@/components/ui/badge";
import { ErrorState, LoadingRows } from "@/components/ui/feedback";
import { BarList } from "@/components/charts/BarList";
import { useActionHistory, useAgentCatalogue, useAgentRuns } from "@/features/intelligence/queries";
import type { ActionStatus } from "@/services/api/agents";
import { errorMessage } from "@/utils/format";
import { CardList } from "./RunView";

const TONE: Record<ActionStatus, "neutral" | "success" | "warning" | "danger" | "info"> = {
  pending: "warning", approved: "info", executed: "success", rejected: "neutral", expired: "neutral", failed: "danger",
};
const when = (s: string | null) => (s ? new Date(s).toLocaleString() : null);

/** Every decided proposal: who-approved trail lives in the audit log; this shows outcome + time. */
export function DecisionHistory() {
  const q = useActionHistory();
  const decided = q.data?.filter((a) => a.status !== "pending") ?? [];
  return (
    <CardList title="Decided changes">
      {q.isPending && <LoadingRows rows={2} label="Loading decisions" />}
      {q.isError && <ErrorState message={errorMessage(q.error)} onRetry={() => q.refetch()} />}
      {q.isSuccess && decided.length === 0 && <p className="text-sm text-muted">No approved, rejected or expired changes yet.</p>}
      <ul className="grid gap-2">
        {decided.map((a) => (
          <li key={a.id} className="rounded-md border border-border p-2 text-sm">
            <p className="flex flex-wrap items-center gap-2 text-ink">
              <Badge tone={TONE[a.status]}>{a.status}</Badge>
              <span className="min-w-0">{a.description}</span>
            </p>
            <p className="mt-1 text-xs text-muted">
              Tool <code>{a.tool}</code> · proposed by {a.agent.replaceAll("_", " ")} agent
              {a.decided_at && ` · decided ${when(a.decided_at)}`}
              {a.executed_at && ` · executed ${when(a.executed_at)}`}
              {a.status === "expired" && ` · expired ${when(a.expires_at)}`}
              {a.error_code && ` · error ${a.error_code}`}
            </p>
          </li>
        ))}
      </ul>
    </CardList>
  );
}

/** Counts from the same data the page already loads: last 20 runs and all proposals. */
export function AgentActivity() {
  const runs = useAgentRuns();
  const actions = useActionHistory();
  const count = (xs: string[]) => Object.entries(xs.reduce<Record<string, number>>((m, x) => ({ ...m, [x]: (m[x] ?? 0) + 1 }), {}))
    .sort((a, b) => b[1] - a[1]);  // prettier-ignore
  return (
    <CardList title="Activity">
      {(runs.isPending || actions.isPending) && <LoadingRows rows={2} label="Loading activity" />}
      {runs.isSuccess && (
        <div className="grid gap-1.5">
          <p className="text-xs font-medium text-muted">Requests by type (last {runs.data.items.length})</p>
          <BarList label="Agent requests by type" emptyText="No requests yet."
            data={count(runs.data.items.map((r) => r.intent)).map(([k, n]) => ({ key: k, label: k.replaceAll("_", " "), value: n, display: String(n) }))} />
        </div>
      )}
      {actions.isSuccess && (
        <div className="mt-3 grid gap-1.5">
          <p className="text-xs font-medium text-muted">Proposed changes by outcome</p>
          <BarList label="Proposed changes by outcome" emptyText="No changes proposed yet."
            data={count(actions.data.map((a) => a.status)).map(([k, n]) => ({ key: k, label: k, value: n, display: String(n) }))} />
        </div>
      )}
    </CardList>
  );
}

/** What the agents are and which typed tools they may call (from GET /agent/catalogue). */
export function AgentCatalogueCard() {
  const q = useAgentCatalogue();
  return (
    <CardList title="Agents and tools">
      {q.isPending && <LoadingRows rows={2} label="Loading catalogue" />}
      {q.isError && <ErrorState message={errorMessage(q.error)} onRetry={() => q.refetch()} />}
      {q.isSuccess && (
        <div className="grid gap-2 text-sm">
          <p className="text-muted">
            {q.data.llm_used
              ? "A language model is used for some answers."
              : "Deterministic orchestration: keyword routing, typed tools and cited rules. No language model is used."}
          </p>
          <details>
            <summary className="cursor-pointer font-medium text-ink">{q.data.agents.length} agents</summary>
            <ul className="mt-1 grid gap-1">
              {q.data.agents.map((a) => (
                <li key={a.name}><span className="font-medium text-ink">{a.title}</span> <span className="text-muted">— {a.purpose}</span></li>
              ))}
            </ul>
          </details>
          <details>
            <summary className="cursor-pointer font-medium text-ink">{q.data.tools.length} tools</summary>
            <ul className="mt-1 grid gap-1">
              {q.data.tools.map((t) => (
                <li key={t.name}>
                  <code className="text-ink">{t.name}</code>{" "}
                  <Badge tone={t.mode === "write" ? "warning" : "neutral"}>{t.requires_approval ? "write · needs approval" : "read only"}</Badge>
                  <span className="block text-xs text-muted">{t.description}</span>
                </li>
              ))}
            </ul>
          </details>
        </div>
      )}
    </CardList>
  );
}
