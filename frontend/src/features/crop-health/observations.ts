import type { Observations } from "@/services/api/cropHealth";
import { todayIso } from "@/utils/format";

export const EMPTY_OBSERVATIONS: Observations = {
  plant_part: "",
  symptoms: [],
  observed_on: "",
  notes: "",
};

export function observationErrors(o: Observations): Partial<Record<keyof Observations, string>> {
  const e: Partial<Record<keyof Observations, string>> = {};
  if (o.observed_on && o.observed_on > todayIso()) e.observed_on = "The date cannot be in the future.";
  if (o.notes.length > 2000) e.notes = "Use 2000 characters or fewer.";
  return e;
}
