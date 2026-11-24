import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { cropHealthApi, reviewApi, type CaseFilters } from "@/services/api/cropHealth";

// Signed image links live 10 minutes; refetch well before they expire.
const LINK_SAFE_MS = 4 * 60_000;

export const chKeys = {
  all: ["crop-health"] as const,
  summary: ["crop-health", "summary"] as const,
  list: (f: CaseFilters) => ["crop-health", "list", f] as const,
  case: (id: string) => ["crop-health", "case", id] as const,
};

export function useExplanation(caseId: string, scope: "owner" | "review" = "owner") {
  return useQuery({
    queryKey: [...chKeys.case(caseId), "explanation", scope],
    queryFn: () => (scope === "review" ? reviewApi.explanation(caseId) : cropHealthApi.explanation(caseId)),
    staleTime: LINK_SAFE_MS,
    refetchInterval: LINK_SAFE_MS,
  });
}

export function useCaseSummary() {
  return useQuery({ queryKey: chKeys.summary, queryFn: cropHealthApi.summary });
}

export function useCaseList(filters: CaseFilters, pageSize = 12) {
  return useInfiniteQuery({
    queryKey: chKeys.list({ ...filters, limit: pageSize }),
    queryFn: ({ pageParam }) => cropHealthApi.list({ ...filters, limit: pageSize, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    staleTime: LINK_SAFE_MS,
    refetchInterval: LINK_SAFE_MS,
  });
}

export function useCase(id: string) {
  return useQuery({
    queryKey: chKeys.case(id),
    queryFn: () => cropHealthApi.get(id),
    staleTime: LINK_SAFE_MS,
    refetchInterval: (q) => {
      const s = q.state.data?.inference_status;
      // Poll while analysis is pending; otherwise refresh links before they expire.
      return s === "queued" || s === "running" ? 5000 : LINK_SAFE_MS;
    },
  });
}

function useInvalidate() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: chKeys.all });
}

export function useCreateCase() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (v: { input: Parameters<typeof cropHealthApi.create>[0]; onProgress?: (f: number) => void }) =>
      cropHealthApi.create(v.input, v.onProgress),
    onSuccess: invalidate,
  });
}

export function useFollowUp(id: string) {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (v: { input: Parameters<typeof cropHealthApi.followUp>[1]; onProgress?: (f: number) => void }) =>
      cropHealthApi.followUp(id, v.input, v.onProgress),
    onSuccess: invalidate,
  });
}

export function useRetryAnalysis(id: string) {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: () => cropHealthApi.retry(id), onSuccess: invalidate });
}
