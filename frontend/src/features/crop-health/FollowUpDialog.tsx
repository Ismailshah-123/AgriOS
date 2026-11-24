import { useState, type FormEvent, type ReactElement } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTrigger } from "@/components/ui/dialog";
import { InlineError } from "@/components/ui/feedback";
import { ApiError } from "@/services/api/client";
import type { Observations } from "@/services/api/cropHealth";
import { errorMessage } from "@/utils/format";
import { EMPTY_OBSERVATIONS, observationErrors } from "./observations";
import { ObservationFields } from "./ObservationFields";
import { PhotoPicker } from "./PhotoPicker";
import { useFollowUp } from "./queries";

/** Adds a follow-up submission; earlier photos and notes are never changed. */
export function FollowUpDialog({ caseId, trigger }: { caseId: string; trigger: ReactElement }) {
  const [open, setOpen] = useState(false);
  const [photos, setPhotos] = useState<File[]>([]);
  const [obs, setObs] = useState<Observations>(EMPTY_OBSERVATIONS);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const followUp = useFollowUp(caseId);

  const reset = () => {
    setPhotos([]);
    setObs(EMPTY_OBSERVATIONS);
    setErrors({});
    setServerError(null);
    setProgress(null);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const next: Record<string, string> = { ...observationErrors(obs) };
    const empty = !obs.plant_part && obs.symptoms.length === 0 && !obs.observed_on && !obs.notes.trim();
    if (photos.length === 0 && empty) next.photos = "Add a photo or an observation.";
    setErrors(next);
    if (Object.keys(next).length) return;
    setProgress(0);
    try {
      await followUp.mutateAsync({ input: { photos, ...obs }, onProgress: setProgress });
      setOpen(false);
      reset();
    } catch (err) {
      setProgress(null);
      if (err instanceof ApiError && err.field === "images") setErrors({ photos: err.message });
      else setServerError(errorMessage(err));
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (!v) reset(); }}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent title="Add a follow-up" description="New photos or observations are added to this case's history."
        className="max-w-2xl">
        <form onSubmit={submit} noValidate className="flex flex-col gap-5">
          {serverError && <InlineError message={serverError} />}
          <PhotoPicker photos={photos} onChange={setPhotos} error={errors.photos} />
          <ObservationFields value={obs} onChange={setObs} errors={errors} />
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={progress !== null}>
              {progress === null ? "Add follow-up" : progress < 1 ? `Uploading ${Math.round(progress * 100)}%` : "Saving…"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
