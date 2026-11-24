import { ArrowLeft, Lock, Sprout } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { InlineError, LoadingRows } from "@/components/ui/feedback";
import { FormField } from "@/components/ui/form-field";
import { Select } from "@/components/ui/input";
import { useAuth } from "@/features/auth/auth-context";
import { newClientId, saveDraft } from "@/features/offline/drafts";
import { OfflineDrafts } from "@/features/offline/OfflineDrafts";
import { useCycles, useFarms, useFields } from "@/features/platform/queries";
import { ApiError } from "@/services/api/client";
import type { Observations } from "@/services/api/cropHealth";
import { errorMessage, formatDate } from "@/utils/format";
import { EMPTY_OBSERVATIONS, observationErrors } from "../observations";
import { ObservationFields } from "../ObservationFields";
import { PhotoPicker } from "../PhotoPicker";
import { useCreateCase } from "../queries";
import { useL } from "@/i18n/useT";

function Step({ n, title, description, children }: { n: number; title: string; description?: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader className="flex-row items-start gap-3">
        <span aria-hidden className="grid size-7 shrink-0 place-items-center rounded-full bg-primary-deep text-sm font-semibold text-white">
          {n}
        </span>
        <div className="flex flex-col gap-1">
          <CardTitle>{title}</CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </div>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export function NewAssessmentPage() {
  const l = useL();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [clientId, setClientId] = useState(newClientId); // one id per case: retries never duplicate
  const [savedOffline, setSavedOffline] = useState(false);
  const [farmId, setFarmId] = useState("");
  const [fieldId, setFieldId] = useState("");
  const [cycleId, setCycleId] = useState("");
  const [photos, setPhotos] = useState<File[]>([]);
  const [obs, setObs] = useState<Observations>(EMPTY_OBSERVATIONS);
  const [consent, setConsent] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);

  const farms = useFarms();
  const fields = useFields(farmId || undefined);
  const cycles = useCycles(fieldId ? { field_id: fieldId, status: "active" } : { status: "active" });
  const growingAnywhere = useCycles({ status: "active" });
  const create = useCreateCase();

  if (growingAnywhere.isPending) return <LoadingRows label={l("Loading")} />;
  if (growingAnywhere.isSuccess && growingAnywhere.data.items.length === 0) {
    return (
      <>
        <PageHeader title={l("New crop health assessment")} />
        <Card>
          <EmptyState icon={Sprout} title={l("No growing crops yet")}
            description="An assessment is linked to a crop that is currently growing. Mark a crop cycle as growing first."
            action={<Button asChild><Link to="/crop-cycles">{l("Go to Crop Cycles")}</Link></Button>} />
        </Card>
      </>
    );
  }

  const fieldOptions = fields.data?.items ?? [];
  const cycleOptions = fieldId ? (cycles.data?.items ?? []) : [];

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const next: Record<string, string> = { ...observationErrors(obs) };
    if (!farmId) next.farm = l("Choose a farm.");
    if (!fieldId) next.field = l("Choose a field.");
    if (!cycleId) next.cycle = l("Choose the growing crop.");
    if (photos.length === 0) next.photos = l("Add at least one photo.");
    setErrors(next);
    setServerError(null);
    if (Object.keys(next).length) return;
    const input = { crop_cycle_id: cycleId, consent_training: consent, photos, client_id: clientId, ...obs };
    const keepOffline = async () => {
      await saveDraft({
        client_id: clientId, user_id: user?.id ?? "", created_at: new Date().toISOString(), status: "pending",
        last_error: null, input: { crop_cycle_id: cycleId, consent_training: consent, ...obs },
        photos: photos.map((p) => ({ name: p.name, type: p.type, blob: p })),
      });  // prettier-ignore
      // Stay on this page: other pages' code may not be loadable while offline (no service worker).
      setProgress(null);
      setSavedOffline(true);
      setPhotos([]);
      setObs(EMPTY_OBSERVATIONS);
      setClientId(newClientId()); // a further case gets its own id
    };
    if (typeof navigator !== "undefined" && navigator.onLine === false) return keepOffline();
    setProgress(0);
    try {
      const created = await create.mutateAsync({ input, onProgress: setProgress });
      navigate(`/crop-doctor/cases/${created.id}`, { replace: true });
    } catch (err) {
      setProgress(null);
      if (err instanceof ApiError && err.status === 0) return keepOffline(); // connection lost: keep it
      if (err instanceof ApiError && err.field === "images") setErrors({ photos: err.message });
      else if (err instanceof ApiError && err.field === "crop_cycle_id") setErrors({ cycle: err.message });
      else if (err instanceof ApiError && err.field === "observed_on") setErrors({ observed_on: err.message });
      else setServerError(errorMessage(err));
    }
  };

  const busy = progress !== null;

  return (
    <>
      <Link to="/crop-doctor" className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-muted hover:text-ink">
        <ArrowLeft aria-hidden className="size-4" />
        {l("Crop Doctor")}
      </Link>
      <PageHeader title={l("New crop health assessment")}
        description={l("Choose the crop, add clear photos and anything you have noticed. Your photos are kept for this case.")} />
      {savedOffline && (
        <div className="mb-6 flex flex-col gap-4">
          <p role="status" className="rounded-[var(--radius-input)] bg-primary-soft p-4 text-sm text-primary-dark">
            Saved on this device. It will upload automatically when you are back online; you can add another case now.
          </p>
          <OfflineDrafts />
        </div>
      )}
      <form onSubmit={submit} noValidate className="flex flex-col gap-6">
        {serverError && <InlineError message={serverError} />}
        <Step n={1} title={l("Which crop?")} description={l("Only crops that are currently growing are listed.")}>
          <div className="grid gap-4 md:grid-cols-3">
            <FormField label={l("Farm")} error={errors.farm}>
              <Select value={farmId} onChange={(e) => { setFarmId(e.target.value); setFieldId(""); setCycleId(""); }}>
                <option value="">{l("Choose a farm")}</option>
                {farms.data?.items.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
              </Select>
            </FormField>
            <FormField label={l("Field")} error={errors.field}>
              <Select value={fieldId} disabled={!farmId} onChange={(e) => { setFieldId(e.target.value); setCycleId(""); }}>
                <option value="">{farmId ? l("Choose a field") : l("Choose a farm first")}</option>
                {fieldOptions.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
              </Select>
            </FormField>
            <FormField label={l("Growing crop")} error={errors.cycle}
              hint={fieldId && cycles.isSuccess && cycleOptions.length === 0 ? l("No crop is growing on this field.") : undefined}>
              <Select value={cycleId} disabled={!fieldId || cycleOptions.length === 0} onChange={(e) => setCycleId(e.target.value)}>
                <option value="">{fieldId ? l("Choose the crop") : l("Choose a field first")}</option>
                {cycleOptions.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.crop.name_en}{c.variety ? ` (${c.variety})` : ""} · sown {formatDate(c.sowing_date)}
                  </option>
                ))}
              </Select>
            </FormField>
          </div>
        </Step>

        <Step n={2} title={l("Photos")} description={l("One affected leaf or part per photo, filling the frame, in daylight, held steady.")}>
          <PhotoPicker photos={photos} onChange={setPhotos} error={errors.photos} />
        </Step>

        <Step n={3} title={l("What have you noticed?")} description={l("Optional. This helps an expert; it is not used as a diagnosis.")}>
          <ObservationFields value={obs} onChange={setObs} errors={errors} />
        </Step>

        <Card className="bg-surface-raised p-5">
          <div className="flex gap-3">
            <Lock aria-hidden className="mt-0.5 size-5 shrink-0 text-primary-dark" />
            <div className="flex flex-col gap-3 text-sm text-ink-soft">
              <p>
                <span className="font-medium text-ink">{l("Your privacy.")}</span> {l("Photos are stored privately for your account. Location and camera details embedded in photos are removed before storage.")}
              </p>
              <label className="flex cursor-pointer items-start gap-3">
                <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)}
                  className="mt-0.5 size-5 accent-[var(--color-primary)]" />
                <span>
                  {l("Allow these photos to be used to improve AgriOS models.")} <span className="text-muted">{l("Optional; off by default.")}</span>
                </span>
              </label>
            </div>
          </div>
        </Card>

        <div className="flex flex-col-reverse items-stretch gap-3 sm:flex-row sm:items-center sm:justify-end">
          {busy && (
            <div className="flex flex-1 items-center gap-3" role="status" aria-live="polite">
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-border" aria-hidden>
                <div className="h-full bg-primary transition-[width]" style={{ width: `${Math.round((progress ?? 0) * 100)}%` }} />
              </div>
              <span className="tabular text-sm text-muted">
                {progress !== null && progress < 1 ? `Uploading ${Math.round(progress * 100)}%` : l("Saving…")}
              </span>
            </div>
          )}
          <Button type="button" variant="secondary" asChild>
            <Link to="/crop-doctor">{l("Cancel")}</Link>
          </Button>
          <Button type="submit" disabled={busy}>
            {busy ? l("Submitting…") : l("Submit assessment")}
          </Button>
        </div>
      </form>
    </>
  );
}
