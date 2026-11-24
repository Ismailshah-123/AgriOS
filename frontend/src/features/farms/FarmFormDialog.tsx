import { zodResolver } from "@hookform/resolvers/zod";
import { useState, type ReactElement } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { InlineError } from "@/components/ui/feedback";
import { FormField } from "@/components/ui/form-field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { useSaveFarm } from "@/features/platform/queries";
import { ApiError } from "@/services/api/client";
import type { Farm, Province } from "@/services/api/types";
import { errorMessage, PROVINCE_LABEL } from "@/utils/format";

const coord = (min: number, max: number, label: string) =>
  z
    .string()
    .trim()
    .refine((v) => v === "" || (!Number.isNaN(Number(v)) && Number(v) >= min && Number(v) <= max), {
      message: `${label} must be between ${min} and ${max}.`,
    });

// Mirrors backend FarmCreate (app/farms/schemas.py).
const schema = z
  .object({
    name: z.string().trim().min(1, "Enter a farm name.").max(120, "Use 120 characters or fewer."),
    province: z.string(),
    district: z.string().trim().max(80, "Use 80 characters or fewer."),
    latitude: coord(-90, 90, "Latitude"),
    longitude: coord(-180, 180, "Longitude"),
    notes: z.string().trim().max(1000, "Use 1000 characters or fewer."),
  })
  .refine((v) => (v.latitude === "") === (v.longitude === ""), {
    message: "Enter both latitude and longitude, or neither.",
    path: ["longitude"],
  });
type Values = z.infer<typeof schema>;

interface FarmFormDialogProps {
  trigger: ReactElement;
  farm?: Farm;
  onSaved?: (farm: Farm) => void;
}

export function FarmFormDialog({ trigger, farm, onSaved }: FarmFormDialogProps) {
  const [open, setOpen] = useState(false);
  const save = useSaveFarm(farm?.id);
  const [serverError, setServerError] = useState<string | null>(null);
  const defaults: Values = {
    name: farm?.name ?? "",
    province: farm?.province ?? "",
    district: farm?.district ?? "",
    latitude: farm?.latitude?.toString() ?? "",
    longitude: farm?.longitude?.toString() ?? "",
    notes: farm?.notes ?? "",
  };
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: defaults });
  const { errors, isSubmitting } = form.formState;

  const onSubmit = form.handleSubmit(async (v) => {
    setServerError(null);
    try {
      const saved = await save.mutateAsync({
        name: v.name,
        province: (v.province || null) as Province | null,
        district: v.district || null,
        latitude: v.latitude || null,
        longitude: v.longitude || null,
        notes: v.notes || null,
      });
      setOpen(false);
      onSaved?.(saved);
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
      <DialogContent
        title={farm ? "Edit farm" : "Add a farm"}
        description="Location is optional and stored approximately (about 1 km) for privacy."
      >
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
          {serverError && <InlineError message={serverError} />}
          <FormField label="Farm name" error={errors.name?.message}>
            <Input autoComplete="off" {...form.register("name")} />
          </FormField>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Province" optional error={errors.province?.message}>
              <Select {...form.register("province")}>
                <option value="">Not specified</option>
                {Object.entries(PROVINCE_LABEL).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField label="District" optional error={errors.district?.message}>
              <Input {...form.register("district")} />
            </FormField>
            <FormField label="Latitude" optional error={errors.latitude?.message}>
              <Input inputMode="decimal" placeholder="e.g. 31.52" {...form.register("latitude")} />
            </FormField>
            <FormField label="Longitude" optional error={errors.longitude?.message}>
              <Input inputMode="decimal" placeholder="e.g. 74.35" {...form.register("longitude")} />
            </FormField>
          </div>
          <FormField label="Notes" optional error={errors.notes?.message}>
            <Textarea rows={3} {...form.register("notes")} />
          </FormField>
          <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Saving…" : farm ? "Save changes" : "Add farm"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
