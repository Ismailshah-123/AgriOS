import { useMutation, useQueryClient } from "@tanstack/react-query";
import { UserCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InlineError } from "@/components/ui/feedback";
import { FormField } from "@/components/ui/form-field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { reviewApi, type CaseDetail, type ExpertReview, type ReviewDecision } from "@/services/api/cropHealth";
import { errorMessage } from "@/utils/format";
import { DECISION_LABEL } from "./labels";
import { useL } from "@/i18n/useT";


const NEEDS_LABEL: ReviewDecision[] = ["confirmed_model", "diagnosed"];
const REQUESTABLE = ["submitted", "retake", "unsure", "accepted", "out_of_scope"];
const when = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

export function ReviewList({ reviews }: { reviews: ExpertReview[] }) {
  return (
    <ul className="flex flex-col gap-3">
      {reviews.map((r) => (
        <li key={r.id} className="rounded-[var(--radius-input)] border border-border p-3 text-sm">
          <p className="flex flex-wrap items-center gap-2 font-medium text-ink">
            {DECISION_LABEL[r.decision]}{r.label && <Badge tone="info">{r.label}</Badge>}
          </p>
          {r.note && <p className="mt-1 text-ink-soft">{r.note}</p>}
          <p className="mt-1 text-xs text-muted">{r.expert_name} · {when.format(new Date(r.reviewed_at))}</p>
        </li>
      ))}
    </ul>
  );
}

/** Farmer side: ask an expert, and see expert outcomes (separate from model output). */
export function ExpertPanel({ d }: { d: CaseDetail }) {
  const l = useL();
  const qc = useQueryClient();
  const ask = useMutation({
    mutationFn: () => reviewApi.request(d.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["crop-health"] }),
  });
  const reviews = d.expert_reviews ?? [];
  return (
    <Card>
      <CardHeader>
        <CardTitle>{l("Expert review")}</CardTitle>
        <CardDescription>A person checks your photos. Their answer is shown here, apart from any model result.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {reviews.length > 0 && <ReviewList reviews={reviews} />}
        {d.status === "expert_review" && <p className="text-sm text-ink" role="status">{l("Waiting for an expert to review this case.")}</p>}
        {REQUESTABLE.includes(d.status) && (
          <Button variant="secondary" className="self-start" disabled={ask.isPending} onClick={() => ask.mutate()}>
            <UserCheck aria-hidden />{ask.isPending ? l("Sending…") : l("Ask an expert")}
          </Button>
        )}
        {ask.isError && <InlineError message={errorMessage(ask.error)} />}
      </CardContent>
    </Card>
  );
}

/** Expert side: record an outcome. A label is required for a diagnosis or confirmation. */
export function ReviewForm({ caseId, modelClass }: { caseId: string; modelClass: string | null }) {
  const qc = useQueryClient();
  const [decision, setDecision] = useState<ReviewDecision>(modelClass ? "confirmed_model" : "diagnosed");
  const [error, setError] = useState<string | null>(null);
  const submit = useMutation({
    mutationFn: (b: Parameters<typeof reviewApi.submit>[1]) => reviewApi.submit(caseId, b),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["review"] }),
  });
  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const label = String(fd.get("label") ?? "").trim() || null;
    const note = String(fd.get("note") ?? "").trim() || null;
    if (NEEDS_LABEL.includes(decision) && (!label || label.length < 2)) {
      setError("Enter the diagnosis label for this decision.");
      return;
    }
    setError(null);
    submit.mutate({ decision, label: NEEDS_LABEL.includes(decision) ? label : null, note }, { onError: (err) => setError(errorMessage(err)) });
  }
  return (
    <form onSubmit={onSubmit} className="grid gap-3" noValidate>
      <FormField label="Decision">
        <Select name="decision" value={decision} onChange={(e) => setDecision(e.target.value as ReviewDecision)}>
          {(Object.keys(DECISION_LABEL) as ReviewDecision[]).filter((k) => k !== "confirmed_model" || modelClass)
            .map((k) => <option key={k} value={k}>{DECISION_LABEL[k]}</option>)}
        </Select>
      </FormField>
      {NEEDS_LABEL.includes(decision) && (
        <FormField label="Diagnosis label"><Input name="label" maxLength={80} defaultValue={decision === "confirmed_model" ? modelClass ?? "" : ""} /></FormField>
      )}
      <FormField label="Note to the farmer" optional><Textarea name="note" rows={3} maxLength={2000} /></FormField>
      {error && <InlineError message={error} />}
      <Button type="submit" className="self-start" disabled={submit.isPending}>{submit.isPending ? "Saving…" : "Submit review"}</Button>
    </form>
  );
}
