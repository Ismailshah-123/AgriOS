import { useState } from "react";

export interface DailyPoint {
  label: string; // e.g. "Mon 24"
  low?: number | null; // range charts: low..high; plain bars: high only
  high: number | null;
  tooltip: string;
}

/**
 * Single-series daily chart (bars from zero, or floating low-high ranges). One series, so
 * no legend: the card title names it. Missing days render as a gap labelled "no data",
 * never as zero. Brand token colour; recessive grid; hover/focus tooltip per day.
 */
export function DailyChart({ points, unit, title, range = false }: {
  points: DailyPoint[];
  unit: string;
  title: string;
  range?: boolean;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 560, H = 180, PAD_L = 36, PAD_B = 24, PAD_T = 12;
  const vals = points.flatMap((p) => [p.high, range ? p.low : 0]).filter((v): v is number => v != null);
  if (vals.length === 0) {
    return <p className="text-sm text-muted">No {title.toLowerCase()} data from the provider.</p>;
  }
  const lo = range ? Math.floor(Math.min(...vals) - 2) : 0;
  const hi = Math.max(lo + 1, Math.ceil(Math.max(...vals) * 1.1 + (range ? 1 : 0)));
  const y = (v: number) => PAD_T + (H - PAD_T - PAD_B) * (1 - (v - lo) / (hi - lo));
  const slot = (W - PAD_L) / points.length;
  const bw = Math.min(28, slot * 0.5);
  const ticks = [lo, lo + (hi - lo) / 2, hi].map((t) => Math.round(t * 10) / 10);

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={`${title} by day`}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD_L} x2={W} y1={y(t)} y2={y(t)} className="stroke-border" strokeWidth={1} />
            <text x={PAD_L - 6} y={y(t) + 4} textAnchor="end" className="fill-muted text-[10px]">
              {t}
            </text>
          </g>
        ))}
        {points.map((p, i) => {
          const cx = PAD_L + slot * i + slot / 2;
          const top = p.high == null ? null : y(p.high);
          const bottom = range ? (p.low == null ? null : y(p.low)) : y(0);
          const ok = top != null && bottom != null;
          return (
            <g
              key={p.label}
              tabIndex={0}
              role="img"
              aria-label={p.tooltip}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(i)}
              onBlur={() => setHover(null)}
              className="outline-none"
            >
              <rect x={cx - slot / 2} y={0} width={slot} height={H - PAD_B} fill="transparent" />
              {ok ? (
                <rect
                  x={cx - bw / 2}
                  y={Math.min(top, bottom)}
                  width={bw}
                  height={Math.max(2, Math.abs(bottom - top))}
                  rx={4}
                  className={hover === i ? "fill-primary-dark" : "fill-primary"}
                />
              ) : (
                <text x={cx} y={H - PAD_B - 6} textAnchor="middle" className="fill-muted text-[9px]">
                  no data
                </text>
              )}
              <text x={cx} y={H - 6} textAnchor="middle" className="fill-muted text-[10px]">
                {p.label}
              </text>
            </g>
          );
        })}
      </svg>
      {hover != null && (
        <div
          role="tooltip"
          className="pointer-events-none absolute top-0 rounded-md border border-border bg-card px-2 py-1 text-xs text-ink shadow-sm"
          style={{ left: `${((PAD_L + slot * hover + slot / 2) / W) * 100}%`, transform: "translateX(-50%)" }}
        >
          {points[hover]!.tooltip}
        </div>
      )}
      <p className="sr-only">Values in {unit}.</p>
    </div>
  );
}
