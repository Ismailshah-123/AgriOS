import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/utils/cn";

// shadcn/ui-style button, themed with AgriOS tokens. Min 44px target height.
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-[var(--radius-input)] text-sm font-semibold transition-colors disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-primary text-white shadow-[var(--shadow-card)] hover:bg-primary-dark",
        secondary: "border border-border-strong bg-card text-ink hover:bg-surface",
        ghost: "text-ink hover:bg-primary-soft",
        danger: "bg-danger text-white hover:bg-danger/90",
      },
      size: {
        md: "h-11 px-4",
        sm: "h-9 px-3",
        icon: "size-11",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export function Button({ className, variant, size, asChild = false, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  return <Comp className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}
