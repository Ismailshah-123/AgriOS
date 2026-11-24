import { CheckCircle2, CircleDashed, Clock3 } from "lucide-react";
import { Link } from "react-router";
import { moduleByKey } from "@/app/modules";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Honest entry page for a module that is not built yet: what it will do, what it will
 * rely on, and what the farmer can do today. No inputs, no sample numbers, no fake
 * buttons.
 */
export function PlannedModulePage({ moduleKey }: { moduleKey: string }) {
  const m = moduleByKey(moduleKey);
  const Icon = m.icon;
  return (
    <>
      <PageHeader
        title={m.label}
        description={m.summary}
        actions={
          <Badge tone="neutral" className="h-7 px-3">
            <Clock3 aria-hidden className="size-3.5" />
            Planned{m.roadmap ? ` · ${m.roadmap}` : ""}
          </Badge>
        }
      />
      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr] [&>*]:min-w-0">
        <Card>
          <CardHeader className="flex-row items-center gap-3">
            <span className="grid size-10 place-items-center rounded-[10px] bg-primary-soft text-primary-dark">
              <Icon aria-hidden className="size-5" />
            </span>
            <CardTitle>What this module will do</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-3">
              {m.capabilities?.map((c) => (
                <li key={c} className="flex gap-3 text-ink-soft">
                  <CheckCircle2 aria-hidden className="mt-0.5 size-5 shrink-0 text-primary" />
                  {c}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <CardTitle>It will rely on</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="flex flex-col gap-2.5">
                {m.needs?.map((n) => (
                  <li key={n} className="flex gap-2.5 text-sm text-ink-soft">
                    <CircleDashed aria-hidden className="mt-0.5 size-4 shrink-0 text-muted" />
                    {n}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
          <Card className="bg-surface-raised">
            <CardHeader>
              <CardTitle>Available now</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <p className="text-sm text-muted">
                This module is not available yet. Records you add now (farms, fields and crop
                cycles) will be used by it when it is released.
              </p>
              <Button asChild variant="secondary" className="self-start">
                <Link to="/crop-cycles">Manage crop cycles</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
