import { useQueryClient } from "@tanstack/react-query";
import { CloudOff, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useAuth } from "@/features/auth/auth-context";
import { draftsArePersistent, removeDraft, type CaseDraft } from "./drafts";
import { syncDrafts, useCaseDrafts } from "./sync";

const STATUS: Record<CaseDraft["status"], { label: string; tone: "warning" | "info" | "danger" }> = {
  pending: { label: "Not uploaded yet", tone: "warning" },
  syncing: { label: "Uploading", tone: "info" },
  needs_attention: { label: "Needs attention", tone: "danger" },
};
const when = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** Sync center for Crop Doctor drafts; renders nothing when there are none. */
export function OfflineDrafts() {
  const userId = useAuth().user?.id ?? "";
  const qc = useQueryClient();
  const drafts = useCaseDrafts();
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const sync = useCallback(async () => {
    if (!userId) return;
    setBusy(true);
    const r = await syncDrafts(userId);
    setBusy(false);
    setNote(r.uploaded ? `${r.uploaded} case${r.uploaded === 1 ? "" : "s"} uploaded.` : r.failed ? "Still not uploaded. AgriOS will try again when you are online." : null);
    await qc.invalidateQueries({ queryKey: ["drafts", userId] });
    if (r.uploaded) await qc.invalidateQueries({ queryKey: ["crop-health"] });
  }, [qc, userId]);

  useEffect(() => {
    window.addEventListener("online", sync);
    return () => window.removeEventListener("online", sync);
  }, [sync]);

  const items = drafts.data ?? [];
  if (items.length === 0) return note ? <p className="text-sm text-muted" role="status">{note}</p> : null;
  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
        <div>
          <div className="flex items-center gap-2"><CloudOff aria-hidden className="size-5 text-warning" /><CardTitle>Saved on this device</CardTitle></div>
          <CardDescription>
            {draftsArePersistent() === false
              ? "Kept only until this browser tab closes (device storage is unavailable)."
              : "Not yet uploaded. They upload when you are online; nothing is sent twice."}
          </CardDescription>
        </div>
        <Button variant="secondary" disabled={busy} onClick={() => void sync()}><RefreshCw aria-hidden />{busy ? "Uploading…" : "Upload now"}</Button>
      </CardHeader>
      <CardContent>
        <ul className="divide-y divide-border">
          {items.map((d) => (
            <li key={d.client_id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
              <span className="min-w-0">
                <span className="text-ink">New case · {d.photos.length} photo{d.photos.length === 1 ? "" : "s"} · {when.format(new Date(d.created_at))}</span>
                {d.last_error && <span className="block text-xs text-danger">{d.last_error}</span>}
              </span>
              <span className="flex items-center gap-2">
                <Badge tone={STATUS[d.status].tone}>{STATUS[d.status].label}</Badge>
                <ConfirmDialog title="Discard this saved case?" description="The photos and notes saved on this device are deleted. Nothing was uploaded."
                  confirmLabel="Discard" onConfirm={async () => { await removeDraft(d.client_id); await qc.invalidateQueries({ queryKey: ["drafts", userId] }); }}
                  trigger={<Button variant="ghost" size="sm" aria-label="Discard saved case"><Trash2 aria-hidden /></Button>} />
              </span>
            </li>
          ))}
        </ul>
        {note && <p className="mt-2 text-sm text-muted" role="status">{note}</p>}
      </CardContent>
    </Card>
  );
}
