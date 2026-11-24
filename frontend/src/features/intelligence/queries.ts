import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { agentsApi } from "@/services/api/agents";
import { irrigationApi, soilApi, weatherApi, type SoilInput } from "@/services/api/intelligence";

export const iKeys = {
  weather: (f: string) => ["weather", f] as const,
  water: (f: string) => ["water-demand", f] as const,
  soil: ["soil"] as const,
  soilSummary: (f: string) => ["soil", "summary", f] as const,
  soilList: (f: string) => ["soil", "list", f] as const,
  agents: ["agents"] as const,
  runs: ["agents", "runs"] as const,
  actions: ["agents", "actions"] as const,
};

export function useWeather(fieldId: string) {
  return useQuery({
    queryKey: iKeys.weather(fieldId),
    queryFn: () => weatherApi.forField(fieldId),
    enabled: Boolean(fieldId),
    staleTime: 5 * 60_000,
  });
}

export function useWaterDemand(fieldId: string) {
  return useQuery({
    queryKey: iKeys.water(fieldId),
    queryFn: () => irrigationApi.waterDemand(fieldId),
    enabled: Boolean(fieldId),
    staleTime: 5 * 60_000,
  });
}

export function useSoilSummary(fieldId: string) {
  return useQuery({
    queryKey: iKeys.soilSummary(fieldId),
    queryFn: () => soilApi.summary(fieldId),
    enabled: Boolean(fieldId),
  });
}

export function useSoilList(fieldId: string) {
  return useQuery({
    queryKey: iKeys.soilList(fieldId),
    queryFn: () => soilApi.list(fieldId),
    enabled: Boolean(fieldId),
  });
}

export function useCreateSoil() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SoilInput) => soilApi.create(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: iKeys.soil }),
  });
}

export function useUpdateSoil() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Omit<SoilInput, "field_id"> }) =>
      soilApi.update(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: iKeys.soil }),
  });
}

export function useDeleteSoil() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => soilApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: iKeys.soil }),
  });
}

export function useAgentRuns() {
  return useQuery({ queryKey: iKeys.runs, queryFn: agentsApi.history });
}

export function useAgentRun(id: string | null) {
  return useQuery({
    queryKey: [...iKeys.runs, id],
    queryFn: () => agentsApi.get(id as string),
    enabled: Boolean(id),
  });
}

export function usePendingActions() {
  return useQuery({ queryKey: [...iKeys.actions, "pending"], queryFn: () => agentsApi.actions("pending") });
}

/** All statuses (newest 100); the history view drops pending ones. */
export function useActionHistory() {
  return useQuery({ queryKey: [...iKeys.actions, "all"], queryFn: () => agentsApi.actions() });
}

export function useAgentCatalogue() {
  return useQuery({ queryKey: [...iKeys.agents, "catalogue"], queryFn: agentsApi.catalogue, staleTime: Infinity });
}

export function useRunAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: agentsApi.run,
    onSuccess: () => qc.invalidateQueries({ queryKey: iKeys.agents }),
  });
}

export function useDecideAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: string; approve: boolean }) =>
      v.approve ? agentsApi.approve(v.id) : agentsApi.reject(v.id),
    onSuccess: () => {
      // An executed action may change farm location or sowing date everywhere.
      void qc.invalidateQueries();
    },
  });
}
