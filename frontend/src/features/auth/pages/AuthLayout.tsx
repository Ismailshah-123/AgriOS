import { CheckCircle2, Sprout } from "lucide-react";
import type { ReactNode } from "react";

const PILLARS = [
  "Farm, field and crop cycle records in one place",
  "Independent crop health models that say when they are unsure",
  "Calculations that show every input, source and assumption",
];

/** Split layout: brand panel (desktop) + form. Mobile shows the form only. */
export function AuthLayout({ title, subtitle, children }: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <div className="grid min-h-dvh bg-surface lg:grid-cols-[1.05fr_1fr]">
      <section
        aria-hidden
        className="relative hidden overflow-hidden bg-primary-deep p-12 text-white lg:flex lg:flex-col lg:justify-between"
      >
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage:
              "repeating-linear-gradient(115deg, #fff 0 1px, transparent 1px 28px)",
          }}
        />
        <div className="relative flex items-center gap-2.5">
          <span className="grid size-10 place-items-center rounded-[10px] bg-white/10">
            <Sprout className="size-5" />
          </span>
          <span className="text-xl font-semibold tracking-tight">AgriOS</span>
        </div>
        <div className="relative flex max-w-md flex-col gap-6">
          <h2 className="text-3xl leading-tight font-semibold tracking-tight">
            Agricultural intelligence built on your own farm records.
          </h2>
          <ul className="flex flex-col gap-3 text-white/85">
            {PILLARS.map((p) => (
              <li key={p} className="flex gap-3">
                <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-accent" />
                {p}
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-sm text-white/60">Decision support for farms in Pakistan.</p>
      </section>

      <main className="flex items-center justify-center px-4 py-10 sm:px-8">
        <div className="flex w-full max-w-sm flex-col gap-8">
          <div className="flex items-center gap-2.5 lg:hidden">
            <span className="grid size-9 place-items-center rounded-[10px] bg-primary-dark text-white">
              <Sprout aria-hidden className="size-5" />
            </span>
            <span className="text-lg font-semibold tracking-tight">AgriOS</span>
          </div>
          <div className="flex flex-col gap-1.5">
            <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
            <p className="text-muted">{subtitle}</p>
          </div>
          {children}
        </div>
      </main>
    </div>
  );
}
