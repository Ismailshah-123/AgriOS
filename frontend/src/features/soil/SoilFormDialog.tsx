import { Pencil, Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { InlineError } from "@/components/ui/feedback";
import { FormField } from "@/components/ui/form-field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { useCreateSoil, useUpdateSoil } from "@/features/intelligence/queries";
import { TEXTURES, type SoilInput, type SoilObservation } from "@/services/api/intelligence";
import { errorMessage, formatDate } from "@/utils/format";
import { SOIL_MEASURES } from "./measures";

const METHODS: Record<string, [string, string][]> = {
  ph_method: [["unknown", "Unknown"], ["water_1_1", "Water 1:1"], ["water_1_2_5", "Water 1:2.5"], ["saturated_paste", "Saturated paste"], ["cacl2", "CaCl2"]],
  ec_method: [["unknown", "Unknown"], ["saturated_paste_ece", "Saturated paste (ECe)"], ["extract_1_1", "1:1 extract"], ["extract_1_2_5", "1:2.5 extract"], ["extract_1_5", "1:5 extract"]],
  phosphorus_method: [["unknown", "Unknown"], ["olsen", "Olsen"], ["bray_1", "Bray-1"], ["mehlich_3", "Mehlich-3"]],
};

interface SoilFormDialogProps {
  fieldId: string;
  /** Present = edit this test (PATCH); absent = add a new one. */
  initial?: SoilObservation;
}

export function SoilFormDialog({ fieldId, initial }: SoilFormDialogProps) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const create = useCreateSoil();
  const update = useUpdateSoil();
  const saving = create.isPending || update.isPending;
  const init = initial as unknown as Record<string, string | number | null> | undefined;
  const dv = (k: string, fallback = "") => (init?.[k] == null ? fallback : String(init[k]));

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const v = (k: string) => {
      const s = String(fd.get(k) ?? "").trim();
      return s === "" ? null : s;
    };
    const values = Object.fromEntries(SOIL_MEASURES.map((m) => [m.key, v(m.key)]));
    const texture = v("texture");
    if (Object.values(values).every((x) => x === null) && !texture) {
      setError("Enter at least one measured value. Leave unmeasured values empty.");
      return;
    }
    const origin = v("data_origin") as "measured" | "farmer_entered";
    if (origin === "measured" && !v("lab_name")) {
      setError("Laboratory results need the laboratory name (otherwise choose 'Field kit / manual').");
      return;
    }
    const body: SoilInput = {
      field_id: fieldId, sampled_on: String(fd.get("sampled_on")), data_origin: origin,
      lab_name: v("lab_name"), lab_reference: v("lab_reference"),
      depth_from_cm: v("depth_from_cm"), depth_to_cm: v("depth_to_cm"),
      ...values, texture, notes: v("notes"),
      ph_method: v("ph_method"), ec_method: v("ec_method"), phosphorus_method: v("phosphorus_method"),
    };
    setError(null);
    const done = { onSuccess: () => setOpen(false), onError: (err: unknown) => setError(errorMessage(err)) };
    if (initial) {
      const changes: Partial<SoilInput> = { ...body };
      delete changes.field_id; // a test cannot move to another field
      update.mutate({ id: initial.id, body: changes as Omit<SoilInput, "field_id"> }, done);
    } else {
      create.mutate(body, done);
    }
  }

  const when = initial ? formatDate(initial.sampled_on) : "";
  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); setError(null); }}>
      <DialogTrigger asChild>
        {initial ? (
          <Button variant="ghost" size="sm" aria-label={`Edit soil test of ${when}`}>
            <Pencil aria-hidden /><span className="md:sr-only">Edit</span>
          </Button>
        ) : (
          <Button><Plus aria-hidden />Add soil test</Button>
        )}
      </DialogTrigger>
      <DialogContent
        title={initial ? `Edit soil test of ${when}` : "Add a soil test"}
        description="Copy values exactly as on the lab report. Leave anything not measured empty."
      >
        <form onSubmit={submit} className="grid gap-3" noValidate>
          <div className="grid gap-3 sm:grid-cols-2">
            <FormField label="Sample date"><Input name="sampled_on" type="date" required defaultValue={dv("sampled_on")} max={new Date().toISOString().slice(0, 10)} /></FormField>
            <FormField label="Origin">
              <Select name="data_origin" defaultValue={dv("data_origin", "measured")}>
                <option value="measured">Laboratory report (measured)</option>
                <option value="farmer_entered">Field kit / manual (farmer entered)</option>
              </Select>
            </FormField>
            <FormField label="Laboratory" optional><Input name="lab_name" maxLength={120} defaultValue={dv("lab_name")} /></FormField>
            <FormField label="Lab reference" optional><Input name="lab_reference" maxLength={80} defaultValue={dv("lab_reference")} /></FormField>
            <FormField label="Depth from (cm)" optional><Input name="depth_from_cm" type="number" min={0} step="0.1" defaultValue={dv("depth_from_cm")} /></FormField>
            <FormField label="Depth to (cm)" optional><Input name="depth_to_cm" type="number" min={0} step="0.1" defaultValue={dv("depth_to_cm")} /></FormField>
          </div>
          <fieldset className="grid gap-3 sm:grid-cols-2">
            <legend className="mb-1 text-sm font-semibold text-ink">Measurements (units as shown)</legend>
            {SOIL_MEASURES.map((m) => (
              <div key={m.key} className="grid gap-1">
                <FormField label={`${m.label} (${m.unit})`} optional>
                  <Input name={m.key} type="number" min={0} step="any" inputMode="decimal" defaultValue={dv(m.key)} />
                </FormField>
                {m.method && (
                  <Select name={m.method} aria-label={`${m.label} method`} defaultValue={dv(m.method, "unknown")}>
                    {METHODS[m.method]!.map(([val, label]) => <option key={val} value={val}>{label}</option>)}
                  </Select>
                )}
              </div>
            ))}
            <FormField label="Texture" optional>
              <Select name="texture" defaultValue={dv("texture")}>
                <option value="">Not reported</option>
                {TEXTURES.map((t) => <option key={t} value={t}>{t.replaceAll("_", " ")}</option>)}
              </Select>
            </FormField>
          </fieldset>
          <FormField label="Notes" optional><Textarea name="notes" maxLength={1000} rows={2} defaultValue={dv("notes")} /></FormField>
          {error && <InlineError message={error} />}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={saving}>{saving ? "Saving…" : initial ? "Save changes" : "Save soil test"}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
