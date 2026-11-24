import { Stethoscope, type LucideIcon } from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

/** Only modules that actually exist are listed. Add entries as modules ship. */
export const NAV_ITEMS: NavItem[] = [{ to: "/crop-doctor", label: "Crop Doctor", icon: Stethoscope }];
