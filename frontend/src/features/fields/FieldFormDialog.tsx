import { zodResolver } from "@hookform/resolvers/zod";
import { useState, type ReactElement } from "react";
import { useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { InlineError } from "@/components/ui/feedback";
import { FormField } from "@/components/ui/form-field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { useFarms, useSaveField } from "@/features/platform/queries";
import { ApiError } from "@/services/api/client";
import type { AreaUnit, FieldRecord } from "@/services/api/types";
import { errorMessage, formatNumber } from "@/utils/format";

/** Exact definitions only (backend app/units/area.py). Kanal/marla await a verified source. */
const HECTARES_PER: Record<AreaUnit, number> = { ha: 1, acre: 0.40468564224 };

const schema = z.object({
  farm_id: z.string().min(1, "Choose a farm."),
  name: z.string().trim().min(1, "Enter a field name.").max(120, "Use 120 characters or fewer."),
  area_value: z
    .string()
    .trim()
    .min(1, "Enter the field area.")
    .refine((v) => /^\d+(\.\d{1,4})?$/.test(v) && Number(v) > 0, {
      message: "Enter a positive number with up to 4 decimals.",
    }),
  area_unit: z.enum(["ha", "acre"]),
  area_origin: z.enum(["farmer_entered", "measured"]),
  notes: z.string().trim().max(1000, "Use 1000 characters or fewer."),
});
type Values = z.infer<typeof schema>;

interface FieldFormDialogProps {
  trigger: ReactElement;
  field?: FieldRecord;
  /** Preselect (and lock) the farm, e.g. when adding from a farm page. */
  farmId?: string;
}

export function FieldFormDialog({ trigger, field, farmId }: FieldFormDialogProps) {
  const [open, setOpen] = useState(false);
  const save = useSaveField(field?.id);
  const farms = useFarms();
  const [serverError, setServerError] = useState<string | null>(null);
  const defaults: Values = {
    farm_id: field?.farm_id ?? farmId ?? "",
    name: field?.name ?? "",
    area_value: field ? String(field.area.value) : "",
    area_unit: field?.area.unit ?? "acre",
    area_origin: field?.area.data_origin === "measured" ? "measured" : "farmer_entered",
    notes: field?.notes ?? "",
  };
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: defaults });
  const { errors, isSubmitting } = form.formState;
  const [value, unit] = useWatch({ control: form.control, name: ["area_value", "area_unit"] });
  const preview = Number(value) > 0 ? Number(value) * HECTARES_PER[unit] : null;
  const lockFarm = Boolean(field || farmId);

  const onSubmit = form.handleSubmit(async (v) => {
    setServerError(null);
    try {
      await save.mutateAsync({
        ...(field ? {} : { farm_id: v.farm_id }),
        name: v.name,
        area: { value: v.area_value, unit: v.area_unit },
        area_origin: v.area_origin,
        notes: v.notes || null,
      });
      setOpen(false);
    } catch (err) {
      if (err instanceof ApiError && err.field === "name") {
        form.setError("name", { message: err.message });
      } else if (err instanceof ApiError && err.field === "area") {
        form.setError("area_value", { message: err.message });
      } else {
        setServerError(errorMessage(err));
      }
    }
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) form.reset(defaults);
        setServerError(null);
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent title={field ? "Edit field" : "Add a field"}>
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
          {serverError && <InlineError message={serverError} />}
          <FormField label="Farm" error={errors.farm_id?.message}>
            <Select disabled={lockFarm} {...form.register("farm_id")}>
              <option value="">Choose a farm</option>
              {farms.data?.items.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField label="Field name" error={errors.name?.message}>
            <Input autoComplete="off" {...form.register("name")} />
          </FormField>
          <div className="grid grid-cols-[1fr_auto] gap-3">
            <FormField
              label="Area"
              error={errors.area_value?.message}
              hint={preview !== null ? `= ${formatNumber(preview)} hectares` : undefined}
            >
              <Input inputMode="decimal" {...form.register("area_value")} />
            </FormField>
            <FormField label="Unit">
              <Select className="w-28" {...form.register("area_unit")}>
                <option value="acre">acres</option>
                <option value="ha">hectares</option>
              </Select>
            </FormField>
          </div>
          <FormField label="How was the area obtained?">
            <Select {...form.register("area_origin")}>
              <option value="farmer_entered">My own estimate</option>
              <option value="measured">Measured (survey or GPS)</option>
            </Select>
          </FormField>
          <FormField label="Notes" optional error={errors.notes?.message}>
            <Textarea rows={3} {...form.register("notes")} />
          </FormField>
          <p className="text-sm text-muted">
            Kanal and marla will be added once a verified official definition is recorded.
          </p>
          <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Saving…" : field ? "Save changes" : "Add field"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
