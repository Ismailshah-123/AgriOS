import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  cropsApi,
  cyclesApi,
  farmsApi,
  fieldsApi,
  overviewApi,
  type CycleFilters,
} from "@/services/api/platform";
import type { CropCycleInput, FarmInput, FieldInput } from "@/services/api/types";

/** Lists are capped at 100 per request (API maximum); pagination UI comes when needed. */
export const LIST_LIMIT = 100;

export const keys = {
  farms: (q?: string) => ["farms", { q }] as const,
  farm: (id: string) => ["farms", id] as const,
  fields: (farmId?: string) => ["fields", { farmId }] as const,
  crops: ["crops"] as const,
  cycles: (f: CycleFilters = {}) => ["crop-cycles", f] as const,
  overview: ["overview"] as const,
};

// Any farm-domain write can change counts shown elsewhere (farm area, active cycles).
function useInvalidateFarmDomain() {
  const qc = useQueryClient();
  return () =>
    Promise.all(
      ["farms", "fields", "crop-cycles", "overview"].map((k) =>
        qc.invalidateQueries({ queryKey: [k] }),
      ),
    );
}

export function useFarms(q?: string) {
  return useQuery({
    queryKey: keys.farms(q),
    queryFn: () => farmsApi.list({ q, limit: LIST_LIMIT }),
  });
}

export function useFarm(id: string) {
  return useQuery({ queryKey: keys.farm(id), queryFn: () => farmsApi.get(id) });
}

export function useFields(farmId?: string) {
  return useQuery({
    queryKey: keys.fields(farmId),
    queryFn: () => fieldsApi.list({ farm_id: farmId, limit: LIST_LIMIT }),
  });
}

export function useCrops() {
  return useQuery({ queryKey: keys.crops, queryFn: cropsApi.list, staleTime: 10 * 60_000 });
}

export function useCycles(filters: CycleFilters = {}) {
  return useQuery({
    queryKey: keys.cycles(filters),
    queryFn: () => cyclesApi.list({ ...filters, limit: LIST_LIMIT }),
  });
}

export function useSaveFarm(id?: string) {
  const invalidate = useInvalidateFarmDomain();
  return useMutation({
    mutationFn: (body: FarmInput) => (id ? farmsApi.update(id, body) : farmsApi.create(body)),
    onSuccess: invalidate,
  });
}

export function useDeleteFarm() {
  const invalidate = useInvalidateFarmDomain();
  return useMutation({ mutationFn: farmsApi.remove, onSuccess: invalidate });
}

export function useSaveField(id?: string) {
  const invalidate = useInvalidateFarmDomain();
  return useMutation({
    mutationFn: (body: FieldInput) => (id ? fieldsApi.update(id, body) : fieldsApi.create(body)),
    onSuccess: invalidate,
  });
}

export function useDeleteField() {
  const invalidate = useInvalidateFarmDomain();
  return useMutation({ mutationFn: fieldsApi.remove, onSuccess: invalidate });
}

export function useSaveCycle(id?: string) {
  const invalidate = useInvalidateFarmDomain();
  return useMutation({
    mutationFn: (body: CropCycleInput) =>
      id ? cyclesApi.update(id, body) : cyclesApi.create(body),
    onSuccess: invalidate,
  });
}

export function useDeleteCycle() {
  const invalidate = useInvalidateFarmDomain();
  return useMutation({ mutationFn: cyclesApi.remove, onSuccess: invalidate });
}

export function useOverview() {
  return useQuery({ queryKey: keys.overview, queryFn: overviewApi.get });
}
