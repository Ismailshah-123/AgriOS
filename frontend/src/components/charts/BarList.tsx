import { cn } from "@/utils/cn";

export interface BarDatum {
  key: string;
  label: string;
  value: number;
  /** Text shown for the value (units included), e.g. "PKR 1,000.00" or "2.5 ha". */
  display: string;
  detail?: string;
}

/**
 * Single-series horizontal bars (magnitude). One hue (brand), no legend: the card title
 * names the series. Every bar carries its text value, so the list doubles as the table
 * view. Bars start at zero; a 4px rounded end marks the value.
 */
export function BarList({ data, label, emptyText = "No data recorded yet." }: {
  data: BarDatum[];
  label: string;
  emptyText?: string;
}) {
  if (data.length === 0) return <p className="text-sm text-muted">{emptyText}</p>;
  const max = Math.max(...data.map((d) => d.value), 0);
  return (
    <ul aria-label={label} className="flex flex-col gap-2.5">
      {data.map((d) => (
        <li key={d.key} className="grid grid-cols-[minmax(0,9rem)_1fr_auto] items-center gap-3 text-sm sm:grid-cols-[minmax(0,12rem)_1fr_auto]"
          title={`${d.label}: ${d.display}${d.detail ? ` (${d.detail})` : ""}`}>
          <span className="truncate text-ink-soft">{d.label}</span>
          <span aria-hidden className="h-2.5 overflow-hidden rounded-e-[4px] bg-surface">
            <span className={cn("block h-full rounded-e-[4px] bg-primary", d.value === 0 && "w-0")}
              style={{ width: max > 0 ? `${(d.value / max) * 100}%` : "0%" }} />
          </span>
          <span className="tabular text-end text-ink">{d.display}</span>
        </li>
      ))}
    </ul>
  );
}
