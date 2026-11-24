import { Sprout } from "lucide-react";

export function BrandMark() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="grid size-9 place-items-center rounded-[10px] bg-primary-dark text-white">
        <Sprout aria-hidden className="size-5" />
      </span>
      <span className="text-lg font-semibold tracking-tight text-ink">AgriOS</span>
    </div>
  );
}
