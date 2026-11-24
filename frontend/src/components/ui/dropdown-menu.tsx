import * as Menu from "@radix-ui/react-dropdown-menu";
import type { ReactNode } from "react";
import { cn } from "@/utils/cn";

export const DropdownMenu = Menu.Root;
export const DropdownMenuTrigger = Menu.Trigger;

interface ContentProps {
  children: ReactNode;
  align?: "start" | "end";
}

export function DropdownMenuContent({ children, align = "end" }: ContentProps) {
  return (
    <Menu.Portal>
      <Menu.Content
        align={align}
        sideOffset={6}
        className="z-50 min-w-52 animate-fade-in rounded-[var(--radius-input)] border border-border bg-card p-1.5 shadow-[var(--shadow-overlay)]"
      >
        {children}
      </Menu.Content>
    </Menu.Portal>
  );
}

export function DropdownMenuItem({
  className,
  ...props
}: Menu.DropdownMenuItemProps & { className?: string }) {
  return (
    <Menu.Item
      className={cn(
        "flex h-10 cursor-pointer items-center gap-2.5 rounded-md px-2.5 text-sm text-ink outline-none select-none",
        "data-[highlighted]:bg-surface [&_svg]:size-4 [&_svg]:text-muted",
        className,
      )}
      {...props}
    />
  );
}

export function DropdownMenuLabel({ children }: { children: ReactNode }) {
  return <Menu.Label className="px-2.5 py-2 text-xs text-muted">{children}</Menu.Label>;
}

export function DropdownMenuSeparator() {
  return <Menu.Separator className="my-1 h-px bg-border" />;
}
