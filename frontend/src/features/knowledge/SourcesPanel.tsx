import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpenText, Plus, RefreshCw, Trash2, Upload } from "lucide-react";
import { Fragment, useState, type FormEvent } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState, InlineError, LoadingRows } from "@/components/ui/feedback";
import { FormField } from "@/components/ui/form-field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { DOMAIN_LABEL, knowledgeApi, type KnowledgeSource, type SourceInput } from "@/services/api/knowledge";
import { errorMessage } from "@/utils/format";

const REVIEW_TONE: Record<string, "success" | "info" | "warning" | "danger"> = {
  content_reviewed: "success", licence_verified: "info", unverified: "warning", blocked: "danger",
};
const INGEST_TONE: Record<string, "success" | "info" | "warning" | "danger" | "neutral"> = {
  indexed: "success", queued: "info", processing: "info", failed: "danger", not_ingested: "neutral",
};

function RegisterDialog({ onDone }: { onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState<SourceInput & { crops_text: string }>({
    title: "", publisher: "", licence: "", commercial_use: "unknown", language: "en", url: "", licence_url: "",
    attribution: "", domain: null, document_type: null, crops_text: "",
  });
  const tax = useQuery({ queryKey: ["knowledge", "taxonomy"], queryFn: knowledgeApi.taxonomy, staleTime: Infinity });
  const save = useMutation({
    mutationFn: () => {
      const { crops_text, ...rest } = f;
      const body = Object.fromEntries(Object.entries(rest).filter(([, v]) => v !== "" && v !== null)) as SourceInput;
      return knowledgeApi.createSource({ ...body, crops: crops_text.split(",").map((c) => c.trim()).filter(Boolean) });
    },
    onSuccess: () => { setOpen(false); onDone(); },
  });  // prettier-ignore
  const set = (k: string) => (e: { target: { value: string } }) => setF((x) => ({ ...x, [k]: e.target.value }));
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild><Button><Plus aria-hidden />Register source</Button></DialogTrigger>
      <DialogContent title="Register a knowledge source" description="Record provenance and licence first. The source stays unsearchable until its licence is verified." className="max-w-2xl">
        <form className="grid gap-3 overflow-y-auto p-5 sm:grid-cols-2" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
          <FormField label="Title"><Input required minLength={3} value={f.title} onChange={set("title")} /></FormField>
          <FormField label="Publisher"><Input required minLength={2} value={f.publisher} onChange={set("publisher")} /></FormField>
          <FormField label="Source URL" optional><Input type="url" value={f.url ?? ""} onChange={set("url")} /></FormField>
          <FormField label="Licence" hint="e.g. CC BY 4.0, public domain"><Input required value={f.licence} onChange={set("licence")} /></FormField>
          <FormField label="Licence URL" optional><Input type="url" value={f.licence_url ?? ""} onChange={set("licence_url")} /></FormField>
          <FormField label="Commercial use">
            <Select value={f.commercial_use} onChange={set("commercial_use")}><option value="unknown">Unknown</option><option value="allowed">Allowed</option><option value="not_allowed">Not allowed</option></Select>
          </FormField>
          <FormField label="Domain" optional>
            <Select value={f.domain ?? ""} onChange={set("domain")}><option value="">—</option>{tax.data?.domains.map((d) => <option key={d} value={d}>{DOMAIN_LABEL[d] ?? d}</option>)}</Select>
          </FormField>
          <FormField label="Document type" optional>
            <Select value={f.document_type ?? ""} onChange={set("document_type")}><option value="">—</option>{tax.data?.document_types.map((d) => <option key={d} value={d}>{d.replaceAll("_", " ")}</option>)}</Select>
          </FormField>
          <FormField label="Language"><Select value={f.language} onChange={set("language")}><option value="en">English</option><option value="ur">Urdu</option></Select></FormField>
          <FormField label="Crops" optional hint="comma-separated"><Input value={f.crops_text} onChange={set("crops_text")} /></FormField>
          <div className="sm:col-span-2"><FormField label="Attribution" optional><Textarea rows={2} value={f.attribution ?? ""} onChange={set("attribution")} /></FormField></div>
          {save.isError && <div className="sm:col-span-2"><InlineError message={errorMessage(save.error)} /></div>}
          <div className="flex justify-end gap-2 sm:col-span-2"><Button type="submit" disabled={save.isPending}>Register</Button></div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function SourceActions({ s, onDone }: { s: KnowledgeSource; onDone: () => void }) {
  const [note, setNote] = useState("");
  const [progress, setProgress] = useState<number | null>(null);
  const act = useMutation({ mutationFn: (fn: () => Promise<unknown>) => fn(), onSuccess: onDone, onSettled: () => setProgress(null) });
  const detail = useQuery({ queryKey: ["knowledge", "source", s.id], queryFn: () => knowledgeApi.source(s.id) });
  return (
    <div className="flex flex-col gap-3 text-sm">
      <dl className="grid grid-cols-[8rem_1fr] gap-x-3 gap-y-1 text-ink-soft">
        <dt className="text-muted">Licence</dt><dd>{s.licence} · commercial use {s.commercial_use.replace("_", " ")}</dd>
        <dt className="text-muted">Review note</dt><dd>{s.review_note ?? "—"}</dd>
        <dt className="text-muted">File</dt><dd>{s.file_name ? `${s.file_name} (${Math.round((s.file_bytes ?? 0) / 1024)} KB, v${s.version})` : "none uploaded"}</dd>
        <dt className="text-muted">Index</dt><dd>{s.ingest_status.replace("_", " ")}{s.ingest_error ? ` — ${s.ingest_error}` : ""} · {s.chunk_count} passages</dd>
      </dl>
      <label className="flex flex-col gap-1"><span className="text-muted">Upload or replace document (PDF, DOCX, TXT, MD, HTML, CSV)</span>
        <input type="file" accept=".pdf,.docx,.txt,.md,.html,.htm,.csv" className="text-sm"
          onChange={(e) => { const file = e.target.files?.[0]; if (file) act.mutate(() => knowledgeApi.upload(s.id, file, setProgress)); }} />
      </label>
      {progress !== null && <p className="text-xs text-muted"><Upload aria-hidden className="inline size-3" /> Uploading {Math.round(progress * 100)}%</p>}
      <FormField label="Licence review note" hint="Required evidence: where the licence is stated and what it permits."><Textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} /></FormField>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" disabled={note.trim().length < 5 || act.isPending} onClick={() => act.mutate(() => knowledgeApi.review(s.id, "licence_verified", note))}>Verify licence</Button>
        <Button size="sm" variant="secondary" disabled={note.trim().length < 5 || act.isPending} onClick={() => act.mutate(() => knowledgeApi.review(s.id, "content_reviewed", note))}>Mark content reviewed</Button>
        <Button size="sm" variant="secondary" disabled={note.trim().length < 5 || act.isPending} onClick={() => act.mutate(() => knowledgeApi.review(s.id, "blocked", note))}>Block</Button>
        <Button size="sm" variant="secondary" disabled={act.isPending} onClick={() => act.mutate(() => knowledgeApi.reprocess(s.id))}><RefreshCw aria-hidden />Reprocess</Button>
        <Button size="sm" variant="secondary" disabled={act.isPending} onClick={() => act.mutate(() => knowledgeApi.patchSource(s.id, { is_active: !s.is_active }))}>{s.is_active ? "Deactivate" : "Activate"}</Button>
        <ConfirmDialog trigger={<Button size="sm" variant="danger"><Trash2 aria-hidden />Delete</Button>} title="Delete this source?"
          description="Its indexed passages and stored file are removed. Past answers keep their citation text." confirmLabel="Delete source"
          onConfirm={async () => { await knowledgeApi.deleteSource(s.id); onDone(); }} />
      </div>
      {act.isError && <InlineError message={errorMessage(act.error)} />}
      {detail.data?.ingest_log && detail.data.ingest_log.length > 0 && (
        <details><summary className="cursor-pointer text-muted">Processing log ({detail.data.ingest_log.length})</summary>
          <ol className="mt-1 flex flex-col gap-0.5 font-mono text-xs text-ink-soft">
            {detail.data.ingest_log.slice().reverse().map((l, i) => {
              const { at, event, ...rest } = l;
              return <li key={i}>{at} {event} {Object.keys(rest).length ? JSON.stringify(rest) : ""}</li>;
            })}
          </ol></details>
      )}
    </div>
  );
}

export function SourcesPanel({ isAdmin }: { isAdmin: boolean }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState<string | null>(null);
  const sources = useQuery({ queryKey: ["knowledge", "sources"], queryFn: knowledgeApi.sources,
    refetchInterval: (q) => (q.state.data?.some((s) => s.ingest_status === "queued" || s.ingest_status === "processing") ? 3000 : false) });
  const refresh = () => { void qc.invalidateQueries({ queryKey: ["knowledge"] }); };
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>Source register</CardTitle>
          {isAdmin && <RegisterDialog onDone={refresh} />}
        </div>
        <CardDescription>Only active sources with a verified licence are searched. Unverified and blocked sources are listed for transparency.{!isAdmin && " Sources are managed by an administrator."}</CardDescription>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        {sources.isPending && <LoadingRows rows={3} label="Loading sources" />}
        {sources.isError && <ErrorState message={errorMessage(sources.error)} onRetry={() => sources.refetch()} />}
        {sources.isSuccess && sources.data.length === 0 && <EmptyState as="h3" icon={BookOpenText} title="No sources registered" description="Sources are added by an administrator after their licence is checked." />}
        {sources.isSuccess && sources.data.length > 0 && (
          <table className="w-full min-w-[40rem] text-sm">
            <caption className="sr-only">Knowledge sources</caption>
            <thead className="text-start text-muted"><tr>
              <th className="py-1 pe-3 text-start">Title</th><th className="pe-3 text-start">Domain</th><th className="pe-3 text-start">Licence</th>
              <th className="pe-3 text-start">Review</th><th className="pe-3 text-start">Index</th><th className="text-end">Passages</th>
            </tr></thead>
            <tbody>
              {sources.data.map((s) => (
                <Fragment key={s.id}>
                  <tr className="border-t border-border align-top text-ink">
                    <td className="py-1.5 pe-3">
                      {isAdmin ? <button type="button" className="text-start underline-offset-2 hover:underline" aria-expanded={open === s.id} onClick={() => setOpen(open === s.id ? null : s.id)}>{s.title}</button> : s.title}
                      <div className="text-xs text-muted">{s.publisher}{!s.is_active && " · inactive"}</div>
                    </td>
                    <td className="pe-3 text-ink-soft">{s.domain ? DOMAIN_LABEL[s.domain] ?? s.domain : "—"}</td>
                    <td className="pe-3">{s.licence}</td>
                    <td className="pe-3"><Badge tone={REVIEW_TONE[s.review_status] ?? "warning"}>{s.review_status.replaceAll("_", " ")}</Badge></td>
                    <td className="pe-3"><Badge tone={INGEST_TONE[s.ingest_status] ?? "neutral"}>{s.ingest_status.replace("_", " ")}</Badge></td>
                    <td className="tabular text-end">{s.chunk_count}</td>
                  </tr>
                  {isAdmin && open === s.id && (
                    <tr className="bg-surface"><td colSpan={6} className="p-3"><SourceActions s={s} onDone={refresh} /></td></tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}
