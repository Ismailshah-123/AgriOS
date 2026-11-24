import { useQuery } from "@tanstack/react-query";
import { getHealth, getReadiness } from "@/services/api/system";

export const systemKeys = {
  health: ["system", "health"] as const,
  readiness: ["system", "readiness"] as const,
};

const REFRESH_MS = 30_000;

export function useApiHealth() {
  return useQuery({
    queryKey: systemKeys.health,
    queryFn: ({ signal }) => getHealth(signal),
    refetchInterval: REFRESH_MS,
    retry: false,
  });
}

export function useApiReadiness() {
  return useQuery({
    queryKey: systemKeys.readiness,
    queryFn: ({ signal }) => getReadiness(signal),
    refetchInterval: REFRESH_MS,
    retry: false,
  });
}
