import { FormField } from "@/components/ui/form-field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { MicButton } from "@/features/voice/VoiceControls";
import type { Observations, PlantPart, Symptom } from "@/services/api/cropHealth";
import { todayIso } from "@/utils/format";
import { PLANT_PART_LABEL, SYMPTOM_LABEL } from "./labels";
import { useL } from "@/i18n/useT";

interface Props {
  value: Observations;
  onChange: (v: Observations) => void;
  errors?: Partial<Record<keyof Observations, string>>;
}

/** Optional farmer observations. Recorded as reported; they are not a diagnosis. */
export function ObservationFields({ value, onChange, errors = {} }: Props) {
  const l = useL();
  const set = <K extends keyof Observations>(k: K, v: Observations[K]) => onChange({ ...value, [k]: v });
  const toggle = (s: Symptom) =>
    set("symptoms", value.symptoms.includes(s) ? value.symptoms.filter((x) => x !== s) : [...value.symptoms, s]);

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label={l("Plant part photographed")} optional>
          <Select value={value.plant_part} onChange={(e) => set("plant_part", e.target.value as PlantPart | "")}>
            <option value="">{l("Not specified")}</option>
            {Object.entries(PLANT_PART_LABEL).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField label={l("When did you notice it?")} optional error={errors.observed_on}>
          <Input type="date" max={todayIso()} value={value.observed_on}
            onChange={(e) => set("observed_on", e.target.value)} />
        </FormField>
      </div>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1.5 text-sm font-medium text-ink">
          {l("What do you see?")} <span className="font-normal text-muted">{l("(optional)")}</span>
        </legend>
        <div className="flex flex-wrap gap-2">
          {(Object.keys(SYMPTOM_LABEL) as Symptom[]).map((s) => {
            const on = value.symptoms.includes(s);
            return (
              <label key={s}
                className={`flex h-10 cursor-pointer items-center gap-2 rounded-full border px-3.5 text-sm transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-primary ${
                  on ? "border-primary bg-primary-soft text-primary-dark" : "border-border-strong bg-card text-ink-soft hover:bg-surface"
                }`}>
                <input type="checkbox" className="sr-only" checked={on} onChange={() => toggle(s)} />
                {l(SYMPTOM_LABEL[s])}
              </label>
            );
          })}
        </div>
      </fieldset>
      <FormField label={l("Notes")} optional error={errors.notes}
        hint={l("For example: where on the plant, how many plants, recent weather or sprays.")}>
        <Textarea rows={3} maxLength={2000} value={value.notes} onChange={(e) => set("notes", e.target.value)} />
      </FormField>
      <MicButton onText={(t) => set("notes", (value.notes ? `${value.notes} ` : "") + t)} />
    </div>
  );
}
