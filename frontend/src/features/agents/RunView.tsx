import { CheckCircle2, CircleDashed, Clock, ShieldAlert, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { InlineError } from "@/components/ui/feedback";
import { useDecideAction } from "@/features/intelligence/queries";
import type { AgentAction, AgentRun, AgentStep } from "@/services/api/agents";
import { errorMessage, formatDate } from "@/utils/format";
import { SpeakButton } from "@/features/voice/VoiceControls";

const STEP_ICON = {
  ok: CheckCircle2, unavailable: CircleDashed, error: XCircle, timeout: Clock,
  denied: ShieldAlert, proposed: ShieldAlert,
} as const;
const STEP_TONE = {
  ok: "success", unavailable: "neutral", error: "danger", timeout: "warning", denied: "danger",
  proposed: "warning",
} as const;
const COVER_TONE = { ok: "success", partial: "warning", unavailable: "neutral", not_run: "neutral" } as const;

export function RunView({ run }: { run: AgentRun }) {
  const r = run.response;
  return (
    <div className="grid gap-3">
      <div className="ml-auto max-w-[85%] rounded-lg bg-primary px-3 py-2 text-sm text-white">{run.message}</div>
      <Card>
        <CardHeader>
          <CardTitle>Agent response</CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            {r.agents.map((a) => (
              <Badge key={a.name} tone="info" title={a.purpose}>{a.title} agent</Badge>
            ))}
            {r.agents.length === 0 && <Badge>Orchestrator</Badge>}
            <span className="text-xs text-muted">
              {run.status} · {run.duration_ms} ms · {r.llm_used ? "LLM used" : "no LLM: rules + typed tools"}
            </span>
          </div>
        </CardHeader>
        <CardContent className="grid gap-4 text-sm">
          <p className="whitespace-pre-line text-ink">{r.answer}</p>
          <SpeakButton text={r.answer} label="Listen to the answer" />
          {r.report && <ReportSummary run={run} />}
          {r.sections.map((s) => (
            <section key={s.agent} aria-label={s.title} className="rounded-md border border-border p-3">
              <h3 className="flex items-center gap-2 font-semibold text-ink">
                {s.title} <Badge tone={COVER_TONE[s.status]}>{s.status}</Badge>
              </h3>
              <ul className="mt-1 list-disc pl-5 text-ink">{s.findings.map((f) => <li key={f}>{f}</li>)}</ul>
              {s.limitations.length > 0 && (
                <details className="mt-1 text-xs text-muted">
                  <summary className="cursor-pointer">Limitations ({s.limitations.length})</summary>
                  <ul className="list-disc pl-5">{s.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
                </details>
              )}
            </section>
          ))}
          {r.suggested_actions.length > 0 && (
            <div>
              <h3 className="font-semibold text-ink">Suggested actions</h3>
              <ul className="mt-1 grid gap-1">
                {r.suggested_actions.map((a) => (
                  <li key={a.action} className="text-ink">{a.action} <span className="text-xs text-muted">— {a.reason}</span></li>
                ))}
              </ul>
            </div>
          )}
          {r.missing_information.length > 0 && (
            <div>
              <h3 className="font-semibold text-ink">Missing information</h3>
              <p className="text-muted">{r.missing_information.map((m) => m.replaceAll("_", " ")).join(" · ")}</p>
            </div>
          )}
          {run.actions.length > 0 && <Approvals actions={run.actions} />}
          <ToolTimeline steps={run.steps} />
        </CardContent>
      </Card>
    </div>
  );
}

function ReportSummary({ run }: { run: AgentRun }) {
  const rep = run.response.report!;
  return (
    <div className="rounded-md bg-surface p-3">
      <h3 className="font-semibold text-ink">{rep.title}</h3>
      <p className="text-muted">
        {rep.farm?.name} · {rep.field?.area_ha} ha ·{" "}
        {rep.crop ? `${rep.crop.crop}${rep.crop.variety ? ` (${rep.crop.variety})` : ""}, ${rep.crop.fao56_stage?.replaceAll("_", " ") ?? "stage unknown"}` : "no active crop cycle"}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {Object.entries(rep.coverage).map(([k, v]) => (
          <Badge key={k} tone={COVER_TONE[v]}>{k.replace("_", " ")}: {v}</Badge>
        ))}
      </div>
      <p className="mt-2 text-xs text-muted">{rep.confidence}</p>
      <p className="text-xs text-muted">
        Data times — report {new Date(rep.generated_at).toLocaleString()}
        {rep.timestamps.weather_retrieved_at && ` · weather ${new Date(rep.timestamps.weather_retrieved_at).toLocaleString()}`}
        {rep.timestamps.soil_sampled_on && ` · soil sampled ${formatDate(rep.timestamps.soil_sampled_on)}`}
      </p>
    </div>
  );
}

export function Approvals({ actions }: { actions: AgentAction[] }) {
  const decide = useDecideAction();
  return (
    <div>
      <h3 className="font-semibold text-ink">Proposed changes (need your approval)</h3>
      <ul className="mt-1 grid gap-2">
        {actions.map((a) => (
          <li key={a.id} className="rounded-md border border-border p-2">
            <p className="text-ink">{a.description}</p>
            <p className="text-xs text-muted">
              Status: <strong>{a.status}</strong> · expires {new Date(a.expires_at).toLocaleString()}
              {a.executed_at && ` · executed ${new Date(a.executed_at).toLocaleString()}`}
              {a.error_code && ` · error ${a.error_code}`}
            </p>
            {a.status === "pending" && (
              <div className="mt-2 flex gap-2">
                <Button size="sm" disabled={decide.isPending} onClick={() => decide.mutate({ id: a.id, approve: true })}>Approve</Button>
                <Button size="sm" variant="secondary" disabled={decide.isPending} onClick={() => decide.mutate({ id: a.id, approve: false })}>Reject</Button>
              </div>
            )}
          </li>
        ))}
      </ul>
      {decide.isError && <InlineError message={errorMessage(decide.error)} />}
    </div>
  );
}

function ToolTimeline({ steps }: { steps: AgentStep[] }) {
  return (
    <details>
      <summary className="cursor-pointer font-semibold text-ink">Tool execution ({steps.length} steps)</summary>
      <ol className="mt-2 grid gap-1">
        {steps.map((s) => {
          const Icon = STEP_ICON[s.status];
          return (
            <li key={s.position} className="flex flex-wrap items-center gap-2 text-xs">
              <Icon aria-hidden className="size-3.5 text-muted" />
              <code className="text-ink">{s.tool}</code>
              <Badge tone={STEP_TONE[s.status]}>{s.status}</Badge>
              <span className="text-muted">{s.agent} · {s.mode} · {s.duration_ms} ms</span>
              {s.summary && <span className="text-ink">{s.summary}</span>}
              {s.error_code && <span className="text-danger">{s.error_code}</span>}
            </li>
          );
        })}
      </ol>
    </details>
  );
}

export function CardList({ title, children }: { title: string; children: React.ReactNode }) {
  return <Card><CardHeader><CardTitle>{title}</CardTitle></CardHeader><CardContent>{children}</CardContent></Card>;
}
