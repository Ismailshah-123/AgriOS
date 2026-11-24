import {
  Bot,
  CalendarClock,
  CheckCircle2,
  Circle,
  CloudSun,
  Droplets,
  FlaskConical,
  History,
  Sprout,
  Stethoscope,
  type LucideIcon,
} from "lucide-react";
import { Link } from "react-router";
import { Badge } from "@/components/ui/badge";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { OriginBadge } from "@/components/ui/origin-badge";
import { AVAILABILITY_LABEL } from "@/features/crop-health/labels";
import type { Overview } from "@/services/api/types";
import { cn } from "@/utils/cn";
import { formatDate } from "@/utils/format";

// ------------------------------------------------------------------ onboarding

export function GettingStarted({ counts }: { counts: Overview["counts"] }) {
  const cycles = Object.values(counts.cycles_by_status).reduce((a, b) => a + b, 0);
  const steps = [
    { done: counts.farms > 0, label: "Add your farm", to: "/farms" },
    { done: counts.fields > 0, label: "Add its fields with their area", to: "/fields" },
    { done: cycles > 0, label: "Record what is planned or growing", to: "/crop-cycles" },
  ];
  if (steps.every((s) => s.done)) return null;
  return (
    <Card className="border-primary/25 bg-primary-soft/40">
      <CardHeader>
        <CardTitle>Get started</CardTitle>
        <CardDescription>
          Your records are the foundation for every AgriOS module.
        </CardDescription>
      </CardHeader>
      <ol className="flex flex-col gap-1 px-5 pb-5">
        {steps.map((s) => (
          <li key={s.label}>
            <Link
              to={s.to}
              className="flex items-center gap-3 rounded-[var(--radius-input)] px-2 py-2 hover:bg-card"
            >
              {s.done ? (
                <CheckCircle2 aria-hidden className="size-5 text-primary" />
              ) : (
                <Circle aria-hidden className="size-5 text-muted" />
              )}
              <span className={cn("font-medium", s.done ? "text-muted line-through" : "text-ink")}>
                {s.label}
              </span>
              <span className="sr-only">{s.done ? "(done)" : "(to do)"}</span>
            </Link>
          </li>
        ))}
      </ol>
    </Card>
  );
}

// --------------------------------------------------------------- crop activity

