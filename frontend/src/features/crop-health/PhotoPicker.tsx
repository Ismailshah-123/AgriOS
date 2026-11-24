import { Camera, ImagePlus, RefreshCw, Upload, X } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState, type DragEvent } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";
import { checkPhoto, UPLOAD_RULES } from "./labels";
import { useL } from "@/i18n/useT";

interface PhotoPickerProps {
  photos: File[];
  onChange: (photos: File[]) => void;
  max?: number;
  error?: string;
}

/**
 * Drag-and-drop, file picker and phone camera. Previews use object URLs that are
 * revoked when photos are removed or the component unmounts.
 */
export function PhotoPicker({ photos, onChange, max = UPLOAD_RULES.maxPhotos, error }: PhotoPickerProps) {
  const l = useL();
  const id = useId();
  const pickRef = useRef<HTMLInputElement>(null);
  const cameraRef = useRef<HTMLInputElement>(null);
  const replaceRef = useRef<HTMLInputElement>(null);
  const [replaceAt, setReplaceAt] = useState<number | null>(null);
  const [problems, setProblems] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);

  const previews = useMemo(() => photos.map((p) => URL.createObjectURL(p)), [photos]);
  useEffect(() => () => previews.forEach((u) => URL.revokeObjectURL(u)), [previews]);

  const add = (files: FileList | File[] | null) => {
    if (!files) return;
    const issues: string[] = [];
    const accepted: File[] = [];
    for (const f of Array.from(files)) {
      const problem = checkPhoto(f);
      if (problem) issues.push(problem);
      else accepted.push(f);
    }
    const room = max - photos.length;
    if (accepted.length > room) issues.push(`You can add up to ${max} photos.`);
    setProblems(issues);
    if (accepted.length && room > 0) onChange([...photos, ...accepted.slice(0, room)]);
  };

  const replace = (files: FileList | null) => {
    const f = files?.[0];
    if (!f || replaceAt === null) return;
    const problem = checkPhoto(f);
    setProblems(problem ? [problem] : []);
    if (!problem) onChange(photos.map((p, i) => (i === replaceAt ? f : p)));
    setReplaceAt(null);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    add(e.dataTransfer.files);
  };

  const full = photos.length >= max;
  const messages = [...problems, ...(error ? [error] : [])];

  return (
    <div className="flex flex-col gap-3">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "flex flex-col items-center gap-3 rounded-[var(--radius-card)] border-2 border-dashed px-4 py-8 text-center transition-colors",
          dragging ? "border-primary bg-primary-soft" : "border-border-strong bg-surface-raised",
          full && "opacity-60",
        )}
      >
        <span className="grid size-12 place-items-center rounded-full bg-primary-soft text-primary-dark">
          <ImagePlus aria-hidden className="size-6" />
        </span>
        <div>
          <p className="font-medium text-ink">{l("Drag photos here, or choose them")}</p>
          <p className="text-sm text-muted">
            JPEG, PNG or WebP · up to {max} photos · 8 MB each
          </p>
        </div>
        <div className="flex flex-wrap justify-center gap-2">
          <Button type="button" variant="secondary" disabled={full} onClick={() => pickRef.current?.click()}>
            <Upload aria-hidden />
            {l("Choose photos")}
          </Button>
          <Button type="button" variant="secondary" disabled={full} onClick={() => cameraRef.current?.click()}>
            <Camera aria-hidden />
            {l("Take photo")}
          </Button>
        </div>
        <input ref={pickRef} id={`${id}-pick`} type="file" accept={UPLOAD_RULES.accept} multiple hidden
          aria-label="Choose photos" onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
        <input ref={cameraRef} type="file" accept={UPLOAD_RULES.accept} capture="environment" hidden
          aria-label="Take photo" onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
        <input ref={replaceRef} type="file" accept={UPLOAD_RULES.accept} hidden aria-label="Replacement photo"
          onChange={(e) => { replace(e.target.files); e.target.value = ""; }} />
      </div>

      {messages.length > 0 && (
        <ul role="alert" className="flex flex-col gap-1 text-sm font-medium text-danger">
          {messages.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
      )}

      {photos.length > 0 && (
        <ul aria-label="Selected photos" className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {photos.map((p, i) => (
            <li key={`${p.name}-${i}`} className="overflow-hidden rounded-[var(--radius-input)] border border-border bg-card">
              <img src={previews[i]} alt={`Selected photo ${i + 1}: ${p.name}`} className="aspect-square w-full object-cover" />
              <div className="flex items-center justify-between gap-1 px-1.5 py-1">
                <span className="truncate px-1 text-xs text-muted">{(p.size / 1024 / 1024).toFixed(1)} MB</span>
                <span className="flex">
                  <Button type="button" variant="ghost" size="icon" className="size-9"
                    aria-label={`Replace photo ${i + 1}`}
                    onClick={() => { setReplaceAt(i); replaceRef.current?.click(); }}>
                    <RefreshCw aria-hidden />
                  </Button>
                  <Button type="button" variant="ghost" size="icon" className="size-9"
                    aria-label={`Remove photo ${i + 1}`}
                    onClick={() => onChange(photos.filter((_, j) => j !== i))}>
                    <X aria-hidden />
                  </Button>
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
