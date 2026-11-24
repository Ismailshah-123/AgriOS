import { Database, Server } from "lucide-react";
import type { ReactNode } from "react";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { DatabaseState } from "@/services/api/system";
import { useApiHealth, useApiReadiness } from "./useSystemStatus";

type Tone = NonNullable<BadgeProps["tone"]>;

const DB_LABEL: Record<DatabaseState, { text: string; tone: Tone }> = {
  ok: { text: "Connected", tone: "success" },
  not_configured: { text: "Not configured", tone: "warning" },
  unavailable: { text: "Unavailable", tone: "danger" },
};

function StatusRow({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <li className="flex items-center justify-between gap-4 py-3">
      <span className="flex items-center gap-3 text-sm font-medium text-ink">
        {icon}
        {label}
      </span>
      {children}
    </li>
  );
}

/** Live platform status from /health and /ready. Nothing here is hard-coded. */
export function SystemStatusCard() {
  const health = useApiHealth();
  const readiness = useApiReadiness();

  const api = health.isPending
    ? { text: "Checking…", tone: "neutral" as Tone }
    : health.isSuccess
      ? { text: "Online", tone: "success" as Tone }
      : { text: "Unreachable", tone: "danger" as Tone };

  const db = readiness.isPending
    ? { text: "Checking…", tone: "neutral" as Tone }
    : readiness.isSuccess
      ? DB_LABEL[readiness.data.checks.database]
      : { text: "Unknown", tone: "neutral" as Tone };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Platform status</CardTitle>
        <CardDescription>
          {health.isSuccess ? `API version ${health.data.version}` : "Live connection check"}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="divide-y divide-border" aria-live="polite">
          <StatusRow icon={<Server aria-hidden className="size-4 text-muted" />} label="API server">
            <Badge tone={api.tone}>{api.text}</Badge>
          </StatusRow>
          <StatusRow icon={<Database aria-hidden className="size-4 text-muted" />} label="Database">
            <Badge tone={db.tone}>{db.text}</Badge>
          </StatusRow>
        </ul>
      </CardContent>
    </Card>
  );
}
