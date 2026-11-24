import { ArrowLeft, MessageSquarePlus } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { ErrorState, LoadingRows } from "@/components/ui/feedback";
import { ApiError } from "@/services/api/client";
import type { CaseImage, Submission } from "@/services/api/cropHealth";
import { errorMessage, formatDate } from "@/utils/format";
import { useTr } from "@/i18n/useT";
import { AnalysisPanel } from "../AnalysisPanel";
import { AssistantPanel } from "../AssistantPanel";
import { CaseStatusBadge } from "../CaseBits";
import { ExpertPanel } from "../ExpertReview";
import { FollowUpDialog } from "../FollowUpDialog";
import { PLANT_PART_LABEL, SYMPTOM_LABEL } from "../labels";
import { useCase } from "../queries";
import { useL } from "@/i18n/useT";

const when = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

function SubmissionBlock({ s, onOpen }: { s: Submission; onOpen: (img: CaseImage) => void }) {
  const l = useL();
  return (
    <li className="flex flex-col gap-3 border-t border-border pt-4 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-medium text-ink">{s.kind === "initial" ? l("Initial report") : l("Follow-up")}</h3>
        <time dateTime={s.submitted_at} className="text-sm text-muted">{when.format(new Date(s.submitted_at))}</time>
      </div>
      {s.images.length > 0 && (
        <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-5" aria-label="Photos">
          {s.images.map((img) => (
            <li key={img.id}>
              <button type="button" onClick={() => onOpen(img)}
                className="block w-full overflow-hidden rounded-[var(--radius-input)] border border-border focus-visible:outline-2 focus-visible:outline-primary"
                aria-label={`Open photo ${img.position + 1} full size`}>
                <img src={img.thumb_url} alt="" loading="lazy" className="aspect-square w-full object-cover" />
              </button>
            </li>
          ))}
        </ul>
      )}
      <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        {s.plant_part && (<div><dt className="text-muted">{l("Plant part")}</dt><dd className="text-ink">{l(PLANT_PART_LABEL[s.plant_part])}</dd></div>)}
        {s.observed_on && (<div><dt className="text-muted">{l("Noticed on")}</dt><dd className="text-ink">{formatDate(s.observed_on)}</dd></div>)}
        {s.symptoms.length > 0 && (
          <div className="sm:col-span-2"><dt className="text-muted">{l("Farmer observations")}</dt>
            <dd className="text-ink">{s.symptoms.map((x) => l(SYMPTOM_LABEL[x])).join(", ")}</dd></div>
        )}
        {s.notes && (<div className="sm:col-span-2"><dt className="text-muted">{l("Notes")}</dt><dd className="whitespace-pre-line text-ink">{s.notes}</dd></div>)}
      </dl>
    </li>
  );
}

export function CaseDetailPage() {
  const { caseId = "" } = useParams();
  const c = useCase(caseId);
  const [viewing, setViewing] = useState<CaseImage | null>(null);
  const tr = useTr();

  if (c.isPending) return <LoadingRows label="Loading case" />;
  if (c.isError) {
    const notFound = c.error instanceof ApiError && c.error.status === 404;
    return (
      <Card>
        <ErrorState title={notFound ? "Case not found" : "Could not load this case"}
          message={notFound ? "It may belong to another account, or the link is wrong." : errorMessage(c.error)}
          onRetry={notFound ? undefined : () => void c.refetch()} />
      </Card>
    );
  }
  const d = c.data;
  const closed = d.status === "closed";

  return (
    <>
      <Link to="/crop-doctor/cases" className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-muted hover:text-ink">
        <ArrowLeft aria-hidden className="size-4" />
        {tr("Case history", "کیسز کی تاریخ")}
      </Link>
      <PageHeader title={`Case ${d.reference}`}
        description={`${d.crop.name} · ${d.field.name} · ${d.farm.name}`}
        actions={!closed && (
          <FollowUpDialog caseId={d.id} trigger={<Button><MessageSquarePlus aria-hidden />{tr("Add follow-up", "مزید تصاویر شامل کریں")}</Button>} />
        )} />
      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader className="flex-row items-center justify-between gap-3">
              <CardTitle>{tr("Photos and observations", "تصاویر اور مشاہدات")}</CardTitle>
              <CaseStatusBadge status={d.status} />
            </CardHeader>
            <CardContent>
              <ol className="flex flex-col gap-4">
                {d.submissions.map((s) => <SubmissionBlock key={s.id} s={s} onOpen={setViewing} />)}
              </ol>
            </CardContent>
          </Card>
          <AssistantPanel caseId={d.id} />
        </div>
        <div className="flex flex-col gap-6">
          <AnalysisPanel caseId={d.id} analysis={d.analysis} />
          <ExpertPanel d={d} />
          <Card>
            <CardHeader><CardTitle>{tr("Timeline", "ٹائم لائن")}</CardTitle></CardHeader>
            <CardContent>
              <ol className="flex flex-col gap-3 border-l border-border pl-4">
                {d.timeline.map((e, i) => (
                  <li key={`${e.at}-${i}`} className="relative text-sm">
                    <span aria-hidden className="absolute top-1.5 -left-[21px] size-2.5 rounded-full bg-primary" />
                    <p className="text-ink">{e.text}</p>
                    <time dateTime={e.at} className="text-muted">{when.format(new Date(e.at))}</time>
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>
          <Card className="p-5 text-sm text-muted">
            Photos used to improve models: <span className="font-medium text-ink">{d.consent_training ? "Allowed" : "Not allowed"}</span>
          </Card>
        </div>
      </div>
      <Dialog open={viewing !== null} onOpenChange={(v) => !v && setViewing(null)}>
        {viewing && (
          <DialogContent title={`Photo ${viewing.position + 1}`} className="max-w-4xl">
            <img src={viewing.url} alt={`Case photo ${viewing.position + 1}`} className="max-h-[70dvh] w-full rounded-[var(--radius-input)] object-contain" />
          </DialogContent>
        )}
      </Dialog>
    </>
  );
}
