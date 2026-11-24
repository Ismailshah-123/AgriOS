import { useState } from "react";

export interface ColumnDatum {
  key: string;
  label: string;
  value: number;
  display: string;
}

/**
 * Single-series vertical columns for counts over time (e.g. months). Zero-based, one
 * hue, recessive baseline, value label on hover/focus and in the accessible name of
 * each column (keyboard focusable).
 */
export function ColumnChart({ data, label }: { data: ColumnDatum[]; label: string }) {
  const [active, setActive] = useState<string | null>(null);
  const max = Math.max(...data.map((d) => d.value), 0);
  return (
    <figure className="flex flex-col gap-2">
      <div className="flex h-36 items-end gap-2 border-b border-border" role="list" aria-label={label}>
        {data.map((d) => (
          <div key={d.key} role="listitem" tabIndex={0} aria-label={`${d.label}: ${d.display}`}
            onMouseEnter={() => setActive(d.key)} onMouseLeave={() => setActive(null)}
            onFocus={() => setActive(d.key)} onBlur={() => setActive(null)}
            className="relative flex h-full flex-1 flex-col justify-end outline-none focus-visible:ring-2 focus-visible:ring-primary">
            {active === d.key && (
              <span className="absolute -top-1 left-1/2 z-10 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-md bg-ink px-2 py-1 text-xs text-white">
                {d.label}: {d.display}
              </span>
            )}
            <span className="mx-auto block w-full max-w-10 rounded-t-[4px] bg-primary"
              style={{ height: max > 0 ? `${(d.value / max) * 100}%` : "0%", minHeight: d.value > 0 ? 2 : 0 }} />
          </div>
        ))}
      </div>
      <div aria-hidden className="flex gap-2 text-xs text-muted">
        {data.map((d) => <span key={d.key} className="flex-1 truncate text-center">{d.label}</span>)}
      </div>
    </figure>
  );
}
