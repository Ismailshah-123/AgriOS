/**
 * FR13 offline drafts for Crop Doctor cases (the only offline-capable form so far).
 * A draft = the new-case form + photo Blobs, stored per user in IndexedDB under the case's
 * client_id. Sync re-sends with the SAME client_id, and the server returns the case made by
 * an earlier attempt instead of creating a duplicate (backend crop_health/service.py).
 * No tokens or other account data are stored. Where IndexedDB is unavailable (tests,
 * some private modes) drafts live in memory for the session and the UI says so.
 */
import type { Observations } from "@/services/api/cropHealth";

export type DraftStatus = "pending" | "syncing" | "needs_attention";

export interface CaseDraft {
  client_id: string;
  user_id: string;
  created_at: string;
  status: DraftStatus;
  last_error: string | null;
  input: { crop_cycle_id: string; consent_training: boolean } & Observations;
  photos: { name: string; type: string; blob: Blob }[];
}

const DB = "agrios-offline", STORE = "case_drafts";
const memory = new Map<string, CaseDraft>();
let persistent: boolean | null = null;

function openDb(): Promise<IDBDatabase | null> {
  if (typeof indexedDB === "undefined") return Promise.resolve(null);
  return new Promise((resolve) => {
    try {
      const req = indexedDB.open(DB, 1);
      req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: "client_id" });
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
    } catch {
      resolve(null);
    }
  });
}

async function tx<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T | undefined> {
  const db = await openDb();
  persistent = db !== null;
  if (!db) return undefined;
  return new Promise((resolve, reject) => {
    const req = fn(db.transaction(STORE, mode).objectStore(STORE));
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

/** True when drafts survive closing the browser (IndexedDB available). */
export function draftsArePersistent(): boolean | null {
  return persistent;
}

export function newClientId(): string {
  return crypto.randomUUID();
}

export async function saveDraft(d: CaseDraft): Promise<void> {
  memory.set(d.client_id, d);
  await tx("readwrite", (s) => s.put(d));
}

export async function listDrafts(userId: string): Promise<CaseDraft[]> {
  const all = (await tx("readonly", (s) => s.getAll() as IDBRequest<CaseDraft[]>)) ?? [...memory.values()];
  return all.filter((d) => d.user_id === userId).sort((a, b) => a.created_at.localeCompare(b.created_at));
}

export async function removeDraft(clientId: string): Promise<void> {
  memory.delete(clientId);
  await tx("readwrite", (s) => s.delete(clientId));
}

export function draftPhotos(d: CaseDraft): File[] {
  return d.photos.map((p) => new File([p.blob], p.name, { type: p.type }));
}

/** Test helper: forget in-memory drafts. */
export function _resetMemoryDrafts(): void {
  memory.clear();
}
