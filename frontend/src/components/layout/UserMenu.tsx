import { ChevronDown, LogOut, Settings } from "lucide-react";
import { useNavigate } from "react-router";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/features/auth/auth-context";
import { initials } from "@/utils/format";

export function UserMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  if (!user) return null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="flex h-10 items-center gap-2 rounded-[var(--radius-input)] pr-2 pl-1 text-sm hover:bg-surface"
      >
        {/* Accessible name = visible name + "account menu" (WCAG 2.5.3 label in name).
            The initials avatar is decorative. On phones the name is visually hidden but
            stays in the accessible name. */}
        <span
          aria-hidden
          className="grid size-8 place-items-center rounded-full bg-primary-deep text-xs font-semibold text-white uppercase"
        >
          {initials(user.full_name)}
        </span>
        <span className="sr-only max-w-40 truncate font-medium text-ink sm:not-sr-only">
          {user.full_name}
        </span>{" "}
        <span className="sr-only">account menu</span>
        <ChevronDown aria-hidden className="size-4 text-muted" />
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuLabel>
          <span className="block truncate font-medium text-ink">{user.full_name}</span>
          <span className="block truncate">{user.email}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => navigate("/settings")}>
          <Settings aria-hidden />
          Settings
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => void logout()}>
          <LogOut aria-hidden />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
