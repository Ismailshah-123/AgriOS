import { zodResolver } from "@hookform/resolvers/zod";
import { useState, type ReactElement } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { InlineError } from "@/components/ui/feedback";
import { FormField } from "@/components/ui/form-field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { useCrops, useFields, useSaveCycle } from "@/features/platform/queries";
import { ApiError } from "@/services/api/client";
import type { CropCycle, CycleStatus, Season } from "@/services/api/types";
import { errorMessage, SEASON_LABEL, STATUS_LABEL, todayIso } from "@/utils/format";

// Client copy of the server rules in app/farms/service.py::validate_cycle.
// The server remains authoritative; this only gives earlier, clearer feedback.
const cycleSchema = z
  .object({
    field_id: z.string().min(1, "Choose a field."),
    crop_id: z.string().min(1, "Choose a crop."),
    variety: z.string().trim().max(120, "Use 120 characters or fewer."),
    season: z.string(),
    status: z.enum(["planned", "active", "harvested", "abandoned"]),
    sowing_date: z.string(),
    expected_harvest_date: z.string(),
    harvest_date: z.string(),
    notes: z.string().trim().max(1000, "Use 1000 characters or fewer."),
  })
  .superRefine((v, ctx) => {
    const today = todayIso();
    const issue = (path: string, message: string) => ctx.addIssue({ code: "custom", path: [path], message });
    if ((v.status === "active" || v.status === "harvested") && !v.sowing_date) {
      issue("sowing_date", "A sowing date is required for this status.");
    }
    if ((v.status === "active" || v.status === "harvested") && v.sowing_date > today) {
      issue("sowing_date", "Sowing date cannot be in the future for this status.");
    }
    if (v.status === "harvested" && !v.harvest_date) {
      issue("harvest_date", "A harvest date is required for a harvested cycle.");
    }
    if (v.harvest_date && v.harvest_date > today) {
      issue("harvest_date", "Harvest date cannot be in the future.");
    }
    if (v.harvest_date && v.sowing_date && v.harvest_date < v.sowing_date) {
      issue("harvest_date", "Harvest date must be on or after the sowing date.");
    }
    if (v.expected_harvest_date && v.sowing_date && v.expected_harvest_date < v.sowing_date) {
      issue("expected_harvest_date", "Expected harvest must be on or after sowing.");
    }
  });
type Values = z.infer<typeof cycleSchema>;

interface CycleFormDialogProps {
  trigger: ReactElement;
  cycle?: CropCycle;
}

export function CycleFormDialog({ trigger, cycle }: CycleFormDialogProps) {
  const [open, setOpen] = useState(false);
  const save = useSaveCycle(cycle?.id);
  const fields = useFields();
  const crops = useCrops();
  const [serverError, setServerError] = useState<string | null>(null);
  const defaults: Values = {
    field_id: cycle?.field_id ?? "",
    crop_id: cycle?.crop.id ?? "",
    variety: cycle?.variety ?? "",
    season: cycle?.season ?? "",
    status: cycle?.status ?? "planned",
    sowing_date: cycle?.sowing_date ?? "",
    expected_harvest_date: cycle?.expected_harvest_date ?? "",
    harvest_date: cycle?.harvest_date ?? "",
    notes: cycle?.notes ?? "",
  };
  const form = useForm<Values>({ resolver: zodResolver(cycleSchema), defaultValues: defaults });
  const { errors, isSubmitting } = form.formState;

  const onSubmit = form.handleSubmit(async (v) => {
    setServerError(null);
    try {
      await save.mutateAsync({
        ...(cycle ? {} : { field_id: v.field_id, crop_id: v.crop_id }),
        variety: v.variety || null,
        season: (v.season || null) as Season | null,
        status: v.status as CycleStatus,
        sowing_date: v.sowing_date || null,
        expected_harvest_date: v.expected_harvest_date || null,
        harvest_date: v.harvest_date || null,
        notes: v.notes || null,
      });
      setOpen(false);
    } catch (err) {
      if (err instanceof ApiError && err.field && err.field in v) {
        form.setError(err.field as keyof Values, { message: err.message });
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
      <DialogContent title={cycle ? "Edit crop cycle" : "Start a crop cycle"}>
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
          {serverError && <InlineError message={serverError} />}
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Field" error={errors.field_id?.message}>
              <Select disabled={Boolean(cycle)} {...form.register("field_id")}>
                <option value="">Choose a field</option>
                {fields.data?.items.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name} · {f.farm_name}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField label="Crop" error={errors.crop_id?.message}>
              <Select disabled={Boolean(cycle)} {...form.register("crop_id")}>
                <option value="">Choose a crop</option>
                {crops.data?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name_en}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField label="Variety" optional error={errors.variety?.message}>
              <Input {...form.register("variety")} />
            </FormField>
            <FormField label="Season" optional>
              <Select {...form.register("season")}>
                <option value="">Not specified</option>
                {Object.entries(SEASON_LABEL).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField label="Status">
              <Select {...form.register("status")}>
                {Object.entries(STATUS_LABEL).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField label="Sowing date" optional error={errors.sowing_date?.message}>
              <Input type="date" {...form.register("sowing_date")} />
            </FormField>
            <FormField label="Expected harvest" optional error={errors.expected_harvest_date?.message}>
              <Input type="date" {...form.register("expected_harvest_date")} />
            </FormField>
            <FormField label="Harvest date" optional error={errors.harvest_date?.message}>
              <Input type="date" {...form.register("harvest_date")} />
            </FormField>
          </div>
          <FormField label="Notes" optional error={errors.notes?.message}>
            <Textarea rows={2} {...form.register("notes")} />
          </FormField>
          <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Saving…" : cycle ? "Save changes" : "Start cycle"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
