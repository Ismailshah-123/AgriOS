import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/features/auth/auth-context";
import { ApiError } from "@/services/api/client";
import { cropHealthApi } from "@/services/api/cropHealth";
import { errorMessage } from "@/utils/format";
import { draftPhotos, listDrafts, removeDraft, saveDraft } from "./drafts";

/** Uploads pending drafts with their original client_id (the server de-duplicates). */
export async function syncDrafts(userId: string): Promise<{ uploaded: number; failed: number }> {
  let uploaded = 0, failed = 0;
  for (const d of await listDrafts(userId)) {
    if (d.status === "needs_attention") continue;
    await saveDraft({ ...d, status: "syncing" });
    try {
      await cropHealthApi.create({ ...d.input, photos: draftPhotos(d), client_id: d.client_id });
      await removeDraft(d.client_id);
      uploaded++;
    } catch (err) {
      failed++;
      const offline = err instanceof ApiError && err.status === 0;
      await saveDraft({ ...d, status: offline ? "pending" : "needs_attention", last_error: offline ? null : errorMessage(err) });
      if (offline) break; // still offline: stop trying the rest
    }
  }
  return { uploaded, failed };
}

export function useCaseDrafts() {
  const userId = useAuth().user?.id ?? "";
  // networkMode "always": this reads IndexedDB, not the network. The default ("online") pauses
  // queries while offline, which hid the saved drafts exactly when the farmer is offline.
  return useQuery({ queryKey: ["drafts", userId], queryFn: () => listDrafts(userId), enabled: Boolean(userId), networkMode: "always" });
}
