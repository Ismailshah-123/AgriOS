import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Inbox } from "lucide-react";
import { Link, useParams } from "react-router";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState, LoadingRows } from "@/components/ui/feedback";
import { ReviewForm, ReviewList } from "@/features/crop-health/ExpertReview";
import { HeatmapPanel } from "@/features/crop-health/HeatmapPanel";
import { AVAILABILITY_LABEL, PLANT_PART_LABEL, SYMPTOM_LABEL } from "@/features/crop-health/labels";
import { ApiError } from "@/services/api/client";
import { reviewApi, type CaseDetail } from "@/services/api/cropHealth";
import { errorMessage, formatDate } from "@/utils/format";

function Failure({ error, retry }: { error: unknown; retry: () => void }) {
  const forbidden = error instanceof ApiError && error.status === 403;
  return (
    <Card>
      <ErrorState title={forbidden ? "Experts only" : "Could not load"}
        message={forbidden ? "This page is for expert reviewer accounts." : errorMessage(error)}
        onRetry={forbidden ? undefined : retry} />
    </Card>
  );
}

/** FR12 queue: cases farmers sent for expert review, oldest first. */
export function ReviewQueuePage() {
  const q = useQuery({ queryKey: ["review", "queue"], queryFn: reviewApi.queue });
  return (
    <>
      <PageHeader title="Expert review" description="Crop Doctor cases farmers sent for review, oldest first. Your answer is shown to the farmer as an expert outcome." />
      {q.isPending ? <Card><LoadingRows label="Loading queue" /></Card>
        : q.isError ? <Failure error={q.error} retry={() => q.refetch()} />
        : q.data.length === 0 ? <Card><EmptyState icon={Inbox} title="No cases waiting" description="Cases appear here when a farmer asks for an expert." /></Card>
        : (
          <Card>
            <ul className="divide-y divide-border">
              {q.data.map((c) => (
                <li key={c.case_id}>
                  <Link to={`/review/cases/${c.case_id}`} className="flex flex-wrap items-center justify-between gap-2 px-5 py-3.5 hover:bg-surface-raised">
                    <span className="font-medium text-ink">Case #{c.number} · {c.crop_name}</span>
                    <span className="text-sm text-muted">{c.image_count} photo{c.image_count === 1 ? "" : "s"} · waiting since {formatDate(c.waiting_since)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        )}
    </>
  );
}

function ModelSummary({ d }: { d: CaseDetail }) {
  const r = d.analysis.result;
  return (
    <Card>
      <CardHeader><CardTitle>Model output</CardTitle></CardHeader>
      <CardContent className="text-sm">
        {!r ? (
          <p className="text-muted">No model result: {AVAILABILITY_LABEL[d.analysis.model_availability].toLowerCase()} ({d.analysis.inference_status.replaceAll("_", " ")}).</p>
        ) : (
          <div className="grid gap-1">
            <p className="text-ink">Decision: <Badge>{r.decision}</Badge> {r.predicted_class && <strong>{r.predicted_class}</strong>}</p>
            <p className="text-muted">Calibrated confidence {Math.round(r.calibrated_confidence * 100)}% · model {r.model_name} {r.model_version}</p>
            {r.shortlist.length > 0 && <p className="text-muted">Shortlist: {r.shortlist.map((s) => `${s.label} ${Math.round(s.probability * 100)}%`).join(", ")}</p>}
            {r.explanation_available && <HeatmapPanel caseId={d.id} scope="review" />}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function ReviewCasePage() {
  const { caseId = "" } = useParams();
  const q = useQuery({ queryKey: ["review", "case", caseId], queryFn: () => reviewApi.get(caseId) });
  const back = (
    <Link to="/review" className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-muted hover:text-ink">
      <ArrowLeft aria-hidden className="size-4" />Review queue
    </Link>
  );
  if (q.isPending) return <>{back}<Card><LoadingRows label="Loading case" /></Card></>;
  if (q.isError) return <>{back}<Failure error={q.error} retry={() => q.refetch()} /></>;
  const d = q.data.case;
  return (
    <>
      {back}
      <PageHeader title={`Case ${d.reference}`} description={`${d.crop.name} · consent to use photos for training: ${d.consent_training ? "yes" : "no"}`} />
      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr] [&>*]:min-w-0">
        <Card>
          <CardHeader><CardTitle>Photos and farmer observations</CardTitle></CardHeader>
          <CardContent className="flex flex-col gap-4">
            {d.submissions.map((s) => (
              <div key={s.id} className="flex flex-col gap-2">
                <p className="text-sm text-muted">
                  {formatDate(s.submitted_at)} · {s.plant_part ? PLANT_PART_LABEL[s.plant_part] : "Part not given"}
                  {s.symptoms.length > 0 && ` · ${s.symptoms.map((x) => SYMPTOM_LABEL[x]).join(", ")}`}
                </p>
                {s.notes && <p className="text-sm text-ink">“{s.notes}”</p>}
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {s.images.map((img) => (
                    <a key={img.id} href={img.url} target="_blank" rel="noreferrer">
                      <img src={img.thumb_url} alt={`Case photo ${img.position + 1}`} className="aspect-square w-full rounded-[var(--radius-input)] object-cover" />
                    </a>
                  ))}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
        <div className="flex flex-col gap-6">
          <ModelSummary d={d} />
          <Card>
            <CardHeader><CardTitle>{q.data.awaiting_review ? "Your review" : "Review history"}</CardTitle></CardHeader>
            <CardContent className="flex flex-col gap-4">
              {(d.expert_reviews ?? []).length > 0 && <ReviewList reviews={d.expert_reviews ?? []} />}
              {q.data.awaiting_review
                ? <ReviewForm caseId={d.id} modelClass={d.analysis.result?.predicted_class ?? null} />
                : <p className="text-sm text-muted">This case is no longer waiting for review.</p>}
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
