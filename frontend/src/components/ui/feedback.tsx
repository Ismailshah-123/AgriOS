import { AlertTriangle, RefreshCw } from "lucide-react";
import type { HTMLAttributes } from "react";
import { cn } from "@/utils/cn";
import { Button } from "./button";

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden
      className={cn("animate-pulse rounded-[var(--radius-input)] bg-border/70", className)}
      {...props}
    />
  );
}

/** Polite loading region for screen readers plus visual skeleton rows. */
export function LoadingRows({ rows = 3, label = "Loading" }: { rows?: number; label?: string }) {
  return (
    <div role="status" aria-label={label} className="flex flex-col gap-3 p-5">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  );
}

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  as?: "h2" | "h3";
}

/** What happened, what to do, and a retry (DESIGN.md section 9). Never a stack trace. */
export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
  as: Heading = "h2",
}: ErrorStateProps) {
  return (
    <div role="alert" className="flex flex-col items-center gap-3 px-6 py-10 text-center">
      <span className="grid size-11 place-items-center rounded-full bg-danger-soft text-danger">
        <AlertTriangle aria-hidden className="size-5" />
      </span>
      <Heading className="text-base font-semibold text-ink">{title}</Heading>
      <p className="max-w-sm text-sm text-muted">{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          <RefreshCw aria-hidden />
          Try again
        </Button>
      )}
    </div>
  );
}

export function InlineError({ message }: { message: string }) {
  return (
    <p
      role="alert"
      className="rounded-[var(--radius-input)] bg-danger-soft px-3 py-2.5 text-sm text-danger"
    >
      {message}
    </p>
  );
}