export function ActiveCycles({ cycles }: { cycles: Overview["active_cycles"] }) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>Growing now</CardTitle>
        <Link to="/crop-cycles" className="text-sm font-medium text-primary-dark hover:underline">
          All cycles
        </Link>
      </CardHeader>
      {cycles.length === 0 ? (
        <EmptyState as="h3" icon={Sprout} title="No crops growing" description="Mark a crop cycle as growing to see it here." />
      ) : (
        <ul className="divide-y divide-border border-t border-border">
          {cycles.map((c) => (
            <li key={c.id} className="flex flex-col gap-0.5 px-5 py-3">
              <p className="font-medium text-ink">
                {c.crop_name}
                {c.variety && <span className="font-normal text-muted"> · {c.variety}</span>}
              </p>
              <p className="text-sm text-muted">
                {c.field_name} · {c.farm_name} · sown {formatDate(c.sowing_date)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

const UPCOMING_LABEL = { planned_sowing: "Planned sowing", expected_harvest: "Expected harvest" };

export function Upcoming({ items }: { items: Overview["upcoming"] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Coming up</CardTitle>
        <CardDescription>Next 60 days, from the dates you entered.</CardDescription>
      </CardHeader>
      {items.length === 0 ? (
        <EmptyState
          as="h3"
          icon={CalendarClock}
          title="Nothing scheduled"
          description="Add sowing or expected harvest dates to your crop cycles to see them here."
        />
      ) : (
        <ul className="divide-y divide-border border-t border-border">
          {items.map((u) => (
            <li key={`${u.kind}-${u.cycle.id}`} className="flex items-center gap-4 px-5 py-3">
              <time dateTime={u.date} className="tabular w-24 shrink-0 text-sm font-semibold text-ink">
                {formatDate(u.date)}
              </time>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-ink">
                  {UPCOMING_LABEL[u.kind]}: {u.cycle.crop_name}
                </p>
                <p className="truncate text-sm text-muted">{u.cycle.field_name}</p>
              </div>
              <OriginBadge origin={u.source} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

const ACTION_LABEL: Record<string, string> = {
  "farm.created": "Farm added",
  "farm.updated": "Farm updated",
  "farm.deleted": "Farm deleted",
  "field.created": "Field added",
  "field.updated": "Field updated",
  "field.deleted": "Field deleted",
  "crop_cycle.created": "Crop cycle started",
  "crop_cycle.updated": "Crop cycle updated",
  "crop_cycle.deleted": "Crop cycle deleted",
};

const timeFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export function RecentChanges({ items }: { items: Overview["recent_changes"] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent changes</CardTitle>
        <CardDescription>Your latest edits to farm records.</CardDescription>
      </CardHeader>
      {items.length === 0 ? (
        <EmptyState as="h3" icon={History} title="No changes yet" description="Changes you make to farms, fields and crop cycles appear here." />
      ) : (
        <ul className="divide-y divide-border border-t border-border">
          {items.map((c, i) => (
            <li key={`${c.created_at}-${i}`} className="flex items-center justify-between gap-4 px-5 py-3 text-sm">
              <span className="block min-w-0 truncate">
                <span className="font-medium text-ink">{ACTION_LABEL[c.action] ?? c.action}</span>
                <span className="text-muted"> · {c.name ?? "deleted record"}</span>
              </span>
              <time dateTime={c.created_at} className="tabular shrink-0 text-muted">
                {timeFmt.format(new Date(c.created_at))}
              </time>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

// ------------------------------------------------------------- intelligence

type Intel = Overview["intelligence"];
type Tone = "neutral" | "success" | "warning" | "info";
interface IntelRow { icon: LucideIcon; label: string; to: string; badge: string; tone: Tone; note: string }

function n(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

/** Builds each row from stored record counts only: no forecast or estimated values. */
function intelRows(i: Intel): IntelRow[] {
  const ch = i.crop_health;
  const ready = ch.model_availability === "ready";
  return [
    {
      icon: Stethoscope, label: "Crop health", to: "/crop-doctor",
      badge: ready ? "Model ready" : AVAILABILITY_LABEL[ch.model_availability], tone: ready ? "success" : "warning",
      note: ch.cases === 0
        ? "No crop health cases yet."
        : `${n(ch.cases, "case")} · ${ch.awaiting_analysis} awaiting analysis · ${ch.needs_follow_up} need follow-up`,
    },
    {
      icon: FlaskConical, label: "Soil", to: "/soil",
      badge: i.soil.observations ? "Recorded" : "No tests", tone: i.soil.observations ? "success" : "neutral",
      note: i.soil.observations
        ? `${n(i.soil.observations, "soil test")} on ${n(i.soil.fields_with_tests, "field")}, latest ${formatDate(i.soil.latest_sampled_on as string)}`
        : "Add a soil test to see pH and salinity flags.",
    },
    {
      icon: CloudSun, label: "Weather", to: "/weather",
      badge: i.weather.farms_with_location ? "Available" : "Needs location",
      tone: i.weather.farms_with_location ? "success" : "neutral",
      note: i.weather.farms === 0
        ? "Add a farm with its location to see weather."
        : `Forecast available for ${i.weather.farms_with_location} of ${n(i.weather.farms, "farm")} (farm location set).`,
    },
    {
      icon: Droplets, label: "Crop water demand", to: "/irrigation",
      badge: i.irrigation.cycles_with_estimate ? "Estimate available" : "Not available",
      tone: i.irrigation.cycles_with_estimate ? "info" : "neutral",
      note: i.irrigation.growing_cycles === 0
        ? "Mark a crop cycle as growing to estimate its water demand."
        : `FAO-56 estimate for ${i.irrigation.cycles_with_estimate} of ${n(i.irrigation.growing_cycles, "growing crop")}.`,
    },
    {
      icon: Bot, label: "AI agents", to: "/agents",
      badge: i.agents.pending_approvals ? `${i.agents.pending_approvals} to review` : "Nothing to review",
      tone: i.agents.pending_approvals ? "warning" : "neutral",
      note: `${n(i.agents.runs, "agent request")} so far. Changes run only after you approve them.`,
    },
  ];  // prettier-ignore
}

/** Live module status from GET /overview; every figure is a count of your own records. */
export function IntelligenceStatus({ data }: { data: Intel }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Farm intelligence</CardTitle>
        <CardDescription>What each module has from your records today.</CardDescription>
      </CardHeader>
      <ul className="flex flex-col divide-y divide-border border-t border-border">
        {intelRows(data).map(({ icon: Icon, label, to, badge, tone, note }) => (
          <li key={label}>
            <Link to={to} className="flex gap-3 px-5 py-3.5 hover:bg-surface-raised">
              <Icon aria-hidden className="mt-0.5 size-5 shrink-0 text-muted" />
              <span className="flex min-w-0 flex-col gap-1">
                <span className="flex flex-wrap items-center gap-x-2 gap-y-1 font-medium text-ink">
                  {label}
                  <Badge tone={tone} className="whitespace-nowrap">{badge}</Badge>
                </span>
                <span className="text-sm text-muted">{note}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}
