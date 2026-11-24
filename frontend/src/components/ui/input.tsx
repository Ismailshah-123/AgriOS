import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";
import { cn } from "@/utils/cn";

const control = cn(
  "w-full rounded-[var(--radius-input)] border border-border-strong bg-card px-3 text-base text-ink",
  "placeholder:text-muted/70 transition-colors hover:border-muted/60",
  "focus-visible:border-primary focus-visible:outline-2 focus-visible:outline-offset-0",
  "focus-visible:outline-primary/30 disabled:cursor-not-allowed disabled:bg-surface disabled:opacity-70",
  "aria-[invalid=true]:border-danger aria-[invalid=true]:focus-visible:outline-danger/30",
);

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(control, "h-11", className)} {...props} />;
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(control, "min-h-24 py-2.5", className)} {...props} />;
}

/** Native select: fully accessible and mobile-friendly; styled to match inputs. */
export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn(control, "h-11 pr-8", className)} {...props} />;
}
