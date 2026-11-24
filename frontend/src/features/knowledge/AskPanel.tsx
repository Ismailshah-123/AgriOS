import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquarePlus, Send, Trash2 } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { InlineError, LoadingRows } from "@/components/ui/feedback";
import { Select, Textarea } from "@/components/ui/input";
import { MicButton } from "@/features/voice/VoiceControls";
import { DOMAIN_LABEL, knowledgeApi, type AskInput, type AskResult } from "@/services/api/knowledge";
import { errorMessage } from "@/utils/format";
import { AnswerCard } from "./AnswerCard";
import { useL } from "@/i18n/useT";

const EXAMPLES = [
  "Why are my tomato leaves developing yellow spots?",
  "What are the recommended practices for managing soil salinity?",
  "What are the major differences between drip and flood irrigation?",
  "ٹماٹر کے پتوں پر پیلے دھبے کیوں آتے ہیں؟",
  "Summarise the soil tests for my fields",
];

/** Conversational, cited Q&A over the verified library (+ the user's own farm records). */
export function AskPanel({ searchable }: { searchable: number }) {
  const l = useL();
  const qc = useQueryClient();
  const [question, setQuestion] = useState("");
  const [conversation, setConversation] = useState<string | null>(null);
  const [thread, setThread] = useState<AskResult[]>([]);
  const [language, setLanguage] = useState<AskInput["language"]>("auto");
  const [domain, setDomain] = useState("");
  const [crop, setCrop] = useState("");
  const [farm, setFarm] = useState<AskInput["farm_context"]>("auto");
  const endRef = useRef<HTMLDivElement>(null);
  const taxonomy = useQuery({ queryKey: ["knowledge", "taxonomy"], queryFn: knowledgeApi.taxonomy, staleTime: Infinity });
  const history = useQuery({ queryKey: ["knowledge", "conversations"], queryFn: knowledgeApi.conversations });
  const ask = useMutation({
    mutationFn: (q: string) => knowledgeApi.ask({
      question: q, conversation_id: conversation ?? undefined, language, farm_context: farm,
      domain: domain || undefined, crop: crop || undefined,
    }),
    onSuccess: (r) => {
      setThread((t) => [...t, r]);
      setConversation(r.conversation_id);
      setQuestion("");
      void qc.invalidateQueries({ queryKey: ["knowledge", "conversations"] });
      void qc.invalidateQueries({ queryKey: ["knowledge", "stats"] });
    },
  });  // prettier-ignore
  useEffect(() => { endRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" }); }, [thread.length]);

  async function openConversation(id: string) {
    setConversation(id);
    setThread(await knowledgeApi.conversation(id));
  }
  function newConversation() {
    setConversation(null);
    setThread([]);
    ask.reset();
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (q.length >= 3 && !ask.isPending) ask.mutate(q);
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[16rem_minmax(0,1fr)]">
      <Card className="order-2 p-3 lg:order-1">
        <div className="mb-2 flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-ink">{l("Conversations")}</h2>
          <Button variant="ghost" size="sm" onClick={newConversation}><MessageSquarePlus aria-hidden />New</Button>
        </div>
        {history.isPending && <LoadingRows rows={2} label="Loading conversations" />}
        {history.isSuccess && history.data.length === 0 && <p className="text-xs text-muted">{l("No conversations yet.")}</p>}
        <ul className="flex max-h-80 flex-col gap-1 overflow-y-auto">
          {history.data?.map((c) => (
            <li key={c.id} className="flex items-center gap-1">
              <button type="button" onClick={() => void openConversation(c.id)} aria-current={c.id === conversation ? "true" : undefined}
                className="min-w-0 flex-1 truncate rounded px-2 py-1.5 text-start text-sm text-ink-soft hover:bg-surface aria-[current=true]:bg-primary-soft aria-[current=true]:text-primary-dark">
                {c.title}
              </button>
              <ConfirmDialog trigger={<Button variant="ghost" size="sm" aria-label={`Delete conversation ${c.title}`}><Trash2 aria-hidden /></Button>}
                title="Delete conversation?" description="The questions and answers in it are removed." confirmLabel="Delete"
                onConfirm={async () => { await knowledgeApi.deleteConversation(c.id); if (c.id === conversation) newConversation(); await qc.invalidateQueries({ queryKey: ["knowledge", "conversations"] }); }} />
            </li>
          ))}
        </ul>
      </Card>

      <div className="order-1 flex min-w-0 flex-col gap-4 lg:order-2">
        {searchable === 0 && (
          <Card className="p-4 text-sm text-ink-soft" role="status">The verified source library is empty: no source licence has been verified yet, so questions will get “No verified guidance”.</Card>
        )}
        {thread.length === 0 && !ask.isPending && (
          <Card className="p-4">
            <p className="text-sm text-ink-soft">{l("Ask in English or Urdu. Answers use only licence-verified sources and cite them; your own farm records are added when you ask about “my” farm, fields or crops.")}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {EXAMPLES.map((x) => (
                <button key={x} type="button" onClick={() => setQuestion(x)} className="rounded-full border border-border px-3 py-1 text-xs text-ink-soft hover:bg-surface">{x}</button>
              ))}
            </div>
          </Card>
        )}
        <div className="flex flex-col gap-4" aria-live="polite">
          {thread.map((r) => (
            <div key={r.id} className="flex flex-col gap-2">
              <p className="self-end rounded-[var(--radius-card)] bg-primary-soft px-3 py-2 text-sm text-primary-dark" dir="auto">{r.question}</p>
              <AnswerCard r={r} />
            </div>
          ))}
          {ask.isPending && <Card><LoadingRows rows={3} label="Searching verified sources" /></Card>}
          <div ref={endRef} />
        </div>
        <Card className="p-4">
          <form onSubmit={submit} className="flex flex-col gap-3">
            <label htmlFor="kq" className="text-sm font-medium text-ink">{thread.length ? l("Follow-up question") : l("Question")}</label>
            <Textarea id="kq" dir="auto" rows={2} maxLength={600} value={question} onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. How do I manage early blight on tomato?"
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(e); } }} />
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 2xl:grid-cols-4">
              <label className="flex flex-col gap-1 text-xs text-muted">{l("Language")}
                <Select value={language} onChange={(e) => setLanguage(e.target.value as AskInput["language"])}>
                  <option value="auto">{l("Auto-detect")}</option><option value="en">English</option><option value="ur">اردو</option>
                </Select></label>
              <label className="flex flex-col gap-1 text-xs text-muted">{l("Domain")}
                <Select value={domain} onChange={(e) => setDomain(e.target.value)}>
                  <option value="">{l("All domains")}</option>
                  {taxonomy.data?.domains.map((d) => <option key={d} value={d}>{DOMAIN_LABEL[d] ?? d}</option>)}
                </Select></label>
              <label className="flex flex-col gap-1 text-xs text-muted">{l("Crop")}
                <Select value={crop} onChange={(e) => setCrop(e.target.value)}>
                  <option value="">{l("All crops")}</option>
                  {taxonomy.data?.crops.map((c) => <option key={c} value={c}>{c}</option>)}
                </Select></label>
              <label className="flex flex-col gap-1 text-xs text-muted">{l("My farm records")}
                <Select value={farm} onChange={(e) => setFarm(e.target.value as AskInput["farm_context"])}>
                  <option value="auto">When I ask about “my” farm</option><option value="on">Always include</option><option value="off">Never include</option>
                </Select></label>
            </div>
            {ask.isError && <InlineError message={errorMessage(ask.error)} />}
            <div className="flex flex-wrap items-center gap-2">
              <Button type="submit" disabled={question.trim().length < 3 || ask.isPending}><Send aria-hidden />{l("Ask")}</Button>
              <MicButton onText={(t) => setQuestion(t)} />
              {conversation && <Button type="button" variant="ghost" onClick={newConversation}>{l("Start a new conversation")}</Button>}
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
}
